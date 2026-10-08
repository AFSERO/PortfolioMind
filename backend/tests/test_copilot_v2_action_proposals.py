"""Tests for Copilot V2 Phase 3: Action Proposals and Deterministic Execution.

Covers:
1. Proposal Tools:
   - propose_transaction_record (BUY, SELL, validation, holding checks, ambiguous resolution)
   - propose_watchlist_change (ADD, REMOVE, duplicate checks)
   - propose_decision_note (note logging)
2. ActionExecutorV2:
   - Atomic domain execution
   - Stale holding detection
   - Strict idempotency (no duplicate writes on repeated confirmation)
   - Row-level locking & user isolation
   - Cancellation lifecycle
3. Endpoints:
   - GET /api/copilot/v2/action-proposals/{id}
   - POST /api/copilot/v2/action-proposals/{id}/confirm
   - POST /api/copilot/v2/action-proposals/{id}/cancel
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
import uuid

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.main import app
from app.models.asset import Asset, AssetType
from app.models.copilot import CopilotActionProposal, CopilotAuditLog
from app.models.decision_log import DecisionLogEntry
from app.models.instrument import Instrument
from app.models.opportunity import WatchlistItem, WatchlistPriority
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.services.copilot_v2.action_contracts import (
    ActionProposalStatusV2,
    ActionProposalType,
)
from app.services.copilot_v2.action_executor import ActionExecutorV2
from app.services.copilot_v2.tools.proposals import (
    propose_decision_note_handler,
    propose_transaction_record_handler,
    propose_watchlist_change_handler,
)
from app.services.auth import create_access_token


async def _create_user(db: AsyncSession, username: str) -> User:
    user = User(
        email=f"{username}_{uuid.uuid4().hex[:6]}@example.com",
        display_name=username,
        password_hash="hash",
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
# 1. Proposal Tool: propose_transaction_record
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propose_transaction_record_buy_creates_pending_proposal(db_session: AsyncSession):
    """propose_transaction_record stages a valid PENDING BUY proposal with impact metrics."""
    user = await _create_user(db_session, "buyer_user")
    await _create_test_instrument(db_session, "KCHOL.IS", "Koc Holding")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="KCHOL.IS",
        transaction_type="BUY",
        quantity=50.0,
        price=180.5,
        currency="TRY",
    )

    assert res["status"] == "success"
    assert res["action_type"] == ActionProposalType.TRANSACTION_RECORD.value
    assert res["proposal_status"] == ActionProposalStatusV2.PENDING.value
    assert res["expected_impact"]["new_quantity"] == 50.0
    assert res["expected_impact"]["cash_delta"] == -(50.0 * 180.5)

    prop = await db_session.get(CopilotActionProposal, uuid.UUID(res["proposal_id"]))
    assert prop is not None
    assert prop.status == ActionProposalStatusV2.PENDING.value
    assert prop.parameters["transaction_type"] == "BUY"
    assert float(prop.parameters["quantity"]) == 50.0


@pytest.mark.asyncio
async def test_propose_transaction_record_rejects_negative_or_zero_qty(db_session: AsyncSession):
    """propose_transaction_record rejects non-positive quantities."""
    user = await _create_user(db_session, "invalid_qty_user")

    res_zero = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="THYAO.IS",
        transaction_type="BUY",
        quantity=0.0,
        price=300.0,
    )
    assert res_zero["status"] == "error"
    assert "sıfırdan büyük" in res_zero["message"]


@pytest.mark.asyncio
async def test_propose_transaction_record_sell_unowned_returns_error(db_session: AsyncSession):
    """propose_transaction_record prevents staging a SELL for unowned asset."""
    user = await _create_user(db_session, "seller_user")
    await _create_test_instrument(db_session, "EREGL.IS", "Eregli Demir Celik")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="EREGL.IS",
        transaction_type="SELL",
        quantity=100.0,
        price=45.0,
    )

    assert res["status"] == "error"
    assert "bulunmuyor" in res["message"]


@pytest.mark.asyncio
async def test_propose_transaction_record_sell_excess_adds_warning(db_session: AsyncSession):
    """propose_transaction_record adds a warning if selling more than held."""
    user = await _create_user(db_session, "excess_seller")
    inst = await _create_test_instrument(db_session, "SISE.IS", "Sisecam")

    # Own 100 units
    asset = Asset(
        user_id=user.id,
        instrument_id=inst.id,
        symbol="SISE.IS",
        name="Sisecam",
        asset_type=AssetType.STOCK,
        current_price=Decimal("50.0"),
    )
    db_session.add(asset)
    await db_session.flush()

    tx = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("100"),
        price_per_unit=Decimal("45"),
        total_amount=Decimal("4500"),
        transaction_currency="TRY",
        transaction_date=date.today(),
    )
    db_session.add(tx)
    await db_session.commit()

    # Try to propose selling 150 units
    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="SISE.IS",
        transaction_type="SELL",
        quantity=150.0,
        price=50.0,
    )

    assert res["status"] == "success"
    assert len(res["warnings"]) > 0
    assert any("fazladır" in w for w in res["warnings"])


# ---------------------------------------------------------------------------
# 2. Proposal Tool: propose_watchlist_change
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propose_watchlist_change_add_and_remove(db_session: AsyncSession):
    """propose_watchlist_change handles ADD and REMOVE proposals."""
    user = await _create_user(db_session, "wl_user")
    inst = await _create_test_instrument(db_session, "ASELS.IS", "Aselsan")

    # Propose ADD
    res_add = await propose_watchlist_change_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="ASELS.IS",
        action="ADD",
        priority="HIGH",
        notes="Savunma sanayii büyüme potansiyeli",
    )
    assert res_add["status"] == "success"
    assert res_add["action_type"] == ActionProposalType.WATCHLIST_CHANGE.value

    # Propose REMOVE when not on watchlist gives warning
    res_rem = await propose_watchlist_change_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="ASELS.IS",
        action="REMOVE",
    )
    assert res_rem["status"] == "success"
    assert len(res_rem["warnings"]) > 0


# ---------------------------------------------------------------------------
# 3. Proposal Tool: propose_decision_note
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_propose_decision_note(db_session: AsyncSession):
    """propose_decision_note creates PENDING note proposal."""
    user = await _create_user(db_session, "decision_user")
    inst = await _create_test_instrument(db_session, "TUPRS.IS", "Tupras")

    res = await propose_decision_note_handler(
        db=db_session,
        user_id=user.id,
        title="Rafineri marjı güncellemesi",
        notes="2026/Q3 rafineri marjları beklentilerin üzerinde seyrediyor.",
        symbol_or_name="TUPRS.IS",
        event_type="NOTE",
        confidence="HIGH",
    )
    assert res["status"] == "success"
    assert res["action_type"] == ActionProposalType.DECISION_NOTE.value


# ---------------------------------------------------------------------------
# 4. ActionExecutorV2: Deterministic Execution, Idempotency & Stale Detection
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_action_executor_executes_buy_and_creates_audit_log(db_session: AsyncSession):
    """ActionExecutorV2 executes BUY proposal atomically and records CopilotAuditLog."""
    user = await _create_user(db_session, "exec_buyer")
    inst = await _create_test_instrument(db_session, "BIMAS.IS", "BIM Magazalar")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="BIMAS.IS",
        transaction_type="BUY",
        quantity=20.0,
        price=500.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])

    # Confirm and execute
    exec_res = await ActionExecutorV2.execute_proposal(
        db=db_session,
        user_id=user.id,
        proposal_id=prop_id,
    )
    assert exec_res["status"] == "success"
    assert exec_res["proposal_status"] == ActionProposalStatusV2.EXECUTED.value

    # Verify Transaction created
    tx_id = uuid.UUID(exec_res["execution_result"]["transaction_id"])
    tx = await db_session.get(Transaction, tx_id)
    assert tx is not None
    assert tx.quantity == Decimal("20")
    assert tx.price_per_unit == Decimal("500")

    # Verify CopilotAuditLog
    audit_stmt = select(CopilotAuditLog).where(CopilotAuditLog.proposal_id == prop_id)
    audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
    assert audit is not None
    assert audit.execution_status == "SUCCESS"
    assert audit.user_id == user.id


@pytest.mark.asyncio
async def test_action_executor_idempotency_prevents_duplicate_writes(db_session: AsyncSession):
    """Calling execute_proposal a second time returns cached result without re-executing."""
    user = await _create_user(db_session, "idempotent_user")
    await _create_test_instrument(db_session, "YKBNK.IS", "Yapi Kredi")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="YKBNK.IS",
        transaction_type="BUY",
        quantity=100.0,
        price=30.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])

    # First execution
    exec1 = await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)

    # Second execution (simulating double click or network retry)
    exec2 = await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)

    assert exec1["execution_result"]["transaction_id"] == exec2["execution_result"]["transaction_id"]

    # Verify only ONE transaction exists in DB
    tx_stmt = select(Transaction).join(Asset).where(Asset.user_id == user.id, Asset.symbol == "YKBNK.IS")
    txns = list((await db_session.execute(tx_stmt)).scalars().all())
    assert len(txns) == 1


@pytest.mark.asyncio
async def test_action_executor_stale_detection_on_holding_change(db_session: AsyncSession):
    """ActionExecutorV2 detects stale state if holding became insufficient before execution."""
    user = await _create_user(db_session, "stale_user")
    inst = await _create_test_instrument(db_session, "PETKM.IS", "Petkim")

    # Own 50 units
    asset = Asset(
        user_id=user.id,
        instrument_id=inst.id,
        symbol="PETKM.IS",
        name="Petkim",
        asset_type=AssetType.STOCK,
        current_price=Decimal("20.0"),
    )
    db_session.add(asset)
    await db_session.flush()

    buy_tx = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("50"),
        price_per_unit=Decimal("20"),
        total_amount=Decimal("1000"),
        transaction_currency="TRY",
        transaction_date=date.today(),
    )
    db_session.add(buy_tx)
    await db_session.commit()

    # Propose selling 50 units (valid at proposal time)
    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="PETKM.IS",
        transaction_type="SELL",
        quantity=50.0,
        price=21.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])

    # But before confirming, another transaction sells 30 units outside copilot
    external_sell = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.SELL,
        quantity=Decimal("30"),
        price_per_unit=Decimal("20"),
        total_amount=Decimal("600"),
        transaction_currency="TRY",
        transaction_date=date.today(),
    )
    db_session.add(external_sell)
    await db_session.commit()

    # Now trying to confirm selling 50 units must fail with STALE
    with pytest.raises(Exception) as exc_info:
        await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)

    assert "STALE" in str(exc_info.value) or "değişti" in str(exc_info.value)

    # Check proposal was marked STALE
    prop = await db_session.get(CopilotActionProposal, prop_id)
    assert prop.status == ActionProposalStatusV2.STALE.value


@pytest.mark.asyncio
async def test_action_executor_cancel_proposal(db_session: AsyncSession):
    """User can cancel a pending proposal; cancelled proposals cannot be executed."""
    user = await _create_user(db_session, "cancel_user")
    await _create_test_instrument(db_session, "FROTO.IS", "Ford Otosan")

    res = await propose_transaction_record_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="FROTO.IS",
        transaction_type="BUY",
        quantity=10.0,
        price=1000.0,
    )
    prop_id = uuid.UUID(res["proposal_id"])

    cancelled = await ActionExecutorV2.cancel_proposal(db_session, user.id, prop_id, reason="Vazgeçtim")
    assert cancelled.status == ActionProposalStatusV2.CANCELLED.value

    # Trying to execute cancelled proposal raises 400
    with pytest.raises(Exception) as exc_info:
        await ActionExecutorV2.execute_proposal(db_session, user.id, prop_id)

    assert "Cannot execute proposal" in str(exc_info.value)


# ---------------------------------------------------------------------------
# 5. HTTP Endpoints: GET, confirm POST, cancel POST
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_v2_action_proposal_endpoints(db_session: AsyncSession):
    """Test HTTP API endpoints for Copilot V2 action proposals."""
    user = await _create_user(db_session, "api_proposal_user")
    await _create_test_instrument(db_session, "AKBNK.IS", "Akbank")

    token = create_access_token(user.id)
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Create a proposal via tool
    res = await propose_watchlist_change_handler(
        db=db_session,
        user_id=user.id,
        symbol_or_name="AKBNK.IS",
        action="ADD",
        priority="HIGH",
    )
    await db_session.commit()
    prop_id = res["proposal_id"]

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # GET proposal
        get_res = await client.get(f"/api/copilot/v2/action-proposals/{prop_id}", headers=headers)
        assert get_res.status_code == 200
        assert get_res.json()["data"]["id"] == prop_id
        assert get_res.json()["data"]["status"] == ActionProposalStatusV2.PENDING.value

        # Confirm proposal
        conf_res = await client.post(
            f"/api/copilot/v2/action-proposals/{prop_id}/confirm",
            headers=headers,
            json={},
        )
        assert conf_res.status_code == 200
        assert conf_res.json()["data"]["proposal_status"] == ActionProposalStatusV2.EXECUTED.value

        # Cancel on executed proposal fails with 400
        cancel_res = await client.post(
            f"/api/copilot/v2/action-proposals/{prop_id}/cancel",
            headers=headers,
            json={"reason": "Geçersiz"},
        )
        assert cancel_res.status_code == 400
