"""Copilot conversation and message persistence models.

Stores user conversation history and raw messages with intent, context provenance,
and structured AI response metadata.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, List, Optional
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    JSON,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base

if TYPE_CHECKING:
    from app.models.user import User


class CopilotConversation(Base):
    """A user-scoped conversation session with PortfolioMind Copilot."""

    __tablename__ = "copilot_conversations"
    __table_args__ = (
        Index("ix_copilot_conversations_user_id", "user_id"),
        Index("ix_copilot_conversations_updated_at", "updated_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    title: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    codex_session_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    codex_session_status: Mapped[Optional[str]] = mapped_column(String(32), nullable=True, default="ACTIVE")
    session_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=dict
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    messages: Mapped[List["CopilotMessage"]] = relationship(
        "CopilotMessage",
        back_populates="conversation",
        cascade="all, delete-orphan",
        order_by="CopilotMessage.created_at.asc()",
        lazy="selectin",
    )
    user: Mapped["User"] = relationship("User")


class CopilotMessage(Base):
    """An individual message within a Copilot conversation.

    Invariants:
    1. The raw user message must be preserved exactly in raw_content without mutation.
    2. Intent and structured metadata are optionally stored alongside the message.
    """

    __tablename__ = "copilot_messages"
    __table_args__ = (
        Index("ix_copilot_messages_conversation_id", "conversation_id"),
        Index("ix_copilot_messages_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    conversation_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("copilot_conversations.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(String(32), nullable=False)  # 'user', 'assistant', 'system'
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    intent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    structured_metadata: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    conversation: Mapped["CopilotConversation"] = relationship(
        "CopilotConversation", back_populates="messages"
    )


class CopilotActionProposal(Base):
    """A proposed state change created by Copilot requiring explicit user confirmation.

    Invariants:
    1. Financial mutations (BUY/SELL) are NEVER applied automatically.
    2. Proposals maintain a lifecycle: DRAFT -> NEEDS_INPUT -> READY_FOR_CONFIRMATION -> CONFIRMED -> APPLIED.
    3. Idempotency is enforced: confirming multiple times returns the existing result without re-executing.
    4. Proposals are scoped strictly to the owning user.
    """

    __tablename__ = "copilot_action_proposals"
    __table_args__ = (
        Index("ix_copilot_action_proposals_user_id", "user_id"),
        Index("ix_copilot_action_proposals_conversation_id", "conversation_id"),
        Index("ix_copilot_action_proposals_status", "status"),
        Index("ix_copilot_action_proposals_idempotency_key", "idempotency_key"),
        Index("ix_copilot_action_proposals_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    conversation_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("copilot_conversations.id", ondelete="SET NULL"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    permission_level: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="DRAFT")
    parameters: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    expected_impact: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    current_state_snapshot: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    human_readable_summary: Mapped[str] = mapped_column(Text, nullable=False)
    warnings: Mapped[Optional[list[Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True, default=list
    )
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    applied_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    execution_result: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )

    user: Mapped["User"] = relationship("User")
    conversation: Mapped[Optional["CopilotConversation"]] = relationship("CopilotConversation")


class CopilotAuditLog(Base):
    """Durable audit trail for every AI-triggered or AI-proposed state change.

    Invariants:
    1. Independent of chat message retention (survives conversation deletion).
    2. Records complete provenance: user request, interpreted intent, affected entity IDs, old/new states.
    3. Immutable record of mutations and their outcomes.
    """

    __tablename__ = "copilot_audit_logs"
    __table_args__ = (
        Index("ix_copilot_audit_logs_user_id", "user_id"),
        Index("ix_copilot_audit_logs_proposal_id", "proposal_id"),
        Index("ix_copilot_audit_logs_idempotency_key", "idempotency_key"),
        Index("ix_copilot_audit_logs_created_at", "created_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    proposal_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("copilot_action_proposals.id", ondelete="SET NULL"), nullable=True
    )
    action_type: Mapped[str] = mapped_column(String(64), nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(128), nullable=False)
    user_request: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    interpreted_intent: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    affected_resource_type: Mapped[str] = mapped_column(String(64), nullable=False)
    affected_resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    old_state: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    new_state: Mapped[Optional[dict[str, Any]]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=True
    )
    execution_status: Mapped[str] = mapped_column(String(32), nullable=False)  # 'SUCCESS', 'FAILED'
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    user: Mapped["User"] = relationship("User")
    proposal: Mapped[Optional["CopilotActionProposal"]] = relationship("CopilotActionProposal")

