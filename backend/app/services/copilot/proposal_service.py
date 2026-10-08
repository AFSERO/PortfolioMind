"""Action Proposal service for PortfolioMind Copilot.

Manages the lifecycle of proposed state changes:
DRAFT -> NEEDS_INPUT -> READY_FOR_CONFIRMATION -> CONFIRMED -> APPLIED.
"""

from datetime import datetime, timedelta, timezone
import logging
from typing import Any, List, Optional
from uuid import UUID
import uuid

from fastapi import HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.copilot import CopilotActionProposal
from app.schemas.copilot import (
    ActionProposalStatus,
    ActionType,
    ProposalPermissionLevel,
)

logger = logging.getLogger(__name__)


class CopilotProposalService:
    """Manages creation, retrieval, and status transitions of Copilot Action Proposals."""

    @classmethod
    async def create_proposal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        action_type: str,
        human_readable_summary: str,
        parameters: dict[str, Any],
        permission_level: str = ProposalPermissionLevel.LEVEL_2_CONFIRMATION_REQUIRED.value,
        conversation_id: Optional[UUID] = None,
        current_state_snapshot: Optional[dict[str, Any]] = None,
        expected_impact: Optional[dict[str, Any]] = None,
        warnings: Optional[List[str]] = None,
        idempotency_key: Optional[str] = None,
        status: str = ActionProposalStatus.READY_FOR_CONFIRMATION.value,
        expires_in_seconds: int = 86400,  # 24 hours
    ) -> CopilotActionProposal:
        """Create and persist a new action proposal."""
        key = idempotency_key or f"prop_{uuid.uuid4().hex}"
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=expires_in_seconds)

        proposal = CopilotActionProposal(
            user_id=user_id,
            conversation_id=conversation_id,
            action_type=action_type,
            permission_level=permission_level,
            status=status,
            parameters=parameters,
            current_state_snapshot=current_state_snapshot,
            expected_impact=expected_impact,
            human_readable_summary=human_readable_summary,
            warnings=warnings or [],
            idempotency_key=key,
            created_at=now,
            expires_at=expires_at,
        )

        db.add(proposal)
        await db.commit()
        await db.refresh(proposal)
        logger.info(
            "Created action proposal %s (%s, status=%s) for user %s",
            proposal.id,
            action_type,
            status,
            user_id,
        )
        return proposal

    @classmethod
    async def get_proposal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal_id: UUID,
    ) -> Optional[CopilotActionProposal]:
        """Fetch an action proposal verifying strict user ownership."""
        stmt = select(CopilotActionProposal).where(
            CopilotActionProposal.id == proposal_id,
            CopilotActionProposal.user_id == user_id,
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    @classmethod
    async def list_proposals(
        cls,
        db: AsyncSession,
        user_id: UUID,
        conversation_id: Optional[UUID] = None,
        status_filter: Optional[str] = None,
        limit: int = 50,
    ) -> List[CopilotActionProposal]:
        """List proposals for a user with optional filters."""
        stmt = select(CopilotActionProposal).where(
            CopilotActionProposal.user_id == user_id
        )
        if conversation_id is not None:
            stmt = stmt.where(CopilotActionProposal.conversation_id == conversation_id)
        if status_filter:
            stmt = stmt.where(CopilotActionProposal.status == status_filter)

        stmt = stmt.order_by(desc(CopilotActionProposal.created_at)).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @classmethod
    async def cancel_proposal(
        cls,
        db: AsyncSession,
        user_id: UUID,
        proposal_id: UUID,
        reason: Optional[str] = None,
    ) -> CopilotActionProposal:
        """Explicitly cancel a pending action proposal."""
        proposal = await cls.get_proposal(db, user_id, proposal_id)
        if not proposal:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Action proposal not found or access denied.",
            )

        if proposal.status in (
            ActionProposalStatus.APPLIED.value,
            ActionProposalStatus.CANCELLED.value,
            ActionProposalStatus.EXPIRED.value,
        ):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot cancel action proposal in '{proposal.status}' state.",
            )

        proposal.status = ActionProposalStatus.CANCELLED.value
        if reason:
            warnings = list(proposal.warnings or [])
            warnings.append(f"Cancelled by user: {reason}")
            proposal.warnings = warnings

        await db.commit()
        await db.refresh(proposal)
        logger.info("Cancelled action proposal %s for user %s", proposal_id, user_id)
        return proposal
