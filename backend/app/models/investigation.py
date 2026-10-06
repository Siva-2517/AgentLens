"""Domain models for AI-powered root-cause investigation."""

from datetime import datetime
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class InvestigationStatus(str, Enum):
    """Status of an AI investigation."""

    INVESTIGATED = "investigated"
    NO_ISSUE_DETECTED = "no_issue_detected"
    INSUFFICIENT_EVIDENCE = "insufficient_evidence"
    FAILED = "failed"


class RootCause(BaseModel):
    """Detailed root-cause analysis with evidence references."""

    description: str = Field(
        ..., description="Precise description of what caused the failure"
    )
    event_id: Optional[str] = Field(
        None, description="Event ID where the root failure originated"
    )
    finding_id: Optional[str] = Field(
        None, description="Deterministic finding ID associated with this root cause"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Confidence score from 0.0 to 1.0"
    )
    reasoning: str = Field(
        ..., description="Detailed explanation of how this event led to failure"
    )


class EvidenceItem(BaseModel):
    """Specific piece of evidence supporting the investigation."""

    event_id: Optional[str] = Field(
        None, description="Trace event ID referenced as evidence"
    )
    finding_id: Optional[str] = Field(
        None, description="Phase 11 finding ID referenced as evidence"
    )
    description: str = Field(
        ..., description="Description of why this item constitutes evidence"
    )


class DownstreamEffect(BaseModel):
    """Downstream symptom or failure caused by the root cause."""

    event_id: Optional[str] = Field(
        None, description="Event ID where the downstream effect manifested"
    )
    description: str = Field(
        ..., description="Description of the downstream symptom or outcome"
    )
    impact: str = Field(
        ..., description="Severity or impact of this effect on execution flow"
    )


class RecommendedAction(BaseModel):
    """Actionable recommendation for engineers to resolve the failure."""

    action: str = Field(
        ..., description="Concrete fix, investigation step, or remediation"
    )
    related_event_ids: list[str] = Field(
        default_factory=list, description="Event IDs related to this action"
    )
    priority: str = Field(
        default="medium", description="Priority level: high, medium, low"
    )


class InvestigationResult(BaseModel):
    """Complete structured AI root-cause investigation result."""

    investigation_id: str = Field(
        ..., description="Unique identifier for the investigation"
    )
    trace_id: str = Field(..., description="Trace identifier analyzed")
    status: InvestigationStatus = Field(
        ..., description="Outcome status of the investigation"
    )
    summary: str = Field(
        ..., description="Executive summary of the investigation findings"
    )
    root_cause: Optional[RootCause] = Field(
        None, description="Identified root cause (null if no issue detected)"
    )
    first_failure_event_id: Optional[str] = Field(
        None, description="Earliest event ID where execution began failing"
    )
    confidence: float = Field(
        ..., ge=0.0, le=1.0, description="Overall confidence score (0.0 to 1.0)"
    )
    evidence: list[EvidenceItem] = Field(
        default_factory=list, description="Grounding evidence items"
    )
    downstream_effects: list[DownstreamEffect] = Field(
        default_factory=list, description="Downstream symptoms and impacts"
    )
    recommended_actions: list[RecommendedAction] = Field(
        default_factory=list, description="Suggested actions for engineers"
    )
    analyzed_findings: list[str] = Field(
        default_factory=list, description="IDs of Phase 11 findings analyzed"
    )
    analyzed_event_ids: list[str] = Field(
        default_factory=list, description="IDs of trace events analyzed"
    )
    model: str = Field(..., description="LLM model identifier used")
    created_at: datetime = Field(
        ..., description="UTC timestamp of investigation completion"
    )


class CompactEventSummary(BaseModel):
    """Compact sanitized representation of an event for LLM reasoning."""

    event_id: str
    event_type: str
    timestamp: str
    parent_event_id: Optional[str] = None
    agent_name: Optional[str] = None
    name: Optional[str] = None
    duration_ms: Optional[float] = None
    summary_data: dict[str, Any] = Field(default_factory=dict)
    error_detail: Optional[str] = None


class InvestigationContext(BaseModel):
    """Compact context passed to the LLM for investigation."""

    trace_id: str
    name: str
    project_name: Optional[str] = None
    status: str
    start_time: str
    end_time: Optional[str] = None
    duration_ms: Optional[float] = None
    total_events: int
    metadata: dict[str, Any] = Field(default_factory=dict)
    deterministic_findings: list[dict[str, Any]] = Field(default_factory=list)
    key_events: list[CompactEventSummary] = Field(default_factory=list)
    parent_child_relationships: list[dict[str, str]] = Field(default_factory=list)
