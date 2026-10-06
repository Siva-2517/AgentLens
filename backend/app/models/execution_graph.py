"""Domain models for execution graph representation.

Designed for consumption by graph visualizers (such as React Flow)
while keeping the backend domain model clean and decoupled from UI styling.
"""

from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class ExecutionGraphNode(BaseModel):
    """Represents a node in the agent execution graph."""

    id: str = Field(..., description="Unique node identifier (matches event_id)")
    event_id: str = Field(..., description="Event identifier")
    trace_id: str = Field(..., description="Trace identifier")
    event_type: str = Field(..., description="Raw event type (AGENT_START, LLM_CALL, etc.)")
    label: str = Field(..., description="Human-readable deterministic label")
    timestamp: datetime = Field(..., description="Timestamp of the event (UTC)")
    parent_event_id: Optional[str] = Field(None, description="Parent event ID if nested")
    depth: int = Field(default=0, description="Nesting depth in parent-child tree")
    duration_ms: Optional[float] = Field(None, description="Duration in ms if calculable")
    status: Optional[str] = Field(None, description="Status/outcome of the step if available")
    data: dict[str, Any] = Field(default_factory=dict, description="Event payload summary")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Event metadata")


class ExecutionGraphEdge(BaseModel):
    """Represents a directed relationship between two execution nodes."""

    id: str = Field(..., description="Deterministic edge identifier (e.g. edge_{source}_{target})")
    source: str = Field(..., description="Source node ID (parent)")
    target: str = Field(..., description="Target node ID (child)")
    relationship: str = Field(default="parent-child", description="Relationship type")


class ExecutionGraph(BaseModel):
    """Execution graph containing nodes and edges representing agent workflow."""

    trace_id: str = Field(..., description="Trace identifier")
    nodes: list[ExecutionGraphNode] = Field(default_factory=list, description="Ordered graph nodes")
    edges: list[ExecutionGraphEdge] = Field(default_factory=list, description="Graph edges")
    node_count: int = Field(default=0, description="Total number of nodes")
    edge_count: int = Field(default=0, description="Total number of edges")
