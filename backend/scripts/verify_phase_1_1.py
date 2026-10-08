"""Controlled Verification Script for PortfolioMind Copilot Phase 1.1.

Simulates the exact real user scenario:
User: "My mother gave me one half-gold coin as a gift. Can you add it next to my existing half-gold holding?"
Copilot: NEEDS_INPUT (requests date, does not request price or IDs, draft saved)
User: "use today and current value"
Copilot: ACTION_INTENT (completes draft with date=today, unit_price=1348.55, cash_outflow=0.0)

Verifies:
- 0 DB mutations on financial tables
- Exact entity and provenance extraction
- Semantic financial value tagging
"""

import asyncio
from datetime import date
from decimal import Decimal
import sys
import uuid

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from sqlalchemy import select

from app.database import get_session_factory
from app.models.asset import Asset, AssetType
from app.models.copilot import CopilotConversation, CopilotMessage
from app.models.instrument import Instrument
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.copilot import AcquisitionType
from app.services.copilot.service import CopilotService


async def run_verification():
    print("=" * 70)
    print("PORTFOLIOMIND COPILOT — PHASE 1.1 CONTROLLED VERIFICATION")
    print("=" * 70)

    session_maker = get_session_factory()
    async with session_maker() as db:
        # Setup test user
        user = User(
            id=uuid.uuid4(),
            email=f"verify_1_1_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="test_pw",
            display_name="Demo User",
            base_currency="USD",
        )
        db.add(user)
        await db.flush()

        # Setup Instrument & Existing Holding: 1 Half Gold coin at $1,348.55
        inst = Instrument(
            id=uuid.uuid4(),
            symbol="HALF",
            name="Gold Half / Yarım Altın",
            asset_type=AssetType.PRECIOUS_METALS,
            currency="USD",
            exchange="COMMODITY",
        )
        db.add(inst)
        await db.flush()

        asset = Asset(
            id=uuid.uuid4(),
            user_id=user.id,
            instrument_id=inst.id,
            asset_type=AssetType.PRECIOUS_METALS,
            symbol="HALF",
            name="Yarım Altın / Gold Half HALF",
            current_price=Decimal("1348.55"),
            current_price_currency="USD",
        )
        db.add(asset)
        await db.flush()

        tx1 = Transaction(
            id=uuid.uuid4(),
            asset_id=asset.id,
            transaction_type=TransactionType.BUY,
            quantity=Decimal("1.0"),
            price_per_unit=Decimal("1300.00"),
            total_amount=Decimal("1300.00"),
            transaction_currency="USD",
            transaction_date=date(2026, 1, 10),
            affects_cash=True,
        )
        db.add(tx1)
        await db.commit()

        print(f"\n[1] Initial State Created:")
        print(f"    User: {user.display_name} ({user.id})")
        print(f"    Existing Asset: {asset.name} (Symbol: {asset.symbol})")
        print(f"    Current Unit Price: {asset.current_price} {asset.current_price_currency}")
        print(f"    Existing Quantity: 1.0 unit")

        # Create conversation
        conv = await CopilotService.create_conversation(db, user.id, "Gift Verification")

        # ---------------------------------------------------------------------
        # Turn 1
        # ---------------------------------------------------------------------
        q1 = "My mother gave me one half-gold coin as a gift. Can you add it next to my existing half-gold holding?"
        print(f"\n[2] Turn 1 User Message:")
        print(f"    \"{q1}\"")

        msg1, resp1 = await CopilotService.send_message(
            db=db,
            user_id=user.id,
            conversation_id=conv.id,
            content=q1,
        )

        print(f"\n[3] Turn 1 Copilot Response:")
        print(f"    Response Type: {resp1.response_type}")
        print(f"    Question Asked: \"{resp1.question}\"")
        print(f"    Missing Fields: {resp1.missing_fields}")
        if resp1.action_draft:
            print(f"    Action Draft:")
            print(f"      - Action Type: {resp1.action_draft.action_type}")
            print(f"      - Acquisition: {resp1.action_draft.acquisition_type}")
            print(f"      - Symbol: {resp1.action_draft.symbol}")
            print(f"      - Quantity: {resp1.action_draft.quantity}")
            print(f"      - Affects Cash: {resp1.action_draft.affects_cash}")
            print(f"      - Cash Outflow: {resp1.action_draft.cash_outflow}")

        assert resp1.response_type == "NEEDS_INPUT", "Must be NEEDS_INPUT"
        assert resp1.missing_fields == ["transaction_date"], "Only date should be missing"
        assert "id" not in resp1.question.lower(), "Must NEVER ask for technical IDs"
        assert "fiyat" not in resp1.question.lower() and "price" not in resp1.question.lower(), "Must NOT ask for price on a gift"

        # ---------------------------------------------------------------------
        # Turn 2
        # ---------------------------------------------------------------------
        q2 = "use today and current value"
        print(f"\n[4] Turn 2 User Follow-Up:")
        print(f"    \"{q2}\"")

        msg2, resp2 = await CopilotService.send_message(
            db=db,
            user_id=user.id,
            conversation_id=conv.id,
            content=q2,
        )

        print(f"\n[5] Turn 2 Copilot Response:")
        print(f"    Response Type: {resp2.response_type}")
        print(f"    Execution Mode: {resp2.execution_mode}")
        print(f"    Action Parameters:")
        for k, v in resp2.action.items():
            print(f"      - {k}: {v}")
        print(f"    Assistant Answer:\n    {resp2.answer.replace(chr(10), chr(10) + '    ')}")

        assert resp2.response_type == "ACTION_INTENT", "Must be ACTION_INTENT"
        assert resp2.execution_mode == "AUTO_APPLY", "Must be AUTO_APPLY execution mode"
        assert resp2.action["type"] == "RECEIVE_ASSET"
        assert resp2.action["symbol"] == "HALF"
        assert resp2.action["quantity"] == 1.0
        assert resp2.action["unit_price"] == 1348.55
        assert resp2.action["affects_cash"] is False
        assert resp2.action["cash_outflow"] == 0.0
        assert resp2.action["transaction_date"] == str(date.today())

        # ---------------------------------------------------------------------
        # Database Invariant Verification
        # ---------------------------------------------------------------------
        print(f"\n[6] Verifying Strict Read-Only Database Invariants:")
        tx_count_res = await db.execute(select(Transaction).where(Transaction.asset_id == asset.id))
        tx_count = len(tx_count_res.scalars().all())
        print(f"    Transactions in DB for asset: {tx_count} (Expected: exactly 1)")
        assert tx_count == 1, "No transaction records must be inserted in Phase 1.1!"

        asset_check = await db.get(Asset, asset.id)
        assert asset_check.current_price == Decimal("1348.55")
        print(f"    Asset price unchanged: {asset_check.current_price} USD")

        conv_check = await CopilotService.get_conversation(db, user.id, conv.id)
        print(f"    Conversation messages persisted: {len(conv_check.messages)} (Expected: exactly 4)")
        assert len(conv_check.messages) == 4

        print("\n" + "=" * 70)
        print(">>> ALL PHASE 1.1 VERIFICATION CHECKS PASSED PERFECTLY! <<<")
        print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_verification())
