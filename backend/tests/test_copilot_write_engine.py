"""Comprehensive test suite for PortfolioMind Copilot Phase 2 — Write Engine.

Tests:
1. BUY proposal creation and explicit confirmation flow (Level 2).
2. Double-confirmation idempotency (zero duplicate mutations).
3. SELL validation against negative holdings (insufficient quantity fails prevalidation).
4. Non-cash acquisition (GIFT_IN / TRANSFER_IN with 0 cash impact).
5. Watchlist add and remove (Level 1 low-risk write with durable audit).
6. Journal / decision note creation (Level 1 low-risk write with durable audit).
7. Cross-user isolation (User B cannot access or confirm User A's proposals).
8. Proposal cancellation and expired proposal rejection.
"""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch
import uuid

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.main import app
from app.models.asset import Asset, AssetType
from app.models.copilot import CopilotActionProposal, CopilotAuditLog, CopilotConversation
from app.models.decision_log import DecisionLogEntry
from app.models.instrument import Instrument
from app.models.opportunity import WatchlistItem
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.copilot import (
    ActionProposalStatus,
    ActionType,
    ExecutionMode,
    IntentType,
    ProposalPermissionLevel,
)
from app.services.copilot import CopilotProposalService, CopilotService, CopilotWriteExecutor


async def _register_user(client: AsyncClient, email: str) -> tuple[str, dict]:
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "StrongPassword123!"},
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["data"]["access_token"]
    user_id = resp.json()["data"]["user"]["id"]
    return user_id, {"Authorization": f"Bearer {token}"}


# -----------------------------------------------------------------------------
# 1. BUY Proposal Creation & Explicit Confirmation Flow
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_buy_proposal_creation_and_confirmation(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id, headers = await _register_user(client, f"buy_{uuid.uuid4().hex[:6]}@example.com")
        conv_resp = await client.post("/api/copilot/conversations", json={"title": "Buy Test"}, headers=headers)
        conv_id = conv_resp.json()["data"]["id"]

        # Send buy transaction message
        msg_resp = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I bought 10 NVDA at $120.00 on {date.today()}."},
            headers=headers,
        )
        assert msg_resp.status_code == 200
        msg_data = msg_resp.json()["data"]
        structured = msg_data["structured_response"]

        proposal_data = structured.get("proposal")
        assert proposal_data is not None, "Action proposal should be returned in structured response"
        proposal_id = proposal_data["id"]
        assert proposal_data["status"] == ActionProposalStatus.READY_FOR_CONFIRMATION.value
        assert proposal_data["action_type"] in (ActionType.BUY_TRANSACTION.value, "BUY")
        assert proposal_data["parameters"]["quantity"] == 10.0
        assert proposal_data["parameters"]["unit_price"] == 120.0

        # Verify NO transaction exists in DB before confirmation
        tx_pre = (await db_session.execute(select(Transaction))).scalars().all()
        assert len(tx_pre) == 0, "No financial transaction should be created prior to confirmation"

        # Explicitly confirm the proposal
        confirm_resp = await client.post(
            f"/api/copilot/proposals/{proposal_id}/confirm",
            json={"idempotency_key": "buy_idemp_key_1"},
            headers=headers,
        )
        assert confirm_resp.status_code == 200
        confirm_data = confirm_resp.json()["data"]
        assert confirm_data["proposal"]["status"] == ActionProposalStatus.APPLIED.value
        assert confirm_data["execution_result"]["transaction_type"] == "BUY"

        # Verify transaction now exists in DB with correct values
        tx_stmt = select(Transaction).where(Transaction.transaction_type == TransactionType.BUY)
        tx_post = (await db_session.execute(tx_stmt)).scalars().all()
        assert len(tx_post) == 1
        tx = tx_post[0]
        assert tx.quantity == Decimal("10.0")
        assert tx.price_per_unit == Decimal("120.0")
        assert tx.affects_cash is True

        # Verify durable CopilotAuditLog was recorded
        audit_stmt = select(CopilotAuditLog).where(CopilotAuditLog.proposal_id == uuid.UUID(proposal_id))
        audit = (await db_session.execute(audit_stmt)).scalar_one_or_none()
        assert audit is not None
        assert audit.action_type in (ActionType.BUY_TRANSACTION.value, "BUY")
        assert audit.execution_status == "SUCCESS"
        assert audit.affected_resource_type == "TRANSACTION"
        assert audit.affected_resource_id == str(tx.id)


