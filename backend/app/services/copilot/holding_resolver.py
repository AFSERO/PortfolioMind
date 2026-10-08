"""Holding, Instrument, and Financial Value Resolver for PortfolioMind Copilot.

Provides multi-stage deterministic matching across user-owned assets, canonical instruments,
and known commodity/Turkish aliases. Disambiguates unit price vs total holding value,
and parses non-cash acquisition and numerical financial patterns.
"""

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
import re
from typing import Any, List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset
from app.models.instrument import Instrument
from app.models.transaction import Transaction
from app.schemas.copilot import (
    AcquisitionType,
    SemanticFinancialMeaning,
    SemanticFinancialValue,
)
from app.services.portfolio_stats import compute_stats

ZERO = Decimal("0")

# Turkish / English commodity & gold alias normalization map
COMMODITY_ALIASES: dict[str, str] = {
    # Half Gold
    "yarim altin": "HALF",
    "yarim": "HALF",
    "half gold": "HALF",
    "gold half": "HALF",
    "half-gold": "HALF",
    "half": "HALF",
    # Quarter Gold
    "ceyrek altin": "QUARTER",
    "ceyrek": "QUARTER",
    "quarter gold": "QUARTER",
    "gold quarter": "QUARTER",
    "quarter-gold": "QUARTER",
    "quarter": "QUARTER",
    # Full / Republic Gold
    "tam altin": "TAM",
    "tam": "TAM",
    "full gold": "TAM",
    "gold full": "TAM",
    "full": "TAM",
    "cumhuriyet altini": "REPUBLIC",
    "cumhuriyet": "REPUBLIC",
    "republic gold": "REPUBLIC",
    "republic": "REPUBLIC",
    "ata altin": "ATA",
    "ata": "ATA",
    # Gram Gold
    "gram altin": "GRAM",
    "gram gold": "GRAM",
    "gold gram": "GRAM",
    "gram": "GRAM",
    # Ounce Gold
    "ons altin": "XAU",
    "ons": "XAU",
    "gold ounce": "XAU",
    "xau": "XAU",
    # Other coins
    "gremse": "GREMSE",
    "resat altin": "RESAT",
    "resat": "RESAT",
    "hamit altin": "HAMIT",
    "hamit": "HAMIT",
}

# Number words mapping (Turkish & English)
NUMBER_WORDS: dict[str, Decimal] = {
    "zero": Decimal("0"),
    "sıfır": Decimal("0"),
    "sifir": Decimal("0"),
    "one": Decimal("1"),
    "a": Decimal("1"),
    "an": Decimal("1"),
    "bir": Decimal("1"),
    "single": Decimal("1"),
    "two": Decimal("2"),
    "iki": Decimal("2"),
    "three": Decimal("3"),
    "üç": Decimal("3"),
    "uc": Decimal("3"),
    "four": Decimal("4"),
    "dört": Decimal("4"),
    "dort": Decimal("4"),
    "five": Decimal("5"),
    "beş": Decimal("5"),
    "bes": Decimal("5"),
    "six": Decimal("6"),
    "altı": Decimal("6"),
    "alti": Decimal("6"),
    "seven": Decimal("7"),
    "yedi": Decimal("7"),
    "eight": Decimal("8"),
    "sekiz": Decimal("8"),
    "nine": Decimal("9"),
    "dokuz": Decimal("9"),
    "ten": Decimal("10"),
    "on": Decimal("10"),
}


def normalize_text(s: str) -> str:
    """Normalize text by lowercasing and replacing Turkish diacritics for robust matching."""
    if not s:
        return ""
    # Turkish-specific lowercasing
    s = s.replace("İ", "i").replace("I", "ı").lower()
    # Normalize diacritics
    trans = str.maketrans("ıöüşçğ", "iouscg")
    return s.translate(trans).strip()


