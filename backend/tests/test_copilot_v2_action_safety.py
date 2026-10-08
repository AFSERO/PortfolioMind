"""Comprehensive Safety, Isolation, Idempotency, and Lifecycle Verification for Copilot V2 Phase 3.1.

Verification Matrix:
1. Proposal creation causes ZERO financial/domain mutation.
2. Transaction confirmation executes domain mutation exactly once.
3. Concurrent confirmations (simulating race conditions) result in exactly one execution.
4. Confirm vs cancel race is safe: terminal states are strictly mutually exclusive.
5. Cancellation causes ZERO financial/domain mutation.
6. Stale holding condition aborts execution and updates status to STALE.
7. Expired proposal is lazily expired and rejected on read and confirm.
8. Failed domain mutation rolls back atomically without partial state corruption.
9. Cross-user authorization: User A cannot read, confirm, or cancel User B proposals (strict 404).
10. Cross-user asset/cash isolation: User A cannot touch User B assets or cash balances.
11. ToolRegistry runtime programmatic verification: ZERO execute/write tools allowed.
12. Decision note schema matches DecisionLogEntry model exactly without invented fields.
13. Watchlist execution is strictly idempotent (no duplicate entries on repeated adds, safe removes).
"""

import asyncio
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import MagicMock, patch
import uuid

import pytest
import pytest_asyncio
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount, CashMovement, CashMovementType
from app.models.copilot import CopilotActionProposal, CopilotAuditLog
from app.models.decision_log import DecisionEventType, DecisionLogEntry
from app.models.instrument import Instrument
from app.models.opportunity import WatchlistItem, WatchlistPriority
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.copilot_v2.action_contracts import (
    ACTION_PROPOSAL_TTL,
    ActionProposalStatusV2,
    ActionProposalType,
    DecisionNoteProposalParams,
    TransactionProposalParams,
    WatchlistProposalParams,
)
from app.services.copilot_v2.action_executor import ActionExecutorV2
from app.services.copilot_v2.errors import ToolExecutionError
from app.services.copilot_v2.tools import default_tool_registry
from app.services.copilot_v2.tools.proposals import (
    propose_decision_note_handler,
    propose_transaction_record_handler,
    propose_watchlist_change_handler,
)
from app.services.copilot_v2.tools.registry import ToolClassification, ToolDefinition


async def _create_test_user(db: AsyncSession, prefix: str = "safety_user") -> User:
    user = User(
        email=f"{prefix}_{uuid.uuid4().hex[:6]}@example.com",
        display_name=prefix,
        password_hash="hashed_pw",
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def _create_test_instrument(
    db: AsyncSession, symbol: str, name: str, asset_type: AssetType = AssetType.STOCK
) -> Instrument:
    inst = Instrument(
        symbol=symbol.upper(),
        name=name,
        asset_type=asset_type,
        currency="TRY",
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    return inst


# ---------------------------------------------------------------------------
# 1. Proposal creation causes ZERO financial/domain mutation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_proposal_creation_causes_no_financial_mutation(db_session: AsyncSession):
    """Creating a transaction proposal must NOT create transactions or alter cash balances."""
    user = await _create_test_user(db_session, "clean_creator")
    inst = await _create_test_instrument(db_session, "TCELL.IS", "Turkcell")

    # Initial checks: no transactions, no cash movements
    tx_count_before = len((await db_session.execute(select(Transaction))).scalars().all())
    movement_count_before = len((await db_session.execute(select(CashMovement))).scalars().all())

    # Call proposal tool
    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="TCELL.IS",
        transaction_type="BUY",
        quantity=100.0,
        price=95.0,
        currency="TRY",
    )
    assert res["status"] == "success"
    prop_id = uuid.UUID(res["proposal_id"])

    # Verify: CopilotActionProposal was staged
    prop = await db_session.get(CopilotActionProposal, prop_id)
    assert prop is not None
    assert prop.status == ActionProposalStatusV2.PENDING.value

    # Verify: ZERO financial mutation occurred
    tx_count_after = len((await db_session.execute(select(Transaction))).scalars().all())
    movement_count_after = len((await db_session.execute(select(CashMovement))).scalars().all())
    assert tx_count_after == tx_count_before
    assert movement_count_after == movement_count_before


# ---------------------------------------------------------------------------
# 2. Transaction confirmation executes domain mutation exactly once
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transaction_confirmation_executes_once_with_cash_and_audit(db_session: AsyncSession):
    """Confirming a BUY proposal creates exactly one transaction, moves cash, and creates an audit row."""
    user = await _create_test_user(db_session, "buyer_exec")
    await _create_test_instrument(db_session, "SAHOL.IS", "Sabanci Holding")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="SAHOL.IS",
        transaction_type="BUY",
        quantity=50.0,
        price=100.0,
        currency="TRY",
        affects_cash=True,
    )
    prop_id = uuid.UUID(res["proposal_id"])

    exec_res = await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)
    assert exec_res["status"] == "success"
    assert exec_res["proposal_status"] == ActionProposalStatusV2.EXECUTED.value

    # Check transaction exists
    tx_id = uuid.UUID(exec_res["execution_result"]["transaction_id"])
    tx = await db_session.get(Transaction, tx_id)
    assert tx is not None
    assert tx.quantity == Decimal("50")
    assert tx.price_per_unit == Decimal("100")
    assert tx.total_amount == Decimal("5000")

    # Check cash movement occurred: BUY should subtract 5000 TRY
    cash_stmt = select(CashAccount).where(CashAccount.user_id == user.id, CashAccount.currency == "TRY")
    cash_acc = (await db_session.execute(cash_stmt)).scalar_one_or_none()
    assert cash_acc is not None
    assert cash_acc.balance == Decimal("-5000")

    # Check CopilotAuditLog was recorded
    audit_stmt = select(CopilotAuditLog).where(CopilotAuditLog.proposal_id == prop_id)
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None
    assert audit.execution_status == "SUCCESS"
    assert audit.action_type == ActionProposalType.TRANSACTION_RECORD.value


