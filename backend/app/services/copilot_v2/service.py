"""Top-level Copilot V2 Orchestration Service.

Coordinates FAST Orchestrator, Reasoner Engine, session continuity,
DB-backed recovery, ephemeral progress events, and telemetry traces across conversational requests.

CORE INVARIANTS:
1. Canonical memory is PostgreSQL (copilot_conversations, copilot_messages).
   Codex CLI session is an acceleration layer.
2. Escalation from FAST to BALANCED/DEEP strictly reuses the SAME session ID.
3. If Codex session resume fails, conversation recovers seamlessly from PostgreSQL history.
4. Ephemeral progress events (STARTED, TOOL_RUNNING, ESCALATING, REASONING, COMPLETED, FAILED)
   are emitted to callers/clients but NEVER persisted to copilot_messages.
5. Read-only safety: User financial assets and data are never mutated.
"""

import logging
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.copilot import CopilotConversation
from app.schemas.copilot import ActionProposalResponse
from app.services.copilot_v2.action_executor import ActionExecutorV2
from app.services.copilot_v2.adapter import CodexV2Adapter
from app.services.copilot_v2.contracts import (
    HandoffContext,
    OrchestratorAction,
    OrchestratorResult,
)
from app.services.copilot_v2.errors import CodexSessionResumeError
from app.services.copilot_v2.events import EventEmitter, ProgressCallback, ProgressEvent
from app.services.copilot_v2.orchestrator import FastOrchestrator
from app.services.copilot_v2.profiles import ModelProfile
from app.services.copilot_v2.reasoner import ReasonerEngine
from app.services.copilot_v2.session import SessionManager
from app.services.copilot_v2.telemetry import ExecutionTrace
from app.services.copilot_v2.tools.registry import ToolRegistry, default_tool_registry

logger = logging.getLogger(__name__)