def parse_currency_amount(text: str) -> Tuple[Optional[Decimal], Optional[str]]:
    """Parse monetary amounts with currency symbols or suffixes.
    
    Supports:
    - "$1,348.55" -> (Decimal("1348.55"), "USD")
    - "1.348,55 TL" or "1.348,55 ₺" -> (Decimal("1348.55"), "TRY")
    - "1,348.55" -> (Decimal("1348.55"), None)
    - "250.50 EUR" or "€250.50" -> (Decimal("250.50"), "EUR")
    """
    if not text:
        return None, None

    currency = None
    lower = text.lower()
    if "$" in text or "usd" in lower or "dolar" in lower:
        currency = "USD"
    elif "€" in text or "eur" in lower or "euro" in lower:
        currency = "EUR"
    elif "₺" in text or "try" in lower or "tl" in lower:
        currency = "TRY"
    elif "£" in text or "gbp" in lower or "sterlin" in lower:
        currency = "GBP"

    # Match price specifically near @, at, $, €, ₺, £, or followed by currency
    price_pattern = re.search(
        r"(?:at|@|fiyattan|fiyatla|\$|€|₺|£)\s*([0-9\.,]+)|([0-9\.,]+)\s*(?:usd|eur|try|tl|gbp|dolar|euro|türk lirası|\$|€|₺|£)",
        text,
        re.IGNORECASE,
    )
    if price_pattern:
        raw_num = price_pattern.group(1) or price_pattern.group(2)
    else:
        # If no explicit currency prefix/suffix, but the entire string is just a number (e.g. user replied with "1,348.55")
        alone = re.match(r"^\s*([0-9\.,]+)\s*$", text)
        if alone:
            raw_num = alone.group(1)
        else:
            return None, currency

    if not raw_num:
        return None, currency

    # Handle Turkish comma decimal separator: "1.348,55" -> "1348.55"
    if "," in raw_num and "." in raw_num:
        if raw_num.rfind(",") > raw_num.rfind("."):
            # Comma is decimal separator (Turkish/European)
            cleaned = raw_num.replace(".", "").replace(",", ".")
        else:
            # Dot is decimal separator (US)
            cleaned = raw_num.replace(",", "")
    elif "," in raw_num:
        # e.g. "1348,55"
        cleaned = raw_num.replace(",", ".")
    else:
        cleaned = raw_num

    try:
        val = Decimal(cleaned)
        return val, currency
    except InvalidOperation:
        return None, currency


def parse_quantity(text: str) -> Optional[Decimal]:
    """Parse transaction quantity from text including word numbers (e.g. 'one', 'bir', '2').
    
    Carefully handles phrases like 'one half-gold coin' -> quantity is 1 (not 0.5).
    """
    lower = normalize_text(text)

    # Check for specific phrase "one <instrument> coin" or "1 adet <instrument>"
    # E.g. "one half-gold coin", "one half gold", "bir adet yarım altın", "1 yarım altın"
    qty_prefix = re.search(
        r"\b(one|bir|two|iki|three|üç|four|dört|five|beş|\d+(?:\.\d+)?)\s*(?:adet|tane|piece|pieces|coin|coins|shares?|lot|units?)?\s*(?:half|yarim|ceyrek|quarter|tam|full|cumhuriyet|ata|gram|ons)?\b",
        lower,
    )
    if qty_prefix:
        word = qty_prefix.group(1)
        if word in NUMBER_WORDS:
            return NUMBER_WORDS[word]
        try:
            return Decimal(word)
        except InvalidOperation:
            pass

    # Generic number words
    words = re.findall(r"\b[a-z0-9\.]+\b", lower)
    for w in words:
        if w in NUMBER_WORDS and w not in ("a", "an"):
            return NUMBER_WORDS[w]
        try:
            val = Decimal(w)
            # Avoid picking years like 2024, 2025, 2026 as quantities
            if val not in (Decimal("2024"), Decimal("2025"), Decimal("2026")):
                return val
        except InvalidOperation:
            continue

    return None