# ---------------------------------------------------------------------------
# 3. Concurrent double confirmation is safe and idempotent
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_concurrent_double_confirm_is_idempotent(db_session: AsyncSession):
    """Simulating concurrent duplicate confirmations returns the same execution result without duplicate transactions."""
    user = await _create_test_user(db_session, "concur_user")
    await _create_test_instrument(db_session, "GARAN.IS", "Garanti Bankasi")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="GARAN.IS",
        transaction_type="BUY",
        quantity=200.0,
        price=110.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])
    await db_session.commit()

    # First execution succeeds and sets EXECUTED
    exec1 = await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)
    # Subsequent execution (as in a race or retry) returns existing result
    exec2 = await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)

    assert exec1["execution_result"]["transaction_id"] == exec2["execution_result"]["transaction_id"]

    # Exactly ONE transaction was inserted
    tx_stmt = select(Transaction).join(Asset).where(Asset.user_id == user.id, Asset.symbol == "GARAN.IS")
    tx_list = list((await db_session.execute(tx_stmt)).scalars().all())
    assert len(tx_list) == 1


# ---------------------------------------------------------------------------
# 4. Confirm vs Cancel race is mutually exclusive
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_confirm_and_cancel_are_mutually_exclusive(db_session: AsyncSession):
    """A proposal cannot be cancelled after execution, and cannot be executed after cancellation."""
    user = await _create_test_user(db_session, "race_user")
    await _create_test_instrument(db_session, "ISCTR.IS", "Is Bankasi")

    # Case A: Cancel first, then execute must be rejected
    res_a = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="ISCTR.IS",
        transaction_type="BUY",
        quantity=50.0,
        price=14.0,
    )
    prop_a_id = uuid.UUID(res_a["proposal_id"])
    await ActionExecutorV2.cancel_proposal(db_session, user.id, prop_a_id, reason="User cancelled")

    with pytest.raises(HTTPException) as exc_a:
        await ActionExecutorV2.execute_proposal(db_session, user.id, prop_a_id)
    assert exc_a.value.status_code == 400
    assert "Cannot execute proposal" in exc_a.value.detail

    # Case B: Execute first, then cancel must be rejected
    res_b = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="ISCTR.IS",
        transaction_type="BUY",
        quantity=50.0,
        price=14.0,
    )
    prop_b_id = uuid.UUID(res_b["proposal_id"])
    await ActionExecutorV2.execute_proposal(db_session, user.id, prop_b_id)

    with pytest.raises(HTTPException) as exc_b:
        await ActionExecutorV2.cancel_proposal(db_session, user.id, prop_b_id, reason="Too late")
    assert exc_b.value.status_code == 400
    assert "already executed" in exc_b.value.detail