class CopilotV2Service:
    """Entry point for Copilot V2 interactions."""

    def __init__(
        self,
        adapter: Optional[CodexV2Adapter] = None,
        registry: Optional[ToolRegistry] = None,
    ):
        self.adapter = adapter or CodexV2Adapter()
        self.registry = registry or default_tool_registry
        self.orchestrator = FastOrchestrator(adapter=self.adapter, registry=self.registry)
        self.reasoner = ReasonerEngine(adapter=self.adapter, registry=self.registry)

    async def _execute_turn(
        self,
        db: AsyncSession,
        user_id: UUID,
        user_message: str,
        session_id: Optional[str],
        trace: ExecutionTrace,
        conversation_context: Optional[str],
        event_emitter: EventEmitter,
    ) -> Dict[str, Any]:
        """Internal turn execution: runs FAST, and escalates to Reasoner if needed."""
        # 1. Run the FAST Orchestrator
        orch_result: OrchestratorResult = await self.orchestrator.run(
            db=db,
            user_id=user_id,
            user_message=user_message,
            trace=trace,
            conversation_context=conversation_context,
            session_id=session_id,
            event_emitter=event_emitter,
        )

        active_session_id = orch_result.session_id or session_id

        # Check for any proposal or simulation created
        target_proposal_id = orch_result.proposal_id or getattr(self.reasoner, "last_proposal_id", None)
        proposal_dict = None
        if target_proposal_id:
            try:
                prop_obj = await ActionExecutorV2.get_proposal(db, user_id, UUID(str(target_proposal_id)))
                if prop_obj:
                    proposal_dict = ActionProposalResponse.model_validate(prop_obj).model_dump(mode="json")
            except Exception as prop_err:
                logger.warning("Failed to serialize proposal %s: %s", target_proposal_id, prop_err)

        simulation_dict = orch_result.simulation or getattr(self.reasoner, "last_simulation", None)

        # Case A: FAST solved the task directly
        if orch_result.action == OrchestratorAction.FINAL_RESPONSE:
            return {
                "answer": orch_result.final_answer or "",
                "tools_used": orch_result.tools_used,
                "escalated": False,
                "handoff": None,
                "session_id": active_session_id,
                "external_sources": orch_result.external_sources or [],
                "proposal": proposal_dict,
                "simulation": simulation_dict,
            }

        # Case B: FAST escalated to BALANCED or DEEP (SAME session ID)
        elif orch_result.action == OrchestratorAction.HANDOFF and orch_result.handoff:
            handoff: HandoffContext = orch_result.handoff
            logger.info(
                "FAST escalated to %s (effort=%s) in session %s. Reason: %s",
                handoff.target_profile.value,
                handoff.reasoning_effort.value,
                active_session_id,
                handoff.escalation_reason,
            )

            final_answer = await self.reasoner.execute(
                db=db,
                user_id=user_id,
                handoff=handoff,
                trace=trace,
                session_id=active_session_id,
                event_emitter=event_emitter,
            )

            active_session_id = handoff.session_id or active_session_id

            # Check if reasoner created a proposal or simulation
            if not proposal_dict and getattr(self.reasoner, "last_proposal_id", None):
                r_prop_id = self.reasoner.last_proposal_id
                try:
                    prop_obj = await ActionExecutorV2.get_proposal(db, user_id, UUID(str(r_prop_id)))
                    if prop_obj:
                        proposal_dict = ActionProposalResponse.model_validate(prop_obj).model_dump(mode="json")
                except Exception as prop_err:
                    logger.warning("Failed to serialize reasoner proposal %s: %s", r_prop_id, prop_err)

            if not simulation_dict and getattr(self.reasoner, "last_simulation", None):
                simulation_dict = self.reasoner.last_simulation

            # Combine sources from handoff and any newly fetched by Reasoner
            reasoner_sources = getattr(self.reasoner, "last_external_sources", []) or []
            combined_sources = list(handoff.external_evidence) if handoff.external_evidence else []
            seen_urls = {
                s.get("url") for s in combined_sources if isinstance(s, dict) and s.get("url")
            }
            for s in reasoner_sources:
                if isinstance(s, dict) and s.get("url"):
                    if s["url"] not in seen_urls:
                        combined_sources.append(s)
                        seen_urls.add(s["url"])
                elif s not in combined_sources:
                    combined_sources.append(s)

            return {
                "answer": final_answer,
                "tools_used": trace.tools_called,
                "escalated": True,
                "handoff": handoff.model_dump(),
                "session_id": active_session_id,
                "external_sources": combined_sources,
                "proposal": proposal_dict,
                "simulation": simulation_dict,
            }

        # Degraded fallback
        return {
            "answer": orch_result.final_answer or "İsteğiniz başarıyla değerlendirildi.",
            "tools_used": orch_result.tools_used,
            "escalated": False,
            "handoff": None,
            "session_id": active_session_id,
            "external_sources": orch_result.external_sources or [],
            "proposal": proposal_dict,
            "simulation": simulation_dict,
        }

    async def handle_user_message(
        self,
        db: AsyncSession,
        user_id: UUID,
        user_message: str,
        conversation_id: Optional[UUID] = None,
        conversation_context: Optional[str] = None,
        progress_callback: Optional[ProgressCallback] = None,
    ) -> Dict[str, Any]:
        """Execute the locked V2 conversational flow with session continuity and recovery."""
        trace = ExecutionTrace(starting_profile=ModelProfile.FAST)
        if conversation_id:
            trace.conversation_id = str(conversation_id)

        event_emitter = EventEmitter(callback=progress_callback, trace=trace)
        await event_emitter.emit(ProgressEvent.started())

        conversation: Optional[CopilotConversation] = None
        effective_context = conversation_context
        current_session_id: Optional[str] = None

        try:
            # 1. Database-backed canonical session lookup and persistence
            if conversation_id:
                conversation = await SessionManager.get_conversation(db, conversation_id, user_id)
                if conversation:
                    current_session_id = conversation.codex_session_id
                    # Persist user's message before calling model
                    await SessionManager.record_user_message(db, conversation_id, user_message)

                    # Build conversational history if not explicitly passed
                    if not effective_context:
                        db_history = await SessionManager.build_history_context_from_db(
                            db, conversation_id, max_turns=6, exclude_last_message=True
                        )
                        effective_context = db_history if db_history else None

            # 2. Execute turn with automatic session recovery if resume fails
            try:
                turn_result = await self._execute_turn(
                    db=db,
                    user_id=user_id,
                    user_message=user_message,
                    session_id=current_session_id,
                    trace=trace,
                    conversation_context=effective_context,
                    event_emitter=event_emitter,
                )
            except CodexSessionResumeError as resume_err:
                logger.warning(
                    "Session resume failed for %s (%s). Initiating canonical DB recovery.",
                    current_session_id,
                    resume_err,
                )
                trace.record_resume_failure()

                # Reconstruct full context from canonical database memory
                if conversation:
                    await SessionManager.mark_codex_session_stale(
                        db, conversation, reason=f"Resume failed: {str(resume_err)}"
                    )
                    recovery_context = await SessionManager.build_history_context_from_db(
                        db, conversation_id, max_turns=6, exclude_last_message=True
                    )
                    effective_context = recovery_context

                # Reset session_id to None so Codex starts a fresh persistent session
                current_session_id = None
                trace.record_recovery()

                # Retry turn with recovered context and fresh session
                turn_result = await self._execute_turn(
                    db=db,
                    user_id=user_id,
                    user_message=user_message,
                    session_id=None,
                    trace=trace,
                    conversation_context=effective_context,
                    event_emitter=event_emitter,
                )

            # 3. Post-execution persistence and notifications
            final_answer = turn_result["answer"]
            final_session_id = turn_result.get("session_id") or current_session_id
            external_sources = turn_result.get("external_sources", [])
            trace.source_count_used_in_final_answer = len(external_sources)

            await event_emitter.emit(ProgressEvent.completed())

            asst_msg = None
            proposal = turn_result.get("proposal")
            simulation = turn_result.get("simulation")
            if conversation and conversation_id:
                if final_session_id:
                    await SessionManager.update_codex_session(db, conversation, final_session_id)
                # Store final assistant response in canonical database log
                msg_metadata = {
                    "escalated": turn_result["escalated"],
                    "tools_used": turn_result["tools_used"],
                    "trace": trace.to_dict(),
                    "external_sources": external_sources,
                }
                if proposal:
                    msg_metadata["proposal"] = proposal
                    msg_metadata["response_type"] = "PROPOSAL"
                elif simulation:
                    msg_metadata["simulation"] = simulation
                    msg_metadata["response_type"] = "SIMULATION"

                asst_msg = await SessionManager.record_assistant_message(
                    db,
                    conversation_id,
                    final_answer,
                    metadata=msg_metadata,
                )

            trace.finalize()
            return {
                "answer": final_answer,
                "tools_used": turn_result["tools_used"],
                "escalated": turn_result["escalated"],
                "handoff": turn_result["handoff"],
                "session_id": final_session_id,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "message_id": str(asst_msg.id) if asst_msg else None,
                "created_at": asst_msg.created_at.isoformat() if asst_msg else None,
                "trace": trace.to_dict(),
                "external_sources": external_sources,
                "proposal": proposal,
                "simulation": simulation,
            }

        except Exception as exc:
            logger.error("Copilot V2 error processing message: %s", exc, exc_info=True)
            await event_emitter.emit(ProgressEvent.failed(error=type(exc).__name__))
            trace.record_failure(type(exc).__name__)
            trace.finalize()
            return {
                "answer": (
                    "Talebiniz işlenirken bir sorun oluştu. "
                    "Portföy verileriniz tamamen güvendedir ve herhangi bir değişiklik yapılmamıştır."
                ),
                "tools_used": trace.tools_called,
                "escalated": trace.escalation_occurred,
                "handoff": None,
                "session_id": current_session_id,
                "conversation_id": str(conversation_id) if conversation_id else None,
                "trace": trace.to_dict(),
                "external_sources": [],
            }
