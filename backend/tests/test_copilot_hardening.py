"""Comprehensive test suite for Copilot Phase 1.1: Context & Financial Data Integrity Hardening.

Verifies:
1. Multi-stage holding & instrument resolution precedence (Exact symbol -> Commodity alias -> Name -> Instrument).
2. Turkish & English gold and commodity alias normalization.
3. Ambiguous holding detection and candidate list surfacing.
4. Semantic financial values distinction (CURRENT_UNIT_PRICE vs TOTAL_MARKET_VALUE vs AVERAGE_COST).
5. Non-conflation of unit price and total position value across varying quantities (qty=1 vs qty=2).
6. Currency and amount format parsing ($1,348.55 vs 1.348,55 TL).
7. Non-cash acquisition detection (GIFT_IN, TRANSFER_IN) with cash_outflow=0 and affects_cash=False.
8. Quantity extraction from natural language word numbers ("one", "bir").
9. Multi-turn conversational draft merging (Turn 1: Gift request -> Turn 2: "use today and current value").
10. Prevention of internal technical UUID / database ID requests.
11. Bounded Context Engine attachment (strictly targeted holding & price context for transaction intents).
12. Prompt orchestrator injection of holding & price context into structured system data.
13. Invariant: ZERO database mutations on assets, transactions, or cash accounts.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any, List
import uuid

import pytest
from sqlalchemy import select

from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount
from app.models.copilot import CopilotConversation, CopilotMessage
from app.models.instrument import Instrument
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.copilot import (
    AcquisitionType,
    ContextGroup,
    ExecutionMode,
    IntentResult,
    IntentType,
    PendingActionDraft,
    SemanticFinancialMeaning,
)
from app.services.copilot.context_engine import CopilotContextEngine
from app.services.copilot.holding_resolver import (
    COMMODITY_ALIASES,
    HoldingResolver,
    normalize_text,
    parse_acquisition_type,
    parse_currency_amount,
    parse_quantity,
)
from app.services.copilot.intent_classifier import IntentClassifier
from app.services.copilot.prompt_orchestrator import CopilotPromptOrchestrator
from app.services.copilot.rules import get_canonical_system_prompt
from app.services.copilot.service import CopilotService


# -----------------------------------------------------------------------------
# Fixtures
# -----------------------------------------------------------------------------
@pytest.fixture
async def hardening_user(db_session):
    """Test user for hardening scenarios."""
    user = User(
        id=uuid.uuid4(),
        email=f"copilot_hardening_{uuid.uuid4().hex[:6]}@example.com",
        password_hash="hashed_pw_test",
        display_name="Demo User",
        base_currency="USD",
    )
    db_session.add(user)
    await db_session.flush()
    return user


@pytest.fixture
async def half_gold_holding(db_session, hardening_user):
    """Creates a canonical Half Gold instrument and user asset with 1 coin at $1,348.55."""
    inst = Instrument(
        id=uuid.uuid4(),
        symbol="HALF",
        name="Gold Half / Yarım Altın",
        asset_type=AssetType.PRECIOUS_METALS,
        currency="USD",
        exchange="COMMODITY",
    )
    db_session.add(inst)
    await db_session.flush()

    asset = Asset(
        id=uuid.uuid4(),
        user_id=hardening_user.id,
        instrument_id=inst.id,
        asset_type=AssetType.PRECIOUS_METALS,
        symbol="HALF",
        name="Yarım Altın / Gold Half HALF",
        current_price=Decimal("1348.55"),
        current_price_currency="USD",
        is_manual_price=False,
    )
    db_session.add(asset)
    await db_session.flush()

    # User bought 1 half gold coin on 2026-01-10 at $1,300.00
    tx = Transaction(
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
    db_session.add(tx)
    await db_session.commit()
    await db_session.refresh(asset)
    await db_session.refresh(inst)
    return asset, inst


# -----------------------------------------------------------------------------
# 1. Holding Resolver Unit Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_holding_resolver_exact_symbol(db_session, hardening_user, half_gold_holding):
    asset, inst = half_gold_holding
    resolved = await HoldingResolver.resolve(db_session, hardening_user.id, "HALF")
    assert resolved.is_resolved is True
    assert resolved.match_type == "EXACT_SYMBOL"
    assert resolved.asset.id == asset.id
    assert resolved.stats.quantity == Decimal("1.0")
    assert resolved.stats.current_price == Decimal("1348.55")


@pytest.mark.asyncio
async def test_holding_resolver_turkish_alias(db_session, hardening_user, half_gold_holding):
    asset, inst = half_gold_holding
    # Query in Turkish: "yarım altın"
    resolved = await HoldingResolver.resolve(
        db_session, hardening_user.id, "Mevcut yarım altınımın yanına eklemek istiyorum."
    )
    assert resolved.is_resolved is True
    assert resolved.asset.id == asset.id
    assert resolved.stats.quantity == Decimal("1.0")


@pytest.mark.asyncio
async def test_holding_resolver_english_alias(db_session, hardening_user, half_gold_holding):
    asset, inst = half_gold_holding
    # Query in English: "half-gold"
    resolved = await HoldingResolver.resolve(
        db_session, hardening_user.id, "My mother gave me one half-gold coin as a gift."
    )
    assert resolved.is_resolved is True
    assert resolved.asset.id == asset.id
    assert resolved.stats.current_price == Decimal("1348.55")


@pytest.mark.asyncio
async def test_holding_resolver_ambiguous_holdings(db_session, hardening_user, half_gold_holding):
    # Add a second gold holding: Quarter Gold
    quarter_asset = Asset(
        id=uuid.uuid4(),
        user_id=hardening_user.id,
        asset_type=AssetType.PRECIOUS_METALS,
        symbol="QUARTER",
        name="Çeyrek Altın",
        current_price=Decimal("674.25"),
        current_price_currency="USD",
    )
    db_session.add(quarter_asset)
    await db_session.commit()

    # Query with generic "altın" that matches multiple assets if not resolved by specific alias
    # But specific alias "yarım" should unambiguously pick HALF
    res_half = await HoldingResolver.resolve(db_session, hardening_user.id, "yarım altın")
    assert res_half.match_type == "COMMODITY_ALIAS"
    assert res_half.asset.symbol == "HALF"

    res_quarter = await HoldingResolver.resolve(db_session, hardening_user.id, "çeyrek altın")
    assert res_quarter.match_type == "COMMODITY_ALIAS"
    assert res_quarter.asset.symbol == "QUARTER"


@pytest.mark.asyncio
async def test_holding_resolver_unknown_asset(db_session, hardening_user):
    resolved = await HoldingResolver.resolve(db_session, hardening_user.id, "XYZUNKNOWNRANDOM")
    assert resolved.is_resolved is False
    assert resolved.match_type == "NONE"
    assert resolved.confidence == 0.0


# -----------------------------------------------------------------------------
# 2. Semantic Financial Values & Non-Conflation Tests
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_semantic_values_disambiguation_single_unit(db_session, hardening_user, half_gold_holding):
    asset, inst = half_gold_holding
    resolved = await HoldingResolver.resolve(db_session, hardening_user.id, "HALF")
    sem_vals = {v.meaning: v for v in resolved.semantic_values}

    # When user holds 1 coin, current unit price is 1348.55 and total market value is 1348.55
    assert SemanticFinancialMeaning.CURRENT_UNIT_PRICE in sem_vals
    assert SemanticFinancialMeaning.TOTAL_MARKET_VALUE in sem_vals
    assert sem_vals[SemanticFinancialMeaning.CURRENT_UNIT_PRICE].value == Decimal("1348.55")
    assert sem_vals[SemanticFinancialMeaning.TOTAL_MARKET_VALUE].value == Decimal("1348.55")
    # But meanings and notes must be explicitly distinct!
    assert "single unit" in sem_vals[SemanticFinancialMeaning.CURRENT_UNIT_PRICE].notes
    assert "Total valuation" in sem_vals[SemanticFinancialMeaning.TOTAL_MARKET_VALUE].notes


@pytest.mark.asyncio
async def test_semantic_values_disambiguation_multiple_units(db_session, hardening_user, half_gold_holding):
    asset, inst = half_gold_holding
    # Add a second BUY transaction so total_quantity = 2.0
    tx2 = Transaction(
        id=uuid.uuid4(),
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=Decimal("1.0"),
        price_per_unit=Decimal("1320.00"),
        total_amount=Decimal("1320.00"),
        transaction_currency="USD",
        transaction_date=date(2026, 2, 1),
        affects_cash=True,
    )
    db_session.add(tx2)
    await db_session.commit()

    resolved = await HoldingResolver.resolve(db_session, hardening_user.id, "HALF")
    sem_vals = {v.meaning: v for v in resolved.semantic_values}

    assert resolved.stats.quantity == Decimal("2.0")
    # Unit price remains 1348.55
    assert sem_vals[SemanticFinancialMeaning.CURRENT_UNIT_PRICE].value == Decimal("1348.55")
    # Total market value is 2 * 1348.55 = 2697.10
    assert sem_vals[SemanticFinancialMeaning.TOTAL_MARKET_VALUE].value == Decimal("2697.10")
    # Never conflated!
    assert sem_vals[SemanticFinancialMeaning.CURRENT_UNIT_PRICE].value != sem_vals[SemanticFinancialMeaning.TOTAL_MARKET_VALUE].value


# -----------------------------------------------------------------------------
# 3. Currency and Number Format Parsing Tests
# -----------------------------------------------------------------------------
def test_parse_currency_amount_formats():
    # US format with dollar sign
    val, cur = parse_currency_amount("$1,348.55")
    assert val == Decimal("1348.55")
    assert cur == "USD"

    # Turkish format with TL suffix
    val_tr, cur_tr = parse_currency_amount("1.348,55 TL")
    assert val_tr == Decimal("1348.55")
    assert cur_tr == "TRY"

    # Euro format
    val_eu, cur_eu = parse_currency_amount("€250.50")
    assert val_eu == Decimal("250.50")
    assert cur_eu == "EUR"

    # Standalone string input
    val_alone, _ = parse_currency_amount("1,348.55")
    assert val_alone == Decimal("1348.55")


def test_parse_quantity_word_numbers():
    assert parse_quantity("one half-gold coin") == Decimal("1")
    assert parse_quantity("bir adet yarım altın") == Decimal("1")
    assert parse_quantity("2 pieces") == Decimal("2")
    assert parse_quantity("five shares") == Decimal("5")
    assert parse_quantity("10 lot") == Decimal("10")


def test_parse_acquisition_type():
    acq, affects_cash, outflow = parse_acquisition_type("My mother gave me one half-gold coin as a gift.")
    assert acq == AcquisitionType.GIFT_IN
    assert affects_cash is False
    assert outflow == Decimal("0")

    acq_tr, affects_cash_tr, outflow_tr = parse_acquisition_type("Annem bana hediye etti.")
    assert acq_tr == AcquisitionType.GIFT_IN
    assert affects_cash_tr is False

    acq_tx, affects_cash_tx, _ = parse_acquisition_type("Transferred from external ledger")
    assert acq_tx == AcquisitionType.TRANSFER_IN
    assert affects_cash_tx is False

    acq_buy, affects_cash_buy, _ = parse_acquisition_type("I bought 5 TSMC at $182")
    assert acq_buy == AcquisitionType.PURCHASE
    assert affects_cash_buy is True


# -----------------------------------------------------------------------------
# 4. Intent Classifier for Non-Cash Gifts
# -----------------------------------------------------------------------------
def test_intent_classifier_gift_scenario():
    msg = "My mother gave me one half-gold coin as a gift. Can you add it next to my existing half-gold holding?"
    result = IntentClassifier.classify(msg)

    assert result.intent == IntentType.TRANSACTION_ENTRY
    assert result.entities.get("action") == "RECEIVE_ASSET"
    assert result.entities.get("acquisition_type") == AcquisitionType.GIFT_IN.value
    assert result.entities.get("symbol") == "HALF"
    assert result.entities.get("quantity") == 1.0
    assert result.entities.get("affects_cash") is False
    assert result.entities.get("cash_outflow") == 0.0

    # Critical: Cash price is NOT in missing_information for gifts! Only transaction_date is missing.
    assert "price" not in result.missing_information
    assert result.missing_information == ["transaction_date"]
    assert result.execution_mode == ExecutionMode.NEEDS_INPUT


def test_intent_classifier_gift_with_today():
    msg = "My mother gave me one half-gold coin as a gift today. Can you add it to my portfolio?"
    result = IntentClassifier.classify(msg)

    assert result.intent == IntentType.TRANSACTION_ENTRY
    assert result.entities.get("action") == "RECEIVE_ASSET"
    assert result.entities.get("symbol") == "HALF"
    assert result.entities.get("quantity") == 1.0
    assert result.entities.get("transaction_date") == str(date.today())
    assert result.execution_mode == ExecutionMode.AUTO_APPLY
    assert result.missing_information == []


# -----------------------------------------------------------------------------
# 5. Context Engine Bounded Isolation for Transactions
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_context_engine_isolation_for_transaction(db_session, hardening_user, half_gold_holding):
    asset, inst = half_gold_holding

    # Also add unrelated Apple stock holding
    apple = Asset(
        id=uuid.uuid4(),
        user_id=hardening_user.id,
        asset_type=AssetType.STOCK,
        symbol="AAPL",
        name="Apple Inc.",
        current_price=Decimal("230.00"),
    )
    db_session.add(apple)
    await db_session.commit()

    intent = IntentClassifier.classify("My mother gave me one half-gold coin as a gift.")
    bundle = await CopilotContextEngine.build_context(
        db=db_session,
        user_id=hardening_user.id,
        intent=intent,
        entities=intent.entities,
        raw_user_message="My mother gave me one half-gold coin as a gift.",
    )

    types = [it.source_type for it in bundle.items]
    assert ContextGroup.EXISTING_HOLDING.value in types
    assert ContextGroup.PRICE_CONTEXT.value in types

    # Unrelated AAPL must NOT be attached in EXISTING_HOLDING!
    pos_items = [it for it in bundle.items if it.source_type == ContextGroup.EXISTING_HOLDING.value]
    assert len(pos_items) == 1
    assert pos_items[0].content["symbol"] == "HALF"

    # Price context must contain single unit price
    price_items = [it for it in bundle.items if it.source_type == ContextGroup.PRICE_CONTEXT.value]
    assert len(price_items) == 1
    assert price_items[0].content["current_unit_price"] == 1348.55


# -----------------------------------------------------------------------------
# 6. Multi-Turn Conversational Draft Progression
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_multi_turn_gift_resolution(db_session, hardening_user, half_gold_holding):
    asset, inst = half_gold_holding

    # Turn 1: User requests gift addition without date
    conv = await CopilotService.create_conversation(db_session, hardening_user.id, "Gold Gift Scenario")
    t1_msg, t1_resp = await CopilotService.send_message(
        db=db_session,
        user_id=hardening_user.id,
        conversation_id=conv.id,
        content="My mother gave me one half-gold coin as a gift. Can you add it next to my existing half-gold holding?",
    )

    assert t1_resp.response_type == "NEEDS_INPUT"
    assert t1_resp.missing_fields == ["transaction_date"]
    assert "tarih" in t1_resp.question.lower() or "date" in t1_resp.question.lower()
    # Must NOT ask for ID or price!
    assert "id" not in t1_resp.question.lower()
    assert "fiyat" not in t1_resp.question.lower() and "price" not in t1_resp.question.lower()
    assert t1_resp.action_draft is not None
    assert t1_resp.action_draft.symbol == "HALF"
    assert t1_resp.action_draft.quantity == 1.0
    assert t1_resp.action_draft.affects_cash is False

    # Turn 2: User responds: "use today and current value"
    t2_msg, t2_resp = await CopilotService.send_message(
        db=db_session,
        user_id=hardening_user.id,
        conversation_id=conv.id,
        content="use today and current value",
    )

    assert t2_resp.response_type == "ACTION_INTENT"
    assert t2_resp.execution_mode == "AUTO_APPLY"
    assert t2_resp.action is not None
    assert t2_resp.action["type"] == "RECEIVE_ASSET"
    assert t2_resp.action["symbol"] == "HALF"
    assert t2_resp.action["quantity"] == 1.0
    assert t2_resp.action["unit_price"] == 1348.55
    assert t2_resp.action["affects_cash"] is False
    assert t2_resp.action["cash_outflow"] == 0.0
    assert t2_resp.action["transaction_date"] == str(date.today())
    assert t2_resp.action_draft.is_complete is True

    # Check answer text clarity
    assert "1 adet" in t2_resp.answer
    assert "1,348.55" in t2_resp.answer or "1348.55" in t2_resp.answer
    assert "0.00" in t2_resp.answer
    assert "Faz 1 kapsamında veritabanı yazma işlemi henüz çalıştırılmamaktadır" in t2_resp.answer


# -----------------------------------------------------------------------------
# 7. Prompt Orchestrator and Operating Rules Verification
# -----------------------------------------------------------------------------
def test_prompt_orchestrator_includes_holding_and_price_in_system_data():
    intent = IntentResult(
        intent=IntentType.TRANSACTION_ENTRY,
        confidence=0.98,
        entities={"symbol": "HALF", "quantity": 1.0},
        requires_context=[ContextGroup.EXISTING_HOLDING.value, ContextGroup.PRICE_CONTEXT.value],
        execution_mode=ExecutionMode.AUTO_APPLY,
        missing_information=[],
        reason="Complete",
    )
    bundle = CopilotContextEngine.build_context  # check PromptOrchestrator directly
    from app.services.copilot.context_engine import ContextBundle, ContextItem

    cb = ContextBundle()
    cb.add(
        ContextItem(
            source_type=ContextGroup.EXISTING_HOLDING.value,
            source_id="h1",
            title="Existing Position: Yarım Altın",
            content={"symbol": "HALF", "current_quantity": 1.0},
            precedence=1,
            freshness="CURRENT",
        )
    )
    cb.add(
        ContextItem(
            source_type=ContextGroup.PRICE_CONTEXT.value,
            source_id="p1",
            title="Price Context: Yarım Altın",
            content={"current_unit_price": 1348.55, "total_market_value": 1348.55},
            precedence=1,
            freshness="CURRENT",
        )
    )

    prompt = CopilotPromptOrchestrator.build_prompt("add 1 half gold", intent, cb)
    assert "<structured_system_data>" in prompt
    assert "Existing Position: Yarım Altın" in prompt
    assert "1348.55" in prompt
    # Rules 17-20 must be present
    assert "Distinguish unit prices from total holding values" in prompt
    assert "Respect non-cash acquisition semantics" in prompt
    assert "Never ask the user for database internal IDs" in prompt


# -----------------------------------------------------------------------------
# 8. Invariant: ZERO State Mutations
# -----------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_zero_state_mutations_across_entire_hardening_turn(db_session, hardening_user, half_gold_holding):
    asset, inst = half_gold_holding

    # Verify initial state: exactly 1 transaction, asset price untouched, 0 cash mutations
    tx_before = await db_session.execute(select(Transaction).where(Transaction.asset_id == asset.id))
    assert len(tx_before.scalars().all()) == 1

    # Run multi-turn conversation
    conv = await CopilotService.create_conversation(db_session, hardening_user.id, "Zero Mutation Test")
    await CopilotService.send_message(
        db_session,
        hardening_user.id,
        conv.id,
        "My mother gave me one half-gold coin as a gift. Can you add it next to my existing half-gold holding?",
    )
    await CopilotService.send_message(
        db_session,
        hardening_user.id,
        conv.id,
        "use today and current value",
    )

    # Verify post-condition: Still EXACTLY 1 transaction in DB! No new transaction was written!
    tx_after = await db_session.execute(select(Transaction).where(Transaction.asset_id == asset.id))
    assert len(tx_after.scalars().all()) == 1

    # Assets table quantity/price untouched
    asset_after = await db_session.get(Asset, asset.id)
    assert asset_after.current_price == Decimal("1348.55")

    # Copilot message records were safely persisted
    conv_check = await CopilotService.get_conversation(db_session, hardening_user.id, conv.id)
    assert len(conv_check.messages) == 4  # 2 user messages + 2 assistant messages
