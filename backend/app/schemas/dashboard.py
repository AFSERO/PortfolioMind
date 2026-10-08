from typing import Optional

from pydantic import BaseModel


class PerformerInfo(BaseModel):
    asset_id: str
    name: str
    symbol: Optional[str]
    pl: Optional[float]
    pl_pct: Optional[float]


class TypeSummary(BaseModel):
    asset_type: str
    total_value: float
    total_cost: Optional[float]
    pl: Optional[float]
    pl_pct: Optional[float]
    count: int


class ExchangeRateUsage(BaseModel):
    pair: str
    fetched_at: Optional[str]
    stale: bool


class ExchangeRateMetadata(BaseModel):
    status: str
    rates: list[ExchangeRateUsage]


class SummaryResponse(BaseModel):
    total_value: float
    total_assets: float
    total_liabilities: float
    net_worth: float
    total_cost: Optional[float]
    total_pl: Optional[float]
    total_pl_pct: Optional[float]
    unrealized_pl: Optional[float]
    realized_pl: Optional[float]
    total_cash: float
    asset_count: int
    liability_count: int
    best_performer: Optional[PerformerInfo]
    worst_performer: Optional[PerformerInfo]
    by_type_summary: list[TypeSummary]
    base_currency: str
    exchange_rates: ExchangeRateMetadata


class TypeAllocation(BaseModel):
    asset_type: str
    value: float
    percentage: float


class AssetAllocation(BaseModel):
    asset_id: str
    name: str
    symbol: Optional[str]
    asset_type: str
    value: float
    percentage: float


class AllocationResponse(BaseModel):
    total_value: float
    by_type: list[TypeAllocation]
    by_asset: list[AssetAllocation]
    base_currency: str
    exchange_rates: ExchangeRateMetadata


class TimelinePoint(BaseModel):
    date: str
    total_value_try: float
    total_value_usd: float
    total_assets_try: Optional[float]
    total_assets_usd: Optional[float]
    total_liabilities_try: Optional[float]
    total_liabilities_usd: Optional[float]
    net_worth_try: Optional[float]
    net_worth_usd: Optional[float]
    value_semantics: str

