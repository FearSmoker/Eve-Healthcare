import uuid
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserSignUpRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    # max_length=72: bcrypt silently truncates inputs beyond 72 bytes.
    # Without this cap, passwords differing only after byte 72 would hash identically.
    password: str = Field(..., min_length=8, max_length=72, description="8–72 characters")
    full_name: str = Field(..., min_length=2, max_length=255)
    phone: Optional[str] = Field(None, max_length=30)
    # NOTE: role is intentionally NOT exposed in public signup — all public signups are PATIENT.
    # Admin accounts must be created via seed script or directly by an existing admin.


class UserLoginRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    email: EmailStr
    password: str = Field(..., min_length=1)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    email: EmailStr
    full_name: str
    phone: Optional[str] = None
    role: str
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in_seconds: int
    user: UserResponse
