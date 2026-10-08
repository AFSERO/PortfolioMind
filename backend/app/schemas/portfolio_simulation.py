"""Pydantic schemas and typed contracts for Portfolio Simulation (Phase 3.2).

Defines structured inputs, snapshots, allocations, assumptions, and validation states.
"""

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class SimulationType(str, Enum):
    """Direction of the simulated transaction."""

    SELL = "SELL"
    BUY = "BUY"


class PriceSource(str, Enum):
    """Source provenance of the reference price used in simulation."""

    EXPLICIT_SCENARIO_PRICE = "EXPLICIT_SCENARIO_PRICE"
    CURRENT_REFERENCE_PRICE = "CURRENT_REFERENCE_PRICE"
    UNKNOWN = "UNKNOWN"


class SimulationValidation(BaseModel):
    """Validation outcome for the requested hypothetical scenario."""

    is_valid: bool = True
    reason: Optional[str] = None  # e.g., "INSUFFICIENT_HOLDING", "INVALID_QUANTITY", "MISSING_PRICE", "AMBIGUOUS_INSTRUMENT"
    message: Optional[str] = None


class SimulationAssumptions(BaseModel):
    """Explicit and implicit assumptions used in the simulation."""

    price: Optional[float] = None
    price_currency: Optional[str] = None
    price_source: PriceSource = PriceSource.UNKNOWN
    price_timestamp: Optional[str] = None
    fee: float = 0.0
    fee_currency: Optional[str] = None
    affects_cash: bool = True
    notes: Optional[str] = None


class SimulationInstrumentInfo(BaseModel):
    """Canonical instrument metadata for the simulated target asset."""

    symbol: str
    name: str
    instrument_id: Optional[str] = None
    asset_id: Optional[str] = None
    asset_type: str
    currency: str
    is_owned: bool = False


class SimulationPositionSnapshot(BaseModel):
    """Snapshot of holding and market valuation for the target asset."""

    quantity: float
    position_value: float  # In asset currency
    position_value_base: float  # In portfolio base currency
    weight_pct: float  # Percentage of total portfolio assets (0.0 to 100.0)


class SimulationCashSnapshot(BaseModel):
    """Snapshot of relevant cash balance and total cash allocation."""

    balance: float  # Balance in the transaction currency
    currency: str
    total_cash_base: float  # Total cash across all currencies converted to base
    cash_weight_pct: float  # Total cash percentage of portfolio assets
    cash_account_exists: bool = True


class SimulationPortfolioSnapshot(BaseModel):
    """Aggregated portfolio valuation before or after the simulated transaction."""

    total_value_base: float  # Total gross assets in base currency
    total_invested_assets_base: float  # Total non-cash assets in base currency
    base_currency: str
    target_position: SimulationPositionSnapshot
    cash: SimulationCashSnapshot


class SimulationTransactionSpec(BaseModel):
    """Detailed specifications and monetary impact of the simulated transaction."""

    transaction_type: SimulationType
    quantity: float
    gross_value: float  # In transaction currency
    gross_value_base: float  # In portfolio base currency
    fee: float = 0.0
    net_cash_delta: float  # In transaction currency (+ for SELL proceeds, - for BUY outlay)
    net_cash_delta_base: float  # In portfolio base currency
    currency: str
    is_affordable: bool = True
    cash_shortfall: float = 0.0


class SimulationAllocationSnapshot(BaseModel):
    """Deterministic allocation weights before or after the simulation."""

    by_type: List[Dict[str, Any]] = Field(default_factory=list)  # [ { "asset_type": "...", "value": float, "percentage": float } ]
    by_asset: List[Dict[str, Any]] = Field(default_factory=list)  # [ { "symbol": "...", "name": "...", "value": float, "percentage": float } ]


class SimulationResult(BaseModel):
    """Complete, immutable scenario outcome returned by PortfolioSimulationService."""

    status: str = "success"  # "success", "warning", "error"
    simulation_type: SimulationType
    instrument: SimulationInstrumentInfo
    assumptions: SimulationAssumptions
    validation: SimulationValidation
    before: SimulationPortfolioSnapshot
    transaction: SimulationTransactionSpec
    after: SimulationPortfolioSnapshot
    allocation_before: SimulationAllocationSnapshot
    allocation_after: SimulationAllocationSnapshot
    warnings: List[str] = Field(default_factory=list)
