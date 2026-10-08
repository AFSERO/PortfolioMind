"""Natural language portfolio import parser.

Extracts multiple holdings from user chat in Turkish and English without confusing
market value with quantity or cost basis.
"""

from decimal import Decimal, InvalidOperation
import re
from typing import List, Optional, Tuple

from app.services.copilot.holding_resolver import (
    COMMODITY_ALIASES,
    NUMBER_WORDS,
    normalize_text,
)
from app.services.copilot.import_parsers.common import RawParsedItem

# Introductory phrases to strip
INTRO_PHRASES = [
    r"my\s+portfolio\s*:",
    r"i\s+have\s*:",
    r"i\s+already\s+own\s*",
    r"my\s+current\s+portfolio\s+is\s*:",
    r"my\s+portfolio\s+is\s*:",
    r"add\s+my\s+current\s+portfolio\s*:",
    r"add\s+my\s+portfolio\s*:",
    r"(mevcut\s+)?portf[oö]y[uü]m(de)?\s*[:,]?",
    r"(mevcut\s+)?portf[oö]y[uü]me\s*(ekle)?\s*[:,]?",
    r"elimde\s+olanlar\s*:",
    r"mevcut\s+varliklarim\s*:",
    r"mevcut\s+portfoyum\s*:",
    r"bunlar\s+benim\s+portfoyum\s*:",
    r"bunlar\s+benim\s+portföyüm\s*:",
    r"su\s+varliklarim\s+var\s*:",
    r"şu\s+varlıklarım\s+var\s*:",
]

# Currency tokens
CURRENCY_MAP = {
    "tl": "TRY",
    "try": "TRY",
    "usd": "USD",
    "$": "USD",
    "dolar": "USD",
    "dollar": "USD",
    "eur": "EUR",
    "euro": "EUR",
    "€": "EUR",
    "gbp": "GBP",
    "sterlin": "GBP",
    "£": "GBP",
    "usdt": "USDT",
}

# Known crypto tickers
KNOWN_CRYPTO = {
    "BTC", "ETH", "USDT", "SOL", "BNB", "XRP", "DOGE", "ADA", "AVAX", "DOT", "LINK", "MATIC"
}


def _parse_number_with_multipliers(raw_num_str: str) -> Optional[Decimal]:
    """Parse numeric strings like '100k', '70 bin', '1.5m', '12', '0.08'."""
    s = raw_num_str.strip().lower()
    multiplier = Decimal("1")
    if s.endswith("k") or s.endswith("bin"):
        multiplier = Decimal("1000")
        s = re.sub(r"(k|bin)$", "", s).strip()
    elif s.endswith("m") or s.endswith("milyon"):
        multiplier = Decimal("1000000")
        s = re.sub(r"(m|milyon)$", "", s).strip()

    # Normalize decimal separator
    s = s.replace(",", ".")
    try:
        val = Decimal(s)
        return val * multiplier
    except (InvalidOperation, ValueError):
        return None