def parse_acquisition_type(text: str) -> Tuple[AcquisitionType, bool, Decimal]:
    """Determine acquisition semantics: GIFT_IN, TRANSFER_IN, PURCHASE, or SALE.
    
    Returns (AcquisitionType, affects_cash, cash_outflow).
    """
    lower = normalize_text(text)
    
    # Gift indicators
    if any(k in lower for k in ["hediye", "gift", "gave me", "annem verdi", "babam verdi", "hediye etti"]):
        return AcquisitionType.GIFT_IN, False, ZERO

    # Transfer indicators
    if any(k in lower for k in ["transfer", "aktarim", "aktarildi", "virman"]):
        return AcquisitionType.TRANSFER_IN, False, ZERO

    # Sale indicators
    if any(k in lower for k in ["sold", "sell", "sattim", "sattik"]):
        return AcquisitionType.SALE, True, ZERO

    # Default to purchase
    return AcquisitionType.PURCHASE, True, ZERO


@dataclass
class HoldingStats:
    """Precomputed financial stats for a specific user holding."""

    quantity: Decimal
    current_price: Optional[Decimal]
    currency: Optional[str]
    current_value: Optional[Decimal]
    avg_cost: Optional[Decimal]
    total_cost: Decimal
    unrealized_pl: Decimal
    realized_pl: Decimal

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity": float(self.quantity),
            "current_price": float(self.current_price) if self.current_price is not None else None,
            "currency": self.currency,
            "current_value": float(self.current_value) if self.current_value is not None else None,
            "avg_cost": float(self.avg_cost) if self.avg_cost is not None else None,
            "total_cost": float(self.total_cost) if self.total_cost is not None else None,
            "unrealized_pl": float(self.unrealized_pl) if self.unrealized_pl is not None else None,
            "realized_pl": float(self.realized_pl) if self.realized_pl is not None else None,
        }


@dataclass
class ResolvedHolding:
    """Outcome of resolving user text against portfolio holdings and instruments."""

    instrument: Optional[Instrument] = None
    asset: Optional[Asset] = None
    match_type: str = "NONE"  # "EXACT_SYMBOL", "EXACT_NAME", "COMMODITY_ALIAS", "FUZZY_NAME", "INSTRUMENT_MATCH", "AMBIGUOUS"
    confidence: float = 0.0
    stats: Optional[HoldingStats] = None
    semantic_values: List[SemanticFinancialValue] = field(default_factory=list)
    ambiguous_candidates: List[dict[str, Any]] = field(default_factory=list)

    @property
    def is_resolved(self) -> bool:
        return self.asset is not None or self.instrument is not None

    @property
    def is_owned(self) -> bool:
        return self.asset is not None and self.stats is not None and self.stats.quantity > ZERO


