"""User Pydantic models for authentication and access control."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


EMAIL_REGEX = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"


class UserBase(BaseModel):
    """Base user attributes."""

    email: str = Field(..., pattern=EMAIL_REGEX, description="User email address")
    full_name: Optional[str] = Field(None, max_length=255, description="User full name")


class UserCreate(UserBase):
    """User creation schema."""

    password: str = Field(..., min_length=8, max_length=128, description="User raw password")


class UserResponse(UserBase):
    """User public response schema (no password hash)."""

    id: str = Field(..., description="User unique UUID")
    is_active: bool = Field(default=True, description="Whether user is active")
    is_superuser: bool = Field(default=False, description="Whether user is a superuser")
    created_at: datetime = Field(..., description="Account creation timestamp")

    model_config = ConfigDict(from_attributes=True)
