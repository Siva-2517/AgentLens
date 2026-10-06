"""Execution Graph Service.

Transforms Phase 7 ReconstructedTrace objects into deterministic,
frontend-friendly ExecutionGraph representations (nodes and edges).
"""

import logging
from typing import Dict, List, Optional, Set

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.event import EventType
from app.models.execution_graph import (
    ExecutionGraph,
    ExecutionGraphEdge,
    ExecutionGraphNode,
)
from app.models.reconstructed_trace import ReconstructedEvent, ReconstructedTrace
from app.services.trace_reconstruction_service import (
    TraceNotFoundError,
    trace_reconstruction_service,
)

logger = logging.getLogger(__name__)

# Canonical human-readable node labels
NODE_LABELS: Dict[str, str] = {
    EventType.AGENT_START.value: "Agent Start",
    EventType.LLM_CALL.value: "LLM Call",
    EventType.LLM_RESPONSE.value: "LLM Response",
    EventType.TOOL_CALL.value: "Tool Call",
    EventType.TOOL_RESPONSE.value: "Tool Response",
    EventType.STATE_CHANGE.value: "State Change",
    EventType.RETRY.value: "Retry",
    EventType.ERROR.value: "Error",
    EventType.AGENT_END.value: "Agent End",
}


class ExecutionGraphService:
    """Service for building deterministic execution graphs from reconstructed traces."""

    def build_graph(self, trace: ReconstructedTrace) -> ExecutionGraph:
        """Transform a reconstructed trace into an ExecutionGraph.

        This method is purely in-memory and deterministic. It performs no database I/O.

        Args:
            trace: ReconstructedTrace from Phase 7.

        Returns:
            ExecutionGraph containing ordered nodes and directed edges.
        """
        # 1. Construct nodes deterministically from reconstructed events
        nodes: List[ExecutionGraphNode] = []
        event_id_set: Set[str] = set()

        for event in trace.events:
            event_id_set.add(event.event_id)
            node = self._create_node(event)
            nodes.append(node)

        # 2. Construct edges from parent-child relationships
        edges = self._create_edges(trace.events, event_id_set)

        return ExecutionGraph(
            trace_id=trace.trace_id,
            nodes=nodes,
            edges=edges,
            node_count=len(nodes),
            edge_count=len(edges),
        )

    async def get_execution_graph(
        self,
        trace_id: str,
        db: AsyncSession,
    ) -> ExecutionGraph:
        """Retrieve a trace via TraceReconstructionService and build its execution graph.

        Preserves architecture separation:
        Database -> TraceReconstructionService -> ReconstructedTrace -> ExecutionGraphService -> ExecutionGraph

        Args:
            trace_id: Trace identifier.
            db: Database session.

        Returns:
            ExecutionGraph.

        Raises:
            TraceNotFoundError: If the trace does not exist.
        """
        reconstructed_trace = await trace_reconstruction_service.reconstruct_trace(trace_id, db)
        return self.build_graph(reconstructed_trace)

    def _create_node(self, event: ReconstructedEvent) -> ExecutionGraphNode:
        """Create a graph node from a reconstructed event."""
        # Deterministic label resolution
        label = NODE_LABELS.get(
            event.event_type,
            event.event_type.replace("_", " ").title(),
        )

        # Determine status if present in data or error type
        status: Optional[str] = None
        if event.event_type == EventType.ERROR.value:
            status = "error"
        elif "status" in event.data:
            status = str(event.data["status"])
        elif "status" in event.metadata:
            status = str(event.metadata["status"])

        return ExecutionGraphNode(
            id=event.event_id,
            event_id=event.event_id,
            trace_id=event.trace_id,
            event_type=event.event_type,
            label=label,
            timestamp=event.timestamp,
            parent_event_id=event.parent_event_id,
            depth=event.depth,
            duration_ms=event.duration_ms,
            status=status,
            data=event.data,
            metadata=event.metadata,
        )

    def _create_edges(
        self,
        events: List[ReconstructedEvent],
        known_event_ids: Set[str],
    ) -> List[ExecutionGraphEdge]:
        """Construct directed parent-child edges deterministically."""
        edges: List[ExecutionGraphEdge] = []
        seen_edges: Set[tuple[str, str]] = set()

        for event in events:
            parent_id = event.parent_event_id
            child_id = event.event_id

            # Only construct an edge if parent exists in the trace
            if parent_id and parent_id in known_event_ids:
                pair = (parent_id, child_id)
                if pair not in seen_edges:
                    seen_edges.add(pair)
                    edge = ExecutionGraphEdge(
                        id=f"edge_{parent_id}_{child_id}",
                        source=parent_id,
                        target=child_id,
                        relationship="parent-child",
                    )
                    edges.append(edge)

        # Deterministic edge sorting by (source, target)
        edges.sort(key=lambda e: (e.source, e.target, e.id))
        return edges


# Global singleton instance
execution_graph_service = ExecutionGraphService()
