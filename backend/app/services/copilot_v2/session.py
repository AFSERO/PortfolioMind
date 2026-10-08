"""Database-backed session continuity and recovery manager for Copilot V2.

ARCHITECTURE INVARIANT:
PostgreSQL (`copilot_conversations`, `copilot_messages`) is the canonical source of truth.
The local Codex session is an acceleration layer.
If a Codex session disappears or rollout is missing, the conversation is seamlessly
recovered using bounded recent history from PostgreSQL.
"""

from datetime import datetime, timezone
import logging
from typing import Any, Dict, List, Optional, Sequence
from uuid import UUID

from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.copilot import CopilotConversation, CopilotMessage

logger = logging.getLogger(__name__)


def build_recovery_context(messages: Sequence[CopilotMessage], max_turns: int = 6) -> str:
    """Format recent database messages into a compact transcript for session recovery.

    Preserves up to `max_turns` back-and-forth turns.
    """
    if not messages:
        return ""

    # Keep at most max_turns * 2 recent messages
    recent_messages = list(messages)[-(max_turns * 2) :]
    lines = ["=== PRIOR CONVERSATION HISTORY (RECOVERED FROM DATABASE) ==="]
    for msg in recent_messages:
        role_label = "User" if msg.role.lower() == "user" else "Assistant"
        # Bounded line trimming to keep prompt focused
        content = (msg.raw_content or "").strip()
        if content:
            lines.append(f"[{role_label}]: {content}")

    lines.append("=== END PRIOR HISTORY ===")
    return "\n".join(lines)


class SessionManager:
    """Manages database-backed conversation persistence and Codex session synchronization."""

    @staticmethod
    async def get_conversation(
        db: AsyncSession,
        conversation_id: UUID,
        user_id: UUID,
    ) -> Optional[CopilotConversation]:
        """Fetch conversation ensuring user ownership."""
        stmt = select(CopilotConversation).where(
            CopilotConversation.id == conversation_id,
            CopilotConversation.user_id == user_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @staticmethod
    async def get_or_create_conversation(
        db: AsyncSession,
        user_id: UUID,
        conversation_id: Optional[UUID] = None,
        title: Optional[str] = None,
    ) -> CopilotConversation:
        """Fetch existing conversation or create a new one."""
        if conversation_id:
            conv = await SessionManager.get_conversation(db, conversation_id, user_id)
            if conv:
                return conv

        new_conv = CopilotConversation(
            user_id=user_id,
            title=title or "Yeni Sohbet",
            codex_session_status="ACTIVE",
            session_metadata={},
        )
        db.add(new_conv)
        await db.commit()
        await db.refresh(new_conv)
        return new_conv

    @staticmethod
    async def record_user_message(
        db: AsyncSession,
        conversation_id: UUID,
        content: str,
    ) -> CopilotMessage:
        """Persist user message immediately before inference."""
        msg = CopilotMessage(
            conversation_id=conversation_id,
            role="user",
            raw_content=content,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def record_assistant_message(
        db: AsyncSession,
        conversation_id: UUID,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> CopilotMessage:
        """Persist assistant response to the canonical database log."""
        msg = CopilotMessage(
            conversation_id=conversation_id,
            role="assistant",
            raw_content=content,
            structured_metadata=metadata,
        )
        db.add(msg)
        await db.commit()
        await db.refresh(msg)
        return msg

    @staticmethod
    async def update_codex_session(
        db: AsyncSession,
        conversation: CopilotConversation,
        codex_session_id: str,
        status: str = "ACTIVE",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Update conversation with latest Codex session ID and status."""
        conversation.codex_session_id = codex_session_id
        conversation.codex_session_status = status
        current_meta = dict(conversation.session_metadata or {})
        if metadata:
            current_meta.update(metadata)
        current_meta["last_session_update"] = datetime.now(timezone.utc).isoformat()
        conversation.session_metadata = current_meta
        conversation.updated_at = datetime.now(timezone.utc)
        await db.commit()
        await db.refresh(conversation)

    @staticmethod
    async def mark_codex_session_stale(
        db: AsyncSession,
        conversation: CopilotConversation,
        reason: str = "RESUME_FAILED",
    ) -> None:
        """Mark current session as stale when resume fails."""
        conversation.codex_session_status = "STALE"
        current_meta = dict(conversation.session_metadata or {})
        current_meta["stale_reason"] = reason
        current_meta["stale_at"] = datetime.now(timezone.utc).isoformat()
        conversation.session_metadata = current_meta
        await db.commit()
        await db.refresh(conversation)

    @staticmethod
    async def build_history_context_from_db(
        db: AsyncSession,
        conversation_id: UUID,
        max_turns: int = 6,
        exclude_last_message: bool = True,
    ) -> str:
        """Retrieve recent conversation turns from PostgreSQL and build formatted context."""
        stmt = (
            select(CopilotMessage)
            .where(CopilotMessage.conversation_id == conversation_id)
            .order_by(CopilotMessage.created_at.asc())
        )
        res = await db.execute(stmt)
        messages = list(res.scalars().all())

        if exclude_last_message and messages:
            # Exclude current user message that was just persisted
            messages = messages[:-1]

        return build_recovery_context(messages, max_turns=max_turns)
