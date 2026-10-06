"""Domain models for deterministic failure and anomaly findings."""

import hashlib
from datetime import datetime, timezone
from enum import Enum
from typing import Any, List, Optional

from pydantic import BaseModel, Field


class FindingCategory(str, Enum):
    """Categories of deterministic findings."""

    EXPLICIT_ERROR = "explicit_error"
    MISSING_RESPONSE = "missing_response"
    RETRY_EXHAUSTION = "retry_exhaustion"
    REPEATED_TOOL_CALL = "repeated_tool_call"
    EXECUTION_LOOP = "execution_loop"
    INVALID_LIFECYCLE = "invalid_lifecycle"


class FindingSeverity(str, Enum):
    """Severity levels for findings."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Finding(BaseModel):
    """Deterministic failure or anomaly finding detected in an execution trace."""

    finding_id: str = Field(
        ..., description="Unique deterministic identifier for the finding"
    )
    trace_id: str = Field(
        ..., description="Trace identifier associated with this finding"
    )
    rule: str = Field(..., description="Rule code that identified this finding")
    category: FindingCategory = Field(
        ..., description="Category classification of the finding"
    )
    severity: FindingSeverity = Field(
        ..., description="Severity level of the finding"
    )
    message: str = Field(
        ...,
        description="Human-readable description of the detected failure/anomaly",
    )
    evidence_event_ids: list[str] = Field(
        default_factory=list, description="IDs of events providing evidence"
    )
    evidence: dict[str, Any] = Field(
        default_factory=dict, description="Structured evidence details"
    )
    detected_at: datetime = Field(
        ..., description="Timestamp when finding was detected (UTC)"
    )


class DetectionConfig(BaseModel):
    """Configuration thresholds for deterministic failure and anomaly detection."""

    repeated_tool_call_threshold: int = Field(
        default=3,
        ge=2,
        description="Minimum identical tool calls with equivalent inputs to trigger a finding",
    )
    loop_threshold: int = Field(
        default=3,
        ge=2,
        description="Minimum consecutive repetitions of an action sequence to trigger a loop finding",
    )
    retry_threshold: int = Field(
        default=3,
        ge=1,
        description="Minimum total retry events in a trace to trigger a high-retry finding",
    )


class FindingsResponse(BaseModel):
    """Response model for trace findings endpoint."""

    trace_id: str = Field(..., description="Trace identifier")
    total_findings: int = Field(
        default=0, description="Total count of detected findings"
    )
    findings: list[Finding] = Field(
        default_factory=list, description="Deterministic list of findings"
    )


def generate_finding_id(
    trace_id: str, rule: str, evidence_ids: list[str]
) -> str:
    """Generate a deterministic finding_id based on trace, rule, and evidence."""
    sorted_ev = ":".join(sorted(evidence_ids)) if evidence_ids else "trace_level"
    raw_key = f"{trace_id}:{rule}:{sorted_ev}"
    digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:16]
    return f"finding_{rule}_{digest}"