class HoldingResolver:
    """Resolves natural language queries to user holdings and canonical instruments."""

    @classmethod
    async def resolve(
        cls,
        db: AsyncSession,
        user_id: UUID,
        query: str,
        current_page_context: Optional[dict[str, Any]] = None,
    ) -> ResolvedHolding:
        """Execute deterministic multi-stage holding and instrument resolution."""
        text = query.strip()
        norm_text = normalize_text(text)

        # 1. Fetch all assets owned by this user
        assets_res = await db.execute(
            select(Asset)
            .options(
                selectinload(Asset.instrument),
                selectinload(Asset.opening_position),
            )
            .where(Asset.user_id == user_id)
        )
        user_assets = list(assets_res.scalars().all())

        # Collect asset transactions for stats computation
        asset_ids = [a.id for a in user_assets]
        txns_by_asset: dict[UUID, list[Transaction]] = {aid: [] for aid in asset_ids}
        if asset_ids:
            tx_res = await db.execute(
                select(Transaction).where(Transaction.asset_id.in_(asset_ids))
            )
            for tx in tx_res.scalars().all():
                txns_by_asset[tx.asset_id].append(tx)

        # ---------------------------------------------------------------------
        # Stage 1: Exact Symbol Match in User Assets
        # ---------------------------------------------------------------------
        words = re.findall(r"\b[A-Za-z0-9\.\-_]{2,15}\b", text)
        for w in words:
            w_upper = w.upper()
            for asset in user_assets:
                if asset.symbol and asset.symbol.upper() == w_upper:
                    stats = cls._calculate_stats(asset, txns_by_asset[asset.id])
                    sem_vals = cls._build_semantic_values(asset, stats)
                    return ResolvedHolding(
                        instrument=asset.instrument,
                        asset=asset,
                        match_type="EXACT_SYMBOL",
                        confidence=1.0,
                        stats=stats,
                        semantic_values=sem_vals,
                    )

        # ---------------------------------------------------------------------
        # Stage 2: Commodity / Gold Alias Mapping
        # ---------------------------------------------------------------------
        # Check if any alias key exists in norm_text
        matched_alias_symbol: Optional[str] = None
        # Sort keys by length descending to match "yarim altin" before "yarim"
        sorted_aliases = sorted(COMMODITY_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
        for alias_key, target_sym in sorted_aliases:
            if re.search(r"\b" + re.escape(alias_key) + r"\b", norm_text):
                matched_alias_symbol = target_sym
                break

        if matched_alias_symbol:
            # Check if user owns an asset with this symbol or matching name
            matched_user_assets: list[Asset] = []
            for asset in user_assets:
                norm_asset_name = normalize_text(asset.name)
                norm_asset_sym = normalize_text(asset.symbol or "")
                if (
                    (asset.symbol and asset.symbol.upper() == matched_alias_symbol)
                    or (matched_alias_symbol.lower() in norm_asset_sym)
                    or (matched_alias_symbol.lower() in norm_asset_name)
                    or any(
                        alias in norm_asset_name
                        for alias, s in COMMODITY_ALIASES.items()
                        if s == matched_alias_symbol
                    )
                ):
                    matched_user_assets.append(asset)

            if len(matched_user_assets) == 1:
                asset = matched_user_assets[0]
                stats = cls._calculate_stats(asset, txns_by_asset[asset.id])
                sem_vals = cls._build_semantic_values(asset, stats)
                return ResolvedHolding(
                    instrument=asset.instrument,
                    asset=asset,
                    match_type="COMMODITY_ALIAS",
                    confidence=0.98,
                    stats=stats,
                    semantic_values=sem_vals,
                )
            elif len(matched_user_assets) > 1:
                # Ambiguous match among multiple holdings
                candidates = [
                    {"asset_id": str(a.id), "symbol": a.symbol, "name": a.name}
                    for a in matched_user_assets
                ]
                return ResolvedHolding(
                    match_type="AMBIGUOUS",
                    confidence=0.5,
                    ambiguous_candidates=candidates,
                )

        # ---------------------------------------------------------------------
        # Stage 3: Exact Name or Substring Match in User Assets
        # ---------------------------------------------------------------------
        for asset in user_assets:
            norm_name = normalize_text(asset.name)
            if norm_name and (norm_name in norm_text or norm_text in norm_name):
                stats = cls._calculate_stats(asset, txns_by_asset[asset.id])
                sem_vals = cls._build_semantic_values(asset, stats)
                return ResolvedHolding(
                    instrument=asset.instrument,
                    asset=asset,
                    match_type="EXACT_NAME",
                    confidence=0.95,
                    stats=stats,
                    semantic_values=sem_vals,
                )

        # ---------------------------------------------------------------------
        # Stage 4: Match against canonical Instrument table
        # ---------------------------------------------------------------------
        # Look for symbol in instruments
        for w in words:
            w_upper = w.upper()
            inst_res = await db.execute(
                select(Instrument).where(Instrument.symbol == w_upper)
            )
            inst = inst_res.scalars().first()
            if inst:
                return ResolvedHolding(
                    instrument=inst,
                    match_type="INSTRUMENT_SYMBOL",
                    confidence=0.9,
                )

        # Look for alias symbol in instruments
        if matched_alias_symbol:
            inst_res = await db.execute(
                select(Instrument).where(Instrument.symbol == matched_alias_symbol)
            )
            inst = inst_res.scalars().first()
            if inst:
                return ResolvedHolding(
                    instrument=inst,
                    match_type="INSTRUMENT_ALIAS",
                    confidence=0.88,
                )

        # ---------------------------------------------------------------------
        # Stage 5: Fallback to Page Context
        # ---------------------------------------------------------------------
        if current_page_context:
            page_sym = current_page_context.get("symbol")
            if page_sym:
                for asset in user_assets:
                    if asset.symbol and asset.symbol.upper() == str(page_sym).upper():
                        stats = cls._calculate_stats(asset, txns_by_asset[asset.id])
                        sem_vals = cls._build_semantic_values(asset, stats)
                        return ResolvedHolding(
                            instrument=asset.instrument,
                            asset=asset,
                            match_type="PAGE_CONTEXT",
                            confidence=0.85,
                            stats=stats,
                            semantic_values=sem_vals,
                        )

        return ResolvedHolding(match_type="NONE", confidence=0.0)

    @staticmethod
    def _calculate_stats(asset: Asset, txns: list[Transaction]) -> HoldingStats:
        """Compute holding stats from transactions and asset current price."""
        computed = compute_stats(txns, opening_position=getattr(asset, "opening_position", None))
        qty = computed["total_quantity"]
        curr_price = asset.current_price
        currency = asset.current_price_currency or computed.get("avg_cost_currency") or "USD"

        curr_value = (curr_price * qty) if (curr_price is not None and qty > ZERO) else ZERO
        avg_cost = computed.get("avg_cost")
        total_cost = computed.get("total_cost", ZERO)
        unrealized_pl = (curr_value - total_cost) if total_cost is not None and curr_price is not None else None
        realized_pl = computed.get("realized_pl", ZERO)

        return HoldingStats(
            quantity=qty,
            current_price=curr_price,
            currency=currency,
            current_value=curr_value,
            avg_cost=avg_cost,
            total_cost=total_cost,
            unrealized_pl=unrealized_pl,
            realized_pl=realized_pl,
        )

    @staticmethod
    def _build_semantic_values(
        asset: Asset, stats: HoldingStats
    ) -> List[SemanticFinancialValue]:
        """Construct semantic financial values clearly distinguishing unit price from total value."""
        values: List[SemanticFinancialValue] = []
        cur = stats.currency or "USD"

        # 1. CURRENT_UNIT_PRICE
        if stats.current_price is not None:
            values.append(
                SemanticFinancialValue(
                    value=stats.current_price,
                    currency=cur,
                    meaning=SemanticFinancialMeaning.CURRENT_UNIT_PRICE,
                    source="ASSET_MARKET_PRICE",
                    freshness="CURRENT",
                    formatted=f"{stats.current_price:.2f} {cur}",
                    notes="Current market price per single unit / coin / share.",
                )
            )

        # 2. TOTAL_MARKET_VALUE
        if stats.current_value is not None:
            values.append(
                SemanticFinancialValue(
                    value=stats.current_value,
                    currency=cur,
                    meaning=SemanticFinancialMeaning.TOTAL_MARKET_VALUE,
                    source="HOLDING_TOTAL_VALUATION",
                    freshness="CURRENT",
                    formatted=f"{stats.current_value:.2f} {cur}",
                    notes=f"Total valuation of current holding position ({stats.quantity} units).",
                )
            )

        # 3. AVERAGE_COST
        if stats.avg_cost is not None:
            values.append(
                SemanticFinancialValue(
                    value=stats.avg_cost,
                    currency=cur,
                    meaning=SemanticFinancialMeaning.AVERAGE_COST,
                    source="TRANSACTION_COST_BASIS",
                    freshness="CURRENT",
                    formatted=f"{stats.avg_cost:.2f} {cur}",
                    notes="Average historical acquisition cost per unit.",
                )
            )

        # 4. DERIVED_FROM_MARKET_VALUE fallback if unit price is missing but value & qty exist
        if stats.current_price is None and stats.current_value is not None and stats.quantity > ZERO:
            derived_unit = stats.current_value / stats.quantity
            values.append(
                SemanticFinancialValue(
                    value=derived_unit,
                    currency=cur,
                    meaning=SemanticFinancialMeaning.DERIVED_FROM_MARKET_VALUE,
                    source="DERIVED_TOTAL_OVER_QUANTITY",
                    freshness="DERIVED",
                    formatted=f"{derived_unit:.2f} {cur}",
                    notes="Derived unit price computed by dividing total value by quantity.",
                )
            )

        return values

