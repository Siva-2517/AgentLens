"""AgentLens MCP Tools.

Read-only observability tools exposed via Model Context Protocol:
1. get_trace
2. get_execution_graph
3. get_trace_findings
4. investigate_trace
5. compare_traces
6. search_historical_failures
7. list_recent_traces

All tools strictly reuse existing AgentLens domain services.
No business logic is duplicated.
No write operations are permitted.
"""

from contextlib import asynccontextmanager
import logging
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import AsyncSessionLocal
from app.mcp.redaction import sanitize_for_mcp
from app.services.execution_graph_service import execution_graph_service
from app.services.failure_detection_service import failure_detection_service
from app.services.failure_search_service import failure_search_service
from app.services.investigation_service import (
    InvestigationValidationError,
    ai_investigation_service,
)
from app.services.trace_comparison_service import trace_comparison_service
from app.services.trace_reconstruction_service import (
    TraceNotFoundError,
    trace_reconstruction_service,
)
from app.services.trace_service import trace_service

logger = logging.getLogger(__name__)

# Configurable session factory for tests and custom environments
_session_factory: Optional[Callable[[], Any]] = None


def set_session_factory(factory: Optional[Callable[[], Any]]) -> None:
    """Set custom session factory (e.g. for unit and integration testing)."""
    global _session_factory
    _session_factory = factory


