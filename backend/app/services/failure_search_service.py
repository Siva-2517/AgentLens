"""Failure Search and Indexing Service (Phase 15).

Provides deterministic searchable failure representation generation with sensitive
data redaction, vector embedding generation, and semantic historical failure search
backed by pgvector.
"""

import logging
from typing import Any, Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.repositories import FailureEmbeddingRepository
from app.models.failure_search import (
    HistoricalFailureSearchResult,
    HistoricalSearchResponse,
    TraceIndexingResponse,
)
from app.models.finding import Finding
from app.models.reconstructed_trace import ReconstructedEvent, ReconstructedTrace
from app.services.embedding_provider import (
    EmbeddingProvider,
    get_embedding_provider,
)
from app.services.failure_detection_service import failure_detection_service
from app.services.trace_reconstruction_service import (
    TraceNotFoundError,
    trace_reconstruction_service,
)

logger = logging.getLogger(__name__)

from app.services.redaction import SENSITIVE_EXACT_KEYS as SENSITIVE_KEYS, sanitize_telemetry

# Alias for backward compatibility
sanitize_payload = sanitize_telemetry


def build_searchable_failure_text(
    trace: ReconstructedTrace,
    finding: Finding,
) -> str:
    """Construct a compact, information-dense, sanitized failure text for embedding.

    Includes trace identity, project, finding rule/severity/category, message,
    and sanitized context from associated evidence events.
    """
    rule_str = finding.rule
    sev_str = (
        finding.severity.value
        if hasattr(finding.severity, "value")
        else str(finding.severity)
    )
    cat_str = (
        finding.category.value
        if hasattr(finding.category, "value")
        else str(finding.category)
    )

    lines = [
        f"Agent Trace: {trace.name} (Project: {trace.project_name or 'default'})",
        f"Finding Rule: {rule_str} | Category: {cat_str} | Severity: {sev_str}",
        f"Failure Message: {finding.message}",
    ]

    # Include evidence event descriptions and payload highlights
    evidence_ids = set(finding.evidence_event_ids)
    evidence_events = [e for e in trace.events if e.event_id in evidence_ids]

    if evidence_events:
        lines.append("Evidence Event Context:")
        for ev in evidence_events[:5]:  # Limit to earliest 5 relevant events
            sanitized_data = sanitize_payload(ev.data or {})
            tool_or_model = (
                sanitized_data.get("tool_name")
                or sanitized_data.get("name")
                or sanitized_data.get("model")
            )
            err_msg = (
                sanitized_data.get("error")
                or sanitized_data.get("message")
                or ev.metadata.get("error")
            )

            parts = [f"- Event {ev.event_id} ({ev.event_type})"]
            if tool_or_model:
                parts.append(f"entity: {tool_or_model}")
            if err_msg:
                parts.append(f"error: {str(err_msg)[:150]}")
            lines.append(" ".join(parts))

    return "\n".join(lines)


