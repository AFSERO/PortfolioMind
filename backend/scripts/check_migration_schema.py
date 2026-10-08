"""Verify critical tables, indexes, columns, and foreign keys after Alembic."""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import create_async_engine

from app.config import settings


EXPECTED_TABLES = {
    "alembic_version",
    "users",
    "assets",
    "price_history",
    "portfolio_snapshots",
    "forex_rates",
    "transactions",
    "cash_accounts",
    "cash_movements",
    "refresh_sessions",
    "liabilities",
    "liability_statements",
    "statement_transactions",
    "installment_plans",
}

EXPECTED_REFRESH_INDEXES = {
    "ix_refresh_sessions_user_id",
    "ix_refresh_sessions_family_id",
    "ix_refresh_sessions_expires_at",
}

EXPECTED_LIABILITY_INDEXES = {
    "ix_liabilities_user_active",
}

EXPECTED_SNAPSHOT_COLUMNS = {
    "total_assets_try",
    "total_assets_usd",
    "total_liabilities_try",
    "total_liabilities_usd",
    "net_worth_try",
    "net_worth_usd",
}

EXPECTED_STATEMENT_INDEXES = {
    "ix_statements_user_status": ("user_id", "status"),
    "ix_statements_liability_date": ("liability_id", "statement_date"),
}

EXPECTED_STATEMENT_TX_INDEXES = {
    "ix_statement_tx_statement_date": ("statement_id", "transaction_date"),
    "ix_statement_tx_user_date": ("user_id", "transaction_date"),
}

EXPECTED_INSTALLMENT_INDEXES = {
    "ix_installments_user_status": ("user_id", "status"),
    "ix_installments_liability_status": ("liability_id", "status"),
}

EXPECTED_STATEMENT_CHECKS = {
    "ck_statement_period_order",
    "ck_statement_due_date",
    "ck_statement_balance",
    "ck_statement_minimum_payment",
    "ck_statement_remaining_installments",
}

EXPECTED_INSTALLMENT_CHECKS = {
    "ck_installment_original_amount",
    "ck_installment_count",
    "ck_installment_monthly_amount",
    "ck_installment_completed_nonnegative",
    "ck_installment_completed_limit",
}

EXPECTED_STATEMENT_TX_CHECKS = {
    "ck_statement_tx_amount",
    "ck_statement_tx_installment_fields",
}


