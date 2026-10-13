"""Pydantic schemas for authentication and API key management (Phase 19B)."""

import re
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, field_validator


class RegisterRequest(BaseModel):
    """Payload for user registration."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., min_length=8, description="Password (at least 8 characters)")
    full_name: Optional[str] = Field(None, max_length=255, description="Full name")

    @field_validator("email")
    @classmethod
    def validate_email_format(cls, v: str) -> str:
        clean = v.strip().lower()
        if not re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", clean):
            raise ValueError("Invalid email format")
        return clean

    @field_validator("password")
    @classmethod
    def validate_password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class LoginRequest(BaseModel):
    """Payload for user login."""

    email: str = Field(..., description="User email address")
    password: str = Field(..., description="Account password")

    @field_validator("email")
    @classmethod
    def sanitize_email(cls, v: str) -> str:
        return v.strip().lower()


class UserResponse(BaseModel):
    """Safe public representation of a user (never returns password hash)."""

    id: str
    email: str
    full_name: Optional[str] = None
    is_active: bool
    is_superuser: bool = False
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationBrief(BaseModel):
    """Brief organization metadata for user context."""

    id: str
    name: str
    slug: str
    role: str


class ProjectBrief(BaseModel):
    """Brief project metadata for user context."""

    id: str
    organization_id: str
    name: str
    slug: str
    description: Optional[str] = None


class UserProfileResponse(BaseModel):
    """Profile representation with assigned organizations and projects."""

    user: UserResponse
    organizations: List[OrganizationBrief] = Field(default_factory=list)
    projects: List[ProjectBrief] = Field(default_factory=list)


class AuthResponse(BaseModel):
    """Response returned upon registration or login."""

    user: UserResponse
    message: str
    access_token: Optional[str] = None
    token_type: str = "bearer"
    csrf_token: Optional[str] = None
    api_key: Optional[str] = Field(
        None,
        description="Initial project ingestion key returned ONCE upon registration",
    )


ALLOWED_API_KEY_SCOPES = {"ingest", "read", "mcp"}
ALLOWED_API_KEY_TYPES = {"ingestion", "mcp"}


class ApiKeyCreateRequest(BaseModel):
    """Request to generate a new project-scoped API key (ingestion or MCP)."""

    name: str = Field(..., min_length=1, max_length=128, description="Human-readable label")
    expires_in_days: Optional[int] = Field(
        None, ge=1, le=365, description="Optional validity window in days"
    )
    scopes: Optional[List[str]] = Field(
        None, description="Optional scopes: 'ingest', 'mcp', 'read'. Defaults to ['ingest']."
    )
    key_type: Optional[str] = Field(
        None, description="Optional key type: 'ingestion' or 'mcp'. Defaults to 'ingestion'."
    )

    @field_validator("scopes")
    @classmethod
    def validate_scopes(cls, v: Optional[List[str]]) -> Optional[List[str]]:
        if v is None:
            return None
        if not v:
            raise ValueError("Scopes list, if provided, must not be empty")
        cleaned: List[str] = []
        for s in v:
            if not isinstance(s, str):
                raise ValueError("Scope item must be a string")
            clean = s.strip().lower()
            if clean not in ALLOWED_API_KEY_SCOPES:
                raise ValueError(
                    f"Unsupported scope '{s}'. Allowed scopes: {sorted(ALLOWED_API_KEY_SCOPES)}"
                )
            if clean not in cleaned:
                cleaned.append(clean)
        return cleaned

    @field_validator("key_type")
    @classmethod
    def validate_key_type(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return None
        clean = v.strip().lower()
        if clean not in ALLOWED_API_KEY_TYPES:
            raise ValueError(
                f"Unsupported key_type '{v}'. Allowed types: {sorted(ALLOWED_API_KEY_TYPES)}"
            )
        return clean


class ApiKeyCreatedResponse(BaseModel):
    """Response returned upon key generation.

    The secret `api_key` is shown ONLY in this response and never persisted or retrievable again.
    """

    id: str
    project_id: str
    name: str
    key_prefix: str
    key_type: str = "ingestion"
    scopes: List[str] = Field(default_factory=lambda: ["ingest"])
    api_key: str = Field(..., description="Raw secret API key shown ONLY ONCE")
    created_at: datetime
    expires_at: Optional[datetime] = None


class ApiKeyInfoResponse(BaseModel):
    """Safe metadata representation of an API key (hash is never returned)."""

    id: str
    project_id: str
    name: str
    key_prefix: str
    key_type: str = "ingestion"
    scopes: List[str] = Field(default_factory=list)
    is_revoked: bool
    created_at: datetime
    expires_at: Optional[datetime] = None
    last_used_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
