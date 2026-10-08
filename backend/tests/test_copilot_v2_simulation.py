"""Comprehensive Verification Suite for Portfolio Simulation Engine (Phase 3.2).

Verification Matrix:
1. Tool Classification: `simulate_transaction` is strictly `ToolClassification.READ_ONLY`.
2. SELL exact quantity: computes before/after positions, proceeds, cash balance, and preserves total net worth.
3. SELL fractions: parses "yarısı", "50%", "çeyreği", "%25", "tamamı", "100%", "1/2", "1/4", 0.5, 0.25.
4. SELL full exit: holding goes to 0, weight goes to 0%, entire position converted to cash.
5. SELL insufficient holding: flagged with validation error, zero mutation.
6. BUY exact quantity: verifies affordability, outlay, position growth, and total net worth preservation.
7. BUY target amount (lump-sum): computes required shares, cash reduction.
8. BUY insufficient cash: simulation succeeds but explicitly flags `is_affordable=False` and `cash_shortfall`.
9. Explicit scenario price: respects user scenario price over reference market price.
10. Fee deduction: verifies `after_total == before_total - fee_base`.
11. Unowned asset: can simulate BUY for an asset not currently in the portfolio.
12. Virtual cash bucket: operates cleanly when user does not have a cash account in asset currency.
13. Strict ZERO mutation invariant: running simulations produces zero database records.
14. Registry execution: tool handler is safely callable through default_tool_registry.execute().
15. Deterministic allocation weights: before and after allocation snapshots sum to 100%.
"""

from decimal import Decimal
from typing import Any, Dict
import uuid

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.asset import Asset, AssetType
from app.models.cash import CashAccount, CashMovement
from app.models.copilot import CopilotActionProposal
from app.models.decision_log import DecisionLogEntry
from app.models.instrument import Instrument
from app.models.transaction import Transaction, TransactionType
from app.models.user import User
from app.schemas.portfolio_simulation import PriceSource, SimulationResult, SimulationType
from app.services.copilot_v2.tools import default_tool_registry
from app.services.copilot_v2.tools.registry import ToolClassification
from app.services.copilot_v2.tools.simulation import simulate_transaction_handler
from app.services.portfolio_simulation import PortfolioSimulationService, parse_fraction


# ---------------------------------------------------------------------------
# Test Helpers & Fixtures
# ---------------------------------------------------------------------------


async def _create_test_user(db: AsyncSession, prefix: str = "sim_user") -> User:
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
    db: AsyncSession,
    symbol: str,
    name: str,
    asset_type: AssetType = AssetType.FUND,
    currency: str = "TRY",
) -> Instrument:
    inst = Instrument(
        symbol=symbol.upper(),
        name=name,
        asset_type=asset_type,
        currency=currency,
    )
    db.add(inst)
    await db.commit()
    await db.refresh(inst)
    return inst


from datetime import date, datetime

async def _create_test_asset_with_transactions(
    db: AsyncSession,
    user: User,
    instrument: Instrument,
    quantity: Decimal,
    price: Decimal,
) -> Asset:
    asset = Asset(
        user_id=user.id,
        instrument_id=instrument.id,
        asset_type=instrument.asset_type,
        symbol=instrument.symbol,
        name=instrument.name,
        current_price=price,
        current_price_currency=instrument.currency,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)

    tx = Transaction(
        asset_id=asset.id,
        transaction_type=TransactionType.BUY,
        quantity=quantity,
        price_per_unit=price,
        total_amount=quantity * price,
        transaction_currency=instrument.currency,
        transaction_date=date.today(),
        affects_cash=False,
    )
    db.add(tx)
    await db.commit()
    await db.refresh(asset)
    return asset



async def _create_test_cash_account(
    db: AsyncSession,
    user: User,
    currency: str = "TRY",
    balance: Decimal = Decimal("50000"),
) -> CashAccount:
    account = CashAccount(
        user_id=user.id,
        currency=currency,
        balance=balance,
    )
    db.add(account)
    await db.commit()
    await db.refresh(account)
    return account



# ---------------------------------------------------------------------------
# 1. Tool Classification & Registry Invariants
# ---------------------------------------------------------------------------


def test_simulation_tool_classification_is_strictly_read_only():
    """simulate_transaction MUST be registered as ToolClassification.READ_ONLY."""
    tool_def = default_tool_registry.get("simulate_transaction")
    assert tool_def is not None
    assert tool_def.classification == ToolClassification.READ_ONLY
    assert "hypothetical" in tool_def.description.lower() or "simulate" in tool_def.description.lower()
    assert "proposal" in tool_def.description.lower()


