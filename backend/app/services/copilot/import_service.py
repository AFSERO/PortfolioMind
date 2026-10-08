"""Common Portfolio Import Service.

Implements the single converged import pipeline across Natural Language, Screenshot, and CSV:
INPUT -> PARSE -> NORMALIZE -> INSTRUMENT RESOLUTION -> FINANCIAL VALIDATION
-> COMPARE AGAINST CURRENT PORTFOLIO -> IMPORT DRAFT -> PREVIEW/DIFF -> CONFIRMATION -> WRITE -> AUDIT.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import logging
import re
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetType
from app.models.copilot import CopilotActionProposal, CopilotConversation
from app.models.instrument import Instrument
from app.models.portfolio_import import PortfolioImportBatch, PortfolioImportItem
from app.schemas.portfolio_import import (
    ActionResolutionType,
    ImportBatchStatus,
    ImportItemAction,
    ImportItemResolutionRequest,
    ImportSourceType,
    PortfolioImportBatchResponse,
    PortfolioImportItemResponse,
)
from app.services import asset as asset_service
from app.services.copilot.holding_resolver import HoldingResolver
from app.services.copilot.import_parsers import (
    CsvPortfolioParser,
    ImagePortfolioParser,
    NaturalLanguagePortfolioParser,
    RawParsedItem,
)
from app.services.copilot.proposal_service import CopilotProposalService
from app.services.portfolio_stats import compute_stats

logger = logging.getLogger(__name__)

ZERO = Decimal("0")


class PortfolioImportService:
    """Orchestrates parsing, holding reconciliation, and draft staging for portfolio imports."""

    @classmethod
    async def process_import(
        cls,
        db: AsyncSession,
        user_id: UUID,
        conversation_id: Optional[UUID],
        source_type: str,
        raw_content: str,
        parsed_items: Optional[List[RawParsedItem]] = None,
        source_reference: Optional[str] = None,
    ) -> PortfolioImportBatch:
        """Execute common pipeline: parse -> resolve -> reconcile -> stage batch & proposal."""
        if conversation_id is not None:
            conversation = await db.scalar(select(CopilotConversation).where(
                CopilotConversation.id == conversation_id, CopilotConversation.user_id == user_id))
            if conversation is None:
                raise ValueError("Conversation not found or access denied.")
        # 1. Parse raw input if not already parsed
        parse_errors: List[str] = []
        if parsed_items is None:
            if source_type == ImportSourceType.NATURAL_LANGUAGE.value:
                parsed_items = NaturalLanguagePortfolioParser.parse(raw_content)
            elif source_type == ImportSourceType.CSV.value:
                parsed_items, parse_errors = CsvPortfolioParser.parse(raw_content)
            elif source_type == ImportSourceType.SCREENSHOT.value:
                # Expects JSON string payload containing extracted items
                try:
                    import json
                    payload = json.loads(raw_content)
                    parsed_items = ImagePortfolioParser.parse_extracted_payload(payload)
                except Exception as err:
                    parse_errors.append(f"Görsel veri çözümleme hatası: {str(err)}")
                    parsed_items = []
            else:
                parsed_items = []

        # 2. Fetch existing user assets for portfolio comparison
        existing_assets = await asset_service.list_assets(db, user_id)
        assets_by_symbol: Dict[str, Asset] = {}
        assets_by_name: Dict[str, Asset] = {}
        for a in existing_assets:
            if a.symbol:
                assets_by_symbol[a.symbol.upper()] = a
            assets_by_name[a.name.lower()] = a

        # 3. Create Import Batch
        batch_id = uuid4()
        idempotency_key = f"import_batch_{batch_id.hex}"
        batch = PortfolioImportBatch(
            id=batch_id,
            user_id=user_id,
            conversation_id=conversation_id,
            source_type=source_type,
            source_reference=source_reference,
            status=ImportBatchStatus.PARSED.value,
            raw_content_preview=raw_content[:500] if raw_content else None,
            warnings=[],
            errors=parse_errors,
            idempotency_key=idempotency_key,
            parsed_at=datetime.now(timezone.utc),
        )
        db.add(batch)
        await db.flush()

        # 4. Instrument Resolution & Existing Holding Reconciliation for each item
        db_items: List[PortfolioImportItem] = []
        for raw_item in parsed_items:
            for field in ("quantity", "average_cost", "total_cost", "market_value"):
                value = getattr(raw_item, field)
                if value is not None and (not value.is_finite() or value < 0 or value >= Decimal("1e12") or (field == "quantity" and value == 0)):
                    setattr(raw_item, field, None)
                    raw_item.missing_fields.append(field)
            if raw_item.quantity and raw_item.total_cost is not None:
                derived_cost = raw_item.total_cost / raw_item.quantity
                if raw_item.average_cost is None:
                    raw_item.average_cost = derived_cost
                    raw_item.semantic_fields["average_cost"] = "TOTAL_COST / QUANTITY"
                elif abs(raw_item.average_cost - derived_cost) > Decimal("0.000001"):
                    raw_item.missing_fields.append("cost_conflict")
            resolved = await HoldingResolver.resolve(
                db, user_id, raw_item.symbol or raw_item.name or raw_item.raw_text
            )

            # Determine existing asset match
            matched_asset: Optional[Asset] = None
            if raw_item.symbol and raw_item.symbol.upper() in assets_by_symbol:
                matched_asset = assets_by_symbol[raw_item.symbol.upper()]
            elif resolved.asset:
                matched_asset = resolved.asset
            elif raw_item.name and raw_item.name.lower() in assets_by_name:
                matched_asset = assets_by_name[raw_item.name.lower()]

            existing_asset_id = matched_asset.id if matched_asset else None
            existing_qty: Optional[Decimal] = None
            if matched_asset:
                # Load stats to get current total quantity
                _, stats = await asset_service.get_asset_with_stats(db, matched_asset.id, user_id)
                existing_qty = stats.get("total_quantity", ZERO)

            # Reconcile intended action
            intended_action = ImportItemAction.NEEDS_REVIEW.value
            item_warnings = list(raw_item.warnings)
            missing = list(raw_item.missing_fields)
            matches = [a for a in existing_assets if raw_item.symbol and a.symbol and a.symbol.upper() == raw_item.symbol.upper()]
            if len(matches) > 1 or resolved.ambiguous_candidates:
                missing.append("instrument_ambiguity")
                item_warnings.append("Birden fazla varlık eşleşiyor; otomatik seçim yapılmaz. Kalemi atlayıp kimliği netleştirin.")

            # Case A: Missing quantity
            if raw_item.quantity is None:
                intended_action = ImportItemAction.NEEDS_REVIEW.value
                if "quantity" not in missing:
                    missing.append("quantity")

            # Case B: No existing holding
            elif matched_asset is None:
                intended_action = ImportItemAction.CREATE_OPENING_POSITION.value

            # Case C: Existing holding detected
            else:
                # User says "add" / "ekle" explicitly in the raw text
                is_explicit_add = bool(re.search(r"\b(add|ekle|ilave)\b", raw_item.raw_text, re.IGNORECASE))
                if is_explicit_add:
                    intended_action = ImportItemAction.ADD_TO_EXISTING_POSITION.value
                else:
                    # Ambiguous between total current position vs increment: requires review!
                    intended_action = ImportItemAction.NEEDS_REVIEW.value
                    item_warnings.append(
                        f"Mevcut {existing_qty} adet {matched_asset.symbol or matched_asset.name} pozisyonunuz var. "
                        f"İçe aktarılan {raw_item.quantity} adedin toplam yeni pozisyon mu (üzerine yaz/açılış güncelle) "
                        f"yoksa ilave mi olduğunu lütfen belirleyin."
                    )

            # Validate Asset Type
            asset_type = raw_item.asset_type
            if not asset_type:
                if resolved.instrument and resolved.instrument.asset_type:
                    asset_type = resolved.instrument.asset_type
                elif raw_item.symbol and raw_item.symbol.upper() in ("BTC", "ETH", "USDT", "SOL", "AVAX"):
                    asset_type = "CRYPTO"
                elif raw_item.symbol in ("HALF", "QUARTER", "TAM", "REPUBLIC", "ATA", "GRAM", "XAU"):
                    asset_type = "PRECIOUS_METALS"
                else:
                    asset_type = "STOCK"

            db_item = PortfolioImportItem(
                batch_id=batch.id,
                raw_input=raw_item.raw_text,
                resolved_instrument_id=resolved.instrument.id if resolved.instrument else None,
                asset_type=asset_type,
                symbol=raw_item.symbol.upper() if raw_item.symbol else (resolved.instrument.symbol if resolved.instrument else None),
                name=raw_item.name or (resolved.instrument.name if resolved.instrument else raw_item.raw_text),
                quantity=raw_item.quantity,
                market_value=raw_item.market_value,
                average_cost=raw_item.average_cost,
                total_cost=raw_item.total_cost,
                currency=raw_item.currency or "USD",
                as_of_date=raw_item.as_of_date or date.today(),
                semantic_fields=raw_item.semantic_fields,
                confidence=raw_item.confidence,
                existing_asset_id=existing_asset_id,
                existing_quantity=existing_qty,
                intended_action=intended_action,
                warnings=item_warnings,
                missing_fields=missing,
            )
            db.add(db_item)
            db_items.append(db_item)

        seen = set()
        for item in db_items:
            identity = (item.symbol or item.name).upper()
            if identity in seen:
                item.missing_fields = list(item.missing_fields or []) + ["duplicate_row"]
                item.intended_action = ImportItemAction.AMBIGUOUS.value
                item.warnings = list(item.warnings or []) + ["Tekrarlanan kalem otomatik toplanmaz. Bu satırı atlayın veya yeni bir taslak hazırlayın."]
            seen.add(identity)

        await db.flush()

        # 5. Compute Batch Readiness
        ready_count = sum(
            1 for it in db_items
            if it.intended_action in (
                ImportItemAction.CREATE_OPENING_POSITION.value,
                ImportItemAction.UPDATE_EXISTING_OPENING_POSITION.value,
                ImportItemAction.ADD_TO_EXISTING_POSITION.value,
                ImportItemAction.SKIP.value,
            ) and not it.missing_fields
        )
        needs_review_count = sum(1 for it in db_items if it.intended_action == ImportItemAction.NEEDS_REVIEW.value or it.missing_fields)
        ambiguous_count = sum(1 for it in db_items if it.intended_action == ImportItemAction.AMBIGUOUS.value)

        is_ready = (not parse_errors and needs_review_count == 0 and ambiguous_count == 0 and len(db_items) > 0)
        batch.status = ImportBatchStatus.READY_FOR_CONFIRMATION.value if is_ready else ImportBatchStatus.PARSED.value

        # 6. Create or Link CopilotActionProposal (Level 3 Confirmation)
        proposal_status = "READY_FOR_CONFIRMATION" if is_ready else "NEEDS_INPUT"
        summary_text = (
            f"{len(db_items)} varlık için portföy içe aktarımı "
            f"({ready_count} hazır, {needs_review_count} inceleme bekleyen, {ambiguous_count} belirsiz)"
        )
        proposal = await CopilotProposalService.create_proposal(
            db=db,
            user_id=user_id,
            conversation_id=conversation_id,
            action_type="PORTFOLIO_IMPORT",
            permission_level="LEVEL_3_STRONG_CONFIRMATION",
            parameters={"batch_id": str(batch.id)},
            human_readable_summary=summary_text,
            expected_impact={
                "total_items": len(db_items),
                "ready_count": ready_count,
                "needs_review_count": needs_review_count,
                "ambiguous_count": ambiguous_count,
            },
            warnings=batch.warnings or [],
            idempotency_key=f"proposal_import_{batch.id.hex}",
            status=proposal_status,
        )
        batch.proposal_id = proposal.id
        await db.commit()

        # Re-fetch with loaded items
        loaded_batch = await cls.get_batch(db, user_id, batch.id)
        return loaded_batch or batch

    @classmethod
    async def get_batch(
        cls, db: AsyncSession, user_id: UUID, batch_id: UUID
    ) -> Optional[PortfolioImportBatch]:
        """Fetch an import batch owned by user with items loaded."""
        res = await db.execute(
            select(PortfolioImportBatch)
            .options(
                selectinload(PortfolioImportBatch.items),
                selectinload(PortfolioImportBatch.proposal),
            )
            .where(
                PortfolioImportBatch.id == batch_id,
                PortfolioImportBatch.user_id == user_id,
            )
        )
        return res.scalar_one_or_none()

    @classmethod
    async def resolve_item(
        cls,
        db: AsyncSession,
        user_id: UUID,
        batch_id: UUID,
        item_id: UUID,
        resolution: ImportItemResolutionRequest,
    ) -> Tuple[PortfolioImportBatch, PortfolioImportItem]:
        """Update an item with user-provided missing values or resolution choices."""
        batch = await cls.get_batch(db, user_id, batch_id)
        if not batch:
            raise ValueError("Import batch bulunamadı veya erişim yetkiniz yok.")
        if batch.status not in ("DRAFT", "PARSED", "READY_FOR_CONFIRMATION") or not batch.proposal or batch.proposal.status not in ("NEEDS_INPUT", "READY_FOR_CONFIRMATION", "DRAFT"):
            raise ValueError("Bu içe aktarım artık düzenlenemez.")
        expiry = batch.proposal.expires_at
        if expiry and expiry.replace(tzinfo=timezone.utc) < datetime.now(timezone.utc):
            raise ValueError("İçe aktarımın süresi doldu.")

        item = next((it for it in batch.items if it.id == item_id), None)
        if not item:
            raise ValueError("İçe aktarım kalemi bulunamadı.")

        # Update supplied fields
        if resolution.quantity is not None:
            item.quantity = Decimal(str(resolution.quantity))
            if "quantity" in (item.missing_fields or []):
                item.missing_fields = [f for f in item.missing_fields if f != "quantity"]

        if resolution.average_cost is not None:
            item.average_cost = Decimal(str(resolution.average_cost))
            item.total_cost = item.average_cost * item.quantity if item.quantity else None
            if "cost_basis_type" in (item.missing_fields or []):
                item.missing_fields = [f for f in item.missing_fields if f != "cost_basis_type"]

        if resolution.currency is not None:
            item.currency = resolution.currency

        if resolution.total_cost is not None:
            item.total_cost = resolution.total_cost
            item.average_cost = item.total_cost / item.quantity if item.quantity else None
            item.missing_fields = [f for f in (item.missing_fields or []) if f != "cost_basis_type"]

        if resolution.selected_instrument_id is not None:
            instrument = await db.get(Instrument, resolution.selected_instrument_id)
            if not instrument or instrument.symbol != item.symbol or instrument.currency != item.currency:
                raise ValueError("Seçilen enstrüman kalem ile eşleşmiyor.")
            item.resolved_instrument_id = resolution.selected_instrument_id

        # Update action resolution choice
        if resolution.action_resolution:
            item.action_resolution = resolution.action_resolution.value
            if resolution.action_resolution == ActionResolutionType.REPLACE_OPENING_STATE:
                item.intended_action = ImportItemAction.UPDATE_EXISTING_OPENING_POSITION.value
            elif resolution.action_resolution == ActionResolutionType.ADD_TO_EXISTING:
                item.intended_action = ImportItemAction.ADD_TO_EXISTING_POSITION.value
            elif resolution.action_resolution == ActionResolutionType.SKIP:
                item.intended_action = ImportItemAction.SKIP.value
                item.missing_fields = []

        # Re-evaluate item readiness
        if not item.missing_fields and item.intended_action in (
            ImportItemAction.NEEDS_REVIEW.value,
            ImportItemAction.AMBIGUOUS.value,
        ):
            if item.existing_asset_id:
                # Quantity alone is never consent to replace or add.
                item.intended_action = ImportItemAction.NEEDS_REVIEW.value
            else:
                item.intended_action = ImportItemAction.CREATE_OPENING_POSITION.value

        item.updated_at = datetime.now(timezone.utc)
        await db.flush()

        # Recompute batch readiness
        ready_count = sum(
            1 for it in batch.items
            if it.intended_action in (
                ImportItemAction.CREATE_OPENING_POSITION.value,
                ImportItemAction.UPDATE_EXISTING_OPENING_POSITION.value,
                ImportItemAction.ADD_TO_EXISTING_POSITION.value,
                ImportItemAction.SKIP.value,
            ) and not it.missing_fields
        )
        needs_review_count = sum(1 for it in batch.items if it.intended_action == ImportItemAction.NEEDS_REVIEW.value or it.missing_fields)
        ambiguous_count = sum(1 for it in batch.items if it.intended_action == ImportItemAction.AMBIGUOUS.value)

        is_ready = (not batch.errors and needs_review_count == 0 and ambiguous_count == 0 and len(batch.items) > 0)
        batch.status = ImportBatchStatus.READY_FOR_CONFIRMATION.value if is_ready else ImportBatchStatus.PARSED.value

        if batch.proposal:
            batch.proposal.status = "READY_FOR_CONFIRMATION" if is_ready else "NEEDS_INPUT"
            batch.proposal.human_readable_summary = (
                f"{len(batch.items)} varlık için portföy içe aktarımı "
                f"({ready_count} hazır, {needs_review_count} inceleme bekleyen, {ambiguous_count} belirsiz)"
            )
            batch.proposal.expected_impact = {
                "total_items": len(batch.items),
                "ready_count": ready_count,
                "needs_review_count": needs_review_count,
                "ambiguous_count": ambiguous_count,
            }

        await db.commit()
        return batch, item

    @classmethod
    async def update_draft_via_message(
        cls,
        db: AsyncSession,
        user_id: UUID,
        conversation_id: UUID,
        message_text: str,
    ) -> Optional[Tuple[PortfolioImportBatch, PortfolioImportItem]]:
        """Multi-turn draft completion: extracts missing quantity or resolution for active draft batch."""
        # Find latest non-applied batch in this conversation
        res = await db.execute(
            select(PortfolioImportBatch)
            .options(selectinload(PortfolioImportBatch.items), selectinload(PortfolioImportBatch.proposal))
            .where(
                PortfolioImportBatch.user_id == user_id,
                PortfolioImportBatch.conversation_id == conversation_id,
                PortfolioImportBatch.status.in_([
                    ImportBatchStatus.DRAFT.value,
                    ImportBatchStatus.PARSED.value,
                    ImportBatchStatus.READY_FOR_CONFIRMATION.value,
                ]),
            )
            .order_by(PortfolioImportBatch.created_at.desc())
        )
        batch = res.scalars().first()
        if not batch or not batch.items:
            return None

        # Look for missing items in batch
        missing_items = [it for it in batch.items if "quantity" in (it.missing_fields or []) or it.intended_action == ImportItemAction.NEEDS_REVIEW.value]
        if not missing_items:
            return None

        # Extract number from message (e.g. "Quantity is 28" or "UBER adedi 28" or "28")
        num_m = re.search(r"(?:adet|quantity|miktar|is|için|icin)?\s*[:=]?\s*(\d+(?:[.,]\d+)?)", message_text, re.IGNORECASE)
        if not num_m:
            return None

        try:
            qty_val = Decimal(num_m.group(1).replace(",", "."))
        except ValueError:
            return None

        # Target item: check if symbol mentioned, otherwise first missing item
        target_item = missing_items[0]
        if len(missing_items) > 1 and not any(it.symbol and re.search(r"\b" + re.escape(it.symbol) + r"\b", message_text, re.IGNORECASE) for it in missing_items):
            return None
        if re.search(r"\b(cost|maliyet|USD|TL|TRY|EUR)\b", message_text, re.IGNORECASE):
            return None
        for it in missing_items:
            if it.symbol and re.search(r"\b" + re.escape(it.symbol) + r"\b", message_text, re.IGNORECASE):
                target_item = it
                break

        resolution = ImportItemResolutionRequest(quantity=qty_val)
        updated_batch, updated_item = await cls.resolve_item(
            db, user_id, batch.id, target_item.id, resolution
        )
        return updated_batch, updated_item

    @classmethod
    def to_batch_response(cls, batch: PortfolioImportBatch) -> PortfolioImportBatchResponse:
        """Convert ORM batch to schema response."""
        items_resp: List[PortfolioImportItemResponse] = []
        for it in batch.items:
            items_resp.append(
                PortfolioImportItemResponse(
                    id=it.id,
                    batch_id=it.batch_id,
                    raw_input=it.raw_input,
                    resolved_instrument_id=it.resolved_instrument_id,
                    asset_type=it.asset_type,
                    symbol=it.symbol,
                    name=it.name,
                    quantity=float(it.quantity) if it.quantity is not None else None,
                    market_value=float(it.market_value) if it.market_value is not None else None,
                    average_cost=float(it.average_cost) if it.average_cost is not None else None,
                    total_cost=float(it.total_cost) if it.total_cost is not None else None,
                    currency=it.currency,
                    as_of_date=it.as_of_date,
                    semantic_fields=it.semantic_fields,
                    confidence=it.confidence,
                    existing_asset_id=it.existing_asset_id,
                    existing_quantity=float(it.existing_quantity) if it.existing_quantity is not None else None,
                    intended_action=ImportItemAction(it.intended_action),
                    action_resolution=ActionResolutionType(it.action_resolution) if it.action_resolution else None,
                    warnings=it.warnings or [],
                    missing_fields=it.missing_fields or [],
                    resulting_asset_id=it.resulting_asset_id,
                    resulting_opening_position_id=it.resulting_opening_position_id,
                    created_at=it.created_at,
                    updated_at=it.updated_at,
                )
            )

        ready_count = sum(1 for it in items_resp if it.intended_action in (
            ImportItemAction.CREATE_OPENING_POSITION,
            ImportItemAction.UPDATE_EXISTING_OPENING_POSITION,
            ImportItemAction.ADD_TO_EXISTING_POSITION,
            ImportItemAction.SKIP,
        ) and not it.missing_fields)
        needs_review_count = sum(1 for it in items_resp if it.intended_action == ImportItemAction.NEEDS_REVIEW or it.missing_fields)
        ambiguous_count = sum(1 for it in items_resp if it.intended_action == ImportItemAction.AMBIGUOUS)

        return PortfolioImportBatchResponse(
            id=batch.id,
            user_id=batch.user_id,
            conversation_id=batch.conversation_id,
            proposal_id=batch.proposal_id,
            source_type=ImportSourceType(batch.source_type),
            source_reference=batch.source_reference,
            status=ImportBatchStatus(batch.status),
            raw_content_preview=batch.raw_content_preview,
            warnings=batch.warnings or [],
            errors=batch.errors or [],
            idempotency_key=batch.idempotency_key,
            created_at=batch.created_at,
            parsed_at=batch.parsed_at,
            confirmed_at=batch.confirmed_at,
            applied_at=batch.applied_at,
            items=items_resp,
            ready_count=ready_count,
            needs_review_count=needs_review_count,
            ambiguous_count=ambiguous_count,
        )
