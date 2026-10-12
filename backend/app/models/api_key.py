"""Project API Key Pydantic models for SDK telemetry ingestion."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ApiKeyCreate(BaseModel):
    """Schema for creating a new project API key."""

    name: str = Field(..., min_length=1, max_length=128, description="Key description name")
    project_id: str = Field(..., description="Project UUID to scope this key to")
    key_type: str = Field(default="ingestion", description="Key type (ingestion or mcp)")
    scopes: List[str] = Field(default_factory=lambda: ["ingest"], description="Authorized key scopes")
    expires_at: Optional[datetime] = Field(None, description="Optional key expiration timestamp")


class ApiKeyResponse(BaseModel):
    """Public API key representation (only key_prefix returned, never key_hash)."""

    id: str = Field(..., description="API key UUID")
    project_id: str = Field(..., description="Project UUID this key is scoped to")
    name: str = Field(..., description="Key description name")
    key_prefix: str = Field(..., description="Key prefix (e.g., al_live_ab12)")
    key_type: str = Field(default="ingestion", description="Key type")
    scopes: List[str] = Field(default_factory=list, description="Authorized scopes")
    is_revoked: bool = Field(default=False, description="Whether key is revoked")
    last_used_at: Optional[datetime] = Field(None, description="Timestamp key was last used")
    expires_at: Optional[datetime] = Field(None, description="Expiration timestamp")
    created_at: datetime = Field(..., description="Creation timestamp")

    # Present only immediately upon creation
    secret_key: Optional[str] = Field(None, description="Raw secret key (only returned once upon creation)")

    model_config = ConfigDict(from_attributes=True)
