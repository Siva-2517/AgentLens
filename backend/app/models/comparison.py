"""Domain models for trace comparison and replay."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from app.models.finding import Finding


class TraceComparisonSummary(BaseModel):
    """High-level summary of a trace in a comparison context."""

    trace_id: str = Field(..., description="Unique trace identifier")
    name: str = Field(..., description="Agent or trace name")
    project_name: Optional[str] = Field(None, description="Project identifier")
    status: str = Field(..., description="Trace status (running, completed, failed)")
    start_time: datetime = Field(..., description="Trace start time")
    end_time: Optional[datetime] = Field(None, description="Trace end time")
    duration_ms: Optional[float] = Field(None, description="Total execution duration in milliseconds")
    event_count: int = Field(default=0, description="Total number of events")
    event_type_counts: Dict[str, int] = Field(default_factory=dict, description="Counts by event type")
    findings_count: int = Field(default=0, description="Total detected deterministic findings")
    findings_severity_counts: Dict[str, int] = Field(
        default_factory=dict, description="Count of findings per severity level"
    )
    is_complete: bool = Field(default=False, description="Whether lifecycle is complete")
    has_agent_start: bool = Field(default=False, description="Whether AGENT_START is present")
    has_agent_end: bool = Field(default=False, description="Whether AGENT_END is present")


class HighLevelDifferences(BaseModel):
    """Calculated metric differences between Trace A and Trace B."""

    duration_diff_ms: Optional[float] = Field(
        None, description="Duration difference in ms (Trace B - Trace A)"
    )
    event_count_diff: int = Field(
        ..., description="Event count difference (Trace B - Trace A)"
    )
    status_changed: bool = Field(
        ..., description="True if status differs between Trace A and Trace B"
    )
    status_a: str = Field(..., description="Status of Trace A")
    status_b: str = Field(..., description="Status of Trace B")
    findings_count_diff: int = Field(
        ..., description="Findings count difference (Trace B - Trace A)"
    )
    event_type_diffs: Dict[str, int] = Field(
        default_factory=dict, description="Count difference per event type (B - A)"
    )


class ComparisonEventSummary(BaseModel):
    """Detailed summary of an event aligned in the execution comparison."""

    event_id: str = Field(..., description="Event identifier")
    trace_id: str = Field(..., description="Trace identifier")
    event_type: str = Field(..., description="Event type")
    timestamp: datetime = Field(..., description="Event timestamp (UTC)")
    duration_ms: Optional[float] = Field(None, description="Execution duration in milliseconds")
    depth: int = Field(default=0, description="Tree depth in trace hierarchy")
    parent_event_id: Optional[str] = Field(None, description="Parent event identifier")
    agent_name: Optional[str] = Field(None, description="Agent name")
    data: Dict[str, Any] = Field(default_factory=dict, description="Event payload data")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Event metadata")


class EventComparisonStep(BaseModel):
    """A single aligned step in the execution sequence comparison."""

    step_index: int = Field(..., description="Sequence step index (1-based)")
    status: str = Field(
        ...,
        description="Alignment status: 'matched' (present in both), 'only_a' (only in Trace A), 'only_b' (only in Trace B)",
    )
    event_a: Optional[ComparisonEventSummary] = Field(
        None, description="Corresponding event from Trace A if present"
    )
    event_b: Optional[ComparisonEventSummary] = Field(
        None, description="Corresponding event from Trace B if present"
    )
    duration_diff_ms: Optional[float] = Field(
        None, description="Duration difference for matched events (B - A in ms)"
    )
    change_summary: str = Field(
        ..., description="Human-readable explanation of the comparison step"
    )


class FindingComparison(BaseModel):
    """Comparison of deterministic failure and anomaly findings."""

    findings_only_a: List[Finding] = Field(
        default_factory=list, description="Findings present only in Trace A"
    )
    findings_only_b: List[Finding] = Field(
        default_factory=list, description="Findings present only in Trace B"
    )
    common_findings: List[Finding] = Field(
        default_factory=list, description="Findings rules common to both traces"
    )
    findings_count_diff: int = Field(
        default=0, description="Findings count difference (B - A)"
    )


class TraceComparisonResult(BaseModel):
    """Complete structured comparison response between two agent execution traces."""

    trace_a: TraceComparisonSummary = Field(
        ..., description="Summary metrics and findings for Trace A"
    )
    trace_b: TraceComparisonSummary = Field(
        ..., description="Summary metrics and findings for Trace B"
    )
    differences: HighLevelDifferences = Field(
        ..., description="Calculated high-level differences"
    )
    sequence_comparison: List[EventComparisonStep] = Field(
        default_factory=list,
        description="Chronologically aligned execution event steps (matched, only A, only B)",
    )
    findings_comparison: FindingComparison = Field(
        ..., description="Comparison of deterministic findings"
    )
