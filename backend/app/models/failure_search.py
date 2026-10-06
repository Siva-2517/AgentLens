"""Domain models for historical failure search and pgvector embeddings (Phase 15)."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class HistoricalFailureSearchResult(BaseModel):
    """A historical failure match returned from semantic similarity search."""

    trace_id: str = Field(..., description="Trace identifier of the historical failure")
    finding_id: str = Field(..., description="Deterministic finding identifier")
    rule: str = Field(..., description="Detection rule code (e.g., explicit_error, unresolved_retry)")
    category: str = Field(..., description="Category classification of the finding")
    severity: str = Field(..., description="Severity level (critical, error, warning, info)")
    message: str = Field(..., description="Human-readable description of the detected failure")
    searchable_text: str = Field(..., description="Redacted contextual text that was embedded")
    similarity: float = Field(..., ge=0.0, le=1.0, description="Cosine similarity score (0.0 to 1.0)")
    trace_name: str = Field(..., description="Agent or trace name")
    project_name: Optional[str] = Field(None, description="Project identifier if available")
    created_at: datetime = Field(..., description="Timestamp when the failure was indexed")
    evidence_event_ids: List[str] = Field(
        default_factory=list, description="IDs of events associated with this finding"
    )
    metadata: Dict[str, Any] = Field(
        default_factory=dict, description="Additional contextual metadata"
    )


class HistoricalSearchResponse(BaseModel):
    """Response payload for historical failure search."""

    query: str = Field(..., description="Original search query")
    total_results: int = Field(default=0, description="Total matching failure records returned")
    results: List[HistoricalFailureSearchResult] = Field(
        default_factory=list, description="Ranked list of similar historical failures"
    )


class TraceIndexingResponse(BaseModel):
    """Response payload for explicit trace failure indexing."""

    trace_id: str = Field(..., description="Target trace identifier")
    indexed_count: int = Field(default=0, description="Number of failure findings indexed")
    status: str = Field(
        ...,
        description="Outcome status: 'indexed', 'no_findings', or 'already_indexed'",
    )
    finding_ids: List[str] = Field(
        default_factory=list, description="List of finding IDs that were indexed"
    )
    message: str = Field(..., description="Human-readable status summary")