def _inspect_schema(connection) -> None:
    inspector = inspect(connection)
    tables = set(inspector.get_table_names())
    missing_tables = EXPECTED_TABLES - tables
    if missing_tables:
        raise RuntimeError(f"Missing migrated tables: {sorted(missing_tables)}")

    index_names = {
        index["name"] for index in inspector.get_indexes("refresh_sessions")
    }
    missing_indexes = EXPECTED_REFRESH_INDEXES - index_names
    if missing_indexes:
        raise RuntimeError(
            f"Missing refresh-session indexes: {sorted(missing_indexes)}"
        )

    unique_names = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("refresh_sessions")
    }
    if "uq_refresh_sessions_token_hash" not in unique_names:
        raise RuntimeError("Refresh-session token hash is not unique")

    column_names = {
        column["name"] for column in inspector.get_columns("refresh_sessions")
    }
    if "token" in column_names or "refresh_token" in column_names:
        raise RuntimeError("Refresh token plaintext column must not exist")

    foreign_keys = inspector.get_foreign_keys("refresh_sessions")
    constrained_columns = {
        tuple(foreign_key["constrained_columns"]) for foreign_key in foreign_keys
    }
    expected_foreign_keys = {("user_id",), ("replaced_by_jti",)}
    if not expected_foreign_keys.issubset(constrained_columns):
        raise RuntimeError("Refresh-session foreign keys are incomplete")

    liability_indexes = {
        index["name"]: tuple(index["column_names"])
        for index in inspector.get_indexes("liabilities")
    }
    missing_liability_indexes = EXPECTED_LIABILITY_INDEXES - set(liability_indexes)
    if missing_liability_indexes:
        raise RuntimeError(
            f"Missing liability indexes: {sorted(missing_liability_indexes)}"
        )
    if liability_indexes["ix_liabilities_user_active"] != (
        "user_id",
        "is_active",
    ):
        raise RuntimeError("Liability composite index columns are incorrect")

    liability_fks = inspector.get_foreign_keys("liabilities")
    user_fk = next(
        (
            foreign_key
            for foreign_key in liability_fks
            if foreign_key["constrained_columns"] == ["user_id"]
        ),
        None,
    )
    if user_fk is None or user_fk.get("options", {}).get("ondelete") != "CASCADE":
        raise RuntimeError("Liability user foreign key must cascade on delete")

    snapshot_columns = {
        column["name"] for column in inspector.get_columns("portfolio_snapshots")
    }
    missing_snapshot_columns = EXPECTED_SNAPSHOT_COLUMNS - snapshot_columns
    if missing_snapshot_columns:
        raise RuntimeError(
            f"Missing snapshot net-worth columns: {sorted(missing_snapshot_columns)}"
        )

    for table, expected in (
        ("liability_statements", EXPECTED_STATEMENT_INDEXES),
        ("statement_transactions", EXPECTED_STATEMENT_TX_INDEXES),
        ("installment_plans", EXPECTED_INSTALLMENT_INDEXES),
    ):
        actual = {
            index["name"]: tuple(index["column_names"])
            for index in inspector.get_indexes(table)
        }
        for name, columns in expected.items():
            if actual.get(name) != columns:
                raise RuntimeError(
                    f"Missing or incorrect index {name} on {table}: {actual.get(name)}"
                )

    statement_unique = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("liability_statements")
    }
    if not {
        "uq_liability_statement_period",
        "uq_liability_statement_date",
        "uq_statement_source_file",
    }.issubset(statement_unique):
        raise RuntimeError("Statement duplicate constraints are incomplete")

    transaction_unique = {
        constraint["name"]
        for constraint in inspector.get_unique_constraints("statement_transactions")
    }
    if "uq_statement_tx_source_line" not in transaction_unique:
        raise RuntimeError("Statement transaction source hash must be unique")

    expected_checks = {
        "liability_statements": EXPECTED_STATEMENT_CHECKS,
        "installment_plans": EXPECTED_INSTALLMENT_CHECKS,
        "statement_transactions": EXPECTED_STATEMENT_TX_CHECKS,
    }
    for table, expected in expected_checks.items():
        actual = {
            constraint["name"]
            for constraint in inspector.get_check_constraints(table)
        }
        missing = expected - actual
        if missing:
            raise RuntimeError(
                f"Missing check constraints on {table}: {sorted(missing)}"
            )

    expected_foreign_keys = {
        "liability_statements": {
            ("user_id",): ("users", "CASCADE"),
            ("liability_id",): ("liabilities", "CASCADE"),
        },
        "installment_plans": {
            ("user_id",): ("users", "CASCADE"),
            ("liability_id",): ("liabilities", "CASCADE"),
        },
        "statement_transactions": {
            ("user_id",): ("users", "CASCADE"),
            ("statement_id",): ("liability_statements", "CASCADE"),
            ("installment_plan_id",): ("installment_plans", "SET NULL"),
        },
    }
    for table, expected in expected_foreign_keys.items():
        actual = {
            tuple(foreign_key["constrained_columns"]): (
                foreign_key["referred_table"],
                foreign_key.get("options", {}).get("ondelete"),
            )
            for foreign_key in inspector.get_foreign_keys(table)
        }
        if not all(
            actual.get(columns) == contract
            for columns, contract in expected.items()
        ):
            raise RuntimeError(f"Foreign-key contract is incomplete on {table}")


async def main() -> None:
    engine = create_async_engine(settings.DATABASE_URL)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_inspect_schema)
    finally:
        await engine.dispose()
    print("Migration schema smoke check passed")


if __name__ == "__main__":
    asyncio.run(main())
