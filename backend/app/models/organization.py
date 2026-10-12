"""Organization and membership Pydantic models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class OrganizationBase(BaseModel):
    """Base organization attributes."""

    name: str = Field(..., min_length=1, max_length=128, description="Organization name")
    slug: str = Field(..., min_length=1, max_length=128, description="URL-safe unique organization slug")


class OrganizationCreate(OrganizationBase):
    """Organization creation schema."""

    pass


class OrganizationResponse(OrganizationBase):
    """Organization response schema."""

    id: str = Field(..., description="Organization unique UUID")
    created_at: datetime = Field(..., description="Organization creation timestamp")

    model_config = ConfigDict(from_attributes=True)


class OrganizationMemberResponse(BaseModel):
    """Organization membership response schema."""

    id: str = Field(..., description="Membership unique UUID")
    organization_id: str = Field(..., description="Organization UUID")
    user_id: str = Field(..., description="User UUID")
    role: str = Field(default="member", description="Role (owner, admin, member, viewer)")
    created_at: datetime = Field(..., description="Membership created timestamp")

    model_config = ConfigDict(from_attributes=True)
