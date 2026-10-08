"""Deterministic Action Executor for Copilot V2 Phase 3.

CORE SAFETY ARCHITECTURE:
1. Revalidates current state and holdings atomically before commit.
2. If state changed (e.g. insufficient balance on SELL), marks proposal STALE and aborts.
3. Delegates strictly to domain services (app.services.transaction, app.services.decision_log, etc.).
4. Strict idempotency: returns existing result if already EXECUTED/APPLIED without duplicate writes.
5. Strict user ownership validation and row-level locking (with_for_update).
6. Records durable CopilotAuditLog for every execution outcome.
7. Product Boundary: Mutations are internal PortfolioMind bookkeeping records, not broker/exchange orders.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Dict, Optional, Tuple
from uuid import UUID
import uuid

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.asset import Asset, AssetType
from app.models.copilot import CopilotActionProposal, CopilotAuditLog
from app.models.decision_log import DecisionEventType
from app.models.instrument import Instrument
from app.models.opportunity import WatchlistItem, WatchlistPriority
from app.models.transaction import Transaction, TransactionType
from app.schemas.copilot import ActionProposalResponse
from app.schemas.transaction import TransactionCreateRequest
from app.services import (
    decision_log as decision_service,
    instrument as instrument_service,
    transaction as tx_service,
)
from app.services.copilot_v2.action_contracts import (
    ActionProposalStatusV2,
    ActionProposalType,
)
from app.services.portfolio_stats import compute_stats

logger = logging.getLogger(__name__)


class ActionExecutorV2:
    """Executes validated Copilot V2 action proposals deterministically."""

    @classmethod
    async def get_proposal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal_id: UUID,
    ) -> Optional[CopilotActionProposal]:
        """Fetch an action proposal verifying strict user ownership with lazy expiration."""
        stmt = select(CopilotActionProposal).where(
            CopilotActionProposal.id == proposal_id,
            CopilotActionProposal.user_id == user_id,
        )
        res = await db.execute(stmt)
        proposal = res.scalar_one_or_none()
        if proposal and proposal.status in (
            ActionProposalStatusV2.PENDING.value,
            ActionProposalStatusV2.READY_FOR_CONFIRMATION.value,
            "DRAFT",
        ):
            now = datetime.now(timezone.utc)
            if proposal.expires_at:
                exp = proposal.expires_at if proposal.expires_at.tzinfo else proposal.expires_at.replace(tzinfo=timezone.utc)
                if exp < now:
                    proposal.status = ActionProposalStatusV2.EXPIRED.value
                    await db.commit()
                    await db.refresh(proposal)
        return proposal

    @classmethod
    async def execute_proposal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal_id: UUID,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Execute a confirmed action proposal with atomic locking, revalidation, and audit logging."""
        # 1. Fetch proposal with row-level lock (with_for_update)
        stmt = (
            select(CopilotActionProposal)
            .where(
                CopilotActionProposal.id == proposal_id,
                CopilotActionProposal.user_id == user_id,
            )
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        res = await db.execute(stmt)
        proposal = res.scalar_one_or_none()

        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action proposal not found or access denied.",
            )

        # 2. Idempotency Check: Return existing result if already applied/executed
        if proposal.status in (
            ActionProposalStatusV2.EXECUTED.value,
            ActionProposalStatusV2.APPLIED.value,
        ):
            logger.info("Proposal %s already executed; returning existing result.", proposal_id)
            return {
                "status": "success",
                "proposal_id": str(proposal.id),
                "action_type": proposal.action_type,
                "proposal_status": proposal.status,
                "execution_result": proposal.execution_result or {},
                "proposal": ActionProposalResponse.model_validate(proposal).model_dump(mode="json"),
            }

        # 3. Status validation
        if proposal.status not in (
            ActionProposalStatusV2.PENDING.value,
            ActionProposalStatusV2.READY_FOR_CONFIRMATION.value,
            "DRAFT",
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot execute proposal in status '{proposal.status}'.",
            )

        # 4. Expiration check
        now = datetime.now(timezone.utc)
        if proposal.expires_at:
            exp = proposal.expires_at if proposal.expires_at.tzinfo else proposal.expires_at.replace(tzinfo=timezone.utc)
            if exp < now:
                proposal.status = ActionProposalStatusV2.EXPIRED.value
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Action proposal has expired.",
                )

        params = dict(proposal.parameters or {})
        affected_type = "UNKNOWN"
        affected_id: Optional[str] = None
        result_data: Dict[str, Any] = {}

        try:
            # 5. Dispatch by action_type
            if proposal.action_type in (
                ActionProposalType.TRANSACTION_RECORD.value,
                "BUY_TRANSACTION",
                "SELL_TRANSACTION",
                "BUY",
                "SELL",
            ):
                result_data, affected_type, affected_id = await cls._execute_transaction(
                    db=db, user_id=user_id, proposal=proposal, params=params
                )

            elif proposal.action_type in (
                ActionProposalType.WATCHLIST_CHANGE.value,
                "ADD_WATCHLIST",
                "REMOVE_WATCHLIST",
            ):
                result_data, affected_type, affected_id = await cls._execute_watchlist_change(
                    db=db, user_id=user_id, proposal=proposal, params=params
                )

            elif proposal.action_type in (
                ActionProposalType.DECISION_NOTE.value,
                "CREATE_JOURNAL_ENTRY",
                "JOURNAL_ENTRY",
            ):
                result_data, affected_type, affected_id = await cls._execute_decision_note(
                    db=db, user_id=user_id, proposal=proposal, params=params
                )

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported action type '{proposal.action_type}' for V2 ActionExecutor.",
                )

            # 6. Record durable CopilotAuditLog
            audit_entry = CopilotAuditLog(
                user_id=user_id,
                proposal_id=proposal.id,
                action_type=proposal.action_type,
                idempotency_key=proposal.idempotency_key,
                user_request=params.get("user_request"),
                interpreted_intent=proposal.action_type,
                affected_resource_type=affected_type,
                affected_resource_id=affected_id,
                old_state=proposal.current_state_snapshot,
                new_state=result_data,
                execution_status="SUCCESS",
                error_message=None,
                created_at=datetime.now(timezone.utc),
            )
            db.add(audit_entry)

            # 7. Update proposal lifecycle
            proposal.status = ActionProposalStatusV2.EXECUTED.value
            proposal.confirmed_at = proposal.confirmed_at or datetime.now(timezone.utc)
            proposal.applied_at = datetime.now(timezone.utc)
            proposal.execution_result = result_data

            # Synchronize conversation messages holding this proposal snapshot so conversation reloads reflect EXECUTED
            from sqlalchemy.orm.attributes import flag_modified
            from app.models.copilot import CopilotConversation, CopilotMessage
            prop_str_id = str(proposal.id)
            msg_stmt = (
                select(CopilotMessage)
                .join(CopilotConversation, CopilotMessage.conversation_id == CopilotConversation.id)
                .where(CopilotConversation.user_id == user_id)
            )
            conv_msgs = (await db.execute(msg_stmt)).scalars().all()
            for msg in conv_msgs:
                if msg.structured_metadata and isinstance(msg.structured_metadata, dict):
                    msg_prop = msg.structured_metadata.get("proposal")
                    if msg_prop and isinstance(msg_prop, dict) and str(msg_prop.get("id")) == prop_str_id:
                        msg_prop["status"] = ActionProposalStatusV2.EXECUTED.value
                        if proposal.confirmed_at:
                            msg_prop["confirmed_at"] = proposal.confirmed_at.isoformat()
                        if proposal.applied_at:
                            msg_prop["applied_at"] = proposal.applied_at.isoformat()
                        msg_prop["execution_result"] = result_data
                        flag_modified(msg, "structured_metadata")

            # 8. Atomically commit all domain mutations
            await db.commit()
            await db.refresh(proposal)

            logger.info("Successfully executed action proposal %s (%s)", proposal_id, proposal.action_type)
            return {
                "status": "success",
                "proposal_id": str(proposal.id),
                "action_type": proposal.action_type,
                "proposal_status": proposal.status,
                "execution_result": result_data,
                "proposal": ActionProposalResponse.model_validate(proposal).model_dump(mode="json"),
            }

        except Exception as exc:
            await db.rollback()
            logger.exception("Error executing proposal %s: %s", proposal_id, exc)

            # Record failure in isolated transaction if not already marked STALE/EXPIRED
            try:
                fail_stmt = select(CopilotActionProposal).where(CopilotActionProposal.id == proposal_id)
                fail_res = await db.execute(fail_stmt)
                p = fail_res.scalar_one_or_none()
                if p and p.status not in (ActionProposalStatusV2.STALE.value, ActionProposalStatusV2.EXPIRED.value):
                    p.status = ActionProposalStatusV2.FAILED.value
                    audit_fail = CopilotAuditLog(
                        user_id=user_id,
                        proposal_id=proposal_id,
                        action_type=proposal.action_type,
                        idempotency_key=proposal.idempotency_key,
                        user_request=params.get("user_request"),
                        interpreted_intent=proposal.action_type,
                        affected_resource_type="ERROR",
                        affected_resource_id=None,
                        old_state=proposal.current_state_snapshot,
                        new_state=None,
                        execution_status="FAILED",
                        error_message=str(exc),
                        created_at=datetime.now(timezone.utc),
                    )
                    db.add(audit_fail)
                    await db.commit()
            except Exception:
                pass

            if isinstance(exc, HTTPException):
                raise exc
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"İşlem uygulanamadı: {str(exc)}",
            )

    @classmethod
    async def cancel_proposal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal_id: UUID,
        reason: Optional[str] = None,
    ) -> CopilotActionProposal:
        """Cancel a pending action proposal."""
        stmt = (
            select(CopilotActionProposal)
            .where(
                CopilotActionProposal.id == proposal_id,
                CopilotActionProposal.user_id == user_id,
            )
            .with_for_update()
        )
        res = await db.execute(stmt)
        proposal = res.scalar_one_or_none()

        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action proposal not found or access denied.",
            )

        if proposal.status in (
            ActionProposalStatusV2.EXECUTED.value,
            ActionProposalStatusV2.APPLIED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel an already executed proposal.",
            )

        proposal.status = ActionProposalStatusV2.CANCELLED.value
        if reason:
            warnings = list(proposal.warnings or [])
            warnings.append(f"İptal gerekçesi: {reason}")
            proposal.warnings = warnings

        # Synchronize conversation messages holding this proposal snapshot so conversation reloads reflect CANCELLED
        from sqlalchemy.orm.attributes import flag_modified
        from app.models.copilot import CopilotConversation, CopilotMessage
        prop_str_id = str(proposal.id)
        msg_stmt = (
            select(CopilotMessage)
            .join(CopilotConversation, CopilotMessage.conversation_id == CopilotConversation.id)
            .where(CopilotConversation.user_id == user_id)
        )
        conv_msgs = (await db.execute(msg_stmt)).scalars().all()
        for msg in conv_msgs:
            if msg.structured_metadata and isinstance(msg.structured_metadata, dict):
                msg_prop = msg.structured_metadata.get("proposal")
                if msg_prop and isinstance(msg_prop, dict) and str(msg_prop.get("id")) == prop_str_id:
                    msg_prop["status"] = ActionProposalStatusV2.CANCELLED.value
                    msg_prop["cancellation_reason"] = reason
                    flag_modified(msg, "structured_metadata")

        await db.commit()
        await db.refresh(proposal)
        return proposal

    # -----------------------------------------------------------------------
    # Domain Execution Handlers
    # -----------------------------------------------------------------------

    @classmethod
    async def _execute_transaction(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal: CopilotActionProposal,
        params: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], str, str]:
        """Execute BUY or SELL transaction bookkeeping via transaction_service."""
        symbol = params.get("symbol")
        name = params.get("name") or symbol
        tx_type_str = (params.get("transaction_type") or "BUY").upper()
        qty = Decimal(str(params.get("quantity", "1.0")))
        price = Decimal(str(params.get("price") or params.get("unit_price") or "0.0"))
        currency = params.get("currency") or "TRY"
        tx_date_raw = params.get("transaction_date") or str(date.today())
        affects_cash = bool(params.get("affects_cash", True))
        notes = params.get("notes")
        asset_id_raw = params.get("asset_id")

        parsed_date = date.fromisoformat(tx_date_raw) if isinstance(tx_date_raw, str) else tx_date_raw

        # 1. Resolve Asset
        asset: Optional[Asset] = None
        if asset_id_raw:
            asset_res = await db.execute(
                select(Asset)
                .options(selectinload(Asset.opening_position), selectinload(Asset.instrument))
                .where(Asset.id == UUID(asset_id_raw), Asset.user_id == user_id)
            )
            asset = asset_res.scalar_one_or_none()

        if not asset and symbol:
            asset_res = await db.execute(
                select(Asset)
                .options(selectinload(Asset.opening_position), selectinload(Asset.instrument))
                .where(Asset.user_id == user_id, Asset.symbol == symbol)
            )
            asset = asset_res.scalar_one_or_none()

        # 2. Revalidate Current Holding for SELL (Stale Detection)
        if tx_type_str == "SELL":
            if not asset:
                proposal.status = ActionProposalStatusV2.STALE.value
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Portföyünüzde '{symbol}' varlığı bulunamadı. Öneri geçerliliğini yitirdi (STALE).",
                )

            tx_stmt = select(Transaction).where(Transaction.asset_id == asset.id)
            txns = list((await db.execute(tx_stmt)).scalars().all())
            stats = compute_stats(txns, opening_position=asset.opening_position)
            current_qty = Decimal(str(stats.get("total_quantity", "0")))

            if current_qty < qty:
                proposal.status = ActionProposalStatusV2.STALE.value
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=(
                        f"Varlık pozisyonu değişti (Mevcut bakiye: {current_qty}, Satılmak istenen: {qty}). "
                        "Yetersiz bakiye nedeniyle öneri iptal edildi (STALE)."
                    ),
                )

        # 3. If BUY and asset doesn't exist yet, create Asset position and Instrument
        if not asset:
            asset_type_str = AssetType.STOCK.value
            if symbol and symbol.upper() in {"HALF", "QUARTER", "TAM", "GRAM", "ATA", "REPUBLIC"}:
                asset_type_str = AssetType.PRECIOUS_METALS.value
            elif symbol and symbol.upper() in {"BTC", "ETH", "SOL", "USDT"}:
                asset_type_str = AssetType.CRYPTO.value
            elif symbol and symbol.endswith(".IS"):
                asset_type_str = AssetType.STOCK.value

            inst = await instrument_service.find_or_create_instrument(
                db,
                name=name or symbol or "Asset",
                symbol=symbol,
                asset_type=AssetType(asset_type_str),
                currency=currency,
            )
            asset = Asset(
                user_id=user_id,
                instrument_id=inst.id,
                name=name or symbol or "Asset",
                symbol=symbol,
                asset_type=AssetType(asset_type_str),
                current_price=price if price > 0 else None,
                current_price_currency=currency,
            )
            db.add(asset)
            await db.flush()

        tx_type_enum = TransactionType.BUY if tx_type_str == "BUY" else TransactionType.SELL

        # 4. Stage transaction and cash effect via domain service
        tx = await tx_service.stage_transaction(
            db=db,
            asset_id=asset.id,
            data=TransactionCreateRequest(
                transaction_type=tx_type_enum,
                quantity=qty,
                price_per_unit=price,
                transaction_currency=currency,
                transaction_date=parsed_date,
                notes=notes,
                affects_cash=affects_cash,
            ),
            user_id=user_id,
        )

        result_data = {
            "transaction_id": str(tx.id),
            "asset_id": str(asset.id),
            "symbol": asset.symbol,
            "name": asset.name,
            "transaction_type": tx_type_str,
            "quantity": float(tx.quantity),
            "price_per_unit": float(tx.price_per_unit),
            "total_amount": float(tx.total_amount),
            "currency": tx.transaction_currency,
            "affects_cash": tx.affects_cash,
            "transaction_date": str(tx.transaction_date),
            "notice": "PortfolioMind portföy kayıtlarına işlendi. (Borsa/kurum emri değildir)",
        }
        return result_data, "TRANSACTION", str(tx.id)

    @classmethod
    async def _execute_watchlist_change(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal: CopilotActionProposal,
        params: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], str, str]:
        """Execute adding or removing an item from the user's watchlist."""
        symbol = params.get("symbol")
        name = params.get("name") or symbol
        action = (params.get("action") or "ADD").upper()
        priority_str = (params.get("priority") or "MEDIUM").upper()
        notes = params.get("notes")
        inst_id_raw = params.get("instrument_id")

        inst_id: Optional[UUID] = UUID(inst_id_raw) if inst_id_raw else None

        if not inst_id and symbol:
            inst = await instrument_service.find_or_create_instrument(
                db,
                name=name or symbol,
                symbol=symbol,
                asset_type=AssetType.STOCK,
            )
            inst_id = inst.id

        if not inst_id:
            raise HTTPException(400, "Geçerli bir enstrüman bulunamadı.")

        if action == "ADD":
            wl_stmt = select(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.instrument_id == inst_id,
            )
            existing = (await db.execute(wl_stmt)).scalar_one_or_none()

            priority_enum = WatchlistPriority.MEDIUM
            try:
                priority_enum = WatchlistPriority[priority_str]
            except Exception:
                pass

            if not existing:
                item = WatchlistItem(
                    user_id=user_id,
                    instrument_id=inst_id,
                    priority=priority_enum,
                    notes=notes,
                )
                db.add(item)
                await db.flush()
                item_id = str(item.id)
            else:
                item_id = str(existing.id)

            result_data = {
                "watchlist_item_id": item_id,
                "instrument_id": str(inst_id),
                "symbol": symbol,
                "action": "ADD",
                "message": f"{symbol} izleme listenize eklendi.",
            }
            return result_data, "WATCHLIST_ITEM", item_id

        else:  # REMOVE
            wl_stmt = select(WatchlistItem).where(
                WatchlistItem.user_id == user_id,
                WatchlistItem.instrument_id == inst_id,
            )
            existing = (await db.execute(wl_stmt)).scalar_one_or_none()
            if existing:
                await db.delete(existing)

            result_data = {
                "instrument_id": str(inst_id),
                "symbol": symbol,
                "action": "REMOVE",
                "message": f"{symbol} izleme listenizden çıkarıldı.",
            }
            return result_data, "WATCHLIST_ITEM", str(inst_id)

    @classmethod
    async def _execute_decision_note(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal: CopilotActionProposal,
        params: Dict[str, Any],
    ) -> Tuple[Dict[str, Any], str, str]:
        """Execute creating a note in the formal decision log."""
        title = params.get("title") or "Copilot Karar Notu"
        notes = params.get("notes") or ""
        inst_id_raw = params.get("instrument_id")
        expectation = params.get("expectation")
        confidence = params.get("confidence")

        inst_id: Optional[UUID] = UUID(inst_id_raw) if inst_id_raw else None

        entry = await decision_service.log_decision_event(
            db=db,
            user_id=user_id,
            event_type=DecisionEventType.MANUAL_DECISION_NOTE,
            title=title,
            summary=notes,
            instrument_id=inst_id,
            user_rationale=notes,
            expectation=expectation,
            confidence=confidence,
            occurred_at=datetime.now(timezone.utc),
        )

        result_data = {
            "decision_entry_id": str(entry.id),
            "title": title,
            "instrument_id": str(inst_id) if inst_id else None,
            "message": "Karar günlüğüne başarıyla kaydedildi.",
        }
        return result_data, "DECISION_LOG", str(entry.id)