class NaturalLanguagePortfolioParser:
    """Parses freeform multi-holding text into structured RawParsedItem instances."""

    @classmethod
    def parse(cls, text: str) -> List[RawParsedItem]:
        cleaned = text.strip()
        # Remove introductory conversational headers
        for pattern in INTRO_PHRASES:
            cleaned = re.sub(r"^" + pattern, "", cleaned, flags=re.IGNORECASE).strip()

        # Separate sentences or clauses that describe cost basis (e.g. "Maliyetlerim AAPL için 180 USD, BTC için 60000 USD")
        raw_sentences = re.split(r"(?<=[.!?])\s+|\n+", cleaned)
        holding_sentences = []
        cost_statements = []

        for s in raw_sentences:
            s_clean = s.strip()
            if not s_clean:
                continue
            if re.search(r"^(maliyet[a-z]*|ortalama\s+maliyet[a-z]*|costs?)\b", s_clean, re.IGNORECASE):
                cost_statements.append(s_clean)
            else:
                holding_sentences.append(s_clean)

        lines: List[str] = []
        for hs in holding_sentences:
            parts = re.split(r",(?!\d)|\s+ve\s+|\s+and\s+|;", hs, flags=re.IGNORECASE)
            for p in parts:
                p_s = p.strip()
                if p_s and p_s != ".":
                    lines.append(p_s)

        parsed_items: List[RawParsedItem] = []
        for line in lines:
            item = cls._parse_single_line(line)
            if item:
                existing = next((it for it in parsed_items if it.symbol == item.symbol), None)
                if existing:
                    if existing.quantity is None and item.quantity is not None:
                        existing.quantity = item.quantity
                        existing.missing_fields = [f for f in existing.missing_fields if f != "quantity"]
                        existing.warnings = [w for w in existing.warnings if "miktar" not in w.lower()]
                    elif existing.market_value is None and item.market_value is not None:
                        existing.market_value = item.market_value
                else:
                    parsed_items.append(item)

        # Apply any cost statements to matching parsed_items
        for cs in cost_statements:
            cost_matches = re.finditer(
                r"([A-Za-z0-9\.\-_]{2,15})\s*(?:için|icin|:)?\s*([$€£]?)\s*(\d+(?:[.,]\d+)?)\s*([A-Za-z$€£]+)?",
                cs,
                re.IGNORECASE,
            )
            for cm in cost_matches:
                sym_candidate = cm.group(1).upper()
                if sym_candidate.lower() in CURRENCY_MAP or sym_candidate.lower() in ("maliyet", "maliyetim", "maliyetlerim"):
                    continue
                curr_pre = cm.group(2)
                cost_num = cm.group(3)
                curr_post = cm.group(4)
                parsed_c = _parse_number_with_multipliers(cost_num)
                if parsed_c is not None:
                    c_currency = CURRENCY_MAP.get((curr_pre or curr_post or "").lower())
                    for it in parsed_items:
                        if it.symbol == sym_candidate or (it.name and it.name.upper() == sym_candidate):
                            if not re.search(r"ortalama|average|unit|birim", cs, re.IGNORECASE):
                                it.missing_fields.append("cost_basis_type")
                                it.warnings.append("Maliyet birim mi toplam mı? Açık birim maliyet girin.")
                                continue
                            it.average_cost = parsed_c
                            if c_currency:
                                it.currency = c_currency
                            it.semantic_fields["average_cost"] = "AVERAGE_COST"

        return parsed_items

    @classmethod
    def _parse_single_line(cls, line: str) -> Optional[RawParsedItem]:
        norm_line = normalize_text(line)
        raw_text = line.strip()

        # Check for commodity aliases first (e.g. "2 half gold coins", "15 grams of gold", "2 yarim altin")
        commodity_item = cls._match_commodity(line, norm_line)
        if commodity_item:
            return commodity_item

        # Match Pattern A: Monetary value with Currency before Asset (e.g. "100k TL THF", "244 USD BTC", "$2500 UBER")
        pattern_value_first = re.search(
            r"([$€£]?)\s*(\d+(?:[.,]\d+)?\s*(?:k|bin|m|milyon)?)\s*([A-Za-z$€£]+)?\s+([A-Za-z0-9\.\-_]{2,15})",
            line,
            re.IGNORECASE,
        )
        if pattern_value_first:
            curr_sym_pre = pattern_value_first.group(1)
            num_str = pattern_value_first.group(2)
            curr_sym_post = pattern_value_first.group(3)
            asset_candidate = pattern_value_first.group(4)

            raw_curr = (curr_sym_pre or curr_sym_post or "").lower().strip()
            currency = CURRENCY_MAP.get(raw_curr)

            # If there is a currency associated with this number, it is MARKET_VALUE, not quantity!
            if currency:
                parsed_num = _parse_number_with_multipliers(num_str)
                if parsed_num is not None:
                    asset_type = "CRYPTO" if asset_candidate.upper() in KNOWN_CRYPTO else (
                        "FUND" if len(asset_candidate) == 3 and asset_candidate.isupper() else "STOCK"
                    )
                    return RawParsedItem(
                        raw_text=raw_text,
                        symbol=asset_candidate.upper(),
                        name=asset_candidate.upper(),
                        asset_type=asset_type,
                        quantity=None,
                        market_value=parsed_num,
                        currency=currency,
                        semantic_fields={"market_value": "TOTAL_MARKET_VALUE"},
                        confidence=0.9,
                        warnings=[f"Piyasa değeri ({parsed_num} {currency}) tespit edildi ancak miktar (adet) belirtilmedi."],
                        missing_fields=["quantity"],
                    )

        # Match Pattern B: Quantity followed by Symbol/Ticker (e.g. "12 NVDA", "8 UBER", "0.08 BTC", "1.4 ETH", "10 adet THYAO")
        pattern_qty_first = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(?:adet|shares|lot|units|coins|share)?\s+([A-Za-z0-9\.\-_]{2,15})",
            line,
            re.IGNORECASE,
        )
        if pattern_qty_first:
            num_str = pattern_qty_first.group(1)
            asset_candidate = pattern_qty_first.group(2).upper()

            # Ignore if asset_candidate is actually a currency word like TL or USD
            if asset_candidate.lower() not in CURRENCY_MAP:
                parsed_qty = _parse_number_with_multipliers(num_str)
                if parsed_qty is not None:
                    asset_type = "CRYPTO" if asset_candidate in KNOWN_CRYPTO else (
                        "FUND" if len(asset_candidate) == 3 and asset_candidate.isupper() else "STOCK"
                    )
                    default_curr = "USD" if asset_type in ("CRYPTO", "STOCK") and not asset_candidate.endswith(".IS") else "TRY"
                    return RawParsedItem(
                        raw_text=raw_text,
                        symbol=asset_candidate,
                        name=asset_candidate,
                        asset_type=asset_type,
                        quantity=parsed_qty,
                        market_value=None,
                        currency=default_curr,
                        semantic_fields={"quantity": "QUANTITY"},
                        confidence=0.95,
                    )

        # Match Pattern C: Symbol followed by Quantity (e.g. "NVDA 12", "UBER 8 adet")
        pattern_sym_first = re.search(
            r"([A-Za-z0-9\.\-_]{2,15})\s*[:=]?\s*(\d+(?:[.,]\d+)?)\s*(?:adet|shares|lot)?",
            line,
            re.IGNORECASE,
        )
        if pattern_sym_first:
            asset_candidate = pattern_sym_first.group(1).upper()
            num_str = pattern_sym_first.group(2)
            if asset_candidate.lower() not in CURRENCY_MAP:
                parsed_qty = _parse_number_with_multipliers(num_str)
                if parsed_qty is not None:
                    asset_type = "CRYPTO" if asset_candidate in KNOWN_CRYPTO else "STOCK"
                    return RawParsedItem(
                        raw_text=raw_text,
                        symbol=asset_candidate,
                        name=asset_candidate,
                        asset_type=asset_type,
                        quantity=parsed_qty,
                        market_value=None,
                        currency="USD",
                        semantic_fields={"quantity": "QUANTITY"},
                        confidence=0.9,
                    )

        # Match Pattern D: Asset candidate without quantity (e.g. "Microsoft hisselerim", "Apple hissesi")
        pattern_sym_only = re.search(
            r"\b([A-Za-z0-9\.\-_]{2,20})\s*(?:hissesi|hisselerim|hisse|hisseleri|stock|shares|token|coin)\b",
            line,
            re.IGNORECASE,
        )
        if pattern_sym_only:
            candidate = pattern_sym_only.group(1).strip()
            cand_lower = candidate.lower()
            if cand_lower not in CURRENCY_MAP and cand_lower not in ("benim", "olan", "mevcut", "varliklarim", "varlıklarım"):
                sym = candidate.upper()
                return RawParsedItem(
                    raw_text=raw_text,
                    symbol=sym,
                    name=candidate,
                    asset_type="STOCK",
                    quantity=None,
                    market_value=None,
                    currency="USD",
                    confidence=0.8,
                    warnings=[f"{candidate} için miktar (adet) belirtilmedi."],
                    missing_fields=["quantity"],
                )

        return None

    @classmethod
    def _match_commodity(cls, raw_line: str, norm_line: str) -> Optional[RawParsedItem]:
        """Detect commodity/gold phrases like '2 yarım altın', '15 grams of gold', '1000 TL'lik altın'."""
        # Check if this expresses a monetary value rather than physical quantity
        val_m = re.search(
            r"(\d+(?:[.,]\d+)?)\s*(?:tl|try|usd|dolar|dollar|euro|eur|lira|\$|€|£)?\s*(?:'lik|lik|lık|luk|lük|worth of|değerinde)\b",
            raw_line,
            re.IGNORECASE,
        )
        is_monetary_value = False
        market_val: Optional[Decimal] = None
        if val_m:
            try:
                market_val = Decimal(val_m.group(1).replace(",", "."))
                is_monetary_value = True
            except InvalidOperation:
                pass
        else:
            pre_cur_m = re.search(r"([$€£])\s*(\d+(?:[.,]\d+)?)", raw_line)
            if pre_cur_m:
                try:
                    market_val = Decimal(pre_cur_m.group(2).replace(",", "."))
                    is_monetary_value = True
                except InvalidOperation:
                    pass

        qty: Optional[Decimal] = None
        if not is_monetary_value:
            # Look for leading digit with physical units
            digit_m = re.search(r"(\d+(?:[.,]\d+)?)\s*(?:adet|coins|grams|gram)?", raw_line, re.IGNORECASE)
            if digit_m:
                try:
                    qty = Decimal(digit_m.group(1).replace(",", "."))
                except InvalidOperation:
                    pass

            if qty is None:
                for w, n in NUMBER_WORDS.items():
                    if re.search(r"\b" + re.escape(w) + r"\b", norm_line):
                        qty = n
                        break

            if qty is None:
                # If there is neither quantity nor monetary value, only match if this is an explicit holding declaration
                # (e.g. "altınlarım", "altın hissesi", "gold holdings") rather than an action or reference phrase.
                has_decl = bool(re.search(r"\b(varl[ıi][kğ]|holding|holdings|alt[ıi]nlar[ıi]m|var)\b", norm_line))
                is_action_ref = bool(re.search(r"\b(ekle|add|next to|yan[ıi]na|existing|mevcut)\b", norm_line))
                if not has_decl or is_action_ref:
                    return None

        # Check aliases
        sorted_aliases = sorted(COMMODITY_ALIASES.items(), key=lambda kv: len(kv[0]), reverse=True)
        for alias_key, sym in sorted_aliases:
            if re.search(r"\b" + re.escape(alias_key) + r"\b", norm_line):
                names_map = {
                    "HALF": "Yarım Altın",
                    "QUARTER": "Çeyrek Altın",
                    "TAM": "Tam Altın",
                    "REPUBLIC": "Cumhuriyet Altını",
                    "ATA": "Ata Altın",
                    "GRAM": "Gram Altın",
                    "XAU": "Ons Altın",
                }
                if is_monetary_value:
                    return RawParsedItem(
                        raw_text=raw_line.strip(),
                        symbol=sym,
                        name=names_map.get(sym, sym),
                        asset_type="PRECIOUS_METALS",
                        quantity=None,
                        market_value=market_val,
                        currency="TRY",
                        semantic_fields={"market_value": "TOTAL_MARKET_VALUE"},
                        confidence=0.95,
                        warnings=[f"Piyasa değeri ({market_val} TRY) tespit edildi ancak miktar (gramaj/adet) belirtilmedi."],
                        missing_fields=["quantity"],
                    )
                else:
                    return RawParsedItem(
                        raw_text=raw_line.strip(),
                        symbol=sym,
                        name=names_map.get(sym, sym),
                        asset_type="PRECIOUS_METALS",
                        quantity=qty,
                        currency="TRY",
                        semantic_fields={"quantity": "QUANTITY"} if qty is not None else {},
                        confidence=0.95,
                        warnings=[f"{names_map.get(sym, sym)} için miktar belirtilmedi."] if qty is None else [],
                        missing_fields=["quantity"] if qty is None else [],
                    )

        return None
