"""AI-powered Root-Cause Investigation Service.

Analyzes reconstructed traces, execution graphs, and deterministic findings using
structured LLM reasoning to determine root cause, earliest failure, downstream effects,
and recommended remediation actions.
"""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventType
from app.models.execution_graph import ExecutionGraph
from app.models.finding import Finding
from app.models.investigation import (
    CompactEventSummary,
    DownstreamEffect,
    EvidenceItem,
    InvestigationContext,
    InvestigationResult,
    InvestigationStatus,
    RecommendedAction,
    RootCause,
)
from app.models.reconstructed_trace import ReconstructedEvent, ReconstructedTrace
from app.services.execution_graph_service import execution_graph_service
from app.services.failure_detection_service import failure_detection_service
from app.services.llm_provider import (
    InvestigationLLMProvider,
    get_investigation_provider,
)
from app.services.trace_reconstruction_service import (
    TraceNotFoundError,
    trace_reconstruction_service,
)

logger = logging.getLogger(__name__)

from app.services.redaction import SENSITIVE_EXACT_KEYS as SENSITIVE_KEYS, sanitize_telemetry


class InvestigationValidationError(Exception):
    """Raised when LLM output violates schema or references non-existent IDs."""

    def __init__(self, message: str, invalid_ids: Optional[list[str]] = None):
        super().__init__(message)
        self.message = message
        self.invalid_ids = invalid_ids or []


