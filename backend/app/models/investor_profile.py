"""Investor Profile, Assessment, Answers, and Versioning domain models.

Implements PortfolioMind Phase 4 per `docs/investor_profile_assessment_spec.md`:
- One per-user Investor Profile container
- Assessment lifecycle and persistent raw answers
- Draft reviews with structured interpretations, uncertainties, and contradictions
- Immutable material versions (v1, v2, ...) with full audit provenance
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import TYPE_CHECKING, Any, List, Optional
import uuid

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    Numeric,
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


class InvestorProfile(Base):
    """Authoritative user-scoped Investor Profile container."""

    __tablename__ = "investor_profiles"
    __table_args__ = (
        Index("ix_investor_profiles_user_id", "user_id", unique=True),
        Index("ix_investor_profiles_active_version_id", "active_version_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True
    )
    active_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    active_preferences_revision_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    completeness_overall_pct: Mapped[Decimal] = mapped_column(
        Numeric(5, 2), nullable=False, default=Decimal("0.00")
    )
    analysis_readiness: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
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

    user: Mapped["User"] = relationship("User")
    versions: Mapped[List["InvestorProfileVersion"]] = relationship(
        "InvestorProfileVersion",
        back_populates="profile",
        cascade="all, delete-orphan",
        order_by="InvestorProfileVersion.version_number.desc()",
    )


class InvestorProfileAssessment(Base):
    """An ongoing or completed questionnaire session for collecting investor answers."""

    __tablename__ = "investor_profile_assessments"
    __table_args__ = (
        Index("ix_investor_profile_assessments_user_id", "user_id"),
        Index("ix_investor_profile_assessments_status", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    base_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    questionnaire_version: Mapped[str] = mapped_column(String(32), default="1.0", nullable=False)
    status: Mapped[str] = mapped_column(
        String(32), default="DRAFT", nullable=False
    )  # 'DRAFT', 'READY', 'CONFIRMED', 'POSTPONED', 'DISCARDED'
    resume_question_id: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

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

    user: Mapped["User"] = relationship("User")
    answers: Mapped[List["InvestorProfileAnswer"]] = relationship(
        "InvestorProfileAnswer",
        back_populates="assessment",
        cascade="all, delete-orphan",
        order_by="InvestorProfileAnswer.answered_at.asc()",
    )


class InvestorProfileAnswer(Base):
    """Raw, immutable answer record preserving exact user inputs, options, and text."""

    __tablename__ = "investor_profile_answers"
    __table_args__ = (
        Index("ix_investor_profile_answers_assessment_id", "assessment_id"),
        Index("ix_investor_profile_answers_user_id", "user_id"),
        Index("ix_investor_profile_answers_question_id", "question_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    assessment_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investor_profile_assessments.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    question_id: Mapped[str] = mapped_column(String(32), nullable=False)  # e.g. 'C01', 'C02'
    item_id: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)  # for goals or repeatable rows
    knowledge_state: Mapped[str] = mapped_column(
        String(32), default="KNOWN", nullable=False
    )  # 'KNOWN', 'UNKNOWN', 'NOT_ASKED', 'SKIPPED', 'DECLINED', 'NOT_APPLICABLE'
    selected_options: Mapped[list[Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=list
    )
    numeric_inputs: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    raw_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    locale: Mapped[str] = mapped_column(String(16), default="en", nullable=False)

    answered_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    assessment: Mapped["InvestorProfileAssessment"] = relationship(
        "InvestorProfileAssessment", back_populates="answers"
    )
    user: Mapped["User"] = relationship("User")


class InvestorProfileVersion(Base):
    """An immutable, confirmed material version of an Investor Profile (v1, v2, ...)."""

    __tablename__ = "investor_profile_versions"
    __table_args__ = (
        Index("ix_investor_profile_versions_profile_id", "profile_id"),
        Index("ix_investor_profile_versions_user_id", "user_id"),
        Index("ix_investor_profile_versions_version_number", "version_number"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    profile_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("investor_profiles.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    previous_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    change_reason: Mapped[str] = mapped_column(String(255), nullable=False)
    change_source: Mapped[str] = mapped_column(
        String(64), nullable=False
    )  # 'ONBOARDING', 'SETTINGS', 'COPILOT', 'REASSESSMENT'
    snapshot: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
    )
    confirmed_by: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        server_default=func.now(),
        nullable=False,
    )

    profile: Mapped["InvestorProfile"] = relationship("InvestorProfile", back_populates="versions")
    user: Mapped["User"] = relationship("User", foreign_keys=[user_id])


class InvestorProfileDraft(Base):
    """A working, unconfirmed profile draft holding candidate fields and review issues."""

    __tablename__ = "investor_profile_drafts"
    __table_args__ = (
        Index("ix_investor_profile_drafts_user_id", "user_id"),
        Index("ix_investor_profile_drafts_assessment_id", "assessment_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    assessment_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        Uuid, ForeignKey("investor_profile_assessments.id", ondelete="SET NULL"), nullable=True
    )
    base_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid, nullable=True)
    draft_data: Mapped[dict[str, Any]] = mapped_column(
        JSON().with_variant(JSONB, "postgresql"), nullable=False, default=dict
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

    user: Mapped["User"] = relationship("User")
    assessment: Mapped[Optional["InvestorProfileAssessment"]] = relationship("InvestorProfileAssessment")