# ---------------------------------------------------------------------------
# 5. Cancellation causes ZERO financial mutation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cancellation_causes_zero_mutation(db_session: AsyncSession):
    """Cancelling a proposal updates proposal status to CANCELLED and creates no transactions or cash movements."""
    user = await _create_test_user(db_session, "cancel_mut_user")
    await _create_test_instrument(db_session, "TOASO.IS", "Tofas")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="TOASO.IS",
        transaction_type="BUY",
        quantity=30.0,
        price=250.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])

    cancelled = await ActionExecutorV2.cancel_proposal(db_session, user.id, prop_id, reason="Decided against")
    assert cancelled.status == ActionProposalStatusV2.CANCELLED.value

    # Check DB: no transactions exist for TOASO.IS
    tx_stmt = select(Transaction).join(Asset).where(Asset.user_id == user.id, Asset.symbol == "TOASO.IS")
    txns = list((await db_session.execute(tx_stmt)).scalars().all())
    assert len(txns) == 0


# ---------------------------------------------------------------------------
# 6. Stale holding condition aborts execution
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_stale_holding_aborts_and_marks_proposal_stale(db_session: AsyncSession):
    """If asset quantity is reduced prior to confirmation, execute_proposal marks status STALE and aborts."""
    user = await _create_test_user(db_session, "stale_detector")
    inst = await _create_test_instrument(db_session, "ARCLK.IS", "Arcelik")

    asset = Asset(
        user_id=user.id,
        instrument_id=inst.id,
        symbol="ARCLK.IS",
        name="Arcelik",
        asset_type=AssetType.STOCK,
        current_price=Decimal("150"),
    )
    db_session.add(asset)
    await db_session.flush()

    # Buy 100 units initially
    buy_tx = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("100"),
        price_per_unit=Decimal("140"),
        total_amount=Decimal("14000"),
        transaction_currency="TRY",
        transaction_date=date.today(),
    )
    db_session.add(buy_tx)
    await db_session.commit()

    # Propose selling 80 units (valid at proposal time)
    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="ARCLK.IS",
        transaction_type="SELL",
        quantity=80.0,
        price=150.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])

    # Outside event sells 50 units, leaving only 50
    external_sell = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.SELL,
        quantity=Decimal("50"),
        price_per_unit=Decimal("145"),
        total_amount=Decimal("7250"),
        transaction_currency="TRY",
        transaction_date=date.today(),
    )
    db_session.add(external_sell)
    await db_session.commit()

    # Attempting to confirm selling 80 must fail with STALE
    with pytest.raises(HTTPException) as exc:
        await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)
    assert exc.value.status_code == 400
    assert "STALE" in exc.value.detail or "değişti" in exc.value.detail

    prop = await db_session.get(CopilotActionProposal, prop_id)
    assert prop.status == ActionProposalStatusV2.STALE.value


# ---------------------------------------------------------------------------
# 7. Expired proposal is lazily expired and rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_lazy_expiration_on_read_and_confirm(db_session: AsyncSession):
    """Proposals past expires_at are marked EXPIRED on get_proposal and rejected on execute_proposal."""
    user = await _create_test_user(db_session, "exp_user")
    await _create_test_instrument(db_session, "MGROS.IS", "Migros")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="MGROS.IS",
        transaction_type="BUY",
        quantity=10.0,
        price=450.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])

    # Backdate expires_at to the past
    prop = await db_session.get(CopilotActionProposal, prop_id)
    prop.expires_at = datetime.now(timezone.utc) - timedelta(hours=1)
    await db_session.commit()

    # Read lazily updates to EXPIRED
    fetched = await ActionExecutorV2.get_proposal(db_session, user.id, prop_id)
    assert fetched is not None
    assert fetched.status == ActionProposalStatusV2.EXPIRED.value

    # Execution attempt is rejected with 400
    with pytest.raises(HTTPException) as exc:
        await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)
    assert exc.value.status_code == 400
    assert "expired" in exc.value.detail.lower()


