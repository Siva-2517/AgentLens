"""Failure and Anomaly Detection Service.

Provides deterministic analysis of reconstructed agent execution traces to identify
explicit errors, missing responses, loops, retries, and lifecycle anomalies.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventType
from app.models.finding import (
    DetectionConfig,
    Finding,
    FindingCategory,
    FindingSeverity,
    FindingsResponse,
    generate_finding_id,
)
from app.models.reconstructed_trace import ReconstructedEvent, ReconstructedTrace
from app.services.trace_reconstruction_service import (
    TraceNotFoundError,
    trace_reconstruction_service,
)

logger = logging.getLogger(__name__)

SEVERITY_ORDER: Dict[FindingSeverity, int] = {
    FindingSeverity.CRITICAL: 0,
    FindingSeverity.ERROR: 1,
    FindingSeverity.WARNING: 2,
    FindingSeverity.INFO: 3,
}


def _canonicalize(val: Any) -> Any:
    """Recursively normalize inputs/dictionaries for deterministic comparison."""
    if isinstance(val, dict):
        return {k: _canonicalize(v) for k, v in sorted(val.items())}
    if isinstance(val, list):
        return [_canonicalize(x) for x in val]
    return str(val) if isinstance(val, (int, float, bool, str)) or val is None else repr(val)


def _canonical_json(val: Any) -> str:
    """Generate canonical JSON string representation."""
    try:
        return json.dumps(_canonicalize(val), sort_keys=True)
    except Exception:
        return str(val)


class FailureDetectionService:
    """Service for deterministic failure and anomaly detection on ReconstructedTraces."""

    def __init__(self, default_config: Optional[DetectionConfig] = None):
        self.default_config = default_config or DetectionConfig()

    def detect_failures(
        self,
        trace: ReconstructedTrace,
        config: Optional[DetectionConfig] = None,
    ) -> List[Finding]:
        """Analyze a reconstructed trace and return deterministic findings.

        This method is purely in-memory and operates directly on the ReconstructedTrace.
        It performs NO database queries.

        Args:
            trace: ReconstructedTrace object from Phase 7.
            config: Optional override configuration for detection thresholds.

        Returns:
            Deterministic list of findings ordered by severity, rule, and event identity.
        """
        cfg = config or self.default_config
        now = datetime.now(timezone.utc)
        findings: List[Finding] = []

        # Run all 8 deterministic detection rules
        findings.extend(self._detect_explicit_errors(trace, now))
        findings.extend(self._detect_unresolved_retries(trace, now))
        findings.extend(self._detect_repeated_tool_calls(trace, cfg, now))
        findings.extend(self._detect_missing_tool_responses(trace, now))
        findings.extend(self._detect_missing_llm_responses(trace, now))
        findings.extend(self._detect_invalid_lifecycle(trace, now))
        findings.extend(self._detect_execution_loops(trace, cfg, now))
        findings.extend(self._detect_high_retry_count(trace, cfg, now))

        # Deterministic sorting
        findings.sort(
            key=lambda f: (
                SEVERITY_ORDER.get(f.severity, 99),
                f.rule,
                f.evidence_event_ids[0] if f.evidence_event_ids else "",
                f.finding_id,
            )
        )

        return findings

    async def get_findings(
        self,
        trace_id: str,
        db: AsyncSession,
        config: Optional[DetectionConfig] = None,
    ) -> FindingsResponse:
        """Fetch trace, reconstruct it, and compute deterministic findings.

        Args:
            trace_id: Unique trace identifier.
            db: Database session.
            config: Optional detection thresholds.

        Returns:
            FindingsResponse containing deterministic findings list.
        """
        trace = await trace_reconstruction_service.reconstruct_trace(trace_id, db)
        findings = self.detect_failures(trace, config)
        return FindingsResponse(
            trace_id=trace_id,
            total_findings=len(findings),
            findings=findings,
        )

    # =========================================================================
    # Rule 1: Explicit ERROR event
    # =========================================================================
    def _detect_explicit_errors(
        self, trace: ReconstructedTrace, now: datetime
    ) -> List[Finding]:
        findings: List[Finding] = []
        for ev in trace.events:
            if ev.event_type == EventType.ERROR.value:
                error_msg = (
                    ev.data.get("message")
                    or ev.data.get("error")
                    or ev.metadata.get("error")
                    or ev.data.get("detail")
                    or "Explicit ERROR event recorded in execution"
                )
                severity = (
                    FindingSeverity.CRITICAL
                    if trace.status == "failed"
                    else FindingSeverity.ERROR
                )
                evidence_ids = [ev.event_id]
                rule = "explicit_error"
                findings.append(
                    Finding(
                        finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                        trace_id=trace.trace_id,
                        rule=rule,
                        category=FindingCategory.EXPLICIT_ERROR,
                        severity=severity,
                        message=f"Explicit ERROR event detected: {error_msg}",
                        evidence_event_ids=evidence_ids,
                        evidence={
                            "event_id": ev.event_id,
                            "error_message": error_msg,
                            "data": ev.data,
                            "metadata": ev.metadata,
                        },
                        detected_at=now,
                    )
                )
        return findings

    # =========================================================================
    # Rule 2: Unresolved retry
    # =========================================================================
    def _detect_unresolved_retries(
        self, trace: ReconstructedTrace, now: datetime
    ) -> List[Finding]:
        findings: List[Finding] = []
        retry_events = [ev for ev in trace.events if ev.event_type == EventType.RETRY.value]
        if not retry_events:
            return findings

        # Check if retry sequence failed to reach a successful continuation
        # Conditions for unresolved retry:
        # 1. Trace marked as "failed" after one or more retries
        # 2. Terminal action event in trace is a RETRY without continuation
        # 3. RETRY event followed by ERROR before any successful action
        is_unresolved = False
        evidence_ids = [r.event_id for r in retry_events]

        if trace.status == "failed":
            is_unresolved = True
        else:
            # Check terminal events excluding AGENT_END
            action_events = [
                ev for ev in trace.events
                if ev.event_type not in (EventType.AGENT_START.value, EventType.AGENT_END.value)
            ]
            if action_events:
                last_action = action_events[-1]
                if last_action.event_type in (EventType.RETRY.value, EventType.ERROR.value):
                    is_unresolved = True

            # Also check if any RETRY is immediately followed by ERROR
            for i in range(len(trace.events) - 1):
                if (
                    trace.events[i].event_type == EventType.RETRY.value
                    and trace.events[i + 1].event_type == EventType.ERROR.value
                ):
                    is_unresolved = True
                    if trace.events[i + 1].event_id not in evidence_ids:
                        evidence_ids.append(trace.events[i + 1].event_id)

        if is_unresolved:
            rule = "unresolved_retry"
            findings.append(
                Finding(
                    finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                    trace_id=trace.trace_id,
                    rule=rule,
                    category=FindingCategory.RETRY_EXHAUSTION,
                    severity=FindingSeverity.ERROR,
                    message=(
                        f"Unresolved retry detected: {len(retry_events)} retry event(s) "
                        "did not reach a successful completion."
                    ),
                    evidence_event_ids=evidence_ids,
                    evidence={
                        "retry_count": len(retry_events),
                        "trace_status": trace.status,
                        "retry_event_ids": [r.event_id for r in retry_events],
                    },
                    detected_at=now,
                )
            )

        return findings

    # =========================================================================
    # Rule 3: Repeated tool calls
    # =========================================================================
    def _detect_repeated_tool_calls(
        self,
        trace: ReconstructedTrace,
        config: DetectionConfig,
        now: datetime,
    ) -> List[Finding]:
        findings: List[Finding] = []
        tool_calls: Dict[Tuple[str, str], List[ReconstructedEvent]] = {}

        for ev in trace.events:
            if ev.event_type == EventType.TOOL_CALL.value:
                tool_name = (
                    ev.data.get("name")
                    or ev.data.get("tool")
                    or ev.data.get("tool_name")
                    or ev.metadata.get("tool_name")
                    or "unknown_tool"
                )
                raw_inputs = (
                    ev.data.get("inputs")
                    if "inputs" in ev.data
                    else ev.data.get("input", ev.data.get("arguments", ev.data.get("args", {})))
                )
                input_key = _canonical_json(raw_inputs)
                key = (tool_name, input_key)
                tool_calls.setdefault(key, []).append(ev)

        rule = "repeated_tool_call"
        for (tool_name, input_key), calls in tool_calls.items():
            call_count = len(calls)
            if call_count >= config.repeated_tool_call_threshold:
                evidence_ids = [c.event_id for c in calls]
                severity = (
                    FindingSeverity.ERROR
                    if call_count >= config.repeated_tool_call_threshold * 2
                    else FindingSeverity.WARNING
                )
                findings.append(
                    Finding(
                        finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                        trace_id=trace.trace_id,
                        rule=rule,
                        category=FindingCategory.REPEATED_TOOL_CALL,
                        severity=severity,
                        message=(
                            f"Repeated tool call detected: tool '{tool_name}' was called "
                            f"{call_count} times with equivalent inputs "
                            f"(threshold: {config.repeated_tool_call_threshold})."
                        ),
                        evidence_event_ids=evidence_ids,
                        evidence={
                            "tool_name": tool_name,
                            "call_count": call_count,
                            "threshold": config.repeated_tool_call_threshold,
                            "inputs_summary": input_key[:200],
                        },
                        detected_at=now,
                    )
                )

        return findings

    # =========================================================================
    # Rule 4: Tool call without response
    # =========================================================================
    def _detect_missing_tool_responses(
        self, trace: ReconstructedTrace, now: datetime
    ) -> List[Finding]:
        findings: List[Finding] = []
        rule = "missing_tool_response"

        # Index responses by parent_event_id and explicit tool_call_id
        responses_by_parent: Set[str] = set()
        responses_by_call_id: Set[str] = set()

        for ev in trace.events:
            if ev.event_type == EventType.TOOL_RESPONSE.value:
                if ev.parent_event_id:
                    responses_by_parent.add(ev.parent_event_id)
                cid = ev.data.get("tool_call_id") or ev.metadata.get("tool_call_id")
                if cid:
                    responses_by_call_id.add(str(cid))

        for ev in trace.events:
            if ev.event_type == EventType.TOOL_CALL.value:
                has_child_response = any(
                    cid in responses_by_parent or cid in responses_by_call_id
                    for cid in [ev.event_id]
                )
                has_explicit_response = (
                    ev.event_id in responses_by_parent
                    or ev.event_id in responses_by_call_id
                    or any(
                        child_id for child_id in ev.children_ids
                        if any(
                            r.event_id == child_id and r.event_type == EventType.TOOL_RESPONSE.value
                            for r in trace.events
                        )
                    )
                )

                if not (has_child_response or has_explicit_response):
                    tool_name = (
                        ev.data.get("name")
                        or ev.data.get("tool")
                        or ev.data.get("tool_name")
                        or ev.metadata.get("tool_name")
                        or "unknown_tool"
                    )
                    evidence_ids = [ev.event_id]
                    findings.append(
                        Finding(
                            finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                            trace_id=trace.trace_id,
                            rule=rule,
                            category=FindingCategory.MISSING_RESPONSE,
                            severity=FindingSeverity.ERROR,
                            message=f"TOOL_CALL event '{tool_name}' ({ev.event_id}) has no corresponding TOOL_RESPONSE.",
                            evidence_event_ids=evidence_ids,
                            evidence={
                                "tool_call_id": ev.event_id,
                                "tool_name": tool_name,
                            },
                            detected_at=now,
                        )
                    )

        return findings

    # =========================================================================
    # Rule 5: LLM call without response
    # =========================================================================
    def _detect_missing_llm_responses(
        self, trace: ReconstructedTrace, now: datetime
    ) -> List[Finding]:
        findings: List[Finding] = []
        rule = "missing_llm_response"

        responses_by_parent: Set[str] = set()
        responses_by_call_id: Set[str] = set()

        for ev in trace.events:
            if ev.event_type == EventType.LLM_RESPONSE.value:
                if ev.parent_event_id:
                    responses_by_parent.add(ev.parent_event_id)
                cid = ev.data.get("llm_call_id") or ev.metadata.get("llm_call_id")
                if cid:
                    responses_by_call_id.add(str(cid))

        for ev in trace.events:
            if ev.event_type == EventType.LLM_CALL.value:
                has_response = (
                    ev.event_id in responses_by_parent
                    or ev.event_id in responses_by_call_id
                    or any(
                        child_id for child_id in ev.children_ids
                        if any(
                            r.event_id == child_id and r.event_type == EventType.LLM_RESPONSE.value
                            for r in trace.events
                        )
                    )
                )

                if not has_response:
                    model_name = ev.data.get("model") or "unknown_model"
                    evidence_ids = [ev.event_id]
                    findings.append(
                        Finding(
                            finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                            trace_id=trace.trace_id,
                            rule=rule,
                            category=FindingCategory.MISSING_RESPONSE,
                            severity=FindingSeverity.ERROR,
                            message=f"LLM_CALL event ({ev.event_id}) has no corresponding LLM_RESPONSE.",
                            evidence_event_ids=evidence_ids,
                            evidence={
                                "llm_call_id": ev.event_id,
                                "model": model_name,
                            },
                            detected_at=now,
                        )
                    )

        return findings

    # =========================================================================
    # Rule 6: Invalid event lifecycle
    # =========================================================================
    def _detect_invalid_lifecycle(
        self, trace: ReconstructedTrace, now: datetime
    ) -> List[Finding]:
        findings: List[Finding] = []

        start_events = [ev for ev in trace.events if ev.event_type == EventType.AGENT_START.value]
        end_events = [ev for ev in trace.events if ev.event_type == EventType.AGENT_END.value]

        # 6a. Missing AGENT_START
        if not start_events and not trace.metadata.has_agent_start:
            rule = "missing_agent_start"
            evidence_ids: list[str] = []
            findings.append(
                Finding(
                    finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                    trace_id=trace.trace_id,
                    rule=rule,
                    category=FindingCategory.INVALID_LIFECYCLE,
                    severity=FindingSeverity.ERROR,
                    message="Trace is missing expected AGENT_START lifecycle event.",
                    evidence_event_ids=evidence_ids,
                    evidence={"has_agent_start": False},
                    detected_at=now,
                )
            )

        # 6b. Missing AGENT_END for non-running / finished traces
        if not end_events and not trace.metadata.has_agent_end:
            if trace.status in ("completed", "failed") or trace.end_time is not None:
                rule = "missing_agent_end"
                evidence_ids = []
                findings.append(
                    Finding(
                        finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                        trace_id=trace.trace_id,
                        rule=rule,
                        category=FindingCategory.INVALID_LIFECYCLE,
                        severity=FindingSeverity.ERROR,
                        message=f"Trace marked as '{trace.status}' is missing expected AGENT_END lifecycle event.",
                        evidence_event_ids=evidence_ids,
                        evidence={"status": trace.status, "has_agent_end": False},
                        detected_at=now,
                    )
                )

        # 6c. Invalid ordering: AGENT_END before AGENT_START
        if start_events and end_events:
            first_start = start_events[0]
            first_end = end_events[0]
            if first_end.timestamp < first_start.timestamp:
                rule = "invalid_lifecycle_order"
                evidence_ids = [first_start.event_id, first_end.event_id]
                findings.append(
                    Finding(
                        finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                        trace_id=trace.trace_id,
                        rule=rule,
                        category=FindingCategory.INVALID_LIFECYCLE,
                        severity=FindingSeverity.ERROR,
                        message="AGENT_END event occurred before AGENT_START event in trace lifecycle.",
                        evidence_event_ids=evidence_ids,
                        evidence={
                            "start_event_id": first_start.event_id,
                            "end_event_id": first_end.event_id,
                            "start_timestamp": first_start.timestamp.isoformat(),
                            "end_timestamp": first_end.timestamp.isoformat(),
                        },
                        detected_at=now,
                    )
                )

        return findings

    # =========================================================================
    # Rule 7: Potential execution loop
    # =========================================================================
    def _detect_execution_loops(
        self,
        trace: ReconstructedTrace,
        config: DetectionConfig,
        now: datetime,
    ) -> List[Finding]:
        findings: List[Finding] = []
        rule = "execution_loop_detected"

        # Build signatures for operational actions
        operational_events: List[Tuple[str, str]] = []
        for ev in trace.events:
            if ev.event_type in (
                EventType.TOOL_CALL.value,
                EventType.LLM_CALL.value,
                EventType.STATE_CHANGE.value,
                EventType.RETRY.value,
                EventType.ERROR.value,
            ):
                sig = ""
                if ev.event_type == EventType.TOOL_CALL.value:
                    tool_name = ev.data.get("name") or ev.data.get("tool") or "tool"
                    inp = _canonical_json(ev.data.get("inputs", ev.data.get("input", {})))
                    sig = f"TOOL:{tool_name}:{inp}"
                elif ev.event_type == EventType.LLM_CALL.value:
                    model = ev.data.get("model") or "llm"
                    sig = f"LLM:{model}"
                elif ev.event_type == EventType.STATE_CHANGE.value:
                    st = ev.metadata.get("state_type") or ev.data.get("state_type") or "state"
                    sig = f"STATE:{st}"
                elif ev.event_type == EventType.RETRY.value:
                    sig = "RETRY"
                elif ev.event_type == EventType.ERROR.value:
                    sig = f"ERROR:{ev.data.get('message', '')[:50]}"

                operational_events.append((sig, ev.event_id))

        if len(operational_events) < config.loop_threshold:
            return findings

        sigs = [item[0] for item in operational_events]
        event_ids = [item[1] for item in operational_events]
        n = len(sigs)
        covered_indices: Set[int] = set()

        # Check loop pattern length k from 1 up to 4
        for k in range(1, 5):
            i = 0
            while i <= n - k * config.loop_threshold:
                if i in covered_indices:
                    i += 1
                    continue

                pattern = sigs[i : i + k]
                # Count consecutive repetitions
                m = 0
                while i + (m + 1) * k <= n and sigs[i + m * k : i + (m + 1) * k] == pattern:
                    m += 1

                if m >= config.loop_threshold:
                    loop_event_ids = event_ids[i : i + m * k]
                    pattern_labels = [s.split(":", 2)[0] for s in pattern]
                    pattern_summary = " -> ".join(pattern_labels)

                    findings.append(
                        Finding(
                            finding_id=generate_finding_id(trace.trace_id, rule, loop_event_ids),
                            trace_id=trace.trace_id,
                            rule=rule,
                            category=FindingCategory.EXECUTION_LOOP,
                            severity=FindingSeverity.ERROR,
                            message=(
                                f"Potential execution loop detected: pattern '{pattern_summary}' "
                                f"repeated {m} consecutive times (threshold: {config.loop_threshold})."
                            ),
                            evidence_event_ids=loop_event_ids,
                            evidence={
                                "pattern_length": k,
                                "repetitions": m,
                                "threshold": config.loop_threshold,
                                "pattern_summary": pattern_summary,
                            },
                            detected_at=now,
                        )
                    )
                    # Mark indices to avoid redundant detection
                    for idx in range(i, i + m * k):
                        covered_indices.add(idx)
                    i += m * k
                else:
                    i += 1

        return findings

    # =========================================================================
    # Rule 8: Abnormally high retry count
    # =========================================================================
    def _detect_high_retry_count(
        self,
        trace: ReconstructedTrace,
        config: DetectionConfig,
        now: datetime,
    ) -> List[Finding]:
        findings: List[Finding] = []
        retry_events = [ev for ev in trace.events if ev.event_type == EventType.RETRY.value]
        retry_count = len(retry_events) or trace.metadata.retry_count

        if retry_count >= config.retry_threshold:
            rule = "high_retry_count"
            evidence_ids = [ev.event_id for ev in retry_events]
            severity = (
                FindingSeverity.ERROR
                if retry_count >= config.retry_threshold * 2
                else FindingSeverity.WARNING
            )
            findings.append(
                Finding(
                    finding_id=generate_finding_id(trace.trace_id, rule, evidence_ids),
                    trace_id=trace.trace_id,
                    rule=rule,
                    category=FindingCategory.RETRY_EXHAUSTION,
                    severity=severity,
                    message=(
                        f"Abnormally high retry count: {retry_count} retries observed in trace "
                        f"(threshold: {config.retry_threshold})."
                    ),
                    evidence_event_ids=evidence_ids,
                    evidence={
                        "retry_count": retry_count,
                        "threshold": config.retry_threshold,
                    },
                    detected_at=now,
                )
            )

        return findings


# Global singleton instance
failure_detection_service = FailureDetectionService()
