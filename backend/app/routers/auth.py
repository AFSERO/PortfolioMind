from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.extensions import limiter
from app.middleware.auth import get_current_user
from app.models.user import User
from app.schemas.auth import UserLoginRequest, UserRegisterRequest, UserResponse
from app.services import auth as auth_service
from app.services import cash as cash_service

router = APIRouter()

_COOKIE_MAX_AGE = settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400


def _set_refresh_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key="refresh_token",
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite="lax",
        max_age=_COOKIE_MAX_AGE,
        path="/api/auth",
    )


@router.post("/register", status_code=201)
@limiter.limit("5/minute")
async def register(
    request: Request,
    body: UserRegisterRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Register a new user account.

    Returns an access token in the body and sets a refresh token as an
    httpOnly cookie.
    """
    existing = await auth_service.get_user_by_email(db, body.email)
    if existing:
        raise HTTPException(status_code=409, detail="Email already registered")

    user = await auth_service.create_user(
        db,
        email=body.email,
        password=body.password,
        display_name=body.display_name,
        base_currency=body.base_currency,
    )

    await cash_service.create_default_accounts(db, user.id)
    await db.commit()

    access_token, refresh_token = await auth_service.issue_token_pair(db, user.id)
    _set_refresh_cookie(response, refresh_token)

    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(mode="json"),
        },
    }


@router.post("/login")
@limiter.limit("5/minute")
async def login(
    request: Request,
    body: UserLoginRequest,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Authenticate with email + password.

    Returns an access token in the body and sets a refresh token as an
    httpOnly cookie.
    """
    user = await auth_service.get_user_by_email(db, body.email)
    if not user or not auth_service.verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    access_token, refresh_token = await auth_service.issue_token_pair(db, user.id)
    _set_refresh_cookie(response, refresh_token)

    return {
        "status": "success",
        "data": {
            "access_token": access_token,
            "token_type": "bearer",
            "user": UserResponse.model_validate(user).model_dump(mode="json"),
        },
    }


@router.post("/refresh")
@limiter.limit("5/minute")
async def refresh(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Issue a new access token using the refresh token cookie."""
    token = request.cookies.get("refresh_token")
    if not token:
        raise HTTPException(status_code=401, detail="Refresh token missing")

    try:
        new_access, new_refresh, _user = await auth_service.rotate_refresh_token(
            db, token
        )
    except auth_service.RefreshTokenError:
        response.delete_cookie(key="refresh_token", path="/api/auth")
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")
    _set_refresh_cookie(response, new_refresh)

    return {
        "status": "success",
        "data": {
            "access_token": new_access,
            "token_type": "bearer",
        },
    }


@router.post("/logout")
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke the presented refresh session and clear its cookie."""
    token = request.cookies.get("refresh_token")
    if token:
        await auth_service.revoke_refresh_token(db, token)
    response.delete_cookie(key="refresh_token", path="/api/auth")
    return {"status": "success", "data": {"message": "Logged out"}}


@router.get("/me")
async def get_me(current_user: User = Depends(get_current_user)) -> dict:
    """Return the currently authenticated user's profile."""
    return {
        "status": "success",
        "data": UserResponse.model_validate(current_user).model_dump(mode="json"),
    }
