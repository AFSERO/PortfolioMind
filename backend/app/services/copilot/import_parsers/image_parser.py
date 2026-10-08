"""Screenshot and image portfolio import parser.

Extracts visible portfolio holdings from broker and wallet screenshots while strictly
adhering to financial integrity rules (never inventing missing quantities) and
prompt-injection security defenses.
"""

from decimal import Decimal
import json
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

from app.services.copilot.import_parsers.common import RawParsedItem

logger = logging.getLogger(__name__)

# Security validation constants
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB

IMAGE_SIGNATURES = {
    "image/png": b"\x89PNG\r\n\x1a\n",
    "image/jpeg": b"\xff\xd8\xff",
    "image/webp": b"RIFF",
}

# Known prompt injection signatures to sanitize / block from system instructions
PROMPT_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?previous\s+instructions",
    r"disregard\s+all\s+prior",
    r"system\s+prompt\s*:",
    r"you\s+are\s+now\s+in\s+developer\s+mode",
    r"delete\s+portfolio",
    r"drop\s+(table|database)",
    r"execute\s+command",
    r"rm\s+-rf",
    r"bypass\s+safety",
]


class ImageValidationError(ValueError):
    """Raised when an uploaded image fails security or format validation."""


class ImagePortfolioParser:
    """Validates image security and parses portfolio data without executing untrusted instructions."""

    @classmethod
    def validate_image_bytes(cls, data: bytes, content_type: Optional[str] = None) -> str:
        """Validate size and magic bytes of uploaded image."""
        if not data:
            raise ImageValidationError("Yüklenen dosya boş.")
        if len(data) > MAX_IMAGE_BYTES:
            raise ImageValidationError("Görsel dosya boyutu 10MB sınırını aşıyor.")

        detected_type: Optional[str] = None
        if data.startswith(IMAGE_SIGNATURES["image/png"]):
            detected_type = "image/png"
        elif data.startswith(IMAGE_SIGNATURES["image/jpeg"]):
            detected_type = "image/jpeg"
        elif data.startswith(b"RIFF") and b"WEBP" in data[:16]:
            detected_type = "image/webp"

        if not detected_type:
            raise ImageValidationError("Geçersiz veya desteklenmeyen görsel formatı. Yalnızca PNG, JPEG veya WEBP desteklenmektedir.")

        return detected_type

    @classmethod
    def validate_and_sanitize_image(cls, data: bytes, filename: Optional[str] = None) -> str:
        """Helper alias for validating uploaded image data."""
        return cls.validate_image_bytes(data, filename)

    @classmethod
    def sanitize_untrusted_text(cls, text: str) -> Tuple[str, bool]:
        """Strip prompt injection phrases from OCR or extracted text."""
        sanitized = text
        injected = False
        for pattern in PROMPT_INJECTION_PATTERNS:
            if re.search(pattern, sanitized, re.IGNORECASE):
                injected = True
                sanitized = re.sub(pattern, "[BLOCKED_INSTRUCTION]", sanitized, flags=re.IGNORECASE)
        return sanitized, injected

    @classmethod
    def sanitize_extracted_text(cls, text: str) -> str:
        """Strip prompt injection phrases from extracted text."""
        sanitized, _ = cls.sanitize_untrusted_text(text)
        return sanitized

    @classmethod
    def parse_extracted_payload(cls, extracted_data: Dict[str, Any]) -> List[RawParsedItem]:
        """Convert extracted multimodal/OCR items into strictly tagged RawParsedItem instances.

        Enforces:
        - NEVER infer quantity from market price.
        - Disambiguates quantity vs market value.
        """
        raw_items = extracted_data.get("items", [])
        parsed_items: List[RawParsedItem] = []

        for it in raw_items:
            raw_sym = it.get("symbol")
            raw_name = it.get("name") or raw_sym or "Unknown"

            # Check prompt injection in raw fields
            clean_sym, inj_sym = cls.sanitize_untrusted_text(str(raw_sym or ""))
            clean_name, inj_name = cls.sanitize_untrusted_text(str(raw_name))
            clean_notes, inj_notes = cls.sanitize_untrusted_text(str(it.get("notes") or ""))
            injected = inj_sym or inj_name or inj_notes

            warnings: List[str] = []
            missing_fields: List[str] = []
            semantic_fields: Dict[str, Any] = {}

            if injected:
                warnings.append("Görsel içerisinde zararlı komut/talimat metni tespit edildi ve engellendi.")

            raw_qty = it.get("quantity")
            qty: Optional[Decimal] = None
            if raw_qty is not None:
                try:
                    qty = Decimal(str(raw_qty))
                    semantic_fields["quantity"] = "QUANTITY"
                except Exception:
                    qty = None

            raw_mv = it.get("market_value")
            mv: Optional[Decimal] = None
            if raw_mv is not None:
                try:
                    mv = Decimal(str(raw_mv))
                    semantic_fields["market_value"] = "TOTAL_MARKET_VALUE"
                except Exception:
                    mv = None

            raw_cost = it.get("average_cost")
            avg_cost: Optional[Decimal] = None
            if raw_cost is not None:
                try:
                    avg_cost = Decimal(str(raw_cost))
                    semantic_fields["average_cost"] = "AVERAGE_COST"
                except Exception:
                    avg_cost = None

            raw_price = it.get("current_price")
            curr_price: Optional[Decimal] = None
            if raw_price is not None:
                try:
                    curr_price = Decimal(str(raw_price))
                    semantic_fields["current_price"] = "CURRENT_UNIT_PRICE"
                except Exception:
                    curr_price = None

            # Critical rule: NEVER invent missing financial data
            if qty is None:
                missing_fields.append("quantity")
                if mv is not None:
                    warnings.append(
                        f"{clean_sym or clean_name}: Piyasa değeri ({mv}) tespit edildi ancak adet/miktar görselde görünmüyor. "
                        "Piyasa fiyatından tahmini adet türetilmedi; lütfen gerçek adedi belirtin."
                    )
                else:
                    warnings.append(f"{clean_sym or clean_name}: Adet/miktar görselde tespit edilemedi.")

            item = RawParsedItem(
                raw_text=json.dumps(it, ensure_ascii=False),
                symbol=clean_sym.upper() if clean_sym else None,
                name=clean_name,
                asset_type=it.get("asset_type") or "STOCK",
                quantity=qty,
                market_value=mv,
                average_cost=avg_cost,
                currency=it.get("currency", "USD"),
                semantic_fields=semantic_fields,
                confidence=float(it.get("confidence", 0.9)),
                warnings=warnings,
                missing_fields=missing_fields,
            )
            parsed_items.append(item)

        return parsed_items
