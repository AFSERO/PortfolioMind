from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class LivePriceResponse(BaseModel):
    symbol: str
    price: Optional[float]
    currency: Optional[str]
    source: str  # "cache", "live", "last_known", "unavailable"
    fetched_at: Optional[str]


class RefreshResultItem(BaseModel):
    asset_id: str
    symbol: Optional[str]
    status: str  # "updated" or "failed"
    price: Optional[float] = None
    currency: Optional[str] = None
    error: Optional[str] = None
