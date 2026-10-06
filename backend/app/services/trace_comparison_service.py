"""Trace Comparison Service.

Provides deterministic side-by-side comparison of two reconstructed agent execution traces,
including high-level metrics, event sequence alignment (replay/diff), and findings comparison.
This service is strictly observational and performs NO agent, tool, or LLM execution.
"""

import logging
from typing import Any, List, Optional, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.comparison import (
    ComparisonEventSummary,
    EventComparisonStep,
    FindingComparison,
    HighLevelDifferences,
    TraceComparisonResult,
    TraceComparisonSummary,
)
from app.models.finding import Finding
from app.models.reconstructed_trace import ReconstructedEvent, ReconstructedTrace
from app.services.failure_detection_service import failure_detection_service
from app.services.trace_reconstruction_service import (
    TraceNotFoundError,
    trace_reconstruction_service,
)

logger = logging.getLogger(__name__)


def _extract_tool_name(event: ReconstructedEvent) -> Optional[str]:
    """Extract tool identifier from event payload or metadata."""
    data = event.data or {}
    meta = event.metadata or {}
    return (
        data.get("tool_name")
        or data.get("name")
        or data.get("tool")
        or meta.get("tool_name")
        or meta.get("tool")
    )


def _extract_model_name(event: ReconstructedEvent) -> Optional[str]:
    """Extract model identifier from event payload or metadata."""
    data = event.data or {}
    meta = event.metadata or {}
    return data.get("model") or meta.get("model")


def _events_match(ev_a: ReconstructedEvent, ev_b: ReconstructedEvent) -> bool:
    """Determine whether two events in separate runs correspond to the same logical step.
    
    Uses deterministic properties: event_type, tool name (for tool calls), and model name (for LLM calls).
    Does NOT depend on event UUIDs.
    """
    if ev_a.event_type != ev_b.event_type:
        return False

    norm_type = ev_a.event_type.upper()
    if norm_type in ("TOOL_CALL", "TOOL_RESPONSE"):
        tool_a = _extract_tool_name(ev_a)
        tool_b = _extract_tool_name(ev_b)
        if tool_a and tool_b:
            return tool_a == tool_b

    if norm_type in ("LLM_CALL", "LLM_RESPONSE"):
        model_a = _extract_model_name(ev_a)
        model_b = _extract_model_name(ev_b)
        if model_a and model_b:
            return model_a == model_b

    return True


def _to_event_summary(event: ReconstructedEvent) -> ComparisonEventSummary:
    """Convert ReconstructedEvent into ComparisonEventSummary for API response."""
    return ComparisonEventSummary(
        event_id=event.event_id,
        trace_id=event.trace_id,
        event_type=event.event_type,
        timestamp=event.timestamp,
        duration_ms=event.duration_ms,
        depth=event.depth,
        parent_event_id=event.parent_event_id,
        agent_name=event.agent_name,
        data=event.data,
        metadata=event.metadata,
    )