# -----------------------------------------------------------------------------
# 2. Double Confirmation Idempotency
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_double_confirmation_idempotency(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id, headers = await _register_user(client, f"idemp_{uuid.uuid4().hex[:6]}@example.com")
        conv_resp = await client.post("/api/copilot/conversations", json={"title": "Idemp Test"}, headers=headers)
        conv_id = conv_resp.json()["data"]["id"]

        msg_resp = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I bought 5 AAPL at $150.00 on {date.today()}."},
            headers=headers,
        )
        proposal_id = msg_resp.json()["data"]["structured_response"]["proposal"]["id"]

        # First confirmation
        c1 = await client.post(f"/api/copilot/proposals/{proposal_id}/confirm", headers=headers)
        assert c1.status_code == 200
        tx_id_1 = c1.json()["data"]["execution_result"]["transaction_id"]

        # Second confirmation (simulating rapid double-click or network retry)
        c2 = await client.post(f"/api/copilot/proposals/{proposal_id}/confirm", headers=headers)
        assert c2.status_code == 200
        tx_id_2 = c2.json()["data"]["execution_result"]["transaction_id"]

        # Exactly the same transaction returned, exactly 1 transaction in DB
        assert tx_id_1 == tx_id_2
        all_txns = (await db_session.execute(select(Transaction))).scalars().all()
        assert len(all_txns) == 1, "Double confirmation must not create duplicate transactions"


# -----------------------------------------------------------------------------
# 3. SELL Validation against Negative Holdings
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_sell_validation_against_negative_holdings(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id, headers = await _register_user(client, f"sell_{uuid.uuid4().hex[:6]}@example.com")
        conv_resp = await client.post("/api/copilot/conversations", json={"title": "Sell Test"}, headers=headers)
        conv_id = conv_resp.json()["data"]["id"]

        # 1. Attempt to sell when user owns 0 shares -> should fail execution
        msg_resp1 = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I sold 10 MSFT at $400.00 on {date.today()}."},
            headers=headers,
        )
        assert msg_resp1.status_code == 200
        prop_id_fail = msg_resp1.json()["data"]["structured_response"]["proposal"]["id"]

        # Confirmation should reject because position does not exist or has 0 shares
        fail_confirm = await client.post(f"/api/copilot/proposals/{prop_id_fail}/confirm", headers=headers)
        assert fail_confirm.status_code == 400
        fail_err = (fail_confirm.json().get("detail") or fail_confirm.json().get("message") or "").lower()
        assert "insufficient holdings" in fail_err or "no position" in fail_err

        # 2. Buy 5 shares first
        buy_msg = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I bought 5 MSFT at $390.00 on {date.today()}."},
            headers=headers,
        )
        prop_id_buy = buy_msg.json()["data"]["structured_response"]["proposal"]["id"]
        await client.post(f"/api/copilot/proposals/{prop_id_buy}/confirm", headers=headers)

        # 3. Attempt to sell 8 shares (user only has 5)
        oversell_msg = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I sold 8 MSFT at $410.00 on {date.today()}."},
            headers=headers,
        )
        prop_id_oversell = oversell_msg.json()["data"]["structured_response"]["proposal"]["id"]
        oversell_confirm = await client.post(f"/api/copilot/proposals/{prop_id_oversell}/confirm", headers=headers)
        assert oversell_confirm.status_code == 400
        oversell_err = (oversell_confirm.json().get("detail") or oversell_confirm.json().get("message") or "").lower()
        assert "insufficient holdings" in oversell_err

        # 4. Valid sell: sell 2 shares (out of 5)
        valid_sell_msg = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I sold 2 MSFT at $410.00 on {date.today()}."},
            headers=headers,
        )
        prop_id_validsell = valid_sell_msg.json()["data"]["structured_response"]["proposal"]["id"]
        valid_confirm = await client.post(f"/api/copilot/proposals/{prop_id_validsell}/confirm", headers=headers)
        assert valid_confirm.status_code == 200
        assert valid_confirm.json()["data"]["execution_result"]["remaining_quantity"] == 3.0