# ---------------------------------------------------------------------------
# 2. Fraction Parsing Robustness
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "raw_input,expected",
    [
        (0.5, Decimal("0.5")),
        (50, Decimal("0.5")),
        ("50%", Decimal("0.5")),
        ("%50", Decimal("0.5")),
        ("yarisi", Decimal("0.5")),
        ("yarısını", Decimal("0.5")),
        ("half", Decimal("0.5")),
        ("1/2", Decimal("0.5")),
        (0.25, Decimal("0.25")),
        (25, Decimal("0.25")),
        ("25%", Decimal("0.25")),
        ("%25", Decimal("0.25")),
        ("ceyrek", Decimal("0.25")),
        ("çeyreği", Decimal("0.25")),
        ("1/4", Decimal("0.25")),
        ("tamamı", Decimal("1.0")),
        ("all", Decimal("1.0")),
        ("100%", Decimal("1.0")),
        (1.0, Decimal("1.0")),
        ("1/3", Decimal("0.333333")),
    ],
)
def test_parse_fraction_variations(raw_input: Any, expected: Decimal):
    """parse_fraction correctly normalizes all standard Turkish and numeric expressions."""
    result = parse_fraction(raw_input)
    assert result is not None
    assert abs(result - expected) < Decimal("0.0001")


# ---------------------------------------------------------------------------
# 3. SELL Exact Quantity Simulation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_sell_exact_quantity(db_session: AsyncSession):
    """Simulating SELL of exact units produces accurate before/after snapshots and preserves net worth."""
    user = await _create_test_user(db_session, "sell_qty_user")
    inst = await _create_test_instrument(db_session, "THF", "Tacirler Portföy Fonu", AssetType.FUND)
    # Asset: 1000 units @ 10 TRY = 10,000 TRY
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("1000"), price=Decimal("10.0"))
    # Cash: 20,000 TRY. Total portfolio = 30,000 TRY
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("20000"))

    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="THF",
        transaction_type=SimulationType.SELL,
        quantity=Decimal("400"),
    )

    assert result.status == "success"
    assert result.simulation_type == SimulationType.SELL
    assert result.validation.is_valid is True

    # Before snapshot
    assert result.before.target_position.quantity == 1000.0
    assert result.before.target_position.position_value == 10000.0
    assert result.before.cash.balance == 20000.0
    assert result.before.total_value_base == 30000.0
    # THF weight was 10000 / 30000 = 33.3333%
    assert round(result.before.target_position.weight_pct, 2) == 33.33

    # Transaction spec: 400 * 10 = 4,000 TRY
    assert result.transaction.quantity == 400.0
    assert result.transaction.gross_value == 4000.0
    assert result.transaction.net_cash_delta == 4000.0

    # After snapshot
    assert result.after.target_position.quantity == 600.0
    assert result.after.target_position.position_value == 6000.0
    assert result.after.cash.balance == 24000.0
    # Net-worth preservation invariant: 6000 + 24000 = 30000
    assert result.after.total_value_base == 30000.0
    # New THF weight: 6000 / 30000 = 20.00%
    assert round(result.after.target_position.weight_pct, 2) == 20.00
    # New cash weight: 24000 / 30000 = 80.00%
    assert round(result.after.cash.cash_weight_pct, 2) == 80.00


# ---------------------------------------------------------------------------
# 4. SELL Fraction: "yarısı" (50%)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_sell_half_fraction(db_session: AsyncSession):
    """Simulating selling 'yarısı' (50%) resolves half of the total holding."""
    user = await _create_test_user(db_session, "half_user")
    inst = await _create_test_instrument(db_session, "THYAO.IS", "Türk Hava Yolları", AssetType.STOCK)
    # 200 units @ 300 TRY = 60,000 TRY
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("200"), price=Decimal("300.0"))
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("40000"))

    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="THYAO",
        transaction_type=SimulationType.SELL,
        quantity_fraction="yarısı",
    )

    assert result.status == "success"
    assert result.transaction.quantity == 100.0
    assert result.transaction.gross_value == 30000.0
    assert result.after.target_position.quantity == 100.0
    assert result.after.cash.balance == 70000.0
    assert result.after.total_value_base == 100000.0


