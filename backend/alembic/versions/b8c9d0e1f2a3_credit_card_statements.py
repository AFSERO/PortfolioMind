"""credit-card statements, line items, and installment plans

Revision ID: b8c9d0e1f2a3
Revises: a7b8c9d0e1f2
Create Date: 2026-08-06 00:00:00.000000
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "b8c9d0e1f2a3"
down_revision: str = "a7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _enum(name: str, values: list[str], length: int) -> sa.Enum:
    return sa.Enum(
        *values,
        name=name,
        native_enum=False,
        create_constraint=True,
        length=length,
    )


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
    ]


def upgrade() -> None:
    op.create_table(
        "liability_statements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("liability_id", sa.Uuid(), nullable=False),
        sa.Column("statement_period_start", sa.Date(), nullable=False),
        sa.Column("statement_period_end", sa.Date(), nullable=False),
        sa.Column("statement_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("previous_balance", sa.Numeric(18, 6), nullable=False),
        sa.Column("payments_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("purchases_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("fees_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("interest_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("refunds_total", sa.Numeric(18, 6), nullable=False),
        sa.Column("statement_balance", sa.Numeric(18, 6), nullable=False),
        sa.Column("minimum_payment", sa.Numeric(18, 6), nullable=False),
        sa.Column(
            "remaining_installments_total",
            sa.Numeric(18, 6),
            nullable=False,
        ),
        sa.Column(
            "status",
            _enum(
                "statement_status_enum",
                ["draft", "confirmed", "paid", "partially_paid", "overdue"],
                20,
            ),
            nullable=False,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column(
            "source",
            _enum(
                "statement_source_enum",
                ["manual", "pdf_import", "csv_import"],
                16,
            ),
            nullable=False,
        ),
        sa.Column("source_file_hash", sa.String(length=64), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "applied_to_liability_at", sa.DateTime(timezone=True), nullable=True
        ),
        sa.Column("applied_balance", sa.Numeric(18, 6), nullable=True),
        *_timestamps(),
        sa.CheckConstraint(
            "statement_period_start <= statement_period_end",
            name="ck_statement_period_order",
        ),
        sa.CheckConstraint("due_date >= statement_date", name="ck_statement_due_date"),
        sa.CheckConstraint("previous_balance >= 0", name="ck_statement_previous_balance"),
        sa.CheckConstraint("payments_total >= 0", name="ck_statement_payments_total"),
        sa.CheckConstraint("purchases_total >= 0", name="ck_statement_purchases_total"),
        sa.CheckConstraint("fees_total >= 0", name="ck_statement_fees_total"),
        sa.CheckConstraint("interest_total >= 0", name="ck_statement_interest_total"),
        sa.CheckConstraint("refunds_total >= 0", name="ck_statement_refunds_total"),
        sa.CheckConstraint("statement_balance >= 0", name="ck_statement_balance"),
        sa.CheckConstraint("minimum_payment >= 0", name="ck_statement_minimum_payment"),
        sa.CheckConstraint(
            "remaining_installments_total >= 0",
            name="ck_statement_remaining_installments",
        ),
        sa.CheckConstraint(
            "applied_balance IS NULL OR applied_balance >= 0",
            name="ck_statement_applied_balance",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["liability_id"], ["liabilities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "liability_id",
            "statement_period_start",
            "statement_period_end",
            name="uq_liability_statement_period",
        ),
        sa.UniqueConstraint(
            "liability_id", "statement_date", name="uq_liability_statement_date"
        ),
        sa.UniqueConstraint(
            "user_id", "source_file_hash", name="uq_statement_source_file"
        ),
    )
    op.create_index(
        "ix_statements_user_status", "liability_statements", ["user_id", "status"]
    )
    op.create_index(
        "ix_statements_liability_date",
        "liability_statements",
        ["liability_id", "statement_date"],
    )

    op.create_table(
        "installment_plans",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("liability_id", sa.Uuid(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("merchant_name", sa.String(length=255), nullable=True),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("original_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("installment_count", sa.Integer(), nullable=False),
        sa.Column("monthly_installment_amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("first_installment_date", sa.Date(), nullable=False),
        sa.Column("completed_installment_count", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            _enum(
                "installment_plan_status_enum",
                ["active", "completed", "cancelled"],
                16,
            ),
            nullable=False,
        ),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("original_amount > 0", name="ck_installment_original_amount"),
        sa.CheckConstraint("installment_count >= 2", name="ck_installment_count"),
        sa.CheckConstraint(
            "monthly_installment_amount > 0", name="ck_installment_monthly_amount"
        ),
        sa.CheckConstraint(
            "completed_installment_count >= 0",
            name="ck_installment_completed_nonnegative",
        ),
        sa.CheckConstraint(
            "completed_installment_count <= installment_count",
            name="ck_installment_completed_limit",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["liability_id"], ["liabilities.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "liability_id",
            "external_reference",
            name="uq_installment_external_ref",
        ),
    )
    op.create_index(
        "ix_installments_user_status", "installment_plans", ["user_id", "status"]
    )
    op.create_index(
        "ix_installments_liability_status",
        "installment_plans",
        ["liability_id", "status"],
    )

    op.create_table(
        "statement_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("statement_id", sa.Uuid(), nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("posting_date", sa.Date(), nullable=True),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("merchant_name", sa.String(length=255), nullable=True),
        sa.Column(
            "transaction_type",
            _enum(
                "statement_transaction_type_enum",
                [
                    "purchase",
                    "payment",
                    "refund",
                    "fee",
                    "interest",
                    "cash_advance",
                    "installment",
                    "other",
                ],
                16,
            ),
            nullable=False,
        ),
        sa.Column("amount", sa.Numeric(18, 6), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("installment_plan_id", sa.Uuid(), nullable=True),
        sa.Column("installment_number", sa.Integer(), nullable=True),
        sa.Column("installment_count", sa.Integer(), nullable=True),
        sa.Column("external_reference", sa.String(length=255), nullable=True),
        sa.Column("source_line_hash", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_statement_tx_amount"),
        sa.CheckConstraint(
            "(transaction_type = 'installment' AND installment_number IS NOT NULL "
            "AND installment_count IS NOT NULL AND installment_number >= 1 "
            "AND installment_count >= installment_number) OR "
            "(transaction_type <> 'installment' AND installment_plan_id IS NULL "
            "AND installment_number IS NULL AND installment_count IS NULL)",
            name="ck_statement_tx_installment_fields",
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["statement_id"], ["liability_statements.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["installment_plan_id"],
            ["installment_plans.id"],
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "statement_id",
            "source_line_hash",
            name="uq_statement_tx_source_line",
        ),
    )
    op.create_index(
        "ix_statement_tx_statement_date",
        "statement_transactions",
        ["statement_id", "transaction_date"],
    )
    op.create_index(
        "ix_statement_tx_user_date",
        "statement_transactions",
        ["user_id", "transaction_date"],
    )


def downgrade() -> None:
    op.drop_index("ix_statement_tx_user_date", table_name="statement_transactions")
    op.drop_index("ix_statement_tx_statement_date", table_name="statement_transactions")
    op.drop_table("statement_transactions")
    op.drop_index("ix_installments_liability_status", table_name="installment_plans")
    op.drop_index("ix_installments_user_status", table_name="installment_plans")
    op.drop_table("installment_plans")
    op.drop_index("ix_statements_liability_date", table_name="liability_statements")
    op.drop_index("ix_statements_user_status", table_name="liability_statements")
    op.drop_table("liability_statements")