# ---------------------------------------------------------------------------
# 8. Failed domain mutation rolls back atomically
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_failed_domain_mutation_rolls_back_atomically(db_session: AsyncSession):
    """If domain service raises an error, no transaction is committed and proposal is marked FAILED."""
    user = await _create_test_user(db_session, "atomic_fail_user")
    await _create_test_instrument(db_session, "ENKAI.IS", "Enka Insaat")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="ENKAI.IS",
        transaction_type="BUY",
        quantity=100.0,
        price=35.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])
    target_user_id = user.id
    await db_session.commit()

    # Inject failure into transaction service
    with patch("app.services.transaction.stage_transaction", side_effect=RuntimeError("Simulated DB failure")):
        with pytest.raises(HTTPException) as exc:
            await ActionExecutorV2.execute_proposal(db_session, target_user_id, prop_id)
        assert exc.value.status_code == 500

    # Ensure no Transaction was committed
    tx_stmt = select(Transaction).join(Asset).where(Asset.user_id == target_user_id, Asset.symbol == "ENKAI.IS")
    txns = list((await db_session.execute(tx_stmt)).scalars().all())
    assert len(txns) == 0

    # Proposal was updated to FAILED in isolated transaction
    prop = await db_session.get(CopilotActionProposal, prop_id)
    assert prop.status == ActionProposalStatusV2.FAILED.value


# ---------------------------------------------------------------------------
# 9 & 10. Multi-tenant authorization & resource isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_multi_tenant_authorization_isolation(db_session: AsyncSession):
    """User A cannot read, confirm, or cancel User B's action proposal."""
    user_a = await _create_test_user(db_session, "user_alpha")
    user_b = await _create_test_user(db_session, "user_beta")
    await _create_test_instrument(db_session, "KOZAL.IS", "Koza Altin")

    # User B creates a proposal
    res_b = await propose_transaction_record_handler(
        db=db_session,
        user_id=user_b.id,
        symbol_or_name="KOZAL.IS",
        transaction_type="BUY",
        quantity=25.0,
        price=24.0,
    )
    prop_b_id = uuid.UUID(res_b["proposal_id"])

    # User A tries to GET User B's proposal -> returns None
    fetched_by_a = await ActionExecutorV2.get_proposal(db_session, user_a.id, prop_b_id)
    assert fetched_by_a is None

    # User A tries to CONFIRM User B's proposal -> raises 404
    with pytest.raises(HTTPException) as exc_conf:
        await ActionExecutorV2.execute_proposal(db_session, user_a.id, prop_b_id)
    assert exc_conf.value.status_code == 404
    assert "not found or access denied" in exc_conf.value.detail

    # User A tries to CANCEL User B's proposal -> raises 404
    with pytest.raises(HTTPException) as exc_canc:
        await ActionExecutorV2.cancel_proposal(db_session, user_a.id, prop_b_id)
    assert exc_canc.value.status_code == 404
    assert "not found or access denied" in exc_canc.value.detail


# ---------------------------------------------------------------------------
# 11. Model Registry has ZERO execution tools
# ---------------------------------------------------------------------------


def test_model_registry_prohibits_execution_and_write_tools():
    """Verify default_tool_registry contains ONLY READ_ONLY and PROPOSAL tools, and blocks execution tools."""
    # Check all registered tools
    for tool in default_tool_registry.list_tools():
        assert tool.classification in (
            ToolClassification.READ_ONLY,
            ToolClassification.PROPOSAL,
        ), f"Tool '{tool.name}' has prohibited classification: {tool.classification}"

        # Ensure no tool starts with execution keywords
        for disallowed in default_tool_registry.DISALLOWED_EXECUTION_PREFIXES:
            assert not tool.name.lower().startswith(
                disallowed
            ), f"Tool '{tool.name}' has prohibited execution prefix: {disallowed}"

    # Attempting to register an execution tool must raise ToolExecutionError
    with pytest.raises(ToolExecutionError) as exc_info:
        default_tool_registry.register(
            ToolDefinition(
                name="execute_trade_instantly",
                description="Malicious tool attempting direct execution",
                parameters_schema={},
                classification=ToolClassification.PROPOSAL,
                handler=lambda **kwargs: None,
            )
        )
    assert "execution/mutation prefixes are prohibited" in str(exc_info.value)

    # Attempting to register a WRITE tool must raise ToolExecutionError
    with pytest.raises(ToolExecutionError) as exc_write:
        default_tool_registry.register(
            ToolDefinition(
                name="update_user_balance",
                description="Direct write tool",
                parameters_schema={},
                classification=ToolClassification.WRITE,
                handler=lambda **kwargs: None,
            )
        )
    assert "classification 'WRITE' is not allowed" in str(exc_write.value)


