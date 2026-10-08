"""Common definitions and data structures for import parsers."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Any, Dict, List, Optional


@dataclass
class RawParsedItem:
    """An intermediate holding parsed from an input source (chat, image, or CSV)."""

    raw_text: str
    symbol: Optional[str] = None
    name: Optional[str] = None
    asset_type: Optional[str] = None
    quantity: Optional[Decimal] = None
    market_value: Optional[Decimal] = None
    average_cost: Optional[Decimal] = None
    total_cost: Optional[Decimal] = None
    currency: Optional[str] = None
    as_of_date: Optional[date] = None
    semantic_fields: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)
    missing_fields: List[str] = field(default_factory=list)

    @property
    def is_market_value_only(self) -> bool:
        return self.quantity is None and self.market_value is not None