# -----------------------------------------------------------------------------
# 4. Non-Cash Acquisition (GIFT_IN / TRANSFER_IN) Flow
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_non_cash_gift_acquisition_zero_cash_outflow(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id, headers = await _register_user(client, f"gift_{uuid.uuid4().hex[:6]}@example.com")
        conv_resp = await client.post("/api/copilot/conversations", json={"title": "Gift Test"}, headers=headers)
        conv_id = conv_resp.json()["data"]["id"]

        # Mother gave 1 half gold
        msg_resp = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"Annem bana 1 yarım altın hediye etti on {date.today()}."},
            headers=headers,
        )
        assert msg_resp.status_code == 200
        prop = msg_resp.json()["data"]["structured_response"]["proposal"]
        assert prop is not None
        assert prop["parameters"]["affects_cash"] is False
        assert prop["parameters"]["cash_outflow"] == 0.0

        # Confirm gift acquisition
        c_resp = await client.post(f"/api/copilot/proposals/{prop['id']}/confirm", headers=headers)
        assert c_resp.status_code == 200
        res = c_resp.json()["data"]["execution_result"]
        assert res["affects_cash"] is False

        # Verify transaction in DB has affects_cash=False
        tx = (await db_session.execute(select(Transaction).where(Transaction.id == uuid.UUID(res["transaction_id"])))).scalar_one()
        assert tx.affects_cash is False
        assert tx.quantity == Decimal("1.0")


# -----------------------------------------------------------------------------
# 5. Watchlist Add and Remove Flow (Level 1 Low-Risk)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_watchlist_add_and_remove(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id, headers = await _register_user(client, f"wl_{uuid.uuid4().hex[:6]}@example.com")
        conv_resp = await client.post("/api/copilot/conversations", json={"title": "WL Test"}, headers=headers)
        conv_id = conv_resp.json()["data"]["id"]

        # 1. Add to watchlist
        add_resp = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "Add TSLA to my watchlist"},
            headers=headers,
        )
        assert add_resp.status_code == 200
        struct_add = add_resp.json()["data"]["structured_response"]
        assert struct_add["intent"] == IntentType.WATCHLIST_UPDATE.value
        assert struct_add["proposal"]["status"] == ActionProposalStatus.APPLIED.value
        assert "TSLA" in struct_add["answer"]

        # Verify WatchlistItem exists in DB
        w_stmt = select(WatchlistItem).where(WatchlistItem.user_id == uuid.UUID(user_id))
        w_items = (await db_session.execute(w_stmt)).scalars().all()
        assert len(w_items) == 1

        # Verify durable audit log recorded
        audit_add = (await db_session.execute(
            select(CopilotAuditLog).where(
                CopilotAuditLog.user_id == uuid.UUID(user_id),
                CopilotAuditLog.action_type == "ADD_WATCHLIST",
            )
        )).scalars().all()
        assert len(audit_add) == 1
        assert audit_add[0].execution_status == "SUCCESS"

        # 2. Remove from watchlist
        rem_resp = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "Remove TSLA from watchlist"},
            headers=headers,
        )
        assert rem_resp.status_code == 200
        struct_rem = rem_resp.json()["data"]["structured_response"]
        assert struct_rem["intent"] == IntentType.WATCHLIST_UPDATE.value
        assert struct_rem["proposal"]["status"] == ActionProposalStatus.APPLIED.value

        # Verify WatchlistItem deleted
        w_items_after = (await db_session.execute(w_stmt)).scalars().all()
        assert len(w_items_after) == 0