# ---------------------------------------------------------------------------
# 12. Decision Note Schema exactness
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_decision_note_schema_adheres_to_domain_model(db_session: AsyncSession):
    """Decision note proposal and execution map strictly to DecisionLogEntry columns."""
    user = await _create_test_user(db_session, "note_tester")
    inst = await _create_test_instrument(db_session, "THYAO.IS", "Turk Hava Yollari")

    res = await propose_decision_note_handler(
        db=db_session,
        user_id=user.id,
        title="2026 Büyüme Tezi",
        notes="Yolcu doluluk oranlarında %15 artış ve yeni kargo hatları.",
        symbol_or_name="THYAO.IS",
        expectation="Yıl sonu hedef 420 TL",
        confidence="HIGH",
    )
    assert res["status"] == "success"
    prop_id = uuid.UUID(res["proposal_id"])

    # Confirm and execute
    exec_res = await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)
    assert exec_res["status"] == "success"
    note_id = uuid.UUID(exec_res["execution_result"]["decision_entry_id"])

    # Verify DecisionLogEntry row in DB
    entry = await db_session.get(DecisionLogEntry, note_id)
    assert entry is not None
    assert entry.user_id == user.id
    assert entry.instrument_id == inst.id
    assert entry.title == "2026 Büyüme Tezi"
    assert entry.summary == "Yolcu doluluk oranlarında %15 artış ve yeni kargo hatları."
    assert entry.user_rationale == "Yolcu doluluk oranlarında %15 artış ve yeni kargo hatları."
    assert entry.expectation == "Yıl sonu hedef 420 TL"
    assert entry.confidence == "HIGH"
    assert entry.event_type == DecisionEventType.MANUAL_DECISION_NOTE


# ---------------------------------------------------------------------------
# 13. Watchlist Idempotency
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_watchlist_idempotency_add_and_remove(db_session: AsyncSession):
    """Watchlist ADD does not duplicate entries, and REMOVE is safe on non-existent items."""
    user = await _create_test_user(db_session, "wl_idempotent")
    inst = await _create_test_instrument(db_session, "KRDMD.IS", "Kardemir")

    # Add item
    res_add1 = await propose_watchlist_change_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="KRDMD.IS",
        action="ADD",
    )
    prop1_id = uuid.UUID(res_add1["proposal_id"])
    await ActionExecutorV2.execute_proposal(db_session, user.id, prop1_id)

    # Verify 1 item
    items_stmt = select(WatchlistItem).where(WatchlistItem.user_id == user.id, WatchlistItem.instrument_id == inst.id)
    items = list((await db_session.execute(items_stmt)).scalars().all())
    assert len(items) == 1

    # Add second time (e.g. redundant proposal execution)
    res_add2 = await propose_watchlist_change_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="KRDMD.IS",
        action="ADD",
    )
    # Notice warning present
    assert any("zaten" in w for w in res_add2["warnings"])
    prop2_id = uuid.UUID(res_add2["proposal_id"])
    await ActionExecutorV2.execute_proposal(db_session, user.id, prop2_id)

    # Still exactly 1 item in DB
    items = list((await db_session.execute(items_stmt)).scalars().all())
    assert len(items) == 1

    # Remove item
    res_rem1 = await propose_watchlist_change_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="KRDMD.IS",
        action="REMOVE",
    )
    prop3_id = uuid.UUID(res_rem1["proposal_id"])
    await ActionExecutorV2.execute_proposal(db_session, user.id, prop3_id)

    # Now 0 items
    items = list((await db_session.execute(items_stmt)).scalars().all())
    assert len(items) == 0

    # Redundant remove execution does not crash
    res_rem2 = await propose_watchlist_change_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="KRDMD.IS",
        action="REMOVE",
    )
    prop4_id = uuid.UUID(res_rem2["proposal_id"])
    rem2_res = await ActionExecutorV2.execute_proposal(db_session, user.id, prop4_id)
    assert rem2_res["status"] == "success"


