"""Real-time event and message contracts for WebSocket streaming."""

from datetime import datetime
from typing import Any, Literal, Optional, Union
from pydantic import BaseModel, Field


class RealtimeEventPayload(BaseModel):
    """Payload representing an ingested execution event."""

    event_id: str = Field(..., description="Unique event identifier")
    trace_id: str = Field(..., description="Trace identifier")
    event_type: str = Field(..., description="Type of event (AGENT_START, LLM_CALL, etc.)")
    timestamp: datetime = Field(..., description="Timestamp of the event (UTC)")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID for hierarchy")
    data: dict[str, Any] = Field(default_factory=dict, description="Event data payload")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Event metadata")
    depth: Optional[int] = Field(None, description="Nesting depth if calculated")
    duration_ms: Optional[float] = Field(None, description="Event duration in ms")


class EventCreatedMessage(BaseModel):
    """Notification published when a new execution event is persisted."""

    type: Literal["event_created"] = "event_created"
    trace_id: str = Field(..., description="Trace identifier")
    event: RealtimeEventPayload = Field(..., description="Created event payload")


class TraceStartedMessage(BaseModel):
    """Notification published when a new trace starts."""

    type: Literal["trace_started"] = "trace_started"
    trace_id: str = Field(..., description="Trace identifier")
    name: str = Field(..., description="Trace name")
    project_name: Optional[str] = Field(None, description="Project name")
    start_time: datetime = Field(..., description="Trace start timestamp")
    status: str = Field(default="running", description="Trace status")


class TraceCompletedMessage(BaseModel):
    """Notification published when a trace completes or fails."""

    type: Literal["trace_completed"] = "trace_completed"
    trace_id: str = Field(..., description="Trace identifier")
    status: str = Field(..., description="Final trace status (completed, failed)")
    end_time: Optional[datetime] = Field(None, description="Trace end timestamp")
    duration_ms: Optional[float] = Field(None, description="Total execution duration in ms")


# Discriminated union of all possible real-time messages
RealtimeMessage = Union[EventCreatedMessage, TraceStartedMessage, TraceCompletedMessage]
