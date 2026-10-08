"""Generic CSV portfolio import parser.

Supports arbitrary broker CSV exports, auto-detects delimiters (comma, semicolon, tab),
maps Turkish and English headers, parses European/Turkish number formats, and detects
ambiguous financial columns (e.g. standalone 'maliyet').
"""

import csv
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
import io
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.copilot.holding_resolver import normalize_text
from app.services.copilot.import_parsers.common import RawParsedItem

CANONICAL_COLUMN_MAP: Dict[str, str] = {
    # Symbol
    "symbol": "symbol",
    "sembol": "symbol",
    "ticker": "symbol",
    "kod": "symbol",
    "hisse": "symbol",
    "varlik": "symbol",
    "varlık": "symbol",
    "menkul": "symbol",
    # Name
    "name": "name",
    "ad": "name",
    "isim": "name",
    "unvan": "name",
    "tanim": "name",
    "tanım": "name",
    "aciklama": "name",
    "açıklama": "name",
    "varlik_adi": "name",
    "varlık adı": "name",
    # Asset Type
    "asset_type": "asset_type",
    "type": "asset_type",
    "tur": "asset_type",
    "tür": "asset_type",
    "varlik_turu": "asset_type",
    "varlık türü": "asset_type",
    # Quantity
    "quantity": "quantity",
    "qty": "quantity",
    "adet": "quantity",
    "miktar": "quantity",
    "lot": "quantity",
    "shares": "quantity",
    "adet/lot": "quantity",
    # Average Cost (unit cost)
    "average_cost": "average_cost",
    "avg_cost": "average_cost",
    "birim_maliyet": "average_cost",
    "birim maliyet": "average_cost",
    "alis_fiyati": "average_cost",
    "alış fiyatı": "average_cost",
    "unit_cost": "average_cost",
    "maliyet_fiyati": "average_cost",
    "maliyet fiyatı": "average_cost",
    # Total Cost
    "total_cost": "total_cost",
    "toplam_maliyet": "total_cost",
    "toplam maliyet": "total_cost",
    # Ambiguous Cost (requires user confirmation)
    "maliyet": "AMBIGUOUS_COST",
    "cost": "AMBIGUOUS_COST",
    # Market Value
    "market_value": "market_value",
    "piyasa_degeri": "market_value",
    "piyasa değeri": "market_value",
    "guncel_deger": "market_value",
    "güncel değer": "market_value",
    "tutar": "market_value",
    "toplam_tutar": "market_value",
    "toplam tutar": "market_value",
    "total_value": "market_value",
    # Currency
    "currency": "currency",
    "para_birimi": "currency",
    "para birimi": "currency",
    "doviz": "currency",
    "döviz": "currency",
    # Date
    "date": "as_of_date",
    "tarih": "as_of_date",
    "as_of_date": "as_of_date",
}


def _detect_delimiter(sample_text: str) -> str:
    """Sniff whether CSV uses ',', ';', '\t', or '|'."""
    first_line = sample_text.splitlines()[0] if sample_text.splitlines() else sample_text
    candidates = [";", ",", "\t", "|"]
    counts = {c: first_line.count(c) for c in candidates}
    best = max(counts, key=counts.get)
    return best if counts[best] > 0 else ","


def parse_csv_number(val_str: Optional[str]) -> Optional[Decimal]:
    """Parse string representations of numbers supporting both US and Turkish/European formats.

    e.g. '1.234,56' -> 1234.56
         '1,234.56' -> 1234.56
         '12,5' -> 12.5
         '12.5' -> 12.5
    """
    if not val_str:
        return None
    s = str(val_str).strip()
    if not s or s in ("-", "None", "null", "N/A"):
        return None

    # Remove currency symbols or extra spacing
    s = re.sub(r"[$€£₺TLUSDtlusd\s]", "", s)

    # If has both '.' and ','
    if "." in s and "," in s:
        if s.rfind(",") > s.rfind("."):
            # European format: 1.234,56 -> 1234.56
            s = s.replace(".", "").replace(",", ".")
        else:
            # US format: 1,234.56 -> 1234.56
            s = s.replace(",", "")
    elif "," in s:
        # Check if single comma is decimal or thousands: usually decimal in European/TR
        parts = s.split(",")
        if len(parts) == 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")

    try:
        return Decimal(s)
    except (InvalidOperation, ValueError):
        return None


def parse_csv_date(date_str: Optional[str]) -> Optional[date]:
    """Parse dates in YYYY-MM-DD, DD.MM.YYYY, DD/MM/YYYY."""
    if not date_str:
        return None
    s = str(date_str).strip()
    for fmt in ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y", "%Y/%m/%d"):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


