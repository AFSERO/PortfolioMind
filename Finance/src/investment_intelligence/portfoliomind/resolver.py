"""Safe Instrument Resolver mapping Finance assets to PortfolioMind Instrument identities."""

from typing import Any, Optional
from uuid import UUID

from investment_intelligence.portfoliomind.exceptions import (
    AmbiguousInstrumentResolutionError,
    InstrumentNotFoundError,
)

# Canonical mapping from Finance instrument_type to PortfolioMind asset_type
FINANCE_TO_PORTFOLIOMIND_ASSET_TYPE = {
    "equity": "STOCK",
    "stock": "STOCK",
    "etf": "FUND",
    "fund": "FUND",
    "crypto": "CRYPTO",
    "commodity": "PRECIOUS_METALS",
    "gold": "PRECIOUS_METALS",
    "precious_metals": "PRECIOUS_METALS",
    "forex": "FOREX",
    "real_estate": "REAL_ESTATE",
    "custom": "CUSTOM",
}


class SafeInstrumentResolver:
    """Resolves Finance asset metadata to a canonical PortfolioMind Instrument UUID.

    Guarantees:
    1. Query PortfolioMind /api/instruments?q={symbol}.
    2. Filter candidates strictly by uppercase symbol.
    3. If Finance instrument has exchange/venue, filter candidates:
       - If candidate exchange is specified, it must match.
    4. If Finance instrument has currency, candidate must match.
    5. If Finance instrument has instrument_type, mapped asset_type must match.
    6. Safety invariant:
       - 0 viable matches -> InstrumentNotFoundError
       - >1 viable matches -> AmbiguousInstrumentResolutionError (FAILS CLOSED)
       - Exactly 1 viable match -> Returns Instrument UUID
    """

    @classmethod
    def map_asset_type(cls, finance_type: Optional[str]) -> Optional[str]:
        if not finance_type:
            return None
        cleaned = finance_type.strip().lower()
        return FINANCE_TO_PORTFOLIOMIND_ASSET_TYPE.get(cleaned, finance_type.strip().upper())

    @classmethod
    def resolve_from_candidates(
        cls,
        candidates: list[dict[str, Any]],
        *,
        symbol: str,
        asset_type: Optional[str] = None,
        venue: Optional[str] = None,
        currency: Optional[str] = None,
    ) -> UUID:
        clean_symbol = symbol.strip().upper()
        clean_venue = venue.strip().upper() if venue and venue.strip() else None
        clean_currency = currency.strip().upper() if currency and currency.strip() else None
        target_asset_type = cls.map_asset_type(asset_type)

        viable: list[dict[str, Any]] = []
        for cand in candidates:
            cand_sym = (cand.get("symbol") or "").strip().upper()
            if cand_sym != clean_symbol:
                continue

            # Asset type check
            if target_asset_type and cand.get("asset_type") != target_asset_type:
                continue

            # Venue / Exchange check
            cand_exchange = (cand.get("exchange") or "").strip().upper()
            if clean_venue and cand_exchange and clean_venue != cand_exchange:
                continue

            # Currency check
            cand_curr = (cand.get("currency") or "").strip().upper()
            if clean_currency and cand_curr and clean_currency != cand_curr:
                continue

            viable.append(cand)

        if not viable:
            raise InstrumentNotFoundError(
                f"No PortfolioMind Instrument found matching symbol='{clean_symbol}' "
                f"(type={target_asset_type}, venue={clean_venue}, currency={clean_currency})"
            )

        if len(viable) > 1:
            matched_ids = [c.get("id") for c in viable]
            raise AmbiguousInstrumentResolutionError(
                f"Multiple ambiguous PortfolioMind Instruments match symbol='{clean_symbol}': {matched_ids}. "
                f"Safe resolution requires explicit instrument_id or tighter metadata constraints."
            )

        return UUID(str(viable[0]["id"]))
