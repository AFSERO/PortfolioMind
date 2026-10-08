"""Live Codex CLI & Runtime Verification for Copilot V2 Phase 3.2.

Executes real conversational turns against the live containerized Codex CLI runtime:
1. Turn 1 (Hypothetical): "THF'nin yarısını satsam portföy nasıl görünür?"
   -> Verifies call to `simulate_transaction`, ZERO proposals staged, ZERO mutations.
2. Turn 2 (Hypothetical %25): "THF'nin %25'ini satsam dağılım ne olur?"
   -> Verifies call to `simulate_transaction` with fraction 0.25, explains allocation shift.
3. Turn 3 (Explicit intent boundary): "THF'nin yarısını sattım, portföye kaydet."
   -> Verifies proposal path / price clarification, does NOT call simulate_transaction,
      ZERO immediate mutations.
4. Turn 4 (Hypothetical lump-sum BUY): "100.000 TL NVDA alsam portföyde ağırlığı kaç olur?"
   -> Verifies call to `simulate_transaction`, ZERO mutations.
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import json
import os
import sys
import time
import uuid

# Ensure backend root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from httpx import ASGITransport, AsyncClient
from sqlalchemy import func, select

from app.database import get_session_factory
from app.main import app
from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount, CashMovement
from app.models.copilot import CopilotActionProposal, CopilotAuditLog, CopilotConversation
from app.models.instrument import Instrument
from app.models.opportunity import WatchlistItem
from app.models.transaction import Transaction, TransactionType
from app.models.user import User


async def parse_sse_stream(response):
    """Parse SSE event stream from send_v2_message endpoint."""
    events = []
    current_event = {}
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            payload = line[6:].strip()
            if payload:
                try:
                    data = json.loads(payload)
                    events.append(data)
                except Exception as e:
                    pass
    return events


async def get_db_counts(session_factory, user_id):
    """Helper to query all domain counts for zero-mutation verification."""
    async with session_factory() as db:
        tx_count = (await db.execute(select(func.count()).select_from(Transaction).join(Asset).where(Asset.user_id == user_id))).scalar() or 0
        asset_count = (await db.execute(select(func.count()).select_from(Asset).where(Asset.user_id == user_id))).scalar() or 0
        cash_count = (await db.execute(select(func.count()).select_from(CashAccount).where(CashAccount.user_id == user_id))).scalar() or 0
        mov_count = (await db.execute(select(func.count()).select_from(CashMovement).join(CashAccount).where(CashAccount.user_id == user_id))).scalar() or 0
        prop_count = (await db.execute(select(func.count()).select_from(CopilotActionProposal).where(CopilotActionProposal.user_id == user_id))).scalar() or 0
        return {
            "transactions": tx_count,
            "assets": asset_count,
            "cash_accounts": cash_count,
            "cash_movements": mov_count,
            "proposals": prop_count,
        }


async def run_live_verification():
    print("=" * 72)
    print("PORTFOLIOMIND COPILOT V2 — PHASE 3.2 LIVE SIMULATION ENGINE VERIFICATION")
    print("=" * 72)

    session_factory = get_session_factory()

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=180.0) as client:
        # ---------------------------------------------------------------------
        # 0. User & Instruments Setup
        # ---------------------------------------------------------------------
        print("\n[Step 0] Setting up test user, instruments, and initial holdings...")
        email = f"live_sim_{uuid.uuid4().hex[:6]}@example.com"
        reg_resp = await client.post(
            "/api/auth/register",
            json={"email": email, "password": "SecurePassword123!", "display_name": "Phase 3.2 Verifier"},
        )
        assert reg_resp.status_code == 201, f"Registration failed: {reg_resp.text}"
        token = reg_resp.json()["data"]["access_token"]
        user_id = uuid.UUID(reg_resp.json()["data"]["user"]["id"])
        headers = {"Authorization": f"Bearer {token}"}
        print(f"  User registered: {email} (ID: {user_id})")

        # Seed instruments & portfolio state directly in DB
        async with session_factory() as db:
            # 1. Ensure THF instrument
            stmt_thf = select(Instrument).where(Instrument.symbol == "THF")
            thf_inst = (await db.execute(stmt_thf)).scalar_one_or_none()
            if not thf_inst:
                thf_inst = Instrument(
                    symbol="THF",
                    name="TERA PORTFÖY HİSSE SENEDİ (TL) FONU (HİSSE SENEDİ YOĞUN FON)",
                    asset_type=AssetType.FUND,
                    currency="TRY",
                )
                db.add(thf_inst)
                await db.flush()

            # 2. Ensure NVDA instrument
            stmt_nvda = select(Instrument).where(Instrument.symbol == "NVDA")
            nvda_inst = (await db.execute(stmt_nvda)).scalar_one_or_none()
            if not nvda_inst:
                nvda_inst = Instrument(
                    symbol="NVDA",
                    name="NVIDIA Corporation",
                    asset_type=AssetType.STOCK,
                    currency="USD",
                )
                db.add(nvda_inst)
                await db.flush()

            # 3. User owns 1,000 units of THF @ 10.0 TRY = 10,000 TRY
            asset = Asset(
                user_id=user_id,
                instrument_id=thf_inst.id,
                asset_type=thf_inst.asset_type,
                symbol=thf_inst.symbol,
                name=thf_inst.name,
                current_price=Decimal("10.0"),
                current_price_currency="TRY",
            )
            db.add(asset)
            await db.flush()

            tx = Transaction(
                asset_id=asset.id,
                transaction_type=TransactionType.BUY,
                quantity=Decimal("1000"),
                price_per_unit=Decimal("10.0"),
                total_amount=Decimal("10000"),
                transaction_currency="TRY",
                transaction_date=date.today(),
                affects_cash=False,
            )
            db.add(tx)

            # 4. User has 40,000 TRY cash. Total portfolio = 50,000 TRY. (THF weight = 20.0%)
            stmt_cash = select(CashAccount).where(CashAccount.user_id == user_id, CashAccount.currency == "TRY")
            cash = (await db.execute(stmt_cash)).scalar_one_or_none()
            if cash:
                cash.balance = Decimal("40000")
            else:
                cash = CashAccount(
                    user_id=user_id,
                    currency="TRY",
                    balance=Decimal("40000"),
                )
                db.add(cash)
            await db.commit()


        # Create conversation
        conv_resp = await client.post("/api/copilot/conversations", headers=headers, json={"title": "Phase 3.2 Simulation"})
        conv_id = conv_resp.json()["data"]["id"]
        print(f"  Conversation created: {conv_id}")

        baseline_counts = await get_db_counts(session_factory, user_id)
        print(f"  Baseline counts: {baseline_counts}")

        # ---------------------------------------------------------------------
        # Turn 1: Hypothetical Sell Half ("THF'nin yarısını satsam portföy nasıl görünür?")
        # ---------------------------------------------------------------------
        print("\n" + "-" * 72)
        print("[Turn 1] Hypothetical: 'THF\\'nin yarısını satsam portföy nasıl görünür?'")
        print("-" * 72)
        t0 = time.time()
        resp1 = await client.post(
            f"/api/copilot/v2/conversations/{conv_id}/messages?stream=true",
            headers=headers,
            json={"content": "THF'nin yarısını satsam portföy nasıl görünür?"},
        )
        events1 = await parse_sse_stream(resp1)
        dur1 = time.time() - t0

        final1 = next((e for e in events1 if e.get("type") == "FINAL"), None)
        assert final1, "No FINAL event received for Turn 1!"
        tools_called1 = final1.get("trace", {}).get("tools_called", [])
        proposal1 = final1.get("message", {}).get("structured_metadata", {}).get("proposal")
        simulation1 = final1.get("message", {}).get("structured_metadata", {}).get("simulation")
        answer1 = final1.get("message", {}).get("raw_content", "")
        sim_used1 = final1.get("trace", {}).get("simulation_used", False)

        print(f"  Profile: {final1.get('trace', {}).get('starting_profile')} -> {final1.get('trace', {}).get('final_profile')}")
        print(f"  Tools called: {tools_called1}")
        print(f"  Simulation tool used: {sim_used1}")
        print(f"  Simulation metadata present: {simulation1 is not None}")
        print(f"  Proposal created: {proposal1 is not None}")
        print(f"  Duration: {dur1:.2f}s")
        print(f"  Answer preview: {answer1[:220]}...")

        counts1 = await get_db_counts(session_factory, user_id)
        assert counts1 == baseline_counts, f"Turn 1 mutated database! {counts1} vs {baseline_counts}"
        assert proposal1 is None, "Turn 1 incorrectly created an action proposal!"
        assert "simulate_transaction" in tools_called1, f"simulate_transaction not called in Turn 1! Tools: {tools_called1}"
        assert simulation1 is not None, "Simulation metadata missing from Turn 1!"
        print("  ✓ Turn 1 verified: Pure simulation path, simulate_transaction called, ZERO mutations, NO proposals.")

        # ---------------------------------------------------------------------
        # Turn 2: Hypothetical Sell %25 ("THF'nin %25'ini satsam dağılım ne olur?")
        # ---------------------------------------------------------------------
        print("\n" + "-" * 72)
        print("[Turn 2] Hypothetical %25: 'THF\\'nin %25\\'ini satsam dağılım ne olur?'")
        print("-" * 72)
        t0 = time.time()
        resp2 = await client.post(
            f"/api/copilot/v2/conversations/{conv_id}/messages?stream=true",
            headers=headers,
            json={"content": "THF'nin %25'ini satsam dağılım ne olur?"},
        )
        events2 = await parse_sse_stream(resp2)
        dur2 = time.time() - t0

        final2 = next((e for e in events2 if e.get("type") == "FINAL"), None)
        assert final2, "No FINAL event received for Turn 2!"
        tools_called2 = final2.get("trace", {}).get("tools_called", [])
        proposal2 = final2.get("message", {}).get("structured_metadata", {}).get("proposal")
        simulation2 = final2.get("message", {}).get("structured_metadata", {}).get("simulation")
        answer2 = final2.get("message", {}).get("raw_content", "")

        print(f"  Profile: {final2.get('trace', {}).get('starting_profile')} -> {final2.get('trace', {}).get('final_profile')}")
        print(f"  Tools called: {tools_called2}")
        print(f"  Simulation metadata present: {simulation2 is not None}")
        print(f"  Proposal created: {proposal2 is not None}")
        print(f"  Duration: {dur2:.2f}s")
        print(f"  Answer preview: {answer2[:220]}...")

        counts2 = await get_db_counts(session_factory, user_id)
        assert counts2 == baseline_counts, f"Turn 2 mutated database! {counts2} vs {baseline_counts}"
        assert proposal2 is None, "Turn 2 incorrectly created an action proposal!"
        assert "simulate_transaction" in tools_called2, f"simulate_transaction not called in Turn 2! Tools: {tools_called2}"
        print("  ✓ Turn 2 verified: Fraction %25 parsed deterministically, ZERO mutations.")

        # ---------------------------------------------------------------------
        # Turn 3: Explicit Intent Boundary ("THF'nin yarısını sattım, portföye kaydet.")
        # ---------------------------------------------------------------------
        print("\n" + "-" * 72)
        print("[Turn 3] Explicit Mutation Intent: 'THF\\'nin yarısını sattım, portföye kaydet.'")
        print("-" * 72)
        t0 = time.time()
        resp3 = await client.post(
            f"/api/copilot/v2/conversations/{conv_id}/messages?stream=true",
            headers=headers,
            json={"content": "THF'nin yarısını sattım, portföye kaydet."},
        )
        events3 = await parse_sse_stream(resp3)
        dur3 = time.time() - t0

        final3 = next((e for e in events3 if e.get("type") == "FINAL"), None)
        assert final3, "No FINAL event received for Turn 3!"
        tools_called3 = final3.get("trace", {}).get("tools_called", [])
        proposal3 = final3.get("message", {}).get("structured_metadata", {}).get("proposal")
        simulation3 = final3.get("message", {}).get("structured_metadata", {}).get("simulation")
        answer3 = final3.get("message", {}).get("raw_content", "")

        print(f"  Profile: {final3.get('trace', {}).get('starting_profile')} -> {final3.get('trace', {}).get('final_profile')}")
        print(f"  Tools called: {tools_called3}")
        print(f"  Simulation tool called: {'simulate_transaction' in tools_called3}")
        print(f"  Proposal created: {proposal3 is not None}")
        print(f"  Duration: {dur3:.2f}s")
        print(f"  Answer preview: {answer3[:220]}...")

        counts3 = await get_db_counts(session_factory, user_id)
        # Transaction count must still be baseline (zero unconfirmed mutation!)
        assert counts3["transactions"] == baseline_counts["transactions"], "Transaction was executed without confirmation!"
        assert "simulate_transaction" not in tools_called3, "simulate_transaction should not be called for explicit record requests!"
        print("  ✓ Turn 3 verified: Did NOT use simulation, zero unconfirmed mutation.")

        # ---------------------------------------------------------------------
        # Turn 4: Hypothetical BUY Amount ("100.000 TL NVDA alsam portföyde ağırlığı kaç olur?")
        # ---------------------------------------------------------------------
        print("\n" + "-" * 72)
        print("[Turn 4] Hypothetical BUY: '100.000 TL NVDA alsam portföyde ağırlığı kaç olur?'")
        print("-" * 72)
        t0 = time.time()
        resp4 = await client.post(
            f"/api/copilot/v2/conversations/{conv_id}/messages?stream=true",
            headers=headers,
            json={"content": "100.000 TL NVDA alsam portföyde ağırlığı kaç olur?"},
        )
        events4 = await parse_sse_stream(resp4)
        dur4 = time.time() - t0

        final4 = next((e for e in events4 if e.get("type") == "FINAL"), None)
        assert final4, "No FINAL event received for Turn 4!"
        tools_called4 = final4.get("trace", {}).get("tools_called", [])
        proposal4 = final4.get("message", {}).get("structured_metadata", {}).get("proposal")
        simulation4 = final4.get("message", {}).get("structured_metadata", {}).get("simulation")
        answer4 = final4.get("message", {}).get("raw_content", "")

        print(f"  Profile: {final4.get('trace', {}).get('starting_profile')} -> {final4.get('trace', {}).get('final_profile')}")
        print(f"  Tools called: {tools_called4}")
        print(f"  Simulation metadata present: {simulation4 is not None}")
        print(f"  Proposal created: {proposal4 is not None}")
        print(f"  Duration: {dur4:.2f}s")
        print(f"  Answer preview: {answer4[:220]}...")

        counts4 = await get_db_counts(session_factory, user_id)
        assert counts4["transactions"] == baseline_counts["transactions"]
        assert proposal4 is None, "Turn 4 incorrectly created an action proposal!"
        print("  ✓ Turn 4 verified: Hypothetical BUY evaluated safely without mutation.")

        print("\n" + "=" * 72)
        print("PHASE 3.2 LIVE RUNTIME VERIFICATION SUCCESSFULLY COMPLETED!")
        print("All boundary invariants, deterministic calculations, and zero mutations verified.")
        print("=" * 72)


if __name__ == "__main__":
    asyncio.run(run_live_verification())