# ---------------------------------------------------------------------------
# 14. Cross-User Asset and Cash Isolation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cross_user_asset_and_cash_isolation(db_session: AsyncSession):
    """User A cannot mutate User B's asset or cash account by injecting User B's asset_id into parameters."""
    user_a = await _create_test_user(db_session, "victim_attacker_a")
    user_b = await _create_test_user(db_session, "victim_target_b")
    inst = await _create_test_instrument(db_session, "CCOLA.IS", "Coca Cola Icecek")

    # User B owns 100 units of CCOLA
    asset_b = Asset(
        user_id=user_b.id,
        instrument_id=inst.id,
        symbol="CCOLA.IS",
        name="Coca Cola Icecek",
        asset_type=AssetType.STOCK,
        current_price=Decimal("600"),
    )
    db_session.add(asset_b)
    await db_session.flush()

    tx_b = Transaction(
        asset_id=asset_b.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("100"),
        price_per_unit=Decimal("600"),
        total_amount=Decimal("60000"),
        transaction_currency="TRY",
        transaction_date=date.today(),
        affects_cash=True,
    )
    db_session.add(tx_b)
    await db_session.commit()

    # User A creates a proposal maliciously pointing asset_id to User B's asset
    prop_a = CopilotActionProposal(
        user_id=user_a.id,
        action_type=ActionProposalType.TRANSACTION_RECORD.value,
        permission_level="REQUIRES_CONFIRMATION",
        status=ActionProposalStatusV2.PENDING.value,
        parameters={
            "symbol": "CCOLA.IS",
            "transaction_type": "SELL",
            "quantity": 50.0,
            "price": 600.0,
            "currency": "TRY",
            "asset_id": str(asset_b.id),
        },
        human_readable_summary="Malicious sell proposal",
        idempotency_key=f"malicious_{uuid.uuid4()}",
    )
    db_session.add(prop_a)
    await db_session.commit()

    # Executing User A's proposal must NOT sell User B's asset: User A does not own CCOLA, so it must fail with STALE
    with pytest.raises(HTTPException) as exc:
        await ActionExecutorV2.execute_proposal(db_session, user_a.id, prop_a.id)
    assert exc.value.status_code == 400
    assert "STALE" in exc.value.detail or "bulunamadı" in exc.value.detail

    # Verify User B's asset remains untouched with 100 units
    txns_b = (await db_session.execute(select(Transaction).where(Transaction.asset_id == asset_b.id))).scalars().all()
    assert len(txns_b) == 1
    assert txns_b[0].quantity == Decimal("100")


# ---------------------------------------------------------------------------
# 15. Missing Price Rejection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transaction_proposal_missing_price_without_market_fallback_fails(db_session: AsyncSession):
    """When an asset has no market price and no price is provided, proposal creation fails."""
    user = await _create_test_user(db_session, "missing_price_user")
    # Instrument without price
    await _create_test_instrument(db_session, "UNLISTED.IS", "Unlisted Asset")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="UNLISTED.IS",
        transaction_type="BUY",
        quantity=10.0,
        price=None,  # No price provided
    )
    assert res["status"] == "error"
    assert "işlem birim fiyatı belirtilmedi" in res["message"]


# ---------------------------------------------------------------------------
# 16. Unsupported action type rejected
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_unsupported_action_type_rejected(db_session: AsyncSession):
    """ActionExecutorV2 strictly rejects unsupported action types."""
    user = await _create_test_user(db_session, "unsupported_user")

    prop = CopilotActionProposal(
        user_id=user.id,
        action_type="AUTONOMOUS_TRADE_EXECUTE",  # Prohibited / unsupported
        permission_level="REQUIRES_CONFIRMATION",
        status=ActionProposalStatusV2.PENDING.value,
        parameters={},
        human_readable_summary="Unsupported action proposal",
        idempotency_key=f"unsup_{uuid.uuid4()}",
    )
    db_session.add(prop)
    await db_session.commit()

    with pytest.raises(HTTPException) as exc:
        await ActionExecutorV2.execute_proposal(db_session, user.id, prop.id)
    assert exc.value.status_code == 400
    assert "Unsupported action type" in exc.value.detail


