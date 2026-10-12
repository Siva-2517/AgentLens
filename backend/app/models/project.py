"""Project Pydantic models for multi-tenant isolation."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field


class ProjectBase(BaseModel):
    """Base project attributes."""

    name: str = Field(..., min_length=1, max_length=128, description="Project display name")
    slug: str = Field(..., min_length=1, max_length=128, description="URL-safe project slug")
    description: Optional[str] = Field(None, max_length=1000, description="Optional project description")


class ProjectCreate(ProjectBase):
    """Project creation schema."""

    organization_id: str = Field(..., description="Organization UUID owning this project")


class ProjectResponse(ProjectBase):
    """Project response schema."""

    id: str = Field(..., description="Project unique UUID")
    organization_id: str = Field(..., description="Organization UUID owning this project")
    created_at: datetime = Field(..., description="Project creation timestamp")

    model_config = ConfigDict(from_attributes=True)
