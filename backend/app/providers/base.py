"""Base interfaces and data structures for fund data providers."""

from datetime import date
from decimal import Decimal
from typing import Optional, Protocol
from pydantic import BaseModel, ConfigDict


class FundMetadata(BaseModel):
    """Normalized metadata for an investment fund."""

    model_config = ConfigDict(from_attributes=True)

    fund_code: str
    fund_name: str
    price: Decimal
    currency: str = "TRY"
    price_date: Optional[date] = None
    provider: str = "TEFAS"


class BaseFundProvider(Protocol):
    """Protocol for investment fund price & metadata providers."""

    async def get_fund_info(self, fund_code: str) -> FundMetadata:
        """Fetch latest unit price and metadata for a fund code."""
        ...

    async def search_funds(self, query: str, limit: int = 20) -> list[dict]:
        """Search funds by code or title substring."""
        ...

    async def get_fund_history(
        self, fund_code: str, days: int = 30
    ) -> list[dict]:
        """Fetch chronological historical prices for a fund code."""
        ...