@asynccontextmanager
async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield an async database session."""
    if _session_factory is not None:
        async with _session_factory() as session:
            yield session
    else:
        async with AsyncSessionLocal() as session:
            try:
                yield session
            finally:
                await session.close()


def _format_error(error_code: str, message: str, detail: Optional[Any] = None) -> Dict[str, Any]:
    """Return structured, machine-readable error dictionary with secrets sanitized."""
    err: Dict[str, Any] = {
        "error": error_code,
        "message": sanitize_for_mcp(message),
    }
    if detail is not None:
        err["detail"] = sanitize_for_mcp(str(detail))
    return err


async def get_trace_handler(trace_id: str) -> Dict[str, Any]:
    """Retrieve structured trace summary and reconstructed execution flow."""
    clean_id = (trace_id or "").strip()
    if not clean_id:
        return _format_error("invalid_parameter", "Parameter 'trace_id' must be a non-empty string.")

    try:
        async with get_db_session() as db:
            trace = await trace_reconstruction_service.reconstruct_trace(clean_id, db)

        # Build compact, structured machine-readable trace
        events_summary: List[Dict[str, Any]] = []
        for ev in trace.events:
            events_summary.append({
                "event_id": ev.event_id,
                "event_type": ev.event_type,
                "timestamp": ev.timestamp.isoformat() if hasattr(ev.timestamp, "isoformat") else str(ev.timestamp),
                "parent_event_id": ev.parent_event_id,
                "duration_ms": ev.duration_ms,
                "data": sanitize_for_mcp(ev.data or {}),
            })

        meta = trace.metadata
        return sanitize_for_mcp({
            "trace_id": trace.trace_id,
            "name": trace.name,
            "project_name": trace.project_name,
            "status": trace.status,
            "start_time": trace.start_time.isoformat() if hasattr(trace.start_time, "isoformat") else str(trace.start_time),
            "end_time": trace.end_time.isoformat() if trace.end_time and hasattr(trace.end_time, "isoformat") else str(trace.end_time),
            "duration_ms": trace.duration_ms,
            "event_count": trace.event_count,
            "metrics": {
                "total_events": meta.total_event_count if meta else trace.event_count,
                "errors": meta.error_count if meta else 0,
                "retries": meta.retry_count if meta else 0,
                "llm_calls": meta.llm_call_count if meta else 0,
                "tool_calls": meta.tool_call_count if meta else 0,
                "is_complete": meta.is_complete if meta else False,
            },
            "events": events_summary,
        })

    except TraceNotFoundError:
        return _format_error("trace_not_found", f"Trace '{clean_id}' not found.")
    except Exception as e:
        logger.exception("get_trace failed: %s", e)
        return _format_error("internal_error", "Failed to retrieve trace.", detail=str(e))


async def get_execution_graph_handler(trace_id: str) -> Dict[str, Any]:
    """Retrieve execution graph (nodes, directed edges, and counts) for a trace."""
    clean_id = (trace_id or "").strip()
    if not clean_id:
        return _format_error("invalid_parameter", "Parameter 'trace_id' must be a non-empty string.")

    try:
        async with get_db_session() as db:
            graph = await execution_graph_service.get_execution_graph(clean_id, db)

        return sanitize_for_mcp({
            "trace_id": graph.trace_id,
            "node_count": graph.node_count,
            "edge_count": graph.edge_count,
            "nodes": [
                {
                    "id": n.id,
                    "event_id": n.event_id,
                    "event_type": n.event_type,
                    "label": n.label,
                    "status": n.status,
                    "duration_ms": n.duration_ms,
                    "depth": n.depth,
                    "parent_event_id": n.parent_event_id,
                }
                for n in graph.nodes
            ],
            "edges": [
                {
                    "id": e.id,
                    "source": e.source,
                    "target": e.target,
                    "relationship": e.relationship,
                }
                for e in graph.edges
            ],
        })

    except TraceNotFoundError:
        return _format_error("trace_not_found", f"Trace '{clean_id}' not found.")
    except Exception as e:
        logger.exception("get_execution_graph failed: %s", e)
        return _format_error("internal_error", "Failed to retrieve execution graph.", detail=str(e))


async def get_trace_findings_handler(trace_id: str) -> Dict[str, Any]:
    """Retrieve deterministic failure and anomaly findings for a trace."""
    clean_id = (trace_id or "").strip()
    if not clean_id:
        return _format_error("invalid_parameter", "Parameter 'trace_id' must be a non-empty string.")

    try:
        async with get_db_session() as db:
            findings_resp = await failure_detection_service.get_findings(clean_id, db)

        return sanitize_for_mcp({
            "trace_id": findings_resp.trace_id,
            "total_findings": findings_resp.total_findings,
            "findings": [
                {
                    "finding_id": f.finding_id,
                    "rule": f.rule,
                    "category": f.category.value if hasattr(f.category, "value") else str(f.category),
                    "severity": f.severity.value if hasattr(f.severity, "value") else str(f.severity),
                    "message": f.message,
                    "evidence_event_ids": f.evidence_event_ids,
                    "evidence": sanitize_for_mcp(f.evidence or {}),
                    "detected_at": f.detected_at.isoformat() if hasattr(f.detected_at, "isoformat") else str(f.detected_at),
                }
                for f in findings_resp.findings
            ],
        })

    except TraceNotFoundError:
        return _format_error("trace_not_found", f"Trace '{clean_id}' not found.")
    except Exception as e:
        logger.exception("get_trace_findings failed: %s", e)
        return _format_error("internal_error", "Failed to analyze trace findings.", detail=str(e))


async def investigate_trace_handler(trace_id: str) -> Dict[str, Any]:
    """Perform AI-powered root-cause failure investigation for a trace."""
    clean_id = (trace_id or "").strip()
    if not clean_id:
        return _format_error("invalid_parameter", "Parameter 'trace_id' must be a non-empty string.")

    try:
        async with get_db_session() as db:
            result = await ai_investigation_service.investigate_trace(clean_id, db)

        root_cause = None
        if result.root_cause:
            root_cause = {
                "description": result.root_cause.description,
                "event_id": result.root_cause.event_id,
                "finding_id": result.root_cause.finding_id,
                "confidence": result.root_cause.confidence,
                "reasoning": result.root_cause.reasoning,
            }

        return sanitize_for_mcp({
            "trace_id": result.trace_id,
            "status": result.status.value if hasattr(result.status, "value") else str(result.status),
            "confidence": result.confidence,
            "summary": result.summary,
            "root_cause": root_cause,
            "first_failure_event_id": result.first_failure_event_id,
            "evidence": [
                {
                    "event_id": ev.event_id,
                    "finding_id": ev.finding_id,
                    "description": ev.description,
                }
                for ev in result.evidence
            ],
            "downstream_effects": [
                {
                    "event_id": eff.event_id,
                    "description": eff.description,
                    "impact": eff.impact,
                }
                for eff in result.downstream_effects
            ],
            "recommended_actions": [
                {
                    "action": act.action,
                    "related_event_ids": act.related_event_ids,
                    "priority": act.priority,
                }
                for act in result.recommended_actions
            ],
        })

    except TraceNotFoundError:
        return _format_error("trace_not_found", f"Trace '{clean_id}' not found.")
    except InvestigationValidationError as e:
        return _format_error("investigation_validation_error", str(e))
    except Exception as e:
        logger.exception("investigate_trace failed: %s", e)
        return _format_error("internal_error", "Failed to investigate trace.", detail=str(e))


async def compare_traces_handler(trace_a: str, trace_b: str) -> Dict[str, Any]:
    """Compare two reconstructed execution traces side-by-side."""
    clean_a = (trace_a or "").strip()
    clean_b = (trace_b or "").strip()

    if not clean_a:
        return _format_error("invalid_parameter", "Parameter 'trace_a' must be a non-empty string.")
    if not clean_b:
        return _format_error("invalid_parameter", "Parameter 'trace_b' must be a non-empty string.")
    if len(clean_a) > 256 or len(clean_b) > 256:
        return _format_error("invalid_parameter", "Trace identifiers must not exceed 256 characters.")
    if clean_a == clean_b:
        return _format_error("invalid_parameter", "Cannot compare a trace to itself ('trace_a' and 'trace_b' must differ).")

    try:
        async with get_db_session() as db:
            comp = await trace_comparison_service.compare_traces(clean_a, clean_b, db)

        return sanitize_for_mcp({
            "trace_a": {
                "trace_id": comp.trace_a.trace_id,
                "name": comp.trace_a.name,
                "status": comp.trace_a.status,
                "duration_ms": comp.trace_a.duration_ms,
                "event_count": comp.trace_a.event_count,
                "findings_count": comp.trace_a.findings_count,
            },
            "trace_b": {
                "trace_id": comp.trace_b.trace_id,
                "name": comp.trace_b.name,
                "status": comp.trace_b.status,
                "duration_ms": comp.trace_b.duration_ms,
                "event_count": comp.trace_b.event_count,
                "findings_count": comp.trace_b.findings_count,
            },
            "status_diff": {
                "trace_a": comp.differences.status_a,
                "trace_b": comp.differences.status_b,
                "is_same": not comp.differences.status_changed,
            },
            "duration_diff_ms": comp.differences.duration_diff_ms,
            "event_count_diff": comp.differences.event_count_diff,
            "findings_count_diff": comp.differences.findings_count_diff,
            "matched_steps_count": len([s for s in comp.sequence_comparison if s.status == "matched"]),
            "divergence_steps_count": len([s for s in comp.sequence_comparison if s.status != "matched"]),
            "sequence_summary": [
                {
                    "step_index": s.step_index,
                    "status": s.status,
                    "change_summary": s.change_summary,
                }
                for s in comp.sequence_comparison[:20]
            ],
        })

    except TraceNotFoundError as e:
        return _format_error("trace_not_found", f"Trace '{e.trace_id}' not found.")
    except ValueError as e:
        return _format_error("invalid_parameter", str(e))
    except Exception as e:
        logger.exception("compare_traces failed: %s", e)
        return _format_error("internal_error", "Failed to compare traces.", detail=str(e))


async def search_historical_failures_handler(
    query: str,
    limit: int = 10,
    severity: Optional[str] = None,
    rule: Optional[str] = None,
    project: Optional[str] = None,
) -> Dict[str, Any]:
    """Search historical agent failures using pgvector semantic similarity."""
    clean_q = (query or "").strip()
    if not clean_q:
        return _format_error("invalid_parameter", "Parameter 'query' must be a non-empty string.")
    if len(clean_q) > 1000:
        return _format_error("invalid_parameter", "Parameter 'query' exceeds maximum length of 1000 characters.")

    if not isinstance(limit, int) or limit < 1 or limit > 50:
        return _format_error("invalid_parameter", "Parameter 'limit' must be an integer between 1 and 50.")

    valid_severities = {"critical", "error", "warning", "info"}
    clean_sev = severity.strip().lower() if severity and severity.strip() else None
    if clean_sev and clean_sev not in valid_severities:
        return _format_error("invalid_parameter", f"Invalid severity '{severity}'. Supported: critical, error, warning, info.")

    try:
        async with get_db_session() as db:
            search_res = await failure_search_service.search_failures(
                query=clean_q,
                db=db,
                limit=limit,
                severity=clean_sev,
                rule=rule.strip() if rule and rule.strip() else None,
                project_name=project.strip() if project and project.strip() else None,
            )

        return sanitize_for_mcp({
            "query": search_res.query,
            "total_results": search_res.total_results,
            "results": [
                {
                    "trace_id": r.trace_id,
                    "finding_id": r.finding_id,
                    "rule": r.rule,
                    "category": r.category,
                    "severity": r.severity,
                    "similarity": round(r.similarity, 4),
                    "message": r.message,
                    "trace_name": r.trace_name,
                    "project_name": r.project_name,
                    "evidence_event_ids": r.evidence_event_ids,
                    "created_at": r.created_at.isoformat() if hasattr(r.created_at, "isoformat") else str(r.created_at),
                }
                for r in search_res.results
            ],
        })

    except ValueError as e:
        return _format_error("invalid_parameter", str(e))
    except Exception as e:
        logger.exception("search_historical_failures failed: %s", e)
        return _format_error("internal_error", "Failed to search historical failures.", detail=str(e))


async def list_recent_traces_handler(
    project: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
) -> Dict[str, Any]:
    """Retrieve list of recent lightweight trace summaries."""
    if not isinstance(limit, int) or limit < 1 or limit > 100:
        return _format_error("invalid_parameter", "Parameter 'limit' must be an integer between 1 and 100.")
    if not isinstance(offset, int) or offset < 0:
        return _format_error("invalid_parameter", "Parameter 'offset' must be a non-negative integer.")

    clean_proj = project.strip() if project and project.strip() else None

    try:
        async with get_db_session() as db:
            summaries = await trace_service.list_traces(
                project_name=clean_proj,
                db=db,
                limit=limit,
                offset=offset,
            )

        return sanitize_for_mcp({
            "total": len(summaries),
            "limit": limit,
            "offset": offset,
            "project_filter": clean_proj,
            "traces": [
                {
                    "trace_id": t.trace_id,
                    "name": t.name,
                    "project_name": t.project_name,
                    "status": t.status,
                    "start_time": t.start_time.isoformat() if hasattr(t.start_time, "isoformat") else str(t.start_time),
                    "end_time": t.end_time.isoformat() if t.end_time and hasattr(t.end_time, "isoformat") else str(t.end_time),
                    "duration_ms": t.duration_ms,
                    "event_count": t.event_count,
                }
                for t in summaries
            ],
        })

    except Exception as e:
        logger.exception("list_recent_traces failed: %s", e)
        return _format_error("internal_error", "Failed to list recent traces.", detail=str(e))
