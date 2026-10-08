"""Separate personal JWT authentication from the scoped Finance bridge."""

import hmac
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.user import User
from app.services.auth import decode_token, get_user_by_id

_bearer = HTTPBearer(auto_error=False)


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired access token",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Accept expiring user JWTs only; bridge credentials cannot impersonate users."""
    if credentials is None:
        raise _unauthorized()
    payload = decode_token(credentials.credentials)
    if payload is None or payload.get("type") != "access":
        raise _unauthorized()
    try:
        subject = payload.get("sub")
        if not isinstance(subject, str):
            raise ValueError
        user_id = UUID(subject)
    except (ValueError, TypeError, AttributeError):
        raise _unauthorized() from None
    user = await get_user_by_id(db, user_id)
    if user is None:
        raise _unauthorized()
    return user


async def get_bridge_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    """Allow the bridge credential only where a route explicitly opts in.

    The credential is bound to one configured, existing user. Missing users or
    configuration never fall back to another account. Personal JWTs continue
    to work on these routes.
    """
    token = settings.integration_token
    if credentials is not None and token and hmac.compare_digest(
        credentials.credentials.encode("utf-8"), token.encode("utf-8")
    ):
        if settings.INTEGRATION_USER_ID is None:
            raise _unauthorized()
        user = await get_user_by_id(db, settings.INTEGRATION_USER_ID)
        if user is None:
            raise _unauthorized()
        return user
    return await get_current_user(credentials, db)