class AIInvestigationService:
    """Service for orchestrating AI root-cause investigation."""

    def __init__(
        self,
        default_provider: Optional[InvestigationLLMProvider] = None,
    ):
        self._provider = default_provider

    def get_provider(self) -> InvestigationLLMProvider:
        """Get the active LLM provider."""
        if self._provider is not None:
            return self._provider
        return get_investigation_provider()

    def set_provider(self, provider: InvestigationLLMProvider) -> None:
        """Set or override the active LLM provider (useful for testing)."""
        self._provider = provider

    def build_context(
        self,
        trace: ReconstructedTrace,
        graph: ExecutionGraph,
        findings: list[Finding],
    ) -> InvestigationContext:
        """Construct a compact, sanitized context for LLM reasoning.

        Extracts only relevant events, findings, and structural links to avoid
        unnecessary token overhead and payload leakage.
        """
        # Collect IDs of interest: all evidence events from findings + errors + retries
        finding_ev_ids: Set[str] = set()
        for f in findings:
            finding_ev_ids.update(f.evidence_event_ids)

        key_events: list[CompactEventSummary] = []
        for ev in trace.events:
            # Include if involved in findings, or is a critical lifecycle / error / tool / retry event
            is_relevant = (
                ev.event_id in finding_ev_ids
                or ev.event_type in (
                    EventType.ERROR.value,
                    EventType.RETRY.value,
                    EventType.TOOL_CALL.value,
                    EventType.TOOL_RESPONSE.value,
                    EventType.AGENT_START.value,
                    EventType.AGENT_END.value,
                )
            )

            if is_relevant:
                sanitized_data = self._sanitize_dict(ev.data)
                error_msg = None
                if ev.event_type == EventType.ERROR.value:
                    error_msg = (
                        sanitized_data.get("message")
                        or sanitized_data.get("error")
                        or str(ev.metadata.get("error", ""))
                    )
                elif ev.event_type == EventType.TOOL_RESPONSE.value:
                    if sanitized_data.get("error"):
                        error_msg = str(sanitized_data.get("error"))

                tool_or_call_name = (
                    sanitized_data.get("name")
                    or sanitized_data.get("tool")
                    or sanitized_data.get("tool_name")
                )

                key_events.append(
                    CompactEventSummary(
                        event_id=ev.event_id,
                        event_type=ev.event_type,
                        timestamp=ev.timestamp.isoformat(),
                        parent_event_id=ev.parent_event_id,
                        agent_name=ev.agent_name,
                        name=tool_or_call_name,
                        duration_ms=ev.duration_ms,
                        summary_data=sanitized_data,
                        error_detail=error_msg,
                    )
                )

        # Compact findings summary
        findings_summary = [
            {
                "finding_id": f.finding_id,
                "rule": f.rule,
                "category": f.category.value,
                "severity": f.severity.value,
                "message": f.message,
                "evidence_event_ids": f.evidence_event_ids,
            }
            for f in findings
        ]

        # Graph relationships
        relationships = [
            {"source": e.source, "target": e.target, "relationship": e.relationship}
            for e in graph.edges
        ]

        return InvestigationContext(
            trace_id=trace.trace_id,
            name=trace.name,
            project_name=trace.project_name,
            status=trace.status,
            start_time=trace.start_time.isoformat(),
            end_time=trace.end_time.isoformat() if trace.end_time else None,
            duration_ms=trace.duration_ms,
            total_events=trace.event_count,
            metadata=self._sanitize_dict(trace.metadata.model_dump()),
            deterministic_findings=findings_summary,
            key_events=key_events,
            parent_child_relationships=relationships,
        )

    def validate_llm_output(
        self,
        raw_output: dict[str, Any],
        trace: ReconstructedTrace,
        findings: list[Finding],
    ) -> None:
        """Validate that all referenced event IDs and finding IDs exist in the trace.

        Raises:
            InvestigationValidationError: If the LLM referenced hallucinated IDs.
        """
        valid_event_ids: Set[str] = {e.event_id for e in trace.events}
        valid_finding_ids: Set[str] = {f.finding_id for f in findings}
        invalid_ids: list[str] = []

        # Validate first_failure_event_id
        first_failure = raw_output.get("first_failure_event_id")
        if first_failure and first_failure not in valid_event_ids:
            invalid_ids.append(f"first_failure_event_id:{first_failure}")

        # Validate root_cause
        root_cause = raw_output.get("root_cause")
        if isinstance(root_cause, dict):
            rc_ev = root_cause.get("event_id")
            if rc_ev and rc_ev not in valid_event_ids:
                invalid_ids.append(f"root_cause.event_id:{rc_ev}")
            rc_f = root_cause.get("finding_id")
            if rc_f and rc_f not in valid_finding_ids:
                invalid_ids.append(f"root_cause.finding_id:{rc_f}")

        # Validate evidence items
        evidence_list = raw_output.get("evidence", [])
        if isinstance(evidence_list, list):
            for i, item in enumerate(evidence_list):
                if isinstance(item, dict):
                    ev_id = item.get("event_id")
                    if ev_id and ev_id not in valid_event_ids:
                        invalid_ids.append(f"evidence[{i}].event_id:{ev_id}")
                    f_id = item.get("finding_id")
                    if f_id and f_id not in valid_finding_ids:
                        invalid_ids.append(f"evidence[{i}].finding_id:{f_id}")

        # Validate downstream effects
        downstream = raw_output.get("downstream_effects", [])
        if isinstance(downstream, list):
            for i, effect in enumerate(downstream):
                if isinstance(effect, dict):
                    ev_id = effect.get("event_id")
                    if ev_id and ev_id not in valid_event_ids:
                        invalid_ids.append(f"downstream_effects[{i}].event_id:{ev_id}")

        # Validate recommended actions
        actions = raw_output.get("recommended_actions", [])
        if isinstance(actions, list):
            for i, act in enumerate(actions):
                if isinstance(act, dict):
                    for ev_id in act.get("related_event_ids", []):
                        if ev_id and ev_id not in valid_event_ids:
                            invalid_ids.append(f"recommended_actions[{i}].related_event_id:{ev_id}")

        if invalid_ids:
            raise InvestigationValidationError(
                f"LLM output references non-existent trace entities: {', '.join(invalid_ids)}",
                invalid_ids=invalid_ids,
            )

    async def investigate_trace(
        self,
        trace_id: str,
        db: AsyncSession,
        provider: Optional[InvestigationLLMProvider] = None,
    ) -> InvestigationResult:
        """Perform end-to-end AI root-cause investigation for a trace.

        Coordinates trace reconstruction, execution graph generation, deterministic
        failure detection, context building, LLM invocation, and strict ground-truth validation.

        Args:
            trace_id: Unique trace identifier.
            db: Database session.
            provider: Optional override LLM provider instance.

        Returns:
            Structured InvestigationResult.

        Raises:
            TraceNotFoundError: If trace does not exist.
            InvestigationValidationError: If LLM output fails validation.
            Exception: If provider or reconstruction fails.
        """
        # 1. Reconstruct trace
        trace = await trace_reconstruction_service.reconstruct_trace(trace_id, db)

        # 2. Build execution graph
        graph = execution_graph_service.build_graph(trace)

        # 3. Detect deterministic findings
        findings = failure_detection_service.detect_failures(trace)

        # 4. Check for clean trace
        if not findings and trace.status == "completed":
            return InvestigationResult(
                investigation_id=f"inv-{uuid.uuid4().hex[:12]}",
                trace_id=trace_id,
                status=InvestigationStatus.NO_ISSUE_DETECTED,
                summary=f"Trace '{trace_id}' completed successfully with no failures or anomalies detected.",
                root_cause=None,
                first_failure_event_id=None,
                confidence=1.0,
                evidence=[],
                downstream_effects=[],
                recommended_actions=[],
                analyzed_findings=[],
                analyzed_event_ids=[e.event_id for e in trace.events],
                model="deterministic:no_findings",
                created_at=datetime.now(timezone.utc),
            )

        # 5. Build compact investigation context
        context = self.build_context(trace, graph, findings)

        # 6. Call active LLM provider
        active_provider = provider or self.get_provider()
        raw_output = await active_provider.investigate(context)

        # 7. Validate LLM output against ground truth trace and findings
        self.validate_llm_output(raw_output, trace, findings)

        # 8. Parse into structured domain model
        status_str = raw_output.get("status", "investigated")
        try:
            inv_status = InvestigationStatus(status_str)
        except ValueError:
            inv_status = InvestigationStatus.INVESTIGATED

        root_cause_data = raw_output.get("root_cause")
        root_cause_obj = None
        if root_cause_data and isinstance(root_cause_data, dict):
            root_cause_obj = RootCause(
                description=root_cause_data.get("description", "Root cause identified"),
                event_id=root_cause_data.get("event_id"),
                finding_id=root_cause_data.get("finding_id"),
                confidence=float(root_cause_data.get("confidence", 0.8)),
                reasoning=root_cause_data.get("reasoning", ""),
            )

        evidence_items: list[EvidenceItem] = []
        for item in raw_output.get("evidence", []):
            if isinstance(item, dict):
                evidence_items.append(
                    EvidenceItem(
                        event_id=item.get("event_id"),
                        finding_id=item.get("finding_id"),
                        description=item.get("description", ""),
                    )
                )

        downstream_effects: list[DownstreamEffect] = []
        for item in raw_output.get("downstream_effects", []):
            if isinstance(item, dict):
                downstream_effects.append(
                    DownstreamEffect(
                        event_id=item.get("event_id"),
                        description=item.get("description", ""),
                        impact=item.get("impact", ""),
                    )
                )

        recommended_actions: list[RecommendedAction] = []
        for item in raw_output.get("recommended_actions", []):
            if isinstance(item, dict):
                recommended_actions.append(
                    RecommendedAction(
                        action=item.get("action", ""),
                        related_event_ids=item.get("related_event_ids", []),
                        priority=item.get("priority", "medium"),
                    )
                )

        confidence_val = float(raw_output.get("confidence", 0.8))
        confidence_val = max(0.0, min(1.0, confidence_val))

        return InvestigationResult(
            investigation_id=f"inv-{uuid.uuid4().hex[:12]}",
            trace_id=trace_id,
            status=inv_status,
            summary=raw_output.get("summary", "Investigation completed"),
            root_cause=root_cause_obj,
            first_failure_event_id=raw_output.get("first_failure_event_id"),
            confidence=confidence_val,
            evidence=evidence_items,
            downstream_effects=downstream_effects,
            recommended_actions=recommended_actions,
            analyzed_findings=[f.finding_id for f in findings],
            analyzed_event_ids=[e.event_id for e in trace.events],
            model=active_provider.model_name,
            created_at=datetime.now(timezone.utc),
        )

    def _sanitize_dict(self, d: dict[str, Any]) -> dict[str, Any]:
        """Redact sensitive fields from data dictionary."""
        return sanitize_telemetry(d)


# Global singleton instance
ai_investigation_service = AIInvestigationService()
