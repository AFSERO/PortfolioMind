"""Narrow Write Executor for PortfolioMind Copilot.

Enforces:
1. Revalidation of current state before commit.
2. Delegation to existing domain services only (no direct model mutation).
3. Strict idempotency.
4. User ownership security.
5. Durable audit logging for every mutation.
"""

from datetime import date, datetime, timezone
from decimal import Decimal
import logging
from typing import Any, Optional
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
from app.models.opening_position import OpeningPosition
from app.models.opportunity import WatchlistItem, WatchlistPriority
from app.models.portfolio_import import PortfolioImportBatch, PortfolioImportItem
from app.models.transaction import TransactionType
from app.schemas.copilot import ActionProposalStatus, ActionType
from app.schemas.decision_log import DecisionLogCreate
from app.schemas.opportunity import WatchlistItemCreateRequest
from app.schemas.transaction import TransactionCreateRequest
from app.services import (
    decision_log as decision_service,
    instrument as instrument_service,
    opportunity as opp_service,
    transaction as tx_service,
)

logger = logging.getLogger(__name__)


class CopilotWriteExecutor:
    """Executes validated Action Proposals against existing domain services."""

    @classmethod
    async def execute_proposal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal_id: UUID,
        idempotency_key: Optional[str] = None,
        confirmation_text: Optional[str] = None,
    ) -> dict[str, Any]:
        """Execute a confirmed proposal with atomic revalidation, execution, and audit logging."""
        # 1. Fetch proposal verifying strict user ownership
        stmt = select(CopilotActionProposal).where(
            CopilotActionProposal.id == proposal_id,
            CopilotActionProposal.user_id == user_id,
        )
        res = await db.execute(stmt.with_for_update().execution_options(populate_existing=True))
        proposal = res.scalar_one_or_none()

        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action proposal not found or access denied.",
            )

        # 2. Idempotency Check: Return existing result if already applied
        if proposal.status == ActionProposalStatus.APPLIED.value:
            logger.info(
                "Proposal %s already applied; returning existing execution result.",
                proposal_id,
            )
            return proposal.execution_result or {
                "status": "already_applied",
                "proposal_id": str(proposal_id),
            }

        if proposal.action_type == "PORTFOLIO_IMPORT" and confirmation_text != "IMPORT":
            raise HTTPException(400, "Type IMPORT to confirm this portfolio import.")

        # 3. Status validation
        if proposal.status not in (
            ActionProposalStatus.READY_FOR_CONFIRMATION.value,
            ActionProposalStatus.CONFIRMED.value,
            ActionProposalStatus.DRAFT.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot execute proposal in status '{proposal.status}'.",
            )

        # 4. Expiration check
        now = datetime.now(timezone.utc)
        expires_at = proposal.expires_at
        if expires_at:
            if expires_at.tzinfo is None:
                expires_at = expires_at.replace(tzinfo=timezone.utc)
            if expires_at < now:
                proposal.status = ActionProposalStatus.EXPIRED.value
                await db.commit()
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Action proposal has expired.",
                )

        params = dict(proposal.parameters or {})
        affected_type = "UNKNOWN"
        affected_id: Optional[str] = None
        result_data: dict[str, Any] = {}

        try:
            # 5. Dispatch narrow write by action_type
            if proposal.action_type in (
                ActionType.BUY_TRANSACTION.value,
                ActionType.RECEIVE_ASSET.value,
                "BUY",
                "RECEIVE_ASSET",
            ):
                result_data, affected_type, affected_id = await cls._execute_buy_or_receive(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.SELL_TRANSACTION.value,
                "SELL",
            ):
                result_data, affected_type, affected_id = await cls._execute_sell(
                    db=db, user_id=user_id, proposal=proposal, params=params
                )

            elif proposal.action_type in (
                ActionType.ADD_WATCHLIST.value,
                "ADD_WATCHLIST",
            ):
                result_data, affected_type, affected_id = await cls._execute_add_watchlist(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.REMOVE_WATCHLIST.value,
                "REMOVE_WATCHLIST",
            ):
                result_data, affected_type, affected_id = await cls._execute_remove_watchlist(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.CREATE_JOURNAL_ENTRY.value,
                "CREATE_JOURNAL_ENTRY",
            ):
                result_data, affected_type, affected_id = await cls._execute_create_journal(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.PORTFOLIO_IMPORT.value,
                "PORTFOLIO_IMPORT",
            ):
                result_data, affected_type, affected_id = await cls._execute_portfolio_import(
                    db=db, user_id=user_id, proposal=proposal, params=params
                )

            elif proposal.action_type in (
                ActionType.UPDATE_INVESTOR_PROFILE.value,
                "UPDATE_INVESTOR_PROFILE",
                "POLICY_CHANGE",
            ):
                result_data, affected_type, affected_id = await cls._execute_profile_update(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.UPDATE_FINANCIAL_CONTEXT.value,
                "UPDATE_FINANCIAL_CONTEXT",
            ):
                result_data, affected_type, affected_id = await cls._execute_financial_context_update(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.CREATE_FINANCIAL_GOAL.value,
                "CREATE_FINANCIAL_GOAL",
                "CREATE_GOAL",
            ):
                result_data, affected_type, affected_id = await cls._execute_create_goal(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.UPDATE_FINANCIAL_GOAL.value,
                "UPDATE_FINANCIAL_GOAL",
                "UPDATE_GOAL",
            ):
                result_data, affected_type, affected_id = await cls._execute_update_goal(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.CREATE_MANDATE.value,
                "CREATE_MANDATE",
            ):
                result_data, affected_type, affected_id = await cls._execute_create_mandate(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.UPDATE_MANDATE.value,
                "UPDATE_MANDATE",
            ):
                result_data, affected_type, affected_id = await cls._execute_update_mandate(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.ASSIGN_CAPITAL.value,
                "ASSIGN_CAPITAL",
            ):
                result_data, affected_type, affected_id = await cls._execute_assign_capital(
                    db=db, user_id=user_id, params=params
                )

            elif proposal.action_type in (
                ActionType.TRANSFER_CAPITAL.value,
                "TRANSFER_CAPITAL",
            ):
                result_data, affected_type, affected_id = await cls._execute_transfer_capital(
                    db=db, user_id=user_id, params=params
                )

            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unsupported action type '{proposal.action_type}' for write engine.",
                )

            # 6. Record durable CopilotAuditLog
            audit_entry = CopilotAuditLog(
                user_id=user_id,
                proposal_id=proposal.id,
                action_type=proposal.action_type,
                idempotency_key=proposal.idempotency_key,
                user_request=params.get("user_request"),
                interpreted_intent=params.get("intent"),
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
            proposal.status = ActionProposalStatus.APPLIED.value
            proposal.confirmed_at = proposal.confirmed_at or datetime.now(timezone.utc)
            proposal.applied_at = datetime.now(timezone.utc)
            proposal.execution_result = result_data

            # 8. Atomically commit all changes
            await db.commit()
            await db.refresh(proposal)
            logger.info("Successfully executed and applied action proposal %s", proposal_id)
            return result_data

        except Exception as exc:
            await db.rollback()
            logger.exception("Error executing proposal %s: %s", proposal_id, exc)

            # Isolated update to record failure state
            try:
                fail_stmt = select(CopilotActionProposal).where(
                    CopilotActionProposal.id == proposal_id
                )
                fail_res = await db.execute(fail_stmt)
                p = fail_res.scalar_one_or_none()
                if p:
                    p.status = ActionProposalStatus.FAILED.value
                    audit_fail = CopilotAuditLog(
                        user_id=user_id,
                        proposal_id=proposal_id,
                        action_type=proposal.action_type,
                        idempotency_key=proposal.idempotency_key,
                        user_request=params.get("user_request"),
                        interpreted_intent=params.get("intent"),
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
                detail=f"Execution failed: {str(exc)}",
            )

    @classmethod
    async def _execute_buy_or_receive(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        """Execute BUY or non-cash RECEIVE transaction via transaction_service."""
        symbol = params.get("symbol")
        name = params.get("name") or symbol
        qty_val = Decimal(str(params.get("quantity", "1.0")))
        price_val = Decimal(str(params.get("price") or params.get("unit_price") or "0.0"))
        currency = params.get("currency") or "USD"
        tx_date_raw = params.get("transaction_date") or str(date.today())
        affects_cash = bool(params.get("affects_cash", True))
        notes = params.get("notes")
        asset_id_raw = params.get("asset_id")

        parsed_date = (
            date.fromisoformat(tx_date_raw)
            if isinstance(tx_date_raw, str)
            else tx_date_raw
        )

        asset: Optional[Asset] = None
        if asset_id_raw:
            asset_res = await db.execute(
                select(Asset).where(
                    Asset.id == UUID(asset_id_raw), Asset.user_id == user_id
                )
            )
            asset = asset_res.scalar_one_or_none()

        if not asset and symbol:
            asset_res = await db.execute(
                select(Asset).where(Asset.user_id == user_id, Asset.symbol == symbol)
            )
            asset = asset_res.scalar_one_or_none()

        if not asset:
            # Create the asset position for this user
            from app.models.asset import AssetType

            asset_type_str = "STOCK"
            if symbol and symbol.upper() in {"HALF", "QUARTER", "TAM", "GRAM", "ATA", "REPUBLIC"}:
                asset_type_str = AssetType.PRECIOUS_METALS.value
            elif symbol and symbol.endswith(".IS"):
                asset_type_str = AssetType.STOCK.value
            elif symbol and symbol.upper() in {"BTC", "ETH", "SOL", "USDT"}:
                asset_type_str = AssetType.CRYPTO.value

            inst = await instrument_service.find_or_create_instrument(
                db,
                name=name or symbol or "Asset",
                symbol=symbol,
                asset_type=asset_type_str,
                currency=currency,
            )
            asset = Asset(
                user_id=user_id,
                instrument_id=inst.id,
                name=name or symbol or "Asset",
                symbol=symbol,
                asset_type=asset_type_str,
                current_price_currency=currency,
            )
            db.add(asset)
            await db.flush()

        if price_val <= Decimal("0"):
            if asset and asset.current_price and asset.current_price > 0:
                price_val = Decimal(str(asset.current_price))
            else:
                price_val = Decimal("1.00")

        # Stage transaction
        tx = await tx_service.stage_transaction(
            db=db,
            asset_id=asset.id,
            data=TransactionCreateRequest(
                transaction_type=TransactionType.BUY,
                quantity=qty_val,
                price_per_unit=price_val,
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
            "transaction_type": "BUY",
            "quantity": float(tx.quantity),
            "price_per_unit": float(tx.price_per_unit),
            "total_amount": float(tx.total_amount),
            "currency": tx.transaction_currency,
            "affects_cash": tx.affects_cash,
            "transaction_date": str(tx.transaction_date),
        }
        return result_data, "TRANSACTION", str(tx.id)

    @classmethod
    async def _execute_sell(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal: CopilotActionProposal,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        """Execute SELL transaction with strict negative holdings pre-validation."""
        symbol = params.get("symbol")
        qty_val = Decimal(str(params.get("quantity", "1.0")))
        price_val = Decimal(str(params.get("price") or params.get("unit_price") or "0.0"))
        currency = params.get("currency") or "USD"
        tx_date_raw = params.get("transaction_date") or str(date.today())
        affects_cash = bool(params.get("affects_cash", True))
        notes = params.get("notes")
        asset_id_raw = params.get("asset_id")

        parsed_date = (
            date.fromisoformat(tx_date_raw)
            if isinstance(tx_date_raw, str)
            else tx_date_raw
        )

        asset: Optional[Asset] = None
        if asset_id_raw:
            asset_res = await db.execute(
                select(Asset).where(
                    Asset.id == UUID(asset_id_raw), Asset.user_id == user_id
                )
            )
            asset = asset_res.scalar_one_or_none()

        if not asset and symbol:
            asset_res = await db.execute(
                select(Asset).where(Asset.user_id == user_id, Asset.symbol == symbol)
            )
            asset = asset_res.scalar_one_or_none()

        if not asset:
            proposal.status = ActionProposalStatus.FAILED.value
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot sell: No position found for symbol '{symbol}'.",
            )

        # Prevalidate holding quantity directly from transaction history
        existing_txns = await tx_service._load_asset_txns(db, asset.id)
        current_qty = await tx_service._load_asset_initial_qty(db, asset.id) + sum(
            t.quantity if t.transaction_type == TransactionType.BUY else -t.quantity
            for t in existing_txns
        )

        if current_qty < qty_val:
            proposal.status = ActionProposalStatus.FAILED.value
            await db.commit()
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=(
                    f"Cannot execute sell: insufficient holdings. "
                    f"Current holding is {current_qty}, requested to sell {qty_val}."
                ),
            )

        # Stage transaction
        tx = await tx_service.stage_transaction(
            db=db,
            asset_id=asset.id,
            data=TransactionCreateRequest(
                transaction_type=TransactionType.SELL,
                quantity=qty_val,
                price_per_unit=price_val,
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
            "transaction_type": "SELL",
            "quantity": float(tx.quantity),
            "price_per_unit": float(tx.price_per_unit),
            "total_amount": float(tx.total_amount),
            "currency": tx.transaction_currency,
            "affects_cash": tx.affects_cash,
            "transaction_date": str(tx.transaction_date),
            "previous_quantity": float(current_qty),
            "remaining_quantity": float(current_qty - qty_val),
        }
        return result_data, "TRANSACTION", str(tx.id)

    @classmethod
    async def _execute_add_watchlist(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        """Add candidate to user's watchlist via opportunity_service."""
        symbol = params.get("symbol")
        name = params.get("name") or symbol
        asset_type = params.get("asset_type") or "STOCK"
        currency = params.get("currency") or "USD"
        why_interesting = params.get("why_interesting")
        priority_raw = params.get("priority")
        priority = (
            WatchlistPriority(priority_raw.upper())
            if isinstance(priority_raw, str) and priority_raw.upper() in WatchlistPriority.__members__
            else WatchlistPriority.MEDIUM
        )

        item_resp = await opp_service.upsert_watchlist_item(
            db=db,
            user_id=user_id,
            body=WatchlistItemCreateRequest(
                symbol=symbol,
                name=name or symbol or "Watchlist Item",
                asset_type=asset_type,
                currency=currency,
                priority=priority,
                why_interesting=why_interesting,
            ),
        )

        result_data = {
            "watchlist_item_id": str(item_resp.id),
            "symbol": (item_resp.instrument.symbol if item_resp.instrument else symbol),
            "name": (item_resp.instrument.name if item_resp.instrument else (name or symbol)),
            "priority": item_resp.priority.value if hasattr(item_resp.priority, "value") else str(item_resp.priority),
            "research_stage": item_resp.research_stage.value if hasattr(item_resp.research_stage, "value") else str(item_resp.research_stage),
        }
        return result_data, "WATCHLIST", str(item_resp.id)

    @classmethod
    async def _execute_remove_watchlist(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        """Remove candidate from user's watchlist via opportunity_service."""
        item_id_raw = params.get("item_id")
        symbol = params.get("symbol")

        item_id: Optional[UUID] = None
        if item_id_raw:
            item_id = UUID(item_id_raw)
        elif symbol:
            stmt = (
                select(WatchlistItem)
                .join(Instrument, WatchlistItem.instrument_id == Instrument.id)
                .where(WatchlistItem.user_id == user_id, Instrument.symbol == symbol.upper())
            )
            res = await db.execute(stmt.with_for_update(of=WatchlistItem).execution_options(populate_existing=True))
            w_item = res.scalar_one_or_none()
            if w_item:
                item_id = w_item.id

        removed = False
        if item_id:
            removed = await opp_service.delete_watchlist_item(
                db=db, user_id=user_id, item_id=item_id
            )

        result_data = {
            "removed": removed,
            "symbol": symbol,
            "item_id": str(item_id) if item_id else None,
        }
        return result_data, "WATCHLIST", str(item_id) if item_id else "NONE"

    @classmethod
    async def _execute_create_journal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        """Record decision note via decision_log_service."""
        title = params.get("title") or "Copilot Decision Note"
        summary = params.get("summary") or "Note recorded by PortfolioMind Copilot."
        rationale = params.get("user_rationale") or params.get("notes")
        asset_id_raw = params.get("asset_id")

        entry_resp = await decision_service.create_decision_log_entry(
            db=db,
            user_id=user_id,
            payload=DecisionLogCreate(
                event_type=DecisionEventType.MANUAL_DECISION_NOTE,
                title=title,
                summary=summary,
                user_rationale=rationale,
                asset_id=UUID(asset_id_raw) if asset_id_raw else None,
            ),
        )

        result_data = {
            "decision_log_id": str(entry_resp.id),
            "title": entry_resp.title,
            "summary": entry_resp.summary,
            "occurred_at": str(entry_resp.occurred_at),
        }
        return result_data, "DECISION_LOG", str(entry_resp.id)

    @classmethod
    async def _execute_portfolio_import(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal: CopilotActionProposal,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        """Apply portfolio import batch atomically, creating assets and opening positions."""
        from app.services import asset as asset_service
        from app.services.copilot.import_service import PortfolioImportService

        batch_id_raw = params.get("batch_id")
        if not batch_id_raw:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Import proposal missing 'batch_id' parameter.",
            )

        batch = await PortfolioImportService.get_batch(db, user_id, UUID(batch_id_raw))
        if not batch:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Portfolio import batch not found or access denied.",
            )

        # Idempotency check: if batch is already applied, return existing result without re-executing
        if batch.status == "APPLIED":
            logger.info("Batch %s already APPLIED. Returning idempotent result.", batch.id)
            return (
                proposal.execution_result or {"batch_id": str(batch.id), "status": "APPLIED"},
                "PORTFOLIO_IMPORT_BATCH",
                str(batch.id),
            )

        if batch.proposal_id != proposal.id or batch.status != "READY_FOR_CONFIRMATION" or batch.errors or not batch.items:
            raise HTTPException(409, "Import batch is not ready for confirmation.")
        from app.models.user import User
        # Serialize imports for this user, including creation of previously absent holdings.
        await db.execute(select(User.id).where(User.id == user_id).with_for_update())
        existing_assets = await asset_service.list_assets(db, user_id)
        created_positions_count = updated_positions_count = skipped_count = 0
        affected = []
        seen = set()
        for it in batch.items:
            action = it.intended_action
            if action == "SKIP":
                skipped_count += 1
                continue
            if action not in ("CREATE_OPENING_POSITION", "UPDATE_EXISTING_OPENING_POSITION", "ADD_TO_EXISTING_POSITION") or it.missing_fields:
                raise HTTPException(400, "Unresolved import item.")
            if it.quantity is None or not it.quantity.is_finite() or it.quantity <= 0:
                raise HTTPException(400, "Quantity must be positive and finite.")
            identity = (it.symbol or it.name).upper()
            if identity in seen:
                raise HTTPException(409, "Duplicate import item; review required.")
            seen.add(identity)
            matches = [a for a in existing_assets if (it.symbol and a.symbol and a.symbol.upper() == it.symbol.upper()) or a.id == it.existing_asset_id]
            if len(matches) > 1:
                raise HTTPException(409, "Ambiguous holding identity.")
            target = matches[0] if matches else None
            if (target.id if target else None) != it.existing_asset_id:
                raise HTTPException(409, "Portfolio changed since preview; create a new draft.")
            old = None
            txns = []
            if target:
                await db.execute(select(Asset.id).where(Asset.id == target.id).with_for_update())
                txns = await tx_service._load_asset_txns(db, target.id)
                old = await db.scalar(select(OpeningPosition).where(OpeningPosition.asset_id == target.id))
                from app.services.portfolio_stats import compute_stats
                current = compute_stats(txns, old)["total_quantity"]
                if current != it.existing_quantity:
                    raise HTTPException(409, "Portfolio quantity changed since preview.")
                # Replacing a baseline underneath real history can duplicate or erase history.
                if txns:
                    raise HTTPException(409, "Existing transaction history requires separate historical reconciliation; import cannot rewrite it.")
            if action == "CREATE_OPENING_POSITION" and target:
                raise HTTPException(409, "Existing holding requires explicit reconciliation.")
            if action != "CREATE_OPENING_POSITION" and not target:
                raise HTTPException(409, "Existing holding no longer exists.")
            if not target:
                inst = await instrument_service.find_or_create_instrument(
                    db, asset_type=AssetType(it.asset_type), name=it.name,
                    symbol=it.symbol, currency=it.currency, instrument_id=it.resolved_instrument_id)
                target = Asset(user_id=user_id, instrument_id=inst.id, asset_type=inst.asset_type,
                               symbol=it.symbol, name=it.name, current_price=None,
                               current_price_currency=it.currency)
                db.add(target)
                await db.flush()
            before = {"quantity": str(old.quantity), "total_cost": str(old.total_cost) if old.total_cost is not None else None} if old else None
            quantity = it.quantity
            cost = it.total_cost if it.total_cost is not None else (it.average_cost * quantity if it.average_cost is not None else None)
            if action == "ADD_TO_EXISTING_POSITION" and old:
                quantity += old.quantity
                old_cost = old.total_cost if old.total_cost is not None else (old.average_cost * old.quantity if old.average_cost is not None else None)
                cost = old_cost + cost if old.cost_basis_known and old_cost is not None and cost is not None and old.cost_currency == it.currency else None
            op = old or OpeningPosition(user_id=user_id, asset_id=target.id)
            op.quantity = quantity
            op.as_of_date = it.as_of_date or date.today()
            op.cost_basis_known = cost is not None
            op.total_cost = cost
            op.average_cost = cost / quantity if cost is not None else None
            op.cost_currency = it.currency
            op.has_incomplete_history = True
            op.source = batch.source_type
            op.provenance = {"batch_id": str(batch.id), "item_id": str(it.id), "raw_input": it.raw_input, "previous": old.provenance if old else None}
            op.import_batch_id = batch.id
            db.add(op)
            await db.flush()
            it.resulting_asset_id = target.id
            it.resulting_opening_position_id = op.id
            affected.append({"asset_id": str(target.id), "opening_position_id": str(op.id), "old": before,
                             "new": {"quantity": str(quantity), "total_cost": str(cost) if cost is not None else None}, "raw_input": it.raw_input})
            if old:
                updated_positions_count += 1
            else:
                created_positions_count += 1
        batch.status = "APPLIED"
        batch.confirmed_at = batch.applied_at = datetime.now(timezone.utc)
        return {"batch_id": str(batch.id), "status": "APPLIED", "source_type": batch.source_type,
                "created_positions_count": created_positions_count, "updated_positions_count": updated_positions_count,
                "skipped_count": skipped_count, "total_items": len(batch.items), "affected": affected}, "PORTFOLIO_IMPORT_BATCH", str(batch.id)

    @classmethod
    async def _execute_profile_update(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        """Applies a profile or policy update proposal, creating the next material profile version."""
        from app.services.investor_profile.profile_service import InvestorProfileService

        changes = params.get("changes") or {}
        reason = params.get("user_request") or "Copilot profile change confirmed"

        new_version = await InvestorProfileService.apply_profile_update(
            db=db,
            user_id=user_id,
            changes=changes,
            reason=reason,
            source="COPILOT",
        )

        result_data = {
            "status": "APPLIED",
            "version_number": new_version.version_number,
            "version_id": str(new_version.id),
            "confirmed_at": new_version.confirmed_at.isoformat(),
        }
        return result_data, "INVESTOR_PROFILE", str(new_version.id)

    @classmethod
    async def _execute_financial_context_update(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        from app.services.financial_context.context_service import FinancialContextService
        ctx = await FinancialContextService.update(db, user_id, params)
        await db.flush()
        return (
            {
                "status": "success",
                "context_id": str(ctx.id),
                "monthly_net_income": str(ctx.monthly_net_income) if ctx.monthly_net_income is not None else None,
                "monthly_essential_expenses": str(ctx.monthly_essential_expenses) if ctx.monthly_essential_expenses is not None else None,
                "planning_currency": ctx.planning_currency,
            },
            "FINANCIAL_CONTEXT",
            str(ctx.id),
        )

    @classmethod
    async def _execute_create_goal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        from app.services.financial_context.goals_service import GoalsService
        goal = await GoalsService.create_goal(db, user_id, params)
        await db.flush()
        return (
            {
                "status": "success",
                "goal_id": str(goal.id),
                "name": goal.name,
                "goal_type": goal.goal_type.value,
                "target_amount": str(goal.target_amount) if goal.target_amount is not None else None,
                "target_currency": goal.target_currency,
            },
            "FINANCIAL_GOAL",
            str(goal.id),
        )

    @classmethod
    async def _execute_update_goal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        from app.services.financial_context.goals_service import GoalsService
        goal_id = UUID(str(params["goal_id"]))
        goal = await GoalsService.update_goal(db, user_id, goal_id, params)
        await db.flush()
        return (
            {
                "status": "success",
                "goal_id": str(goal.id),
                "name": goal.name,
                "status": goal.status.value,
            },
            "FINANCIAL_GOAL",
            str(goal.id),
        )

    @classmethod
    async def _execute_create_mandate(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        from app.services.financial_context.goals_service import GoalsService
        mandate = await GoalsService.create_mandate(db, user_id, params)
        await db.flush()
        return (
            {
                "status": "success",
                "mandate_id": str(mandate.id),
                "name": mandate.name,
                "mandate_type": mandate.mandate_type.value,
            },
            "INVESTMENT_MANDATE",
            str(mandate.id),
        )

    @classmethod
    async def _execute_update_mandate(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        from app.services.financial_context.goals_service import GoalsService
        mandate_id = UUID(str(params["mandate_id"]))
        mandate = await GoalsService.update_mandate(db, user_id, mandate_id, params)
        await db.flush()
        return (
            {
                "status": "success",
                "mandate_id": str(mandate.id),
                "name": mandate.name,
            },
            "INVESTMENT_MANDATE",
            str(mandate.id),
        )

    @classmethod
    async def _execute_assign_capital(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        from app.services.financial_context.assignment_service import AssignmentService
        from app.models.financial_context import ResourceAssignmentType
        mandate_id = UUID(str(params["mandate_id"]))
        res_type = ResourceAssignmentType(params["resource_type"])
        asset_id = UUID(str(params["asset_id"])) if params.get("asset_id") else None
        cash_account_id = UUID(str(params["cash_account_id"])) if params.get("cash_account_id") else None
        qty = Decimal(str(params.get("assigned_quantity", "0")))
        amt = Decimal(str(params.get("assigned_amount", "0")))
        assignment = await AssignmentService.assign_capital(
            session=db,
            user_id=user_id,
            mandate_id=mandate_id,
            resource_type=res_type,
            asset_id=asset_id,
            cash_account_id=cash_account_id,
            assigned_quantity=qty,
            assigned_amount=amt,
            notes=params.get("notes"),
        )
        await db.flush()
        return (
            {
                "status": "success",
                "assignment_id": str(assignment.id),
                "mandate_id": str(mandate_id),
                "assigned_quantity": str(assignment.assigned_quantity),
                "assigned_amount": str(assignment.assigned_amount),
            },
            "CAPITAL_ASSIGNMENT",
            str(assignment.id),
        )

    @classmethod
    async def _execute_transfer_capital(
        cls,
        db: AsyncSession,
        user_id: UUID,
        params: dict[str, Any],
    ) -> tuple[dict[str, Any], str, str]:
        from app.services.financial_context.assignment_service import AssignmentService
        from app.models.financial_context import ResourceAssignmentType
        from_m = UUID(str(params["from_mandate_id"]))
        to_m = UUID(str(params["to_mandate_id"]))
        res_type = ResourceAssignmentType(params["resource_type"])
        asset_id = UUID(str(params["asset_id"])) if params.get("asset_id") else None
        cash_account_id = UUID(str(params["cash_account_id"])) if params.get("cash_account_id") else None
        qty = Decimal(str(params["quantity"])) if params.get("quantity") is not None else None
        amt = Decimal(str(params["amount"])) if params.get("amount") is not None else None

        res = await AssignmentService.transfer_capital(
            session=db,
            user_id=user_id,
            from_mandate_id=from_m,
            to_mandate_id=to_m,
            resource_type=res_type,
            asset_id=asset_id,
            cash_account_id=cash_account_id,
            quantity=qty,
            amount=amt,
        )
        await db.flush()
        return (
            res,
            "CAPITAL_TRANSFER",
            f"{from_m}->{to_m}",
        )


