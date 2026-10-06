"""Event models for API validation."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Event types for agent execution telemetry."""

    AGENT_START = "AGENT_START"
    LLM_CALL = "LLM_CALL"
    LLM_RESPONSE = "LLM_RESPONSE"
    TOOL_CALL = "TOOL_CALL"
    TOOL_RESPONSE = "TOOL_RESPONSE"
    STATE_CHANGE = "STATE_CHANGE"
    RETRY = "RETRY"
    ERROR = "ERROR"
    AGENT_END = "AGENT_END"


class EventCreate(BaseModel):
    """Event creation request model."""

    event_id: str = Field(..., min_length=1, max_length=256, description="Unique event identifier")
    trace_id: str = Field(..., min_length=1, max_length=256, description="Trace this event belongs to")
    event_type: EventType = Field(..., description="Type of event")
    timestamp: datetime = Field(..., description="Event timestamp (UTC)")
    data: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )
    parent_event_id: Optional[str] = Field(
        None, max_length=256, description="Parent event ID for nested operations"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class EventResponse(BaseModel):
    """Event response model."""

    event_id: str
    trace_id: str
    event_type: EventType
    timestamp: datetime
    status: str = "received"
