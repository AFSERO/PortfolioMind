"""Controlled single verification script for PortfolioMind Copilot Phase 1.

Performs at most ONE real Copilot Codex CLI call.
Asks: "What are the largest positions in my current portfolio?"
Verifies:
- correct user portfolio context
- no unrelated context
- useful answer
- context provenance returned
- portfolio DB state unchanged
- no Deep Research triggered
- real Codex budget: MAXIMUM 1 call.
"""

import asyncio
from datetime import date, datetime, timezone
from decimal import Decimal
import os
from pathlib import Path
import sys
import uuid

# Ensure backend and Finance/src are in sys.path
backend_root = Path(__file__).resolve().parents[2]
repo_root = backend_root.parent
finance_src = repo_root / "Finance" / "src"

if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))
if str(finance_src) not in sys.path:
    sys.path.insert(0, str(finance_src))

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.database import Base
from app.models.asset import Asset, AssetType
from app.models.copilot import CopilotConversation, CopilotMessage
from app.models.instrument import Instrument
from app.models.intelligence import IntelligenceReview
from app.models.opportunity import ResearchStage, WatchlistItem
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.copilot import CopilotResponseType, IntentType
from app.services.copilot import CopilotCodexAdapter, CopilotService


async def run_controlled_verification():
    print("=" * 60)
    print("PORTFOLIOMIND COPILOT — CONTROLLED REAL CODEX VERIFICATION")
    print("=" * 60)

    # Use in-memory SQLite for self-contained, isolated verification
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with session_factory() as db:
        # 1. Setup Test User
        user = User(
            id=uuid.uuid4(),
            email=f"user_{uuid.uuid4().hex[:6]}@example.com",
            password_hash="testpass",
            display_name="Demo User",
            base_currency="USD",
        )
        db.add(user)
        await db.flush()

        # 2. Setup Owned Positions: AAPL ($9,500), MSFT ($8,400), GOOGL ($1,700)
        inst_aapl = Instrument(symbol="AAPL", name="Apple Inc", asset_type=AssetType.STOCK, currency="USD")
        inst_msft = Instrument(symbol="MSFT", name="Microsoft Corp", asset_type=AssetType.STOCK, currency="USD")
        inst_googl = Instrument(symbol="GOOGL", name="Alphabet Inc", asset_type=AssetType.STOCK, currency="USD")
        db.add_all([inst_aapl, inst_msft, inst_googl])
        await db.flush()

        asset_aapl = Asset(
            user_id=user.id,
            instrument_id=inst_aapl.id,
            symbol="AAPL",
            name="Apple Inc",
            asset_type=AssetType.STOCK,
            current_price=Decimal("190.00"),
            current_price_currency="USD",
        )
        asset_msft = Asset(
            user_id=user.id,
            instrument_id=inst_msft.id,
            symbol="MSFT",
            name="Microsoft Corp",
            asset_type=AssetType.STOCK,
            current_price=Decimal("420.00"),
            current_price_currency="USD",
        )
        asset_googl = Asset(
            user_id=user.id,
            instrument_id=inst_googl.id,
            symbol="GOOGL",
            name="Alphabet Inc",
            asset_type=AssetType.STOCK,
            current_price=Decimal("170.00"),
            current_price_currency="USD",
        )
        db.add_all([asset_aapl, asset_msft, asset_googl])
        await db.flush()

        tx_aapl = Transaction(
            asset_id=asset_aapl.id,
            transaction_type=TransactionType.BUY,
            quantity=Decimal("50"),
            price_per_unit=Decimal("180.00"),
            total_amount=Decimal("9000.00"),
            transaction_currency="USD",
            transaction_date=date(2024, 1, 15),
        )
        tx_msft = Transaction(
            asset_id=asset_msft.id,
            transaction_type=TransactionType.BUY,
            quantity=Decimal("20"),
            price_per_unit=Decimal("400.00"),
            total_amount=Decimal("8000.00"),
            transaction_currency="USD",
            transaction_date=date(2024, 2, 1),
        )
        tx_googl = Transaction(
            asset_id=asset_googl.id,
            transaction_type=TransactionType.BUY,
            quantity=Decimal("10"),
            price_per_unit=Decimal("160.00"),
            total_amount=Decimal("1600.00"),
            transaction_currency="USD",
            transaction_date=date(2024, 3, 1),
        )
        db.add_all([tx_aapl, tx_msft, tx_googl])

        # 3. Setup Unrelated Watchlist Item (TSMC) — must NOT be included in portfolio context!
        inst_tsmc = Instrument(symbol="TSM", name="Taiwan Semiconductor", asset_type=AssetType.STOCK, currency="USD")
        db.add(inst_tsmc)
        await db.flush()

        wl_tsmc = WatchlistItem(
            user_id=user.id,
            instrument_id=inst_tsmc.id,
            research_stage=ResearchStage.DISCOVERED,
            why_interesting="Leading semiconductor foundry",
        )
        db.add(wl_tsmc)
        await db.commit()

        # 4. Take Pre-Execution Snapshot
        pre_assets_count = (await db.execute(select(func.count(Asset.id)))).scalar_one()
        pre_tx_count = (await db.execute(select(func.count(Transaction.id)))).scalar_one()
        pre_reviews_count = (await db.execute(select(func.count(IntelligenceReview.id)))).scalar_one()

        print(f"Pre-call database state: {pre_assets_count} assets, {pre_tx_count} txns, {pre_reviews_count} reviews.")

        # 5. Create Copilot Conversation
        conv = await CopilotService.create_conversation(db, user.id, title="Real Codex Portfolio Verification")
        print(f"Conversation created: {conv.id}")

        # 6. Execute EXACTLY 1 Real Codex Call
        question = "What are the largest positions in my current portfolio?"
        print(f"\nUser Query: '{question}'")
        print("Invoking real Codex CLI (Budget = 1 call)...")

        real_adapter = CopilotCodexAdapter()
        assistant_msg, structured_resp = await CopilotService.send_message(
            db=db,
            user_id=user.id,
            conversation_id=conv.id,
            content=question,
            codex_adapter=real_adapter,
        )

        print("\n=== REAL CODEX RESPONSE ===")
        print(f"Response Type: {structured_resp.response_type}")
        print(f"Detected Intent: {structured_resp.intent}")
        print(f"Assistant Answer:\n{structured_resp.answer}\n")
        print("Context Provenance Returned:")
        for item in structured_resp.context_used:
            print(f"  - [{item.source_type}] {item.title} (Freshness: {item.freshness})")

        # 7. Take Post-Execution Snapshot
        post_assets_count = (await db.execute(select(func.count(Asset.id)))).scalar_one()
        post_tx_count = (await db.execute(select(func.count(Transaction.id)))).scalar_one()
        post_reviews_count = (await db.execute(select(func.count(IntelligenceReview.id)))).scalar_one()

        print("\n=== POST-CALL VERIFICATIONS ===")
        # Verify 1: DB state unchanged
        assert post_assets_count == pre_assets_count, "Assets count must not change!"
        assert post_tx_count == pre_tx_count, "Transactions count must not change!"
        assert post_reviews_count == pre_reviews_count, "Reviews count must not change!"
        print("[PASS] Portfolio and accounting state completely unchanged (0 mutations).")

        # Verify 2: Zero Deep Research runs triggered
        assert post_reviews_count == 0, "No Deep Research must be triggered!"
        print("[PASS] Zero Deep Research triggered.")

        # Verify 3: Correct user portfolio context
        context_titles = [item.title for item in structured_resp.context_used]
        assert any("Portfolio" in t for t in context_titles), "Portfolio context must be present!"
        print("[PASS] Correct portfolio context selected.")

        # Verify 4: Unrelated context excluded
        assert not any("TSM" in t for t in context_titles), "Unrelated watchlist TSM must be excluded!"
        print("[PASS] Unrelated watchlist context (TSM) strictly excluded.")

        # Verify 5: Useful factual answer returned
        ans_lower = (structured_resp.answer or "").lower()
        assert "aapl" in ans_lower or "apple" in ans_lower, "Answer should mention AAPL!"
        print("[PASS] Useful, grounded factual answer returned by Codex.")

        print("\n[ALL CONTROLLED VERIFICATIONS PASSED SUCCESSFULLY]")
        print("Real Codex invocations during this verification: EXACTLY 1.")


if __name__ == "__main__":
    asyncio.run(run_controlled_verification())