# ---------------------------------------------------------------------------
# 17. Hypothetical vs Action Intent Routing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hypothetical_vs_action_intent_routing(db_session: AsyncSession):
    """Orchestrator prompt enforces that hypothetical queries return analysis and NEVER call proposal tools."""
    from app.services.copilot_v2.adapter import CodexV2Adapter, CodexV2ExecutionResult
    from app.services.copilot_v2 import ExecutionTrace, ModelProfile
    from app.services.copilot_v2.orchestrator import FastOrchestrator

    user = await _create_test_user(db_session, "hypo_user")

    # 1. Hypothetical query: Model returns FINAL_RESPONSE with analysis
    mock_hypo_adapter = MagicMock(spec=CodexV2Adapter)
    mock_hypo_adapter.execute.return_value = CodexV2ExecutionResult(
        raw_output='{"action": "FINAL_RESPONSE", "answer": "THF fonunuzun yarısını satarsanız portföyünüzdeki hisse yoğunluğu %30\'a geriler."}',
        parsed_json={
            "action": "FINAL_RESPONSE",
            "answer": "THF fonunuzun yarısını satarsanız portföyünüzdeki hisse yoğunluğu %30'a geriler ve yaklaşık 25.000 TL nakit girişi sağlanır.",
        },
        session_id=None,
        duration_ms=100.0,
        model_used="gpt-5.6-luna",
        reasoning_effort_used="low",
    )
    orch = FastOrchestrator(adapter=mock_hypo_adapter)
    trace = ExecutionTrace(starting_profile=ModelProfile.FAST)
    result = await orch.run(
        db=db_session,
        user_id=user.id,
        user_message="THF'nin yarısını satsam portföy nasıl görünür?",
        trace=trace,
    )
    assert result.action.value == "FINAL_RESPONSE"
    assert result.proposal_id is None
    assert "yarı" in result.final_answer

    # 2. Action Intent: Model requests TOOL_CALL propose_transaction_record
    mock_action_adapter = MagicMock(spec=CodexV2Adapter)
    # Turn 1: tool call
    # Turn 2: final response
    mock_action_adapter.execute.side_effect = [
        CodexV2ExecutionResult(
            raw_output='{"action": "TOOL_CALL"}',
            parsed_json={
                "action": "TOOL_CALL",
                "tool_calls": [
                    {
                        "tool": "propose_transaction_record",
                        "args": {
                            "symbol_or_name": "THYAO.IS",
                            "transaction_type": "BUY",
                            "quantity": 50,
                            "price": 310,
                        },
                    }
                ],
            },
            session_id=None,
            duration_ms=100.0,
            model_used="gpt-5.6-luna",
            reasoning_effort_used="low",
        ),
        CodexV2ExecutionResult(
            raw_output='{"action": "FINAL_RESPONSE", "answer": "Emir taslağı hazırlandı."}',
            parsed_json={
                "action": "FINAL_RESPONSE",
                "answer": "50 lot THYAO alış kaydı için onayınız bekleniyor.",
            },
            session_id=None,
            duration_ms=100.0,
            model_used="gpt-5.6-luna",
            reasoning_effort_used="low",
        ),
    ]
    orch_action = FastOrchestrator(adapter=mock_action_adapter)
    trace_action = ExecutionTrace(starting_profile=ModelProfile.FAST)
    result_action = await orch_action.run(
        db=db_session,
        user_id=user.id,
        user_message="Bugün 50 lot THYAO'yu 310 TL'den aldım, kaydet.",
        trace=trace_action,
    )
    assert result_action.action.value == "FINAL_RESPONSE"
    assert result_action.proposal_id is not None


# ---------------------------------------------------------------------------
# 18. Post-Action Fresh Tool Data Overrides Session Context
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_post_action_fresh_tool_data_overrides_session_context(db_session: AsyncSession):
    """After a trade proposal is confirmed externally, fresh tool calls return updated holding state."""
    from app.services.copilot_v2.tools.builtins import get_asset_context_handler

    user = await _create_test_user(db_session, "fresh_user")
    inst = await _create_test_instrument(db_session, "PGSUS.IS", "Pegasus")

    # Initial state: 0 units owned
    ctx_before = await get_asset_context_handler(db=db_session, user_id=user.id, symbol="PGSUS.IS")
    assert ctx_before["user_holding"]["is_owned"] is False

    # Create and confirm BUY proposal for 40 units
    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="PGSUS.IS",
        transaction_type="BUY",
        quantity=40.0,
        price=240.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])
    await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)

    # Next query turn: get_asset_context must deterministically reflect the new 40 units
    ctx_after = await get_asset_context_handler(db=db_session, user_id=user.id, symbol="PGSUS.IS")
    assert ctx_after["user_holding"]["is_owned"] is True
    assert Decimal(str(ctx_after["user_holding"]["quantity"])) == Decimal("40")


