"""Authentication business logic: passwords, JWTs, and refresh sessions."""

import hashlib
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

import bcrypt
from jose import JWTError, jwt
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.refresh_session import RefreshSession
from app.models.user import User


class RefreshTokenError(ValueError):
    """Raised for any invalid, expired, revoked, or replayed refresh token."""


def hash_password(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def create_access_token(user_id: UUID) -> str:
    expire = _now() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    payload = {"sub": str(user_id), "exp": expire, "type": "access"}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(
    user_id: UUID,
    *,
    jti: UUID,
    expires_at: datetime,
) -> str:
    payload = {
        "sub": str(user_id),
        "jti": str(jti),
        "exp": expires_at,
        "type": "refresh",
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM)


def decode_token(token: str) -> Optional[dict]:
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM],
            options={"require_exp": True, "require_sub": True},
        )
    except JWTError:
        return None


def _hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


async def _stage_refresh_session(
    db: AsyncSession,
    user_id: UUID,
    *,
    family_id: Optional[UUID] = None,
) -> tuple[str, RefreshSession]:
    jti = uuid.uuid4()
    expires_at = _now() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    token = create_refresh_token(user_id, jti=jti, expires_at=expires_at)
    session = RefreshSession(
        jti=jti,
        user_id=user_id,
        family_id=family_id or uuid.uuid4(),
        token_hash=_hash_refresh_token(token),
        expires_at=expires_at,
    )
    db.add(session)
    await db.flush()
    return token, session


async def issue_token_pair(db: AsyncSession, user_id: UUID) -> tuple[str, str]:
    """Create and commit an access token plus a persisted refresh session."""
    try:
        refresh_token, _ = await _stage_refresh_session(db, user_id)
        access_token = create_access_token(user_id)
        await db.commit()
        return access_token, refresh_token
    except Exception:
        await db.rollback()
        raise


def _refresh_identity(token: str) -> tuple[dict, UUID, UUID]:
    payload = decode_token(token)
    if payload is None or payload.get("type") != "refresh":
        raise RefreshTokenError
    try:
        return payload, UUID(payload["sub"]), UUID(payload["jti"])
    except (KeyError, TypeError, ValueError) as exc:
        raise RefreshTokenError from exc


async def _get_locked_refresh_session(
    db: AsyncSession, jti: UUID
) -> Optional[RefreshSession]:
    result = await db.execute(
        select(RefreshSession)
        .where(RefreshSession.jti == jti)
        .with_for_update()
    )
    return result.scalar_one_or_none()


async def rotate_refresh_token(
    db: AsyncSession, token: str
) -> tuple[str, str, User]:
    """Atomically revoke one refresh token and issue its replacement."""
    try:
        _payload, user_id, jti = _refresh_identity(token)
        session = await _get_locked_refresh_session(db, jti)
        if session is None or session.user_id != user_id:
            raise RefreshTokenError
        if not secrets.compare_digest(session.token_hash, _hash_refresh_token(token)):
            raise RefreshTokenError

        if session.revoked_at is not None:
            now = _now()
            await db.execute(
                update(RefreshSession)
                .where(
                    RefreshSession.family_id == session.family_id,
                    RefreshSession.revoked_at.is_(None),
                )
                .values(revoked_at=now)
            )
            await db.commit()
            raise RefreshTokenError

        if _as_utc(session.expires_at) <= _now():
            raise RefreshTokenError

        user = await get_user_by_id(db, user_id)
        if user is None:
            raise RefreshTokenError

        session.revoked_at = _now()
        new_refresh, replacement = await _stage_refresh_session(
            db, user_id, family_id=session.family_id
        )
        session.replaced_by_jti = replacement.jti
        new_access = create_access_token(user_id)
        await db.commit()
        return new_access, new_refresh, user
    except RefreshTokenError:
        if db.in_transaction():
            await db.rollback()
        raise
    except Exception:
        await db.rollback()
        raise


async def revoke_refresh_token(db: AsyncSession, token: str) -> bool:
    """Revoke only the presented device/session token; other families survive."""
    try:
        _payload, user_id, jti = _refresh_identity(token)
        session = await _get_locked_refresh_session(db, jti)
        if (
            session is None
            or session.user_id != user_id
            or not secrets.compare_digest(
                session.token_hash, _hash_refresh_token(token)
            )
        ):
            await db.rollback()
            return False
        if session.revoked_at is None:
            session.revoked_at = _now()
        await db.commit()
        return True
    except RefreshTokenError:
        await db.rollback()
        return False
    except Exception:
        await db.rollback()
        raise


async def get_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    result = await db.execute(select(User).where(User.email == email))
    return result.scalar_one_or_none()


async def get_user_by_id(db: AsyncSession, user_id: UUID) -> Optional[User]:
    result = await db.execute(select(User).where(User.id == user_id))
    return result.scalar_one_or_none()


async def create_user(
    db: AsyncSession,
    email: str,
    password: str,
    display_name: Optional[str] = None,
    base_currency: str = "TRY",
) -> User:
    user = User(
        email=email,
        password_hash=hash_password(password),
        display_name=display_name,
        base_currency=base_currency,
    )
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user
