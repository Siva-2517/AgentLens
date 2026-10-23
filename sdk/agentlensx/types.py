"""AgentLens event and trace types."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


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


class Event(BaseModel):
    """Agent execution event."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )

    event_id: str = Field(..., description="Unique event identifier")
    trace_id: str = Field(..., description="Trace this event belongs to")
    event_type: EventType = Field(..., description="Type of event")
    timestamp: datetime = Field(
        default_factory=datetime.utcnow, description="Event timestamp (UTC)"
    )
    data: dict[str, Any] = Field(
        default_factory=dict, description="Event-specific data"
    )
    parent_event_id: Optional[str] = Field(
        None, description="Parent event ID for nested operations"
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Additional metadata"
    )


class Trace(BaseModel):
    """Agent execution trace."""

    model_config = ConfigDict(
        json_encoders={datetime: lambda v: v.isoformat()}
    )

    trace_id: str = Field(..., description="Unique trace identifier")
    name: str = Field(..., description="Trace name/description")
    start_time: datetime = Field(
        default_factory=datetime.utcnow, description="Trace start time (UTC)"
    )
    end_time: Optional[datetime] = Field(None, description="Trace end time (UTC)")
    status: str = Field(default="running", description="Trace status")
    metadata: dict[str, Any] = Field(
        default_factory=dict, description="Trace metadata"
    )
