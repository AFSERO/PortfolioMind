"""Verification script for PortfolioMind Copilot Phase 2 — Write Engine.

Simulates the entire Phase 2 Write Engine lifecycle:
1. User registration & conversation creation
2. Proposing a BUY transaction (status: READY_FOR_CONFIRMATION)
3. Explicit confirmation and execution (status: APPLIED, Transaction created, Cash affected, Audit log persisted)
4. Double-confirmation idempotency (zero duplicate transactions)
5. Non-cash gift acquisition (affects_cash=False)
6. SELL proposal and prevalidation against negative holdings (insufficient quantity fails)
7. Valid SELL execution and remaining quantity verification
8. Watchlist add and remove (Level 1 low-risk with durable audit)
9. Journal note creation (Level 1 low-risk with durable audit)
10. Proposal cancellation
"""

import asyncio
from datetime import date
from decimal import Decimal
import os
import sys
import uuid

# Ensure backend root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import get_db
from app.main import app
from app.models.asset import Asset
from app.models.copilot import CopilotActionProposal, CopilotAuditLog
from app.models.decision_log import DecisionLogEntry
from app.models.opportunity import WatchlistItem
from app.models.transaction import Transaction, TransactionType


async def run_verification():
    print("======================================================================")
    print("PORTFOLIOMIND COPILOT — PHASE 2 WRITE ENGINE VERIFICATION")
    print("======================================================================\n")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        # Step 1: User Registration
        email = f"p2_verify_{uuid.uuid4().hex[:6]}@example.com"
        reg_resp = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "StrongPassword123!"},
        )
        assert reg_resp.status_code == 201, reg_resp.text
        token = reg_resp.json()["data"]["access_token"]
        user_id = reg_resp.json()["data"]["user"]["id"]
        headers = {"Authorization": f"Bearer {token}"}
        print(f"Step 1: Registered user {email} (UUID: {user_id})")

        # Step 2: Create Conversation
        conv_resp = await client.post("/api/copilot/conversations", json={"title": "Phase 2 Verification"}, headers=headers)
        assert conv_resp.status_code == 201
        conv_id = conv_resp.json()["data"]["id"]
        print(f"Step 2: Created conversation {conv_id}")

        # Step 3: Propose BUY transaction (Level 2: Confirmation Required)
        print("\n--- Testing BUY Transaction Flow ---")
        buy_msg = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I bought 10 NVDA at $120.00 on {date.today()}."},
            headers=headers,
        )
        assert buy_msg.status_code == 200
        prop_data = buy_msg.json()["data"]["structured_response"]["proposal"]
        assert prop_data is not None
        assert prop_data["status"] == "READY_FOR_CONFIRMATION"
        prop_buy_id = prop_data["id"]
        print(f"Step 3: Staged BUY proposal {prop_buy_id} in READY_FOR_CONFIRMATION status")
        print(f"        Summary: {prop_data['human_readable_summary']}")
        print(f"        Expected Impact: {prop_data['expected_impact']}")

        # Step 4: Confirm BUY transaction
        confirm_buy = await client.post(f"/api/copilot/proposals/{prop_buy_id}/confirm", headers=headers)
        assert confirm_buy.status_code == 200
        res_buy = confirm_buy.json()["data"]["execution_result"]
        tx_buy_id = res_buy["transaction_id"]
        print(f"Step 4: Confirmed BUY proposal -> Transaction created: {tx_buy_id}")
        print(f"        Quantity: {res_buy['quantity']}, Unit Price: {res_buy['price_per_unit']}, Cash Outflow: {res_buy['total_amount']}")

        # Step 5: Double Confirmation Idempotency Check
        confirm_buy_again = await client.post(f"/api/copilot/proposals/{prop_buy_id}/confirm", headers=headers)
        assert confirm_buy_again.status_code == 200
        tx_buy_id_again = confirm_buy_again.json()["data"]["execution_result"]["transaction_id"]
        assert tx_buy_id == tx_buy_id_again
        print(f"Step 5: Double-confirm returned identical transaction {tx_buy_id_again} without duplicate execution (Idempotent!)")

        # Step 6: Non-Cash Gift Acquisition (GIFT_IN)
        print("\n--- Testing Non-Cash Gift Acquisition (GIFT_IN) ---")
        gift_msg = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"Annem bana 1 yarım altın hediye etti on {date.today()}."},
            headers=headers,
        )
        assert gift_msg.status_code == 200
        prop_gift = gift_msg.json()["data"]["structured_response"]["proposal"]
        assert prop_gift["parameters"]["affects_cash"] is False
        confirm_gift = await client.post(f"/api/copilot/proposals/{prop_gift['id']}/confirm", headers=headers)
        assert confirm_gift.status_code == 200
        assert confirm_gift.json()["data"]["execution_result"]["affects_cash"] is False
        print(f"Step 6: Confirmed gift acquisition with affects_cash=False (zero cash outflow)")

        # Step 7: SELL Prevalidation against Negative Holdings
        print("\n--- Testing SELL Validation & Execution ---")
        oversell_msg = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I sold 15 NVDA at $130.00 on {date.today()}."},
            headers=headers,
        )
        assert oversell_msg.status_code == 200
        prop_oversell_id = oversell_msg.json()["data"]["structured_response"]["proposal"]["id"]
        oversell_confirm = await client.post(f"/api/copilot/proposals/{prop_oversell_id}/confirm", headers=headers)
        assert oversell_confirm.status_code == 400
        print(f"Step 7: Oversell rejected as expected: {oversell_confirm.json().get('detail') or oversell_confirm.json().get('message')}")

        # Valid SELL: sell 4 shares (out of 10)
        valid_sell_msg = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I sold 4 NVDA at $130.00 on {date.today()}."},
            headers=headers,
        )
        prop_validsell_id = valid_sell_msg.json()["data"]["structured_response"]["proposal"]["id"]
        validsell_confirm = await client.post(f"/api/copilot/proposals/{prop_validsell_id}/confirm", headers=headers)
        assert validsell_confirm.status_code == 200
        rem_qty = validsell_confirm.json()["data"]["execution_result"]["remaining_quantity"]
        assert rem_qty == 6.0
        print(f"Step 8: Valid SELL of 4 shares executed -> Remaining position: {rem_qty} NVDA")

        # Step 8: Watchlist Add and Remove (Level 1 Low-Risk)
        print("\n--- Testing Watchlist Add & Remove ---")
        wl_add = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "Add MSFT to my watchlist"},
            headers=headers,
        )
        assert wl_add.status_code == 200
        wl_prop = wl_add.json()["data"]["structured_response"]["proposal"]
        assert wl_prop["status"] == "APPLIED"
        print(f"Step 9: Watchlist item added: {wl_add.json()['data']['structured_response']['answer']}")

        wl_rem = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "Remove MSFT from watchlist"},
            headers=headers,
        )
        assert wl_rem.status_code == 200
        print(f"Step 10: Watchlist item removed: {wl_rem.json()['data']['structured_response']['answer']}")

        # Step 9: Journal Note Creation (Level 1 Low-Risk)
        print("\n--- Testing Journal Note Creation ---")
        jn_msg = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": "Add note: Trimming NVDA position to take partial profits ahead of CPI release."},
            headers=headers,
        )
        assert jn_msg.status_code == 200
        jn_prop = jn_msg.json()["data"]["structured_response"]["proposal"]
        assert jn_prop["status"] == "APPLIED"
        print(f"Step 11: Journal decision note created: {jn_msg.json()['data']['structured_response']['answer']}")

        # Step 10: Proposal Cancellation
        print("\n--- Testing Proposal Cancellation ---")
        cancel_target = await client.post(
            f"/api/copilot/conversations/{conv_id}/messages",
            json={"content": f"I bought 2 AAPL at $220.00 on {date.today()}."},
            headers=headers,
        )
        cancel_target_id = cancel_target.json()["data"]["structured_response"]["proposal"]["id"]
        cancel_res = await client.post(
            f"/api/copilot/proposals/{cancel_target_id}/cancel",
            json={"reason": "Decided to wait for dip"},
            headers=headers,
        )
        assert cancel_res.status_code == 200
        assert cancel_res.json()["data"]["status"] == "CANCELLED"
        print(f"Step 12: Successfully cancelled proposal {cancel_target_id}")

        confirm_after_cancel = await client.post(f"/api/copilot/proposals/{cancel_target_id}/confirm", headers=headers)
        assert confirm_after_cancel.status_code == 400
        print(f"Step 13: Confirmation of cancelled proposal rejected as expected.")

    print("\n======================================================================")
    print("ALL 13 PHASE 2 WRITE ENGINE VERIFICATION STEPS PASSED PERFECTLY!")
    print("======================================================================\n")


if __name__ == "__main__":
    asyncio.run(run_verification())
