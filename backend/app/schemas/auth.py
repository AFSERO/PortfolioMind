import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = None
    base_currency: str = "TRY"


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class UserResponse(BaseModel):
    """Public-safe user representation (no password_hash)."""

    id: uuid.UUID
    email: str
    display_name: Optional[str]
    base_currency: str
    created_at: datetime

    model_config = {"from_attributes": True}
