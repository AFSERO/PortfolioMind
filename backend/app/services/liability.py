"""Liability CRUD with ownership and transaction boundaries in the service layer."""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.liability import Liability
from app.schemas.liability import LiabilityCreateRequest, LiabilityUpdateRequest


async def list_liabilities(db: AsyncSession, user_id: UUID) -> list[Liability]:
    result = await db.execute(
        select(Liability)
        .where(Liability.user_id == user_id)
        .order_by(Liability.created_at.desc())
    )
    return list(result.scalars().all())


async def get_liability(
    db: AsyncSession, liability_id: UUID, user_id: UUID
) -> Optional[Liability]:
    result = await db.execute(
        select(Liability).where(
            Liability.id == liability_id,
            Liability.user_id == user_id,
        )
    )
    return result.scalar_one_or_none()


async def create_liability(
    db: AsyncSession, user_id: UUID, data: LiabilityCreateRequest
) -> Liability:
    liability = Liability(user_id=user_id, **data.model_dump())
    db.add(liability)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(liability)
    return liability


async def update_liability(
    db: AsyncSession,
    liability_id: UUID,
    user_id: UUID,
    data: LiabilityUpdateRequest,
) -> Optional[Liability]:
    liability = await get_liability(db, liability_id, user_id)
    if liability is None:
        return None
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(liability, field, value)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    await db.refresh(liability)
    return liability


async def delete_liability(
    db: AsyncSession, liability_id: UUID, user_id: UUID
) -> bool:
    liability = await get_liability(db, liability_id, user_id)
    if liability is None:
        return False
    await db.delete(liability)
    try:
        await db.commit()
    except Exception:
        await db.rollback()
        raise
    return True