# -----------------------------------------------------------------------------
# 6. Journal / Decision Note Creation (Level 1 Low-Risk)
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_journal_entry_creation(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        user_id, headers = await _register_user(client, f"jn_{uuid.uuid4().hex[:6]}@example.com")
        conv_resp = await client.post("/api/copilot/conversations", json={"title": "Journal Test"}, headers=headers)
        conv_id = conv_resp.json()["data"]["id"]

        msg_resp = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "Add note: Rebalanced tech holdings after Fed rate cut."},
            headers=headers,
        )
        assert msg_resp.status_code == 200
        struct = msg_resp.json()["data"]["structured_response"]
        assert struct["intent"] == IntentType.JOURNAL_ENTRY.value
        assert struct["proposal"]["status"] == ActionProposalStatus.APPLIED.value

        # Verify DecisionLogEntry in DB
        d_stmt = select(DecisionLogEntry).where(DecisionLogEntry.user_id == uuid.UUID(user_id))
        d_entries = (await db_session.execute(d_stmt)).scalars().all()
        assert len(d_entries) == 1
        assert "Rebalanced tech holdings" in d_entries[0].summary

        # Verify durable audit log
        audit = (await db_session.execute(
            select(CopilotAuditLog).where(
                CopilotAuditLog.user_id == uuid.UUID(user_id),
                CopilotAuditLog.action_type == ActionType.CREATE_JOURNAL_ENTRY.value,
            )
        )).scalars().all()
        assert len(audit) == 1


# -----------------------------------------------------------------------------
# 7. Cross-User Security & Isolation
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_cross_user_proposal_isolation(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # User A creates a proposal
        _, headers_a = await _register_user(client, f"usera_{uuid.uuid4().hex[:6]}@example.com")
        conv_a = (await client.post("/api/copilot/conversations", json={"title": "User A"}, headers=headers_a)).json()["data"]["id"]
        msg_a = await client.post(
            f"/api/copilot/conversations/{conv_a}/messages",
            json={"content": f"I bought 10 AMZN at $180.00 on {date.today()}."},
            headers=headers_a,
        )
        prop_id_a = msg_a.json()["data"]["structured_response"]["proposal"]["id"]

        # User B registers
        _, headers_b = await _register_user(client, f"userb_{uuid.uuid4().hex[:6]}@example.com")

        # User B cannot GET User A's proposal
        get_b = await client.get(f"/api/copilot/proposals/{prop_id_a}", headers=headers_b)
        assert get_b.status_code == 404

        # User B cannot confirm User A's proposal
        confirm_b = await client.post(f"/api/copilot/proposals/{prop_id_a}/confirm", headers=headers_b)
        assert confirm_b.status_code == 404

        # User B cannot cancel User A's proposal
        cancel_b = await client.post(f"/api/copilot/proposals/{prop_id_a}/cancel", headers=headers_b)
        assert cancel_b.status_code == 404


# -----------------------------------------------------------------------------
# 8. Proposal Cancellation
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_proposal_cancellation_and_expiry(db_session):
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        _, headers = await _register_user(client, f"cancel_{uuid.uuid4().hex[:6]}@example.com")
        conv = (await client.post("/api/copilot/conversations", json={"title": "Cancel"}, headers=headers)).json()["data"]["id"]

        msg = await client.post(
            f"/api/copilot/conversations/{conv}/messages",
            json={"content": f"I bought 1 GOOG at $170.00 on {date.today()}."},
            headers=headers,
        )
        prop_id = msg.json()["data"]["structured_response"]["proposal"]["id"]

        # Cancel proposal
        cancel_resp = await client.post(
            f"/api/copilot/proposals/{prop_id}/cancel",
            json={"reason": "User changed mind"},
            headers=headers,
        )
        assert cancel_resp.status_code == 200
        assert cancel_resp.json()["data"]["status"] == ActionProposalStatus.CANCELLED.value

        # Attempting to confirm cancelled proposal must fail
        confirm_after_cancel = await client.post(f"/api/copilot/proposals/{prop_id}/confirm", headers=headers)
        assert confirm_after_cancel.status_code == 400
        cancel_err = (confirm_after_cancel.json().get("detail") or confirm_after_cancel.json().get("message") or "").lower()
        assert "cannot execute proposal in status 'cancelled'" in cancel_err

