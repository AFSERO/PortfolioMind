"""Copilot V2 HTTP & Streaming Router.

Exposes Copilot V2 via an authenticated streaming endpoint:
POST /api/copilot/v2/conversations/{conversation_id}/messages

Core Responsibilities:
1. Authenticate current_user and enforce conversation ownership.
2. Prevent concurrent turn executions on the same conversation session (HTTP 409 Conflict).
3. Stream ephemeral progress events (STARTED, TOOL_RUNNING, ESCALATING, REASONING) via SSE.
4. Stream final assistant response (FINAL) and error events (FAILED).
5. Ensure database persistence and session integrity even if the client disconnects mid-stream.
6. Strictly preserve V1/V2 isolation (never route through V1 IntentClassifier).
"""

import asyncio
from collections import defaultdict
from datetime import datetime, timezone
import json
import logging
from typing import Any, AsyncGenerator, Dict, Optional
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.copilot import (
    ActionProposalCancelRequest,
    ActionProposalConfirmRequest,
    ActionProposalResponse,
)
from app.services.copilot_v2.action_executor import ActionExecutorV2
from app.services.copilot_v2.events import ProgressEvent, ProgressEventType
from app.services.copilot_v2.service import CopilotV2Service
from app.services.copilot_v2.session import SessionManager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/copilot/v2", tags=["copilot_v2"])

# Per-conversation in-flight concurrency locks
_conversation_locks: Dict[uuid.UUID, asyncio.Lock] = defaultdict(asyncio.Lock)

# Singleton service instance
_copilot_v2_service = CopilotV2Service()


class CopilotV2MessageRequest(BaseModel):
    """Payload for submitting a user message to Copilot V2."""

    content: str = Field(..., min_length=1, max_length=10000, description="User prompt text")
    page_context: Optional[Dict[str, Any]] = Field(
        default=None, description="Optional client route/page context"
    )


def format_sse(data: Dict[str, Any]) -> str:
    """Format dictionary as Server-Sent Event (SSE) line."""
    payload = json.dumps(data, ensure_ascii=False)
    return f"data: {payload}\n\n"