# ---------------------------------------------------------------------------
# 5. SELL Full Exit: "tamamı" (100%)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_sell_full_exit(db_session: AsyncSession):
    """Full exit simulation completely zeros holding and brings weight to 0.0%."""
    user = await _create_test_user(db_session, "full_user")
    inst = await _create_test_instrument(db_session, "EREGL.IS", "Ereğli", AssetType.STOCK)
    # 500 units @ 50 TRY = 25,000 TRY
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("500"), price=Decimal("50.0"))
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("25000"))

    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="EREGL",
        transaction_type=SimulationType.SELL,
        quantity_fraction="tamamı",
    )

    assert result.status == "success"
    assert result.transaction.quantity == 500.0
    assert result.after.target_position.quantity == 0.0
    assert result.after.target_position.position_value == 0.0
    assert result.after.target_position.weight_pct == 0.0
    assert result.after.cash.balance == 50000.0
    assert result.after.cash.cash_weight_pct == 100.0


# ---------------------------------------------------------------------------
# 6. SELL Insufficient Holding
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_sell_insufficient_holding(db_session: AsyncSession):
    """Attempting to sell more than held flags validation error without mutating state."""
    user = await _create_test_user(db_session, "over_seller")
    inst = await _create_test_instrument(db_session, "KCHOL.IS", "Koç Holding", AssetType.STOCK)
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("50"), price=Decimal("200.0"))

    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="KCHOL",
        transaction_type=SimulationType.SELL,
        quantity=Decimal("100"),  # Only has 50
    )

    assert result.status == "error"
    assert result.validation.is_valid is False
    assert result.validation.reason == "INSUFFICIENT_HOLDING"
    assert "fazladır" in result.validation.message.lower() or "negatif" in result.validation.message.lower()



# ---------------------------------------------------------------------------
# 7. BUY Exact Quantity with Sufficient Cash
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_buy_exact_quantity(db_session: AsyncSession):
    """Simulating BUY with existing position increases holding and accurately decrements cash."""
    user = await _create_test_user(db_session, "buy_user")
    inst = await _create_test_instrument(db_session, "SISE.IS", "Şişecam", AssetType.STOCK)
    # Existing: 100 units @ 40 TRY = 4,000 TRY
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("100"), price=Decimal("40.0"))
    # Cash: 16,000 TRY. Total = 20,000 TRY
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("16000"))

    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="SISE",
        transaction_type=SimulationType.BUY,
        quantity=Decimal("200"),  # Cost: 200 * 40 = 8,000 TRY
    )

    assert result.status == "success"
    assert result.simulation_type == SimulationType.BUY
    assert result.transaction.quantity == 200.0
    assert result.transaction.gross_value == 8000.0
    assert result.transaction.net_cash_delta == -8000.0
    assert result.transaction.is_affordable is True
    assert result.transaction.cash_shortfall == 0.0

    # After: 300 units @ 40 = 12,000 TRY. Cash = 8,000 TRY. Total = 20,000 TRY
    assert result.after.target_position.quantity == 300.0
    assert result.after.target_position.position_value == 12000.0
    assert result.after.cash.balance == 8000.0
    assert result.after.total_value_base == 20000.0
    assert round(result.after.target_position.weight_pct, 2) == 60.0
    assert round(result.after.cash.cash_weight_pct, 2) == 40.0


# ---------------------------------------------------------------------------
# 8. BUY Target Amount (Lump-Sum, e.g. "100.000 TL NVDA alsam")
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_buy_target_amount(db_session: AsyncSession):
    """Simulating BUY by total cash amount determines quantity and updates allocation."""
    user = await _create_test_user(db_session, "lump_sum_user")
    inst = await _create_test_instrument(db_session, "GARAN.IS", "Garanti Bankası", AssetType.STOCK)
    # Cash: 100,000 TRY
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("100000"))
    # Also set a reference price on an asset or scenario price
    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="GARAN",
        transaction_type=SimulationType.BUY,
        amount=Decimal("50000"),
        price=Decimal("100.0"),  # Scenario price: 100 TRY/share -> 500 shares
    )

    assert result.status == "success"
    assert result.transaction.quantity == 500.0
    assert result.transaction.gross_value == 50000.0
    assert result.after.cash.balance == 50000.0
    assert result.after.target_position.quantity == 500.0
    assert result.after.target_position.position_value == 50000.0
    assert result.after.total_value_base == 100000.0


