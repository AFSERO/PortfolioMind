"""PortfolioMind Copilot orchestration service.

Handles conversation lifecycle, raw message preservation, context assembly,
Codex execution delegation, and assistant response persistence.
"""

from datetime import datetime, timezone
import logging
from typing import Any, List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.copilot import CopilotConversation, CopilotMessage
from app.schemas.copilot import (
    AcquisitionType,
    ActionProposalResponse,
    ActionProposalStatus,
    ActionType,
    CopilotPageContext,
    CopilotResponseType,
    CopilotStructuredResponse,
    ExecutionMode,
    IntentResult,
    IntentType,
    PendingActionDraft,
    ProposalPermissionLevel,
)
from app.services.copilot.codex_adapter import CopilotCodexAdapter
from app.services.copilot.context_engine import ContextBundle, CopilotContextEngine
from app.services.copilot.executor import CopilotWriteExecutor
from app.services.copilot.intent_classifier import IntentClassifier
from app.services.copilot.prompt_orchestrator import CopilotPromptOrchestrator
from app.services.copilot.proposal_service import CopilotProposalService


logger = logging.getLogger(__name__)


class CopilotService:
    """Core domain service orchestrating Copilot conversational interactions."""

    @classmethod
    async def create_conversation(
        cls,
        db: AsyncSession,
        user_id: UUID,
        title: Optional[str] = None,
    ) -> CopilotConversation:
        """Create a new conversation session for a user."""
        conversation = CopilotConversation(
            user_id=user_id,
            title=title or "New Conversation",
        )
        db.add(conversation)
        await db.commit()
        await db.refresh(conversation)
        return conversation

    @classmethod
    async def list_conversations(
        cls,
        db: AsyncSession,
        user_id: UUID,
    ) -> List[CopilotConversation]:
        """List all conversation sessions belonging to the current user."""
        stmt = (
            select(CopilotConversation)
            .options(selectinload(CopilotConversation.messages))
            .where(CopilotConversation.user_id == user_id)
            .order_by(desc(CopilotConversation.updated_at))
        )
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def get_conversation(
        cls,
        db: AsyncSession,
        user_id: UUID,
        conversation_id: UUID,
    ) -> Optional[CopilotConversation]:
        """Fetch a specific conversation with all ordered messages, verifying user ownership."""
        stmt = (
            select(CopilotConversation)
            .options(selectinload(CopilotConversation.messages))
            .where(
                CopilotConversation.id == conversation_id,
                CopilotConversation.user_id == user_id,
            )
        )
        result = await db.execute(stmt)
        conv = result.scalar_one_or_none()
        if not conv:
            return None

        # Hydrate live status for any action proposals stored in message metadata
        from app.models.copilot import CopilotActionProposal
        proposal_ids = []
        for msg in conv.messages:
            if msg.structured_metadata and isinstance(msg.structured_metadata, dict):
                p = msg.structured_metadata.get("proposal")
                if p and isinstance(p, dict) and p.get("id"):
                    try:
                        proposal_ids.append(UUID(str(p["id"])))
                    except (ValueError, TypeError):
                        pass

        if proposal_ids:
            props_stmt = select(CopilotActionProposal).where(CopilotActionProposal.id.in_(proposal_ids))
            live_props = {str(pr.id): pr for pr in (await db.execute(props_stmt)).scalars().all()}
            for msg in conv.messages:
                if msg.structured_metadata and isinstance(msg.structured_metadata, dict):
                    p = msg.structured_metadata.get("proposal")
                    if p and isinstance(p, dict) and str(p.get("id")) in live_props:
                        live = live_props[str(p["id"])]
                        status_str = live.status if isinstance(live.status, str) else live.status.value
                        p["status"] = status_str
                        p["confirmed_at"] = live.confirmed_at.isoformat() if live.confirmed_at else None
                        p["applied_at"] = live.applied_at.isoformat() if live.applied_at else None
                        p["execution_result"] = live.execution_result

        return conv

    @classmethod
    async def delete_conversation(
        cls,
        db: AsyncSession,
        user_id: UUID,
        conversation_id: UUID,
    ) -> bool:
        """Delete a conversation if owned by the user."""
        conv = await cls.get_conversation(db, user_id, conversation_id)
        if not conv:
            return False
        await db.delete(conv)
        await db.commit()
        return True

    @classmethod
    async def send_message(
        cls,
        db: AsyncSession,
        user_id: UUID,
        conversation_id: UUID,
        content: str,
        page_context: Optional[CopilotPageContext] = None,
        codex_adapter: Optional[CopilotCodexAdapter] = None,
    ) -> Tuple[CopilotMessage, CopilotStructuredResponse]:
        """Process user message, determine intent, assemble context, invoke Codex, and persist turn."""
        # 1. Verify conversation ownership
        conversation = await cls.get_conversation(db, user_id, conversation_id)
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Conversation not found or access denied.",
            )

        # 2. Persist the raw user message exactly without mutation
        user_msg = CopilotMessage(
            conversation=conversation,
            role="user",
            raw_content=content,
        )
        db.add(user_msg)
        await db.flush()

        # 3. Intent Detection & Semantics with multi-turn message history
        p_ctx = page_context.model_dump(mode="json") if page_context else None
        intent_res = IntentClassifier.classify(
            content,
            current_page_context=p_ctx,
            recent_messages=conversation.messages,
        )

        # 4. Context Engine Assembly with unmutated query and holding resolution
        context_bundle = await CopilotContextEngine.build_context(
            db=db,
            user_id=user_id,
            intent=intent_res,
            entities=intent_res.entities,
            current_page_context=p_ctx,
            recent_messages=conversation.messages,
            raw_user_message=content,
        )

        # 5. Deterministic Pre-routing / Codex Reasoning
        # If transaction details or mutation details are missing, return NEEDS_INPUT immediately
        if intent_res.execution_mode == ExecutionMode.NEEDS_INPUT:
            missing_text = ", ".join(intent_res.missing_information)
            if intent_res.intent == IntentType.TRANSACTION_ENTRY:
                acq_t = intent_res.entities.get("acquisition_type", AcquisitionType.PURCHASE.value)
                action_word = "hediye girişi" if acq_t == AcquisitionType.GIFT_IN.value else "işlem"
                if intent_res.missing_information == ["transaction_date"]:
                    question = f"Bu {action_word} için geçerli tarihi belirtir misiniz (örneğin 'bugün')?"
                elif intent_res.missing_information == ["symbol"]:
                    question = f"İşlem yapılacak varlığın adını veya sembolünü belirtir misiniz?"
                elif intent_res.missing_information == ["quantity"]:
                    question = f"İşlem miktarını (adet) belirtir misiniz?"
                else:
                    question = f"Bu {action_word} için eksik bilgileri belirtir misiniz ({missing_text})?"

                draft = PendingActionDraft(
                    action_type=intent_res.entities.get("action", "ADD_TRANSACTION"),
                    acquisition_type=acq_t,
                    symbol=intent_res.entities.get("symbol"),
                    quantity=intent_res.entities.get("quantity"),
                    unit_price=intent_res.entities.get("price"),
                    currency=intent_res.entities.get("currency", "USD"),
                    affects_cash=intent_res.entities.get("affects_cash", True),
                    cash_outflow=intent_res.entities.get("cash_outflow", 0.0),
                    transaction_date=intent_res.entities.get("transaction_date"),
                    missing_fields=intent_res.missing_information,
                    is_complete=False,
                )
            else:
                question = f"Bu eylem için eksik bilgileri belirtir misiniz ({missing_text})?"
                draft = None

            structured_resp = CopilotStructuredResponse(
                response_type=CopilotResponseType.NEEDS_INPUT,
                question=question,
                intent=intent_res.intent,
                execution_mode=ExecutionMode.NEEDS_INPUT.value,
                missing_fields=intent_res.missing_information,
                action_draft=draft,
                context_used=context_bundle.provenance,
            )
        # If user issued a portfolio import request
        elif intent_res.intent == IntentType.PORTFOLIO_IMPORT:
            from app.services.copilot.import_service import PortfolioImportService
            from app.schemas.portfolio_import import ImportSourceType
            batch = await PortfolioImportService.process_import(
                db=db,
                user_id=user_id,
                conversation_id=conversation.id,
                source_type=ImportSourceType.NATURAL_LANGUAGE.value,
                raw_content=content,
            )
            batch_resp = PortfolioImportService.to_batch_response(batch)
            proposal_resp = None
            if batch.proposal:
                proposal_resp = ActionProposalResponse.model_validate(batch.proposal)

            answer = (
                f"Portföyünüzde {len(batch.items)} varlık tespit edildi: "
                f"{batch_resp.ready_count} hazır, {batch_resp.needs_review_count} inceleme bekleyen. "
                "Detayları aşağıdaki önizleme kartından inceleyip onaylayabilirsiniz."
            )
            intent_str = intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent)
            structured_resp = CopilotStructuredResponse(
                response_type=CopilotResponseType.PROPOSAL if batch.status == "READY_FOR_CONFIRMATION" else CopilotResponseType.NEEDS_INPUT,
                answer=answer,
                intent=intent_str,
                execution_mode=ExecutionMode.PROPOSE.value,
                proposal=proposal_resp,
                import_batch=batch_resp,
                context_used=context_bundle.provenance,
            )

        # If user replied to update a missing field in an import draft
        elif intent_res.intent in (IntentType.PORTFOLIO_IMPORT_UPDATE, IntentType.PORTFOLIO_IMPORT_UPDATE.value):
            from app.services.copilot.import_service import PortfolioImportService
            update_res = await PortfolioImportService.update_draft_via_message(
                db=db,
                user_id=user_id,
                conversation_id=conversation.id,
                message_text=content,
            )
            intent_str = intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent)
            if update_res:
                batch, updated_item = update_res
                batch_resp = PortfolioImportService.to_batch_response(batch)
                proposal_resp = ActionProposalResponse.model_validate(batch.proposal) if batch.proposal else None
                answer = (
                    f"{updated_item.symbol or updated_item.name} için miktar {updated_item.quantity} olarak güncellendi. "
                    f"Portföy içe aktarımı durumu: {batch_resp.ready_count} hazır, {batch_resp.needs_review_count} inceleme bekleyen."
                )
                structured_resp = CopilotStructuredResponse(
                    response_type=CopilotResponseType.PROPOSAL if batch.status == "READY_FOR_CONFIRMATION" else CopilotResponseType.NEEDS_INPUT,
                    answer=answer,
                    intent=intent_str,
                    execution_mode=ExecutionMode.PROPOSE.value,
                    proposal=proposal_resp,
                    import_batch=batch_resp,
                    context_used=context_bundle.provenance,
                )
            else:
                structured_resp = CopilotStructuredResponse(
                    response_type=CopilotResponseType.ANSWER,
                    answer="Belirtilen miktar için güncellenecek bekleyen bir içe aktarım kalemi bulunamadı.",
                    intent=intent_str,
                    context_used=context_bundle.provenance,
                )

        # If user explicitly issued a completed transaction or non-cash acquisition
        elif intent_res.intent == IntentType.TRANSACTION_ENTRY and intent_res.execution_mode in (ExecutionMode.AUTO_APPLY, ExecutionMode.PROPOSE):
            # Check price from context if not in entities
            price_item = next(
                (it for it in context_bundle.items if it.source_type == "PRICE_CONTEXT"),
                None,
            )
            resolved_price = intent_res.entities.get("price")
            resolved_currency = intent_res.entities.get("currency")
            if price_item and price_item.content:
                if resolved_price is None or intent_res.entities.get("use_current_price"):
                    resolved_price = price_item.content.get("current_unit_price")
                if not resolved_currency:
                    resolved_currency = price_item.content.get("currency")

            existing_pos_item = next(
                (it for it in context_bundle.items if it.source_type == "EXISTING_HOLDING"),
                None,
            )
            existing_qty = 0.0
            holding_name = intent_res.entities.get("symbol") or "varlık"
            if existing_pos_item and existing_pos_item.content:
                existing_qty = float(existing_pos_item.content.get("current_quantity", 0.0))
                holding_name = existing_pos_item.content.get("name", holding_name)

            qty = float(intent_res.entities.get("quantity", 1.0))
            acq_type = intent_res.entities.get("acquisition_type", AcquisitionType.PURCHASE.value)
            affects_cash = False if acq_type in (AcquisitionType.GIFT_IN.value, AcquisitionType.TRANSFER_IN.value) else True
            cash_outflow = 0.0 if not affects_cash else ((resolved_price or 0.0) * qty)
            total_amount = (resolved_price or 0.0) * qty

            action_dict = {
                "type": intent_res.entities.get("action", "RECEIVE_ASSET" if not affects_cash else "BUY"),
                "acquisition_type": acq_type,
                "symbol": intent_res.entities.get("symbol"),
                "name": holding_name,
                "quantity": qty,
                "unit_price": resolved_price,
                "currency": resolved_currency or "USD",
                "total_amount": total_amount,
                "affects_cash": affects_cash,
                "cash_outflow": cash_outflow,
                "transaction_date": intent_res.entities.get("transaction_date", str(datetime.now(timezone.utc).date())),
            }

            draft = PendingActionDraft(
                action_type=action_dict["type"],
                acquisition_type=action_dict["acquisition_type"],
                symbol=action_dict["symbol"],
                instrument_name=holding_name,
                quantity=qty,
                unit_price=resolved_price,
                currency=resolved_currency or "USD",
                total_amount=total_amount,
                affects_cash=affects_cash,
                cash_outflow=cash_outflow,
                transaction_date=action_dict["transaction_date"],
                is_complete=True,
                missing_fields=[],
            )

            # Create Phase 2 Action Proposal (Level 2: Confirmation Required)
            action_type_val = (
                ActionType.RECEIVE_ASSET.value
                if not affects_cash
                else (
                    ActionType.SELL_TRANSACTION.value
                    if action_dict["type"] == "SELL"
                    else ActionType.BUY_TRANSACTION.value
                )
            )

            current_snapshot = {
                "holding_name": holding_name,
                "symbol": action_dict["symbol"],
                "current_quantity": existing_qty,
                "unit_price": resolved_price,
                "currency": action_dict["currency"],
            }

            if action_dict["type"] == "SELL":
                expected_impact = {
                    "previous_quantity": existing_qty,
                    "new_quantity": existing_qty - qty,
                    "quantity_delta": -qty,
                    "cash_delta": total_amount,
                }
                summary = f"{qty:.2f} {action_dict['symbol']} satışı @ {resolved_price or 0.0:.2f} {action_dict['currency']}"
            elif not affects_cash:
                expected_impact = {
                    "previous_quantity": existing_qty,
                    "new_quantity": existing_qty + qty,
                    "quantity_delta": qty,
                    "cash_delta": 0.0,
                }
                summary = f"{qty:.2f} {holding_name} ({action_dict['symbol']}) hediye/bağış girişi"
            else:
                expected_impact = {
                    "previous_quantity": existing_qty,
                    "new_quantity": existing_qty + qty,
                    "quantity_delta": qty,
                    "cash_delta": -total_amount,
                }
                summary = f"{qty:.2f} {action_dict['symbol']} alımı @ {resolved_price or 0.0:.2f} {action_dict['currency']}"

            proposal_warnings: list[str] = []
            if action_dict["type"] == "SELL" and existing_qty < qty:
                proposal_warnings.append(
                    f"Mevcut varlık miktarı ({existing_qty}) satış miktarından ({qty}) düşüktür."
                )

            proposal = await CopilotProposalService.create_proposal(
                db=db,
                user_id=user_id,
                conversation_id=conversation.id,
                action_type=action_type_val,
                permission_level=ProposalPermissionLevel.LEVEL_2_CONFIRMATION_REQUIRED.value,
                parameters={
                    **action_dict,
                    "user_request": content,
                    "intent": intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                },
                current_state_snapshot=current_snapshot,
                expected_impact=expected_impact,
                human_readable_summary=summary,
                warnings=proposal_warnings,
                status=ActionProposalStatus.READY_FOR_CONFIRMATION.value,
            )
            proposal_resp = ActionProposalResponse.model_validate(proposal)

            if acq_type == AcquisitionType.GIFT_IN.value:
                price_desc = f"{resolved_price:.2f} {action_dict['currency']}" if resolved_price is not None else "Belirtilmedi"
                total_qty_after = existing_qty + qty
                answer_text = (
                    f"{qty:.0f} adet {holding_name} ({action_dict['symbol']}) hediye girişi hazırlandı.\n"
                    f"• Tarih: {action_dict['transaction_date']}\n"
                    f"• Birim Piyasa Değeri: {price_desc}\n"
                    f"• Nakit Çıkışı: 0.00 {action_dict['currency']} (Hediye/bağış)\n"
                    f"• Mevcut Pozisyon: {existing_qty:.0f} adet → Eklendikten sonra: {total_qty_after:.0f} adet.\n"
                    f"(Faz 1 kapsamında veritabanı yazma işlemi henüz çalıştırılmamaktadır. Faz 2 kapsamında onay bekleyen işlem önerisi oluşturuldu.)"
                )
            elif action_dict["type"] == "SELL":
                price_desc = f"{resolved_price:.2f} {action_dict['currency']}" if resolved_price is not None else "N/A"
                total_qty_after = existing_qty - qty
                answer_text = (
                    f"{qty:.0f} adet {action_dict['symbol']} satış işlemi hazırlandı.\n"
                    f"• Tarih: {action_dict['transaction_date']}\n"
                    f"• Birim Fiyat: {price_desc}\n"
                    f"• Toplam Tutar: {total_amount:.2f} {action_dict['currency']}\n"
                    f"• Mevcut Pozisyon: {existing_qty:.0f} adet → Kalan: {total_qty_after:.0f} adet.\n"
                    f"(Faz 1 kapsamında veritabanı yazma işlemi henüz çalıştırılmamaktadır. Faz 2 kapsamında onay bekleyen işlem önerisi oluşturuldu.)"
                )
            else:
                price_desc = f"{resolved_price:.2f} {action_dict['currency']}" if resolved_price is not None else "N/A"
                answer_text = (
                    f"{qty:.0f} adet {action_dict['symbol']} alım işlemi hazırlandı.\n"
                    f"• Tarih: {action_dict['transaction_date']}\n"
                    f"• Birim Fiyat: {price_desc}\n"
                    f"• Toplam Tutar: {total_amount:.2f} {action_dict['currency']}\n"
                    f"(Faz 1 kapsamında veritabanı yazma işlemi henüz çalıştırılmamaktadır. Faz 2 kapsamında onay bekleyen işlem önerisi oluşturuldu.)"
                )

            structured_resp = CopilotStructuredResponse(
                response_type=CopilotResponseType.ACTION_INTENT,
                intent=intent_res.intent,
                execution_mode=ExecutionMode.AUTO_APPLY.value,
                action=action_dict,
                action_draft=draft,
                proposal=proposal_resp,
                answer=answer_text,
                context_used=context_bundle.provenance,
            )
        # Watchlist Add/Remove (Level 1: Minimal friction / Immediate execution with audit)
        elif intent_res.intent == IntentType.WATCHLIST_UPDATE:
            action_type_val = intent_res.entities.get("action", "ADD_WATCHLIST")
            sym = intent_res.entities.get("symbol")
            if not sym:
                structured_resp = CopilotStructuredResponse(
                    response_type=CopilotResponseType.NEEDS_INPUT,
                    question="Takip listesine eklenecek veya çıkarılacak varlığın sembolünü belirtir misiniz?",
                    intent=intent_res.intent,
                    execution_mode=ExecutionMode.NEEDS_INPUT.value,
                    missing_fields=["symbol"],
                    context_used=context_bundle.provenance,
                )
            else:
                summary = (
                    f"{sym} takip listesine eklendi."
                    if action_type_val == "ADD_WATCHLIST"
                    else f"{sym} takip listesinden çıkarıldı."
                )
                proposal = await CopilotProposalService.create_proposal(
                    db=db,
                    user_id=user_id,
                    conversation_id=conversation.id,
                    action_type=action_type_val,
                    permission_level=ProposalPermissionLevel.LEVEL_1_LOW_RISK.value,
                    parameters={
                        "symbol": sym,
                        "action": action_type_val,
                        "user_request": content,
                        "intent": intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                    },
                    human_readable_summary=summary,
                    status=ActionProposalStatus.READY_FOR_CONFIRMATION.value,
                )
                exec_result = await CopilotWriteExecutor.execute_proposal(
                    db=db, user_id=user_id, proposal_id=proposal.id
                )
                proposal = await CopilotProposalService.get_proposal(db, user_id, proposal.id)
                prop_resp = ActionProposalResponse.model_validate(proposal) if proposal else None

                structured_resp = CopilotStructuredResponse(
                    response_type=CopilotResponseType.ACTION_INTENT,
                    intent=intent_res.intent,
                    execution_mode=ExecutionMode.AUTO_APPLY.value,
                    action={"action": action_type_val, "symbol": sym, "result": exec_result},
                    proposal=prop_resp,
                    answer=summary,
                    context_used=context_bundle.provenance,
                )
        # Journal Note (Level 1: Minimal friction / Immediate execution with audit)
        elif intent_res.intent == IntentType.JOURNAL_ENTRY:
            title = intent_res.entities.get("title", "Copilot Notu")
            summary_txt = intent_res.entities.get("summary", "")
            if not summary_txt:
                structured_resp = CopilotStructuredResponse(
                    response_type=CopilotResponseType.NEEDS_INPUT,
                    question="Kaydedilecek not içeriğini belirtir misiniz?",
                    intent=intent_res.intent,
                    execution_mode=ExecutionMode.NEEDS_INPUT.value,
                    missing_fields=["note_content"],
                    context_used=context_bundle.provenance,
                )
            else:
                proposal = await CopilotProposalService.create_proposal(
                    db=db,
                    user_id=user_id,
                    conversation_id=conversation.id,
                    action_type=ActionType.CREATE_JOURNAL_ENTRY.value,
                    permission_level=ProposalPermissionLevel.LEVEL_1_LOW_RISK.value,
                    parameters={
                        "title": title,
                        "summary": summary_txt,
                        "user_request": content,
                        "intent": intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                    },
                    human_readable_summary=f"Karar notu: {title}",
                    status=ActionProposalStatus.READY_FOR_CONFIRMATION.value,
                )
                exec_result = await CopilotWriteExecutor.execute_proposal(
                    db=db, user_id=user_id, proposal_id=proposal.id
                )
                proposal = await CopilotProposalService.get_proposal(db, user_id, proposal.id)
                prop_resp = ActionProposalResponse.model_validate(proposal) if proposal else None

                structured_resp = CopilotStructuredResponse(
                    response_type=CopilotResponseType.ACTION_INTENT,
                    intent=intent_res.intent,
                    execution_mode=ExecutionMode.AUTO_APPLY.value,
                    action={"action": "CREATE_JOURNAL_ENTRY", "title": title, "result": exec_result},
                    proposal=prop_resp,
                    answer=f"Karar notunuz başarıyla kaydedildi: \"{title}\".",
                    context_used=context_bundle.provenance,
                )
        # If user explicitly issued a policy or investor profile change command (Level 2: Confirmation Required)
        elif intent_res.intent == IntentType.POLICY_CHANGE:
            policy_field = intent_res.entities.get("policy_field", "general")
            new_value = intent_res.entities.get("new_value")
            change_kind = intent_res.entities.get("change_kind")

            if change_kind == "RISK_AND_INCOME":
                summary = "Yatırımcı profili güncellemesi: Gelir güvenirliği 'Düzenli', risk toleransı '%30' olarak güncellenecek."
                proposed_changes = {
                    "goals": {"income_reliability": "RELIABLE"},
                    "risk": {"drawdown_comfort": "P30", "tolerance_summary": "HIGH"},
                }
            else:
                pct_str = f"%{float(new_value or 0.0) * 100:.1f}" if new_value is not None else "belirtilmemiş"
                summary = f"Yatırım politikası hedef güncellemesi: {policy_field} -> {pct_str}"
                proposed_changes = {
                    "policy": {
                        "allocations": [
                            {
                                "scope": "ALL",
                                "buckets": [
                                    {
                                        "family": intent_res.entities.get("category", "general"),
                                        "target_pct": float(new_value or 0.0) * 100,
                                    }
                                ],
                            }
                        ]
                    }
                }

            proposal = await CopilotProposalService.create_proposal(
                db=db,
                user_id=user_id,
                conversation_id=conversation.id,
                action_type=ActionType.UPDATE_INVESTOR_PROFILE.value,
                permission_level=ProposalPermissionLevel.LEVEL_2_CONFIRMATION_REQUIRED.value,
                parameters={
                    "changes": proposed_changes,
                    "policy_field": policy_field,
                    "new_value": new_value,
                    "user_request": content,
                    "intent": intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                },
                human_readable_summary=summary,
                status=ActionProposalStatus.READY_FOR_CONFIRMATION.value,
            )
            prop_resp = ActionProposalResponse.model_validate(proposal)

            answer = (
                f"{summary}\n"
                "Değişikliklerin yatırımcı profilinize ve analizlerinize yansıması için onayınız gerekmektedir."
            )

            structured_resp = CopilotStructuredResponse(
                response_type=CopilotResponseType.PROPOSAL,
                intent=intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                execution_mode=ExecutionMode.PROPOSE.value,
                proposal=prop_resp,
                answer=answer,
                context_used=context_bundle.provenance,
            )

        # Broad Financial Situation Analysis (Deterministic Intelligence)
        elif intent_res.intent == IntentType.FINANCIAL_ANALYSIS:
            from app.services.financial_context.intelligence_service import FinancialIntelligenceService
            summary = await FinancialIntelligenceService.compute_financial_intelligence(db, user_id)

            net_worth_str = f"{summary['net_worth']:,.2f} {summary['reporting_currency']}"
            liquid_nw_str = f"{summary['liquid_net_worth']:,.2f} {summary['reporting_currency']}"
            assets_str = f"{summary['total_assets_value']:,.2f} {summary['reporting_currency']}"
            cash_str = f"{summary['total_cash_value']:,.2f} {summary['reporting_currency']}"
            debt_str = f"{summary['total_liabilities_value']:,.2f} {summary['reporting_currency']}"

            income_val = summary.get("monthly_net_income")
            income_str = f"{income_val:,.2f} {summary['reporting_currency']}" if income_val is not None else "Bilinmiyor (Girilmemiş)"

            ess_val = summary.get("monthly_essential_expenses")
            ess_str = f"{ess_val:,.2f} {summary['reporting_currency']}" if ess_val is not None else "Bilinmiyor"

            surplus_val = summary.get("monthly_surplus")
            surplus_str = f"{surplus_val:,.2f} {summary['reporting_currency']}" if surplus_val is not None else "Hesaplanamıyor"

            savings_rate = summary.get("savings_rate_pct")
            savings_rate_str = f"%{savings_rate:.1f}" if savings_rate is not None else "Hesaplanamıyor"

            runway = summary.get("emergency_coverage_months")
            runway_str = f"{runway:.1f} ay" if runway is not None else "Yetersiz veri"

            spec_pct = summary.get("speculative_exposure_pct")
            spec_str = f"%{spec_pct:.1f}" if spec_pct is not None else "%0.0"

            goals_lines = []
            for g in summary.get("goals", []):
                t_amt = f"{g['target_amount']:,.2f} {g['target_currency']}" if g.get("target_amount") else "Belirtilmemiş"
                f_amt = f"{g['current_funding']:,.2f} {g['target_currency']}"
                ratio_str = f"(%{g['funded_ratio']*100:.1f})" if g.get("funded_ratio") is not None else ""
                goals_lines.append(f"  • {g['goal_name']}: {f_amt} / {t_amt} {ratio_str} [{g['status_assessment']}]")

            goals_text = "\n".join(goals_lines) if goals_lines else "  • Henüz tanımlı finansal hedef bulunmuyor."

            warnings_lines = [f"  ⚠️ {w}" for w in summary.get("warnings", [])]
            warnings_text = "\n" + "\n".join(warnings_lines) if warnings_lines else ""

            analysis_text = (
                f"### Finansal Durum Analizi\n\n"
                f"**1. Mevcut Varlık & Net Değer Durumu:**\n"
                f"• Net Değer: **{net_worth_str}** (Likidite Net Değer: {liquid_nw_str})\n"
                f"• Toplam Varlıklar: {assets_str} | Nakit Rezervi: {cash_str} | Yükümlülükler: {debt_str}\n\n"
                f"**2. Aylık Nakit Akışı & Tasarruf Kapasitesi:**\n"
                f"• Aylık Net Gelir: {income_str}\n"
                f"• Zorunlu Harcamalar: {ess_str}\n"
                f"• Aylık Tasarruf Fazlası (Surplus): {surplus_str} (Tasarruf Oranı: {savings_rate_str})\n\n"
                f"**3. Güvenlik & Acil Durum Dayanıklılığı:**\n"
                f"• Acil Durum Karşılama Süresi: **{runway_str}**\n\n"
                f"**4. Hedefler & Mandatler:**\n"
                f"{goals_text}\n\n"
                f"**5. Risk & Spekülatif Pozisyonlama:**\n"
                f"• Spekülatif Varlık Oranı: {spec_str}\n"
                f"{warnings_text}"
            )

            structured_resp = CopilotStructuredResponse(
                response_type=CopilotResponseType.ANSWER,
                intent=intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                execution_mode=ExecutionMode.READ_ONLY.value,
                answer=analysis_text,
                context_used=context_bundle.provenance,
            )

        # Adaptive Financial Discovery (Deterministic Intelligence & Contextual Clarification)
        elif intent_res.intent in (IntentType.FINANCIAL_DISCOVERY, IntentType.FINANCIAL_DISCOVERY.value):
            structured_resp = await cls._handle_financial_discovery(
                db=db,
                user_id=user_id,
                intent_res=intent_res,
                context_bundle=context_bundle,
                content=content,
            )

        # Conversational Updates to Financial Context (Level 2 Proposal)
        elif intent_res.intent == IntentType.UPDATE_FINANCIAL_CONTEXT:
            ents = dict(intent_res.entities)
            ents.setdefault("source", "AI_INTERPRETED")
            inc = ents.get("monthly_net_income")
            exp = ents.get("monthly_essential_expenses")
            cur = ents.get("planning_currency", "TRY")
            parts = []
            if inc is not None:
                parts.append(f"Aylık net gelir: {inc:,.2f} {cur}")
            if exp is not None:
                parts.append(f"Aylık zorunlu gider: {exp:,.2f} {cur}")
            summary = "Finansal akış güncellemesi: " + ", ".join(parts)

            proposal = await CopilotProposalService.create_proposal(
                db=db,
                user_id=user_id,
                conversation_id=conversation.id,
                action_type=ActionType.UPDATE_FINANCIAL_CONTEXT.value,
                permission_level=ProposalPermissionLevel.LEVEL_2_CONFIRMATION_REQUIRED.value,
                parameters=ents,
                human_readable_summary=summary,
                status=ActionProposalStatus.READY_FOR_CONFIRMATION.value,
            )
            prop_resp = ActionProposalResponse.model_validate(proposal)
            answer = (
                f"{summary}\n"
                "Bu finansal durum güncellemesini onaylıyor musunuz? Onayınızın ardından analiz ve bütçe metrikleriniz güncellenecektir."
            )
            structured_resp = CopilotStructuredResponse(
                response_type=CopilotResponseType.PROPOSAL,
                intent=intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                execution_mode=ExecutionMode.PROPOSE.value,
                proposal=prop_resp,
                answer=answer,
                context_used=context_bundle.provenance,
            )

        # Conversational Goal Creation (Level 2 Proposal)
        elif intent_res.intent == IntentType.CREATE_GOAL:
            ents = intent_res.entities
            g_name = ents.get("name", "Yeni Hedef")
            target_amt = ents.get("target_amount")
            target_cur = ents.get("target_currency", "TRY")
            amt_str = f"{target_amt:,.2f} {target_cur}" if target_amt else "Tutar belirtilmedi"
            summary = f"Yeni finansal hedef: {g_name} ({amt_str})"

            proposal = await CopilotProposalService.create_proposal(
                db=db,
                user_id=user_id,
                conversation_id=conversation.id,
                action_type=ActionType.CREATE_FINANCIAL_GOAL.value,
                permission_level=ProposalPermissionLevel.LEVEL_2_CONFIRMATION_REQUIRED.value,
                parameters=ents,
                human_readable_summary=summary,
                status=ActionProposalStatus.READY_FOR_CONFIRMATION.value,
            )
            prop_resp = ActionProposalResponse.model_validate(proposal)
            answer = (
                f"{summary}\n"
                "Bu finansal hedefi oluşturmak için lütfen önizleme kartından onay verin."
            )
            structured_resp = CopilotStructuredResponse(
                response_type=CopilotResponseType.PROPOSAL,
                intent=intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                execution_mode=ExecutionMode.PROPOSE.value,
                proposal=prop_resp,
                answer=answer,
                context_used=context_bundle.provenance,
            )

        # Conversational Virtual Transfer (Level 2 Proposal)
        elif intent_res.intent == IntentType.TRANSFER_CAPITAL:
            ents = intent_res.entities
            summary = "Mandatler arası mantıksal sermaye transferi önerisi."

            proposal = await CopilotProposalService.create_proposal(
                db=db,
                user_id=user_id,
                conversation_id=conversation.id,
                action_type=ActionType.TRANSFER_CAPITAL.value,
                permission_level=ProposalPermissionLevel.LEVEL_2_CONFIRMATION_REQUIRED.value,
                parameters=ents,
                human_readable_summary=summary,
                status=ActionProposalStatus.READY_FOR_CONFIRMATION.value,
            )
            prop_resp = ActionProposalResponse.model_validate(proposal)
            answer = (
                f"{summary}\n"
                "Transfer detaylarını inceleyip onaylayabilirsiniz. Bu işlem bir alım/satım işlemi değildir ve maliyet esasını etkilemez."
            )
            structured_resp = CopilotStructuredResponse(
                response_type=CopilotResponseType.PROPOSAL,
                intent=intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
                execution_mode=ExecutionMode.PROPOSE.value,
                proposal=prop_resp,
                answer=answer,
                context_used=context_bundle.provenance,
            )

        else:
            # Dispatch to Codex via CodexCLIProvider
            adapter = codex_adapter or CopilotCodexAdapter()
            prompt = CopilotPromptOrchestrator.build_prompt(
                raw_user_message=content,
                intent=intent_res,
                context_bundle=context_bundle,
            )
            structured_resp = await adapter.execute(
                prompt=prompt,
                intent=intent_res,
                context_bundle=context_bundle,
            )

        # 6. Persist assistant response turn
        assistant_content = (
            structured_resp.answer
            or structured_resp.question
            or "İşlem kaydedildi."
        )
        assistant_msg = CopilotMessage(
            conversation=conversation,
            role="assistant",
            raw_content=assistant_content,
            intent=structured_resp.intent,
            structured_metadata=structured_resp.model_dump(mode="json"),
        )
        db.add(assistant_msg)

        # 7. Update conversation timestamp
        conversation.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(assistant_msg)

        return assistant_msg, structured_resp

    @classmethod
    async def _handle_financial_discovery(
        cls,
        db: AsyncSession,
        user_id: UUID,
        intent_res: IntentResult,
        context_bundle: ContextBundle,
        content: str,
    ) -> CopilotStructuredResponse:
        """Processes adaptive financial discovery queries with deterministic precision and no hallucinations."""
        import re
        from decimal import Decimal
        from app.services.financial_context.context_service import FinancialContextService
        from app.services.financial_context.intelligence_service import FinancialIntelligenceService
        from app.services.investor_profile.profile_service import InvestorProfileService

        topic = intent_res.entities.get("discovery_topic")
        lower_content = content.lower()
        if not topic:
            if any(w in lower_content for w in ["invest", "yatırım", "save", "tasarruf", "birikim"]):
                topic = "monthly_investment_capacity"
            elif any(w in lower_content for w in ["emergency", "acil durum", "reserve", "tampon", "yedek akçe"]):
                topic = "emergency_fund_adequacy"
            else:
                topic = "risk_capacity"

        is_english = bool(
            re.search(r"\b(i\b|don't|dont|not|sure|how|much|invest|risk|take|emergency|fund|what|every|month)\b", lower_content)
        )

        intel = await FinancialIntelligenceService.compute_financial_intelligence(db, user_id)
        fc = await FinancialContextService.get_or_create(db, user_id)
        curr = intel.get("reporting_currency", "TRY")

        if topic == "monthly_investment_capacity":
            income = intel.get("monthly_net_income")
            essential = intel.get("monthly_essential_expenses")
            discretionary = intel.get("monthly_discretionary_expenses")
            surplus = intel.get("monthly_surplus")
            savings_rate = intel.get("savings_rate_pct")

            if income is not None and (essential is not None or discretionary is not None):
                outflows = (essential or Decimal("0")) + (discretionary or Decimal("0"))
                if is_english:
                    if surplus > Decimal("0"):
                        answer = (
                            f"### Monthly Investment Capacity Analysis\n\n"
                            f"Based on your recorded financial context, your investable surplus is calculated deterministically:\n\n"
                            f"• **Monthly Net Income:** {income:,.2f} {curr}\n"
                            f"• **Essential Expenses:** {(essential or Decimal('0')):,.2f} {curr}\n"
                            f"• **Discretionary Expenses:** {(discretionary or Decimal('0')):,.2f} {curr}\n"
                            f"• **Total Monthly Outflows:** {outflows:,.2f} {curr}\n"
                            f"• **Calculated Monthly Surplus:** **{surplus:,.2f} {curr}** (Savings Rate: {savings_rate:.1f}%)\n\n"
                            f"This calculated surplus of **{surplus:,.2f} {curr}** represents your sustainable monthly investing capacity without inducing a cash deficit. "
                            f"You can allocate this amount toward your goals (such as Retirement or Home Purchase) across dedicated investment mandates."
                        )
                    else:
                        answer = (
                            f"### Monthly Investment Capacity Analysis\n\n"
                            f"• **Monthly Net Income:** {income:,.2f} {curr}\n"
                            f"• **Total Outflows:** {outflows:,.2f} {curr}\n"
                            f"• **Monthly Surplus:** **{surplus:,.2f} {curr}**\n\n"
                            f"Your current outflows equal or exceed your declared income. We recommend optimizing essential living costs before establishing regular monthly investment commitments."
                        )
                else:
                    if surplus > Decimal("0"):
                        answer = (
                            f"### Aylık Yatırım Kapasitesi Analizi\n\n"
                            f"Mevcut finansal durumunuza göre aylık yatırım ve tasarruf kapasiteniz deterministik olarak hesaplanmıştır:\n\n"
                            f"• **Aylık Net Gelir:** {income:,.2f} {curr}\n"
                            f"• **Zorunlu Giderler:** {(essential or Decimal('0')):,.2f} {curr}\n"
                            f"• **İsteğe Bağlı Harcamalar:** {(discretionary or Decimal('0')):,.2f} {curr}\n"
                            f"• **Toplam Aylık Çıkış:** {outflows:,.2f} {curr}\n"
                            f"• **Hesaplanan Aylık Tasarruf Fazlası (Surplus):** **{surplus:,.2f} {curr}** (Tasarruf Oranı: %{savings_rate:.1f})\n\n"
                            f"Hesaplanan **{surplus:,.2f} {curr}** tutarındaki fazlalık, bütçenizde açık yaratmadan her ay yatırım mandatlerinize düzenli olarak ayırabileceğiniz sürdürülebilir maksimum tutardır."
                        )
                    else:
                        answer = (
                            f"### Aylık Yatırım Kapasitesi Analizi\n\n"
                            f"• **Aylık Net Gelir:** {income:,.2f} {curr}\n"
                            f"• **Toplam Çıkış:** {outflows:,.2f} {curr}\n"
                            f"• **Aylık Fazla:** **{surplus:,.2f} {curr}**\n\n"
                            f"Mevcut harcamalarınız gelirinizi dengelemekte veya aşmaktadır. Düzenli yatırımlara başlamadan önce nakit akışını pozitif fazlaya geçirmek öncelikli olmalıdır."
                        )
            else:
                inc_str = f"{income:,.2f} {curr}" if income is not None else "UNKNOWN"
                ess_str = f"{essential:,.2f} {curr}" if essential is not None else "UNKNOWN"
                if is_english:
                    answer = (
                        f"### Monthly Investment Capacity Discovery\n\n"
                        f"Determining how much you can sustainably invest each month depends on your monthly cash flow surplus (Take-home Income minus Essential Outflows). In PortfolioMind, we never guess or invent financial figures.\n\n"
                        f"**Current Recorded State:**\n"
                        f"• Monthly Net Income: **{inc_str}**\n"
                        f"• Monthly Essential Expenses: **{ess_str}**\n"
                        f"• Monthly Surplus: **UNKNOWN**\n\n"
                        f"To calculate your exact investable capacity without guessing:\n"
                        f"1. What is your approximate monthly net take-home income?\n"
                        f"2. What are your monthly non-negotiable living expenses (rent/mortgage, utilities, groceries, debt minimums)?"
                    )
                else:
                    answer = (
                        f"### Aylık Yatırım Kapasitesi Tespiti\n\n"
                        f"Her ay ne kadar yatırım yapabileceğinizi belirlemek, aylık net nakit fazlanıza (Net Gelir - Zorunlu Giderler) bağlıdır. Finansal modelimizde varsayımsal veya tahmini değerler kullanılmaz.\n\n"
                        f"**Mevcut Kayıt Durumu:**\n"
                        f"• Aylık Net Gelir: **{inc_str}**\n"
                        f"• Aylık Zorunlu Giderler: **{ess_str}**\n"
                        f"• Aylık Tasarruf Fazlası: **UNKNOWN (Bilinmiyor)**\n\n"
                        f"Net bir yatırım bütçesi hesaplayabilmemiz için:\n"
                        f"1. Yaklaşık aylık net ele geçen geliriniz ne kadardır?\n"
                        f"2. Kira, faturalar, asgari borç ödemeleri ve temel yaşam gibi zorunlu giderleriniz aylık yaklaşık ne kadardır?"
                    )

        elif topic == "emergency_fund_adequacy":
            essential = intel.get("monthly_essential_expenses")
            total_cash = intel.get("total_cash_value", Decimal("0"))
            runway = intel.get("emergency_coverage_months")

            if essential is not None and essential > Decimal("0"):
                runway_dec = Decimal(str(runway)) if runway is not None else (total_cash / essential).quantize(Decimal("0.1"))
                target_3m = essential * Decimal("3")
                if is_english:
                    if runway_dec >= Decimal("6.0"):
                        assessment = f"✅ Your emergency reserve covers **{runway_dec} months** of essential living costs, exceeding the recommended 6-month safety benchmark. Your emergency fund is fully adequate."
                    elif runway_dec >= Decimal("3.0"):
                        assessment = f"✅ Your emergency reserve covers **{runway_dec} months** of essential expenses, satisfying the recommended 3-to-6 month safety threshold. This provides an adequate baseline cushion."
                    else:
                        assessment = f"⚠️ Your emergency reserve covers only **{runway_dec} months** of essential expenses (recommended: at least 3 months / {target_3m:,.2f} {curr}, current gap: {max(Decimal('0'), target_3m - total_cash):,.2f} {curr}). We recommend prioritizing cash reserves before expanding higher-risk investments."

                    answer = (
                        f"### Emergency Fund Adequacy Analysis\n\n"
                        f"Calculated deterministically by comparing your liquid reserves against declared monthly essential living expenses:\n\n"
                        f"• **Liquid Cash & Reserves:** {total_cash:,.2f} {curr}\n"
                        f"• **Monthly Essential Expenses:** {essential:,.2f} {curr}\n"
                        f"• **Current Emergency Runway:** **{runway_dec} months**\n\n"
                        f"{assessment}"
                    )
                else:
                    if runway_dec >= Decimal("6.0"):
                        assessment = f"✅ Acil durum rezerviniz **{runway_dec} aylık** temel harcamanızı karşılamaktadır. Standart 3-6 aylık güvenlik eşiğini aşarak güçlü bir güvence sağlamaktadır."
                    elif runway_dec >= Decimal("3.0"):
                        assessment = f"✅ Acil durum rezerviniz **{runway_dec} aylık** temel harcamanızı karşılamaktadır. Standart 3 ila 6 aylık tavsiye edilen güvenlik aralığındadır."
                    else:
                        assessment = f"⚠️ Acil durum rezerviniz yalnızca **{runway_dec} ayı** karşılamaktadır (asgari 3 aylık tavsiye: {target_3m:,.2f} {curr}). Yüksek riskli yatırımlara sermaye aktarmadan önce acil durum rezervinin tamamlanması önerilir."

                    answer = (
                        f"### Acil Durum Rezervi Yeterlilik Analizi\n\n"
                        f"Mevcut likit rezervleriniz ve beyan edilen zorunlu giderleriniz karşılaştırılarak hesaplanmıştır:\n\n"
                        f"• **Mevcut Likit Nakit & Rezerv:** {total_cash:,.2f} {curr}\n"
                        f"• **Aylık Zorunlu Giderler:** {essential:,.2f} {curr}\n"
                        f"• **Acil Durum Karşılama Süresi:** **{runway_dec} ay**\n\n"
                        f"{assessment}"
                    )
            else:
                if is_english:
                    answer = (
                        f"### Emergency Fund Adequacy Evaluation\n\n"
                        f"Evaluating whether your emergency fund is sufficient requires comparing your liquid reserves against your baseline monthly essential expenses (the 3-to-6 month rule).\n\n"
                        f"**Current Recorded State:**\n"
                        f"• Liquid Cash & Reserve: **{total_cash:,.2f} {curr}**\n"
                        f"• Monthly Essential Expenses: **UNKNOWN**\n"
                        f"• Emergency Runway: **UNKNOWN**\n\n"
                        f"Without knowing your monthly essential living costs, it is impossible to determine whether {total_cash:,.2f} {curr} covers 1 month or 12 months.\n\n"
                        f"Could you share your approximate monthly non-negotiable living expenses (housing, utilities, food, fixed debt minimums)?"
                    )
                else:
                    answer = (
                        f"### Acil Durum Rezervi Değerlendirmesi\n\n"
                        f"Acil durum fonunuzun yeterli olup olmadığını belirlemek, likit rezervlerinizin aylık zorunlu yaşam giderlerinizi kaç ay boyunca sürdürebileceğine (3-6 ay kuralı) bağlıdır.\n\n"
                        f"**Mevcut Kayıt Durumu:**\n"
                        f"• Likit Nakit Rezervi: **{total_cash:,.2f} {curr}**\n"
                        f"• Aylık Zorunlu Giderler: **UNKNOWN (Bilinmiyor)**\n"
                        f"• Acil Durum Karşılama Süresi: **UNKNOWN (Hesaplanamıyor)**\n\n"
                        f"Zorunlu harcamalarınız bilinmeden, mevcut nakdinizin ne kadarlık bir süre güvence sağladığı hesaplanamaz.\n\n"
                        f"Acil durum fonu yeterliliğinizi hesaplayabilmemiz için aylık kira, fatura, gıda ve zorunlu borç ödemeleri gibi asgari harcama tutarınız yaklaşık ne kadardır?"
                    )

        else:  # topic == "risk_capacity"
            profile_data = await InvestorProfileService.get_current_profile(db, user_id)
            has_profile = bool(profile_data and profile_data.get("version_number"))
            risk_tolerance = profile_data.get("risk", {}).get("risk_tolerance", "UNKNOWN") if profile_data else "UNKNOWN"
            horizon = profile_data.get("goals", {}).get("investment_horizon", "UNKNOWN") if profile_data else "UNKNOWN"
            runway = intel.get("emergency_coverage_months")
            stability = fc.income_stability.value if hasattr(fc.income_stability, "value") else str(fc.income_stability)
            dti = intel.get("debt_to_income_pct")

            if has_profile and risk_tolerance != "UNKNOWN":
                runway_str = f"{runway:.1f} months" if (is_english and runway is not None) else (f"{runway:.1f} ay" if runway is not None else "UNKNOWN")
                dti_str = f"{dti:.1f}%" if dti is not None else ("None recorded" if is_english else "Kayıtlı borç yok")
                if is_english:
                    answer = (
                        f"### Risk Capacity & Tolerance Analysis\n\n"
                        f"In portfolio management, risk involves two distinct dimensions: **Risk Tolerance (Psychological willingness)** and **Risk Capacity (Financial ability to absorb drawdowns)**.\n\n"
                        f"**1. Your Profile State:**\n"
                        f"• Declared Risk Tolerance: **{risk_tolerance}**\n"
                        f"• Investment Horizon: **{horizon}**\n"
                        f"• Income Stability: **{stability}**\n"
                        f"• Emergency Buffer: **{runway_str}**\n"
                        f"• Debt Burden: **{dti_str}**\n\n"
                        f"**2. Mandate-Specific Capacity:**\n"
                        f"In PortfolioMind, you don't assign a single global risk level to all your capital. Each **Investment Mandate** operates with its own risk capacity:\n"
                        f"• Near-term capital (e.g. house downpayment in 1-2 years): **LOW / PRESERVATION**\n"
                        f"• Long-term capital (e.g. retirement in 10+ years): **HIGH / GROWTH**\n"
                        f"• Speculative opportunities: **VERY_HIGH**, capped by your global policy limit."
                    )
                else:
                    answer = (
                        f"### Risk Kapasitesi & Toleransı Analizi\n\n"
                        f"Portföy yönetiminde risk iki temel boyutta değerlendirilir: **Risk Toleransı (Psikolojik İsteklilik)** ve **Risk Kapasitesi (Finansal Dayanıklılık)**.\n\n"
                        f"**1. Profil Verileriniz:**\n"
                        f"• Beyan Edilen Risk Toleransı: **{risk_tolerance}**\n"
                        f"• Yatırım Vadesi: **{horizon}**\n"
                        f"• Gelir İstikrarı: **{stability}**\n"
                        f"• Acil Durum Tamponu: **{runway_str}**\n"
                        f"• Borç / Gelir Oranı: **{dti_str}**\n\n"
                        f"**2. Mandat Bazlı Yaklaşım:**\n"
                        f"PortfolioMind'da her **Yatırım Mandatı** hedefine göre bağımsız risk kapasitesine sahiptir. Kısa vadeli hedefler için Düşük (LOW), uzun vadeli büyüme hedefleri için Yüksek (HIGH) risk kapasitesi belirlenir."
                    )
            else:
                if is_english:
                    answer = (
                        f"### Risk Capacity Evaluation\n\n"
                        f"Risk capacity cannot be assumed or invented—it depends on your **financial ability to absorb drawdowns** and your **psychological comfort with volatility**.\n\n"
                        f"**Current Recorded State:**\n"
                        f"• Investor Profile Assessment: **Not Completed (UNKNOWN)**\n"
                        f"• Risk Tolerance: **UNKNOWN**\n"
                        f"• Investment Horizon: **UNKNOWN**\n\n"
                        f"To help determine the appropriate risk capacity for your portfolio:\n"
                        f"1. **Time Horizon:** When do you anticipate needing to withdraw the capital you plan to invest (e.g., less than 2 years, 3-5 years, or 10+ years)?\n"
                        f"2. **Drawdown Comfort:** If your portfolio experienced a temporary market drop of 20%, would you feel compelled to sell to prevent further losses, or could you hold through the volatility?\n"
                        f"3. **Emergency Buffer:** Do you have at least 3-6 months of living expenses saved in cash so you wouldn't need to liquidate investments in an emergency?\n\n"
                        f"You can also complete the structured **Investor Assessment** in your profile settings for a formal evaluation."
                    )
                else:
                    answer = (
                        f"### Risk Kapasitesi Değerlendirmesi\n\n"
                        f"Risk kapasitesi varsayımlara veya tahmine dayandırılamaz. Hem finansal olarak kayıpları karşılama gücünüze (Kapasite) hem de piyasa düşüşlerindeki psikolojik rahatlığınıza (Tolerans) bağlıdır.\n\n"
                        f"**Mevcut Durum:**\n"
                        f"• Yatırımcı Profili Değerlendirmesi: **Tamamlanmadı (UNKNOWN)**\n"
                        f"• Risk Toleransı: **UNKNOWN (Bilinmiyor)**\n"
                        f"• Yatırım Vadesi: **UNKNOWN (Bilinmiyor)**\n\n"
                        f"Size uygun risk kapasitesini belirlemek için:\n"
                        f"1. **Vade (Zaman Ufku):** Yatırım yapmayı planladığınız sermayeye ne zaman ihtiyaç duyacaksınız (örneğin 1-2 yıl, 3-5 yıl, veya 10+ yıl)?\n"
                        f"2. **Düşüş Toleransı:** Piyasalarda %20'lik sert bir düşüş yaşanırsa, bu parayı nakde dönüştürmek zorunda kalır mısınız, yoksa sabırla bekleyebilir misiniz?\n"
                        f"3. **Likit Güvence:** Acil durumlarda yatırımlarınızı satmak zorunda kalmamak için kenarda 3-6 aylık nakit rezerviniz bulunuyor mu?\n\n"
                        f"Dilerseniz profil ayarlarınızdan **Yatırımcı Değerlendirmesi**'ni tamamlayarak risk politikanızı yapılandırabilirsiniz."
                    )

        return CopilotStructuredResponse(
            response_type=CopilotResponseType.ANSWER,
            intent=intent_res.intent.value if hasattr(intent_res.intent, "value") else str(intent_res.intent),
            execution_mode=ExecutionMode.READ_ONLY.value,
            answer=answer,
            context_used=context_bundle.provenance,
        )

