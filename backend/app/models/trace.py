"""Trace models for API validation."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class TraceCreate(BaseModel):
    """Trace creation request model."""

    trace_id: str = Field(..., min_length=1, max_length=256, description="Unique trace identifier")
    name: str = Field(..., min_length=1, max_length=256, description="Trace name/description")
    start_time: datetime = Field(..., description="Trace start time (UTC)")
    end_time: Optional[datetime] = Field(None, description="Trace end time (UTC)")
    status: str = Field(default="running", max_length=64, description="Trace status")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Trace metadata"
    )


class TraceResponse(BaseModel):
    """Trace response model."""

    trace_id: str
    name: str
    start_time: datetime
    status: str


class TraceSummary(BaseModel):
    """Lightweight trace summary for trace list view."""

    trace_id: str = Field(..., description="Unique trace identifier")
    name: str = Field(..., description="Trace name/description")
    project_name: Optional[str] = Field(None, description="Project name")
    status: str = Field(..., description="Trace status (running, completed, failed)")
    start_time: datetime = Field(..., description="Trace start time")
    end_time: Optional[datetime] = Field(None, description="Trace end time")
    duration_ms: Optional[float] = Field(None, description="Trace duration in milliseconds")
    event_count: int = Field(default=0, description="Total number of events in trace")

