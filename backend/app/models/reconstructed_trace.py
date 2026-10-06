"""Domain models for reconstructed execution traces."""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ReconstructedEvent(BaseModel):
    """Reconstructed event model representing a single step in agent execution."""

    event_id: str = Field(..., description="Unique event identifier")
    trace_id: str = Field(..., description="Trace identifier")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID for hierarchy")
    event_type: str = Field(..., description="Type of event (AGENT_START, LLM_CALL, etc.)")
    timestamp: datetime = Field(..., description="Timestamp of the event (UTC)")
    agent_name: Optional[str] = Field(None, description="Agent name associated with event")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload data")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Event metadata")
    depth: int = Field(default=0, description="Nesting depth in parent-child tree (0 for root)")
    children_ids: list[str] = Field(default_factory=list, description="IDs of direct child events")
    duration_ms: Optional[float] = Field(None, description="Calculated duration in ms if paired")


class TraceExecutionMetadata(BaseModel):
    """Deterministic execution metadata calculated from trace events."""

    total_event_count: int = Field(default=0, description="Total events in trace")
    duration_ms: Optional[float] = Field(None, description="Calculated execution duration in ms")
    llm_call_count: int = Field(default=0, description="Number of LLM_CALL events")
    llm_response_count: int = Field(default=0, description="Number of LLM_RESPONSE events")
    tool_call_count: int = Field(default=0, description="Number of TOOL_CALL events")
    tool_response_count: int = Field(default=0, description="Number of TOOL_RESPONSE events")
    error_count: int = Field(default=0, description="Number of ERROR events")
    retry_count: int = Field(default=0, description="Number of RETRY events")
    state_change_count: int = Field(default=0, description="Number of STATE_CHANGE events")
    first_event_timestamp: Optional[datetime] = Field(None, description="Earliest event timestamp")
    last_event_timestamp: Optional[datetime] = Field(None, description="Latest event timestamp")
    has_agent_start: bool = Field(default=False, description="Whether AGENT_START is present")
    has_agent_end: bool = Field(default=False, description="Whether AGENT_END is present")
    is_complete: bool = Field(default=False, description="Whether trace lifecycle is complete")
    event_type_counts: dict[str, int] = Field(default_factory=dict, description="Counts by event type")


class ReconstructedTrace(BaseModel):
    """Reconstructed execution trace with ordered events and calculated metadata."""

    trace_id: str = Field(..., description="Unique trace identifier")
    name: str = Field(..., description="Trace name/agent name")
    project_name: Optional[str] = Field(None, description="Project identifier")
    start_time: datetime = Field(..., description="Trace start time")
    end_time: Optional[datetime] = Field(None, description="Trace end time")
    status: str = Field(default="running", description="Trace status (running, completed, failed)")
    duration_ms: Optional[float] = Field(None, description="Total duration in milliseconds")
    event_count: int = Field(default=0, description="Total count of reconstructed events")
    metadata: TraceExecutionMetadata = Field(..., description="Calculated trace metadata")
    events: list[ReconstructedEvent] = Field(default_factory=list, description="Chronologically ordered events")
    root_event_ids: list[str] = Field(default_factory=list, description="Top-level event IDs")