class CsvPortfolioParser:
    """Parses arbitrary CSV file content into RawParsedItem instances."""

    @classmethod
    def parse(cls, content: str) -> Tuple[List[RawParsedItem], List[str]]:
        errors: List[str] = []
        if not content or not content.strip():
            return [], ["CSV dosyası boş."]

        delimiter = _detect_delimiter(content)
        f = io.StringIO(content.strip())
        reader = csv.reader(f, delimiter=delimiter)

        try:
            raw_headers = next(reader)
        except StopIteration:
            return [], ["CSV başlık satırı okunamadı."]

        # Map headers
        col_mapping: Dict[int, str] = {}
        for idx, h in enumerate(raw_headers):
            norm_h = normalize_text(h.lstrip("\ufeff").strip().lower().replace("_", " "))
            clean_h = h.strip().lower()
            mapped = CANONICAL_COLUMN_MAP.get(norm_h) or CANONICAL_COLUMN_MAP.get(clean_h)
            if mapped:
                col_mapping[idx] = mapped

        if not any(col in col_mapping.values() for col in ("symbol", "name")):
            return [], ["CSV dosyasında sembol (symbol/ticker) veya varlık adı (name) sütunu bulunamadı."]

        items: List[RawParsedItem] = []
        seen_symbols: Dict[str, RawParsedItem] = {}

        for row_idx, row in enumerate(reader, start=2):
            if not row or not any(cell.strip() for cell in row):
                continue  # skip blank lines

            row_data: Dict[str, Any] = {}
            for col_idx, cell in enumerate(row):
                if col_idx in col_mapping:
                    field_name = col_mapping[col_idx]
                    row_data[field_name] = cell.strip()

            raw_row_str = delimiter.join(row)

            symbol = row_data.get("symbol")
            name = row_data.get("name")
            if not symbol and not name:
                continue

            if not symbol and name:
                symbol = name.upper()
            if not name and symbol:
                name = symbol

            symbol = symbol.strip().upper() if symbol else None
            name = name.strip() if name else ""

            # Check quantity
            qty = parse_csv_number(row_data.get("quantity"))
            market_val = parse_csv_number(row_data.get("market_value"))
            avg_cost = parse_csv_number(row_data.get("average_cost"))
            total_cost = parse_csv_number(row_data.get("total_cost"))
            currency = row_data.get("currency")
            if currency:
                currency = currency.strip().upper()
                if currency in ("TL", "TRY"):
                    currency = "TRY"

            as_of = parse_csv_date(row_data.get("as_of_date"))

            warnings: List[str] = []
            missing_fields: List[str] = []
            semantic_fields: Dict[str, str] = {}

            if qty is not None:
                semantic_fields["quantity"] = "QUANTITY"
            else:
                missing_fields.append("quantity")

            if market_val is not None:
                semantic_fields["market_value"] = "TOTAL_MARKET_VALUE"

            if avg_cost is not None:
                semantic_fields["average_cost"] = "AVERAGE_COST"

            if total_cost is not None:
                semantic_fields["total_cost"] = "TOTAL_COST"

            for field in ("quantity", "average_cost", "total_cost", "market_value"):
                if row_data.get(field) and parse_csv_number(row_data[field]) is None:
                    missing_fields.append(field)
                    warnings.append(f"Invalid numeric value: {field}")
            if row_data.get("as_of_date") and as_of is None:
                missing_fields.append("as_of_date")
            # Check ambiguous cost header
            ambiguous_cost = parse_csv_number(row_data.get("AMBIGUOUS_COST"))
            if ambiguous_cost is not None:
                warnings.append(
                    f"'{ambiguous_cost}' değeri genel 'Maliyet' sütunundan okundu. "
                    "Bunun birim maliyet mi yoksa toplam maliyet mi olduğunu lütfen doğrulayın."
                )
                missing_fields.append("cost_basis_type")

            item = RawParsedItem(
                raw_text=raw_row_str,
                symbol=symbol,
                name=name,
                asset_type=row_data.get("asset_type"),
                quantity=qty,
                market_value=market_val,
                average_cost=avg_cost,
                total_cost=total_cost,
                currency=currency,
                as_of_date=as_of,
                semantic_fields=semantic_fields,
                confidence=0.95,
                warnings=warnings,
                missing_fields=missing_fields,
            )
            items.append(item)
            if symbol:
                seen_symbols[symbol] = item

        return items, errors