@router.post("/conversations/{conversation_id}/messages")
async def send_v2_message(
    conversation_id: uuid.UUID,
    body: CopilotV2MessageRequest,
    request: Request,
    stream: bool = Query(default=True, description="Whether to stream progress events via SSE"),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Post a user message to Copilot V2 with live progress streaming.

    Streams:
    - STARTED: Initial ingestion
    - TOOL_RUNNING: Real-time tool invocation with tool name & localized status
    - ESCALATING: Model transition from FAST to BALANCED/DEEP
    - REASONING: Reasoning synthesis status
    - FINAL: Final response message and telemetry diagnostics
    - FAILED: Graceful error status
    """
    # 1. Enforce user ownership of conversation
    conversation = await SessionManager.get_conversation(db, conversation_id, current_user.id)
    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found",
        )

    # 2. Enforce concurrency protection: only one in-flight turn per conversation
    lock = _conversation_locks[conversation_id]
    if lock.locked():
        logger.warning(
            "Concurrent message rejected for conversation %s by user %s",
            conversation_id,
            current_user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="A message is already being processed in this conversation. Please wait for the current response to complete.",
        )

    # If streaming is not requested, execute synchronously and return JSON
    if not stream:
        async with lock:
            result = await _copilot_v2_service.handle_user_message(
                db=db,
                user_id=current_user.id,
                user_message=body.content,
                conversation_id=conversation_id,
            )
            return {
                "status": "success",
                "data": {
                    "message": {
                        "id": result.get("message_id") or str(uuid.uuid4()),
                        "conversation_id": str(conversation_id),
                        "role": "assistant",
                        "raw_content": result["answer"],
                        "created_at": result.get("created_at") or datetime.now(timezone.utc).isoformat(),
                        "structured_metadata": {
                            "escalated": result["escalated"],
                            "tools_used": result["tools_used"],
                            "trace": result.get("trace"),
                            "external_sources": result.get("external_sources", []),
                            "proposal": result.get("proposal"),
                        },
                    },
                    "session_id": result.get("session_id"),
                    "trace": result.get("trace"),
                },
            }

    # 3. Streaming execution with event queue
    queue: asyncio.Queue[Optional[Dict[str, Any]]] = asyncio.Queue()

    async def on_progress(event: ProgressEvent) -> None:
        """Forward internal engine progress events to the SSE queue."""
        event_dict: Dict[str, Any] = {
            "type": event.event_type.value,
            "message": event.message,
        }
        if event.event_type == ProgressEventType.TOOL_RUNNING:
            event_dict["tool"] = event.details.get("tool")
        elif event.event_type == ProgressEventType.ESCALATING:
            event_dict["target_profile"] = event.details.get("target_profile")
        elif event.event_type == ProgressEventType.REASONING:
            event_dict["profile"] = event.details.get("profile")
            event_dict["effort"] = event.details.get("effort")
        await queue.put(event_dict)

    async def run_service_task() -> None:
        """Execute the service turn under the concurrency lock."""
        async with lock:
            try:
                result = await _copilot_v2_service.handle_user_message(
                    db=db,
                    user_id=current_user.id,
                    user_message=body.content,
                    conversation_id=conversation_id,
                    progress_callback=on_progress,
                )

                final_event = {
                    "type": "FINAL",
                    "message": {
                        "id": result.get("message_id") or str(uuid.uuid4()),
                        "conversation_id": str(conversation_id),
                        "role": "assistant",
                        "raw_content": result["answer"],
                        "created_at": result.get("created_at") or datetime.now(timezone.utc).isoformat(),
                        "structured_metadata": {
                            "escalated": result["escalated"],
                            "tools_used": result["tools_used"],
                            "trace": result.get("trace"),
                            "external_sources": result.get("external_sources", []),
                            "proposal": result.get("proposal"),
                            "simulation": result.get("simulation"),
                        },
                    },

                    "session_id": result.get("session_id"),
                    "trace": result.get("trace"),
                }
                await queue.put(final_event)
            except Exception as exc:
                logger.error("Error in Copilot V2 streaming execution: %s", exc, exc_info=True)
                await queue.put({
                    "type": "FAILED",
                    "message": "Talebiniz işlenirken beklenmeyen bir hata oluştu.",
                })
            finally:
                # Sentinel to signal stream completion
                await queue.put(None)

    # Launch execution as a shielded background task so client disconnect cannot corrupt DB
    execution_task = asyncio.create_task(run_service_task())

    async def event_generator() -> AsyncGenerator[str, None]:
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield format_sse(item)
        except asyncio.CancelledError:
            logger.info("Client disconnected from Copilot V2 stream for conversation %s", conversation_id)
            # Allow the underlying execution task to finalize DB persistence cleanly
            await asyncio.shield(execution_task)
            raise

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get("/action-proposals/{proposal_id}")
async def get_action_proposal(
    proposal_id: uuid.UUID,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Retrieve details for a specific V2 action proposal."""
    proposal = await ActionExecutorV2.get_proposal(
        db=db, user_id=current_user.id, proposal_id=proposal_id
    )
    if not proposal:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Action proposal not found or access denied.",
        )
    return {
        "status": "success",
        "data": ActionProposalResponse.model_validate(proposal).model_dump(mode="json"),
    }


@router.post("/action-proposals/{proposal_id}/confirm")
async def confirm_action_proposal(
    proposal_id: uuid.UUID,
    body: ActionProposalConfirmRequest = ActionProposalConfirmRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Confirm and execute a staged V2 action proposal via deterministic domain services."""
    result = await ActionExecutorV2.execute_proposal(
        db=db,
        user_id=current_user.id,
        proposal_id=proposal_id,
        idempotency_key=body.idempotency_key,
    )
    return {
        "status": "success",
        "data": result,
    }


@router.post("/action-proposals/{proposal_id}/cancel")
async def cancel_action_proposal(
    proposal_id: uuid.UUID,
    body: ActionProposalCancelRequest = ActionProposalCancelRequest(),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Explicitly cancel a pending V2 action proposal."""
    cancelled = await ActionExecutorV2.cancel_proposal(
        db=db,
        user_id=current_user.id,
        proposal_id=proposal_id,
        reason=body.reason,
    )
    return {
        "status": "success",
        "data": ActionProposalResponse.model_validate(cancelled).model_dump(mode="json"),
    }