# ---------------------------------------------------------------------------
# 9. BUY Insufficient Cash (Affordability Flagged)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulate_buy_insufficient_cash(db_session: AsyncSession):
    """BUY scenario exceeding available cash succeeds hypothetically but flags cash shortfall."""
    user = await _create_test_user(db_session, "low_cash_user")
    inst = await _create_test_instrument(db_session, "BIMAS.IS", "BIM", AssetType.STOCK)
    # Cash: 10,000 TRY
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("10000"))

    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="BIMAS",
        transaction_type=SimulationType.BUY,
        quantity=Decimal("100"),
        price=Decimal("500.0"),  # Total: 50,000 TRY, but cash is only 10,000 TRY
    )

    assert result.status == "warning"
    assert result.transaction.is_affordable is False
    assert result.transaction.cash_shortfall == 40000.0
    assert len(result.warnings) > 0
    assert "açık" in result.warnings[0].lower() or "uyarısı" in result.warnings[0].lower()



# ---------------------------------------------------------------------------
# 10. Explicit Scenario Price Hierarchy
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_explicit_scenario_price_hierarchy(db_session: AsyncSession):
    """Explicit scenario price overrides current reference market price."""
    user = await _create_test_user(db_session, "price_user")
    inst = await _create_test_instrument(db_session, "ASELS.IS", "Aselsan", AssetType.STOCK)
    # Current market price = 60 TRY
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("1000"), price=Decimal("60.0"))
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("40000"))

    # User says "ASELS 90 TL olursa yarısını satsam"
    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="ASELS",
        transaction_type=SimulationType.SELL,
        quantity_fraction="yarısı",
        price=Decimal("90.0"),
    )

    assert result.status == "success"
    assert result.assumptions.price == 90.0
    assert result.assumptions.price_source == PriceSource.EXPLICIT_SCENARIO_PRICE
    # Sold 500 units @ 90 = 45,000 TRY proceeds
    assert result.transaction.gross_value == 45000.0
    assert result.after.cash.balance == 85000.0


# ---------------------------------------------------------------------------
# 11. Transaction Fee Deduction Invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_fee_deduction_invariant(db_session: AsyncSession):
    """Simulated transaction fee reduces cash proceeds and total portfolio net worth by exactly the fee."""
    user = await _create_test_user(db_session, "fee_user")
    inst = await _create_test_instrument(db_session, "AKBNK.IS", "Akbank", AssetType.STOCK)
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("1000"), price=Decimal("50.0"))
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("50000"))

    fee_val = Decimal("150.0")
    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="AKBNK",
        transaction_type=SimulationType.SELL,
        quantity=Decimal("500"),
        fee=fee_val,
    )

    assert result.status == "success"
    assert result.transaction.fee == 150.0
    # Gross proceeds: 500 * 50 = 25,000 TRY. Net cash delta: 25,000 - 150 = 24,850 TRY
    assert result.transaction.net_cash_delta == 24850.0
    assert result.after.cash.balance == 74850.0
    # Invariant: after_total == before_total - fee
    assert result.after.total_value_base == result.before.total_value_base - 150.0


# ---------------------------------------------------------------------------
# 12. Virtual Cash Bucket for Missing Currency Account
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
@pytest.mark.usefixtures("forex_provider")
async def test_virtual_cash_bucket_handling(db_session: AsyncSession):
    """Simulation succeeds with virtual cash bucket when user has no cash account in asset currency."""
    user = await _create_test_user(db_session, "virtual_cash_user")
    inst = await _create_test_instrument(db_session, "AAPL", "Apple Inc.", AssetType.STOCK, currency="USD")
    # Only have TRY cash account, no USD cash account
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("100000"))

    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="AAPL",
        transaction_type=SimulationType.BUY,
        quantity=Decimal("10"),
        price=Decimal("200.0"),  # 10 * 200 = 2,000 USD
    )

    assert result.status == "warning"
    # Virtual cash account was constructed in-memory
    assert result.before.cash.cash_account_exists is False
    assert result.transaction.currency == "USD"
    # Zero USD balance means shortfall of 2,000 USD
    assert result.transaction.is_affordable is False
    assert result.transaction.cash_shortfall == 2000.0