class FailureSearchService:
    """Service orchestrating failure indexing and pgvector semantic retrieval."""

    def __init__(self, provider: Optional[EmbeddingProvider] = None):
        self._provider = provider

    def get_provider(self) -> EmbeddingProvider:
        """Get or lazily initialize the embedding provider."""
        if self._provider is not None:
            return self._provider
        return get_embedding_provider()

    def set_provider(self, provider: EmbeddingProvider) -> None:
        """Override active embedding provider (useful for testing)."""
        self._provider = provider

    async def index_trace_failures(
        self,
        trace_id: str,
        db: AsyncSession,
    ) -> TraceIndexingResponse:
        """Reconstruct trace, detect deterministic failures, generate embeddings, and persist.

        Args:
            trace_id: Trace ID to index.
            db: Async database session.

        Returns:
            TraceIndexingResponse with count of indexed findings.

        Raises:
            TraceNotFoundError: If trace does not exist.
        """
        clean_id = (trace_id or "").strip()
        if not clean_id:
            raise ValueError("trace_id must be a non-empty string")

        # 1. Reconstruct trace
        trace = await trace_reconstruction_service.reconstruct_trace(clean_id, db)

        # 2. Detect deterministic findings in-memory
        findings = failure_detection_service.detect_failures(trace)

        if not findings:
            return TraceIndexingResponse(
                trace_id=clean_id,
                indexed_count=0,
                status="no_findings",
                finding_ids=[],
                message="No deterministic failure findings detected for this trace. Nothing to index.",
            )

        provider = self.get_provider()
        repo = FailureEmbeddingRepository(db)
        indexed_ids: List[str] = []

        # 3. For each finding, build searchable text, embed, and upsert
        for finding in findings:
            searchable_text = build_searchable_failure_text(trace, finding)
            vector = await provider.embed_text(searchable_text)

            sev_str = (
                finding.severity.value
                if hasattr(finding.severity, "value")
                else str(finding.severity)
            )
            cat_str = (
                finding.category.value
                if hasattr(finding.category, "value")
                else str(finding.category)
            )

            meta = {
                "trace_name": trace.name,
                "project_name": trace.project_name,
                "evidence_event_ids": finding.evidence_event_ids,
                "detected_at": finding.detected_at.isoformat()
                if hasattr(finding.detected_at, "isoformat")
                else str(finding.detected_at),
                "model_name": provider.model_name,
            }

            await repo.upsert(
                trace_id=trace.trace_id,
                finding_id=finding.finding_id,
                rule=finding.rule,
                category=cat_str,
                severity=sev_str,
                searchable_text=searchable_text,
                embedding=vector,
                metadata=meta,
            )
            indexed_ids.append(finding.finding_id)

        return TraceIndexingResponse(
            trace_id=clean_id,
            indexed_count=len(indexed_ids),
            status="indexed",
            finding_ids=indexed_ids,
            message=f"Successfully indexed {len(indexed_ids)} failure findings into pgvector store.",
        )

    async def search_failures(
        self,
        query: str,
        db: AsyncSession,
        limit: int = 10,
        severity: Optional[str] = None,
        rule: Optional[str] = None,
        project_name: Optional[str] = None,
    ) -> HistoricalSearchResponse:
        """Perform semantic similarity search for historical failures.

        Args:
            query: Natural-language failure description or keywords.
            db: Async database session.
            limit: Maximum results (default 10).
            severity: Optional filter by severity (critical, error, warning, info).
            rule: Optional filter by finding rule code.
            project_name: Optional filter by project name.

        Returns:
            HistoricalSearchResponse with ranked matching historical failures.
        """
        clean_query = (query or "").strip()
        if not clean_query:
            raise ValueError("Query parameter 'q' must not be empty")

        bounded_limit = max(1, min(limit, 50))
        provider = self.get_provider()
        query_vector = await provider.embed_text(clean_query)

        repo = FailureEmbeddingRepository(db)
        matches = await repo.search_similar(
            query_vector=query_vector,
            limit=bounded_limit,
            severity=severity,
            rule=rule,
            project_name=project_name,
        )

        results: List[HistoricalFailureSearchResult] = []
        for model, sim, trace_name, proj_name in matches:
            results.append(
                HistoricalFailureSearchResult(
                    trace_id=model.trace_id,
                    finding_id=model.finding_id,
                    rule=model.rule,
                    category=model.category,
                    severity=model.severity,
                    message=model.metadata_.get("message", model.searchable_text.split("\n")[2].replace("Failure Message: ", "") if "\n" in model.searchable_text else model.searchable_text),
                    searchable_text=model.searchable_text,
                    similarity=sim,
                    trace_name=trace_name,
                    project_name=proj_name,
                    created_at=model.created_at,
                    evidence_event_ids=model.metadata_.get("evidence_event_ids", []),
                    metadata=model.metadata_,
                )
            )

        return HistoricalSearchResponse(
            query=clean_query,
            total_results=len(results),
            results=results,
        )


failure_search_service = FailureSearchService()