class TraceComparisonService:
    """Service for deterministic comparison of agent traces."""

    async def compare_traces(
        self,
        trace_a_id: str,
        trace_b_id: str,
        db: AsyncSession,
    ) -> TraceComparisonResult:
        """Compare two reconstructed execution traces side-by-side.

        Args:
            trace_a_id: First trace ID.
            trace_b_id: Second trace ID.
            db: Async database session.

        Returns:
            TraceComparisonResult with summaries, high-level diffs, sequence diff, and findings diff.

        Raises:
            ValueError: If either trace ID is empty or invalid.
            TraceNotFoundError: If either trace does not exist.
        """
        if not trace_a_id or not trace_a_id.strip():
            raise ValueError("trace_a must be a non-empty string")
        if not trace_b_id or not trace_b_id.strip():
            raise ValueError("trace_b must be a non-empty string")

        clean_a_id = trace_a_id.strip()
        clean_b_id = trace_b_id.strip()

        # 1. Reconstruct both traces independently (reusing Phase 7 service)
        trace_a = await trace_reconstruction_service.reconstruct_trace(clean_a_id, db)
        trace_b = await trace_reconstruction_service.reconstruct_trace(clean_b_id, db)

        # 2. Detect deterministic findings in memory (reusing Phase 11 service)
        findings_a = failure_detection_service.detect_failures(trace_a)
        findings_b = failure_detection_service.detect_failures(trace_b)

        # 3. Build trace comparison summaries
        summary_a = self._build_trace_summary(trace_a, findings_a)
        summary_b = self._build_trace_summary(trace_b, findings_b)

        # 4. Calculate high-level differences
        differences = self._calculate_differences(trace_a, trace_b, findings_a, findings_b)

        # 5. Align event sequences using deterministic LCS alignment
        sequence_steps = self._align_event_sequences(trace_a.events, trace_b.events)

        # 6. Compare deterministic findings
        findings_comp = self._compare_findings(findings_a, findings_b)

        return TraceComparisonResult(
            trace_a=summary_a,
            trace_b=summary_b,
            differences=differences,
            sequence_comparison=sequence_steps,
            findings_comparison=findings_comp,
        )

    def _build_trace_summary(
        self, trace: ReconstructedTrace, findings: List[Finding]
    ) -> TraceComparisonSummary:
        """Build a high-level summary of a trace."""
        sev_counts: dict[str, int] = {}
        for f in findings:
            sev_key = f.severity.value if hasattr(f.severity, "value") else str(f.severity)
            sev_counts[sev_key] = sev_counts.get(sev_key, 0) + 1

        return TraceComparisonSummary(
            trace_id=trace.trace_id,
            name=trace.name,
            project_name=trace.project_name,
            status=trace.status,
            start_time=trace.start_time,
            end_time=trace.end_time,
            duration_ms=trace.duration_ms,
            event_count=trace.event_count,
            event_type_counts=trace.metadata.event_type_counts,
            findings_count=len(findings),
            findings_severity_counts=sev_counts,
            is_complete=trace.metadata.is_complete,
            has_agent_start=trace.metadata.has_agent_start,
            has_agent_end=trace.metadata.has_agent_end,
        )

    def _calculate_differences(
        self,
        trace_a: ReconstructedTrace,
        trace_b: ReconstructedTrace,
        findings_a: List[Finding],
        findings_b: List[Finding],
    ) -> HighLevelDifferences:
        """Calculate high-level metric deltas (B - A)."""
        duration_diff = None
        if trace_a.duration_ms is not None and trace_b.duration_ms is not None:
            duration_diff = round(trace_b.duration_ms - trace_a.duration_ms, 3)

        all_types = set(trace_a.metadata.event_type_counts.keys()) | set(
            trace_b.metadata.event_type_counts.keys()
        )
        type_diffs = {
            t: trace_b.metadata.event_type_counts.get(t, 0)
            - trace_a.metadata.event_type_counts.get(t, 0)
            for t in sorted(all_types)
        }

        return HighLevelDifferences(
            duration_diff_ms=duration_diff,
            event_count_diff=trace_b.event_count - trace_a.event_count,
            status_changed=(trace_a.status != trace_b.status),
            status_a=trace_a.status,
            status_b=trace_b.status,
            findings_count_diff=len(findings_b) - len(findings_a),
            event_type_diffs=type_diffs,
        )

    def _align_event_sequences(
        self,
        events_a: List[ReconstructedEvent],
        events_b: List[ReconstructedEvent],
    ) -> List[EventComparisonStep]:
        """Align two ordered execution sequences using Longest Common Subsequence (LCS).
        
        Produces an ordered list of EventComparisonSteps where each step is either:
        - 'matched': Present in both runs with duration delta
        - 'only_a': Present in Run A only
        - 'only_b': Present in Run B only
        """
        m = len(events_a)
        n = len(events_b)

        # 1. DP matrix for Longest Common Subsequence
        dp = [[0] * (n + 1) for _ in range(m + 1)]
        for i in range(m):
            for j in range(n):
                if _events_match(events_a[i], events_b[j]):
                    dp[i + 1][j + 1] = dp[i][j] + 1
                else:
                    dp[i + 1][j + 1] = max(dp[i + 1][j], dp[i][j + 1])

        # 2. Backtrack to reconstruct aligned sequence
        i, j = m, n
        aligned_steps: List[Tuple[str, Optional[ReconstructedEvent], Optional[ReconstructedEvent]]] = []

        while i > 0 or j > 0:
            if i > 0 and j > 0 and _events_match(events_a[i - 1], events_b[j - 1]) and dp[i][j] == dp[i - 1][j - 1] + 1:
                aligned_steps.append(("matched", events_a[i - 1], events_b[j - 1]))
                i -= 1
                j -= 1
            elif j > 0 and (i == 0 or dp[i][j - 1] >= dp[i - 1][j]):
                aligned_steps.append(("only_b", None, events_b[j - 1]))
                j -= 1
            elif i > 0:
                aligned_steps.append(("only_a", events_a[i - 1], None))
                i -= 1

        aligned_steps.reverse()

        # 3. Format into EventComparisonStep instances
        result: List[EventComparisonStep] = []
        for idx, (status, ev_a, ev_b) in enumerate(aligned_steps, start=1):
            dur_diff: Optional[float] = None
            summary: str = ""

            if status == "matched" and ev_a and ev_b:
                if ev_a.duration_ms is not None and ev_b.duration_ms is not None:
                    dur_diff = round(ev_b.duration_ms - ev_a.duration_ms, 2)
                    sign = "+" if dur_diff >= 0 else ""
                    summary = f"Matched {ev_a.event_type} ({sign}{dur_diff}ms)"
                else:
                    summary = f"Matched {ev_a.event_type}"

                tool_name = _extract_tool_name(ev_a)
                if tool_name:
                    summary += f" [{tool_name}]"

            elif status == "only_a" and ev_a:
                summary = f"Event only in Run A: {ev_a.event_type}"
                tool_name = _extract_tool_name(ev_a)
                if tool_name:
                    summary += f" [{tool_name}]"

            elif status == "only_b" and ev_b:
                summary = f"Event only in Run B: {ev_b.event_type}"
                tool_name = _extract_tool_name(ev_b)
                if tool_name:
                    summary += f" [{tool_name}]"

            result.append(
                EventComparisonStep(
                    step_index=idx,
                    status=status,
                    event_a=_to_event_summary(ev_a) if ev_a else None,
                    event_b=_to_event_summary(ev_b) if ev_b else None,
                    duration_diff_ms=dur_diff,
                    change_summary=summary,
                )
            )

        return result

    def _compare_findings(
        self,
        findings_a: List[Finding],
        findings_b: List[Finding],
    ) -> FindingComparison:
        """Compare deterministic findings between the two runs."""
        rules_a = {f.rule for f in findings_a}
        rules_b = {f.rule for f in findings_b}

        # Common finding rules
        common_rules = rules_a & rules_b
        common_findings = [f for f in findings_b if f.rule in common_rules]

        # Unique findings
        only_a = [f for f in findings_a if f.rule not in rules_b]
        only_b = [f for f in findings_b if f.rule not in rules_a]

        return FindingComparison(
            findings_only_a=only_a,
            findings_only_b=only_b,
            common_findings=common_findings,
            findings_count_diff=len(findings_b) - len(findings_a),
        )


trace_comparison_service = TraceComparisonService()