# ---------------------------------------------------------------------------
# 13. Absolute Zero Mutation Invariant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_simulation_causes_strictly_zero_db_mutations(db_session: AsyncSession):
    """Running multiple simulations MUST NOT write any rows to the database."""
    user = await _create_test_user(db_session, "zero_mutation_user")
    inst = await _create_test_instrument(db_session, "YKBNK.IS", "Yapı Kredi", AssetType.STOCK)
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("500"), price=Decimal("30.0"))
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("20000"))

    # Record row counts before
    tx_count_before = len((await db_session.execute(select(Transaction))).scalars().all())
    asset_count_before = len((await db_session.execute(select(Asset))).scalars().all())
    cash_count_before = len((await db_session.execute(select(CashAccount))).scalars().all())
    mov_count_before = len((await db_session.execute(select(CashMovement))).scalars().all())
    prop_count_before = len((await db_session.execute(select(CopilotActionProposal))).scalars().all())
    log_count_before = len((await db_session.execute(select(DecisionLogEntry))).scalars().all())

    # Execute multiple simulation turns
    await PortfolioSimulationService.simulate_transaction(
        db=db_session, user_id=user.id, instrument_query="YKBNK", transaction_type=SimulationType.SELL, quantity_fraction="yarısı"
    )
    await PortfolioSimulationService.simulate_transaction(
        db=db_session, user_id=user.id, instrument_query="YKBNK", transaction_type=SimulationType.SELL, quantity_fraction="tamamı"
    )
    await PortfolioSimulationService.simulate_transaction(
        db=db_session, user_id=user.id, instrument_query="YKBNK", transaction_type=SimulationType.BUY, quantity=Decimal("100")
    )
    await PortfolioSimulationService.simulate_transaction(
        db=db_session, user_id=user.id, instrument_query="YKBNK", transaction_type=SimulationType.SELL, quantity=Decimal("99999")  # Error case
    )

    # Record row counts after
    tx_count_after = len((await db_session.execute(select(Transaction))).scalars().all())
    asset_count_after = len((await db_session.execute(select(Asset))).scalars().all())
    cash_count_after = len((await db_session.execute(select(CashAccount))).scalars().all())
    mov_count_after = len((await db_session.execute(select(CashMovement))).scalars().all())
    prop_count_after = len((await db_session.execute(select(CopilotActionProposal))).scalars().all())
    log_count_after = len((await db_session.execute(select(DecisionLogEntry))).scalars().all())

    assert tx_count_after == tx_count_before
    assert asset_count_after == asset_count_before
    assert cash_count_after == cash_count_before
    assert mov_count_after == mov_count_before
    assert prop_count_after == prop_count_before
    assert log_count_after == log_count_before


# ---------------------------------------------------------------------------
# 14. Model-Facing Tool Handler via Registry
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_tool_registry_execution(db_session: AsyncSession):
    """Executing simulate_transaction via default_tool_registry yields sanitized JSON output."""
    user = await _create_test_user(db_session, "registry_user")
    inst = await _create_test_instrument(db_session, "TUPRS.IS", "Tüpraş", AssetType.STOCK)
    await _create_test_asset_with_transactions(db_session, user, inst, quantity=Decimal("100"), price=Decimal("160.0"))
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("10000"))

    tool_res = await default_tool_registry.execute(
        name="simulate_transaction",
        db=db_session,
        user_id=user.id,
        args={
            "symbol": "TUPRS",
            "action_type": "SELL",
            "fraction": "yarısı",
        },
    )

    assert tool_res.is_success
    assert tool_res.error is None
    data = tool_res.output
    assert isinstance(data, dict)
    assert data["status"] == "success"
    assert data["simulation_type"] == "SELL"
    assert data["transaction"]["quantity"] == 50.0
    assert data["after"]["target_position"]["quantity"] == 50.0


# ---------------------------------------------------------------------------
# 15. Deterministic Allocation Weights
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_deterministic_allocation_weights_sum_to_100(db_session: AsyncSession):
    """Allocation snapshot weights must sum to 100% before and after the simulation."""
    user = await _create_test_user(db_session, "alloc_user")
    inst1 = await _create_test_instrument(db_session, "PGSUS.IS", "Pegasus", AssetType.STOCK)
    inst2 = await _create_test_instrument(db_session, "TAVHL.IS", "TAV", AssetType.STOCK)

    await _create_test_asset_with_transactions(db_session, user, inst1, quantity=Decimal("100"), price=Decimal("200.0"))
    await _create_test_asset_with_transactions(db_session, user, inst2, quantity=Decimal("100"), price=Decimal("300.0"))
    await _create_test_cash_account(db_session, user, currency="TRY", balance=Decimal("50000"))

    result = await PortfolioSimulationService.simulate_transaction(
        db=db_session,
        user_id=user.id,
        instrument_query="PGSUS",
        transaction_type=SimulationType.SELL,
        quantity_fraction="tamamı",
    )

    assert result.status == "success"

    # Before allocation sum
    before_by_type_sum = sum(item["percentage"] for item in result.allocation_before.by_type)
    assert abs(before_by_type_sum - 100.0) < 0.1

    # After allocation sum
    after_by_type_sum = sum(item["percentage"] for item in result.allocation_after.by_type)
    assert abs(after_by_type_sum - 100.0) < 0.1
