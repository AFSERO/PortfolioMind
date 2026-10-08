"""Model-facing portfolio simulation tool for PortfolioMind Copilot V2 (Phase 3.2).

CORE SAFETY INVARIANTS:
1. Classification is strictly READ_ONLY.
2. Under NO circumstances does this tool create proposals, transactions, cash accounts,
   or modify any database state.
3. Performs pure functional in-memory calculations using PortfolioSimulationService.
4. Returns deterministic before/after snapshots, allocation weights, and assumptions.
"""

from decimal import Decimal
import logging
from typing import Any, Dict, List, Optional, Union
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas.portfolio_simulation import PriceSource, SimulationResult, SimulationType
from app.services.copilot_v2.tools.registry import (
    ToolClassification,
    ToolDefinition,
    ToolRegistry,
)
from app.services.portfolio_simulation import PortfolioSimulationService

logger = logging.getLogger(__name__)


async def simulate_transaction_handler(
    db: AsyncSession,
    user_id: UUID,
    symbol: Optional[str] = None,
    instrument_query: Optional[str] = None,
    action_type: Optional[str] = None,
    transaction_type: Optional[str] = None,
    quantity: Optional[Union[float, int, str]] = None,
    quantity_fraction: Optional[Union[float, int, str]] = None,
    fraction: Optional[Union[float, int, str]] = None,
    amount: Optional[Union[float, int, str]] = None,
    price: Optional[Union[float, int, str]] = None,
    fee: Optional[Union[float, int, str]] = 0.0,
    base_currency: str = "TRY",
    **kwargs: Any,
) -> Dict[str, Any]:
    """Execute a purely hypothetical, in-memory portfolio simulation.

    Zero mutations are performed. All calculations are mathematical projections.
    """
    target_query = symbol or instrument_query or kwargs.get("ticker")
    if not target_query or not str(target_query).strip():
        return {
            "status": "error",
            "simulation_type": "SELL",
            "validation": {
                "is_valid": False,
                "reason": "MISSING_INSTRUMENT",
                "message": "Simülasyon için sembol veya enstrüman adı belirtilmelidir.",
            },
        }

    raw_tx_type = action_type or transaction_type or "SELL"
    norm_tx_type = str(raw_tx_type).strip().upper()
    if norm_tx_type in ("SAT", "SATIS", "SATIŞ", "SELL"):
        sim_type = SimulationType.SELL
    elif norm_tx_type in ("AL", "ALIS", "ALIŞ", "BUY"):
        sim_type = SimulationType.BUY
    else:
        sim_type = SimulationType.SELL

    active_fraction = fraction if fraction is not None else quantity_fraction

    # If quantity was given as a fraction string (e.g. "yarisi", "50%"), handle it
    parsed_qty = None
    if quantity is not None:
        try:
            parsed_qty = float(quantity)
        except (ValueError, TypeError):
            if active_fraction is None:
                active_fraction = str(quantity)

    parsed_amount = None
    if amount is not None:
        try:
            parsed_amount = float(amount)
        except (ValueError, TypeError):
            pass

    parsed_price = None
    if price is not None:
        try:
            parsed_price = float(price)
        except (ValueError, TypeError):
            pass

    parsed_fee = 0.0
    if fee is not None:
        try:
            parsed_fee = float(fee)
        except (ValueError, TypeError):
            parsed_fee = 0.0

    try:
        result: SimulationResult = await PortfolioSimulationService.simulate_transaction(
            db=db,
            user_id=user_id,
            instrument_query=str(target_query).strip(),
            transaction_type=sim_type,
            quantity=parsed_qty,
            quantity_fraction=active_fraction,
            amount=parsed_amount,
            price=parsed_price,
            fee=parsed_fee,
            base_currency=base_currency,
        )
        return result.model_dump(mode="json")
    except Exception as exc:
        logger.error("Simulation error for '%s': %s", target_query, exc, exc_info=True)
        return {
            "status": "error",
            "simulation_type": sim_type.value,
            "validation": {
                "is_valid": False,
                "reason": "INTERNAL_SIMULATION_ERROR",
                "message": f"Simülasyon motoru hatası: {str(exc)}",
            },
        }


def register_simulation_tools(registry: ToolRegistry) -> None:
    """Register simulation tools into the ToolRegistry.

    All tools registered here are strictly ToolClassification.READ_ONLY.
    """
    registry.register(
        ToolDefinition(
            name="simulate_transaction",
            description=(
                "Simulate a hypothetical BUY or SELL transaction without mutating any application or portfolio state. "
                "Calculates exact before/after holding quantities, market values, target asset portfolio weights, "
                "cash impact, and allocation breakdown by asset and by asset type. "
                "Use whenever the user asks 'what if' or scenario questions (e.g. 'THF'nin yarısını satsam ne olur?', "
                "'100.000 TL NVDA alsam dağılım nasıl değişir?', 'BTC'nin %25'ini satsam nakit oranım ne olur?'). "
                "DO NOT use proposal tools for hypothetical questions. Simulation is pure calculation."
            ),
            parameters_schema={
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Symbol or name of the instrument (e.g. 'THF', 'THYAO', 'NVDA', 'BTC')",
                    },
                    "action_type": {
                        "type": "string",
                        "enum": ["SELL", "BUY"],
                        "description": "Transaction direction: SELL (selling part or all of holding) or BUY (purchasing additional or new position)",
                    },
                    "quantity": {
                        "type": "number",
                        "description": "Exact number of units or shares to simulate (optional if fraction or amount is provided)",
                    },
                    "fraction": {
                        "type": "string",
                        "description": "Fraction or percentage of holding to simulate for SELL (e.g. '0.5', '50%', 'yarısı', 'tamamı', '0.25', '1/3')",
                    },
                    "amount": {
                        "type": "number",
                        "description": "Total cash amount in asset/base currency to simulate (e.g. 100000 for '100.000 TL')",
                    },
                    "price": {
                        "type": "number",
                        "description": "Optional explicit scenario price (if omitted, uses current reference market price)",
                    },
                    "fee": {
                        "type": "number",
                        "description": "Optional transaction commission/fee (default: 0.0)",
                        "default": 0.0,
                    },
                },
                "required": ["symbol", "action_type"],
            },
            classification=ToolClassification.READ_ONLY,
            handler=simulate_transaction_handler,
        )
    )
