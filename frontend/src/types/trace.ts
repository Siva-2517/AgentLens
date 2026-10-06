/**
 * TypeScript definitions for AgentLens traces, events, and execution graphs.
 * Matches backend Pydantic contracts from Phase 7 & 8.
 */

export type TraceStatus = 'running' | 'completed' | 'failed';

export interface TraceSummary {
  trace_id: string;
  name: string;
  project_name: string | null;
  status: TraceStatus | string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  event_count: number;
}

export interface TraceExecutionMetadata {
  total_event_count: number;
  duration_ms: number | null;
  llm_call_count: number;
  llm_response_count: number;
  tool_call_count: number;
  tool_response_count: number;
  error_count: number;
  retry_count: number;
  state_change_count: number;
  first_event_timestamp: string | null;
  last_event_timestamp: string | null;
  has_agent_start: boolean;
  has_agent_end: boolean;
  is_complete: boolean;
  event_type_counts: Record<string, number>;
}

export interface ReconstructedEvent {
  event_id: string;
  trace_id: string;
  parent_event_id: string | null;
  event_type: string;
  timestamp: string;
  agent_name: string | null;
  data: Record<string, unknown>;
  metadata: Record<string, unknown>;
  depth: number;
  children_ids: string[];
  duration_ms: number | null;
}

export interface ReconstructedTrace {
  trace_id: string;
  name: string;
  project_name: string | null;
  start_time: string;
  end_time: string | null;
  status: TraceStatus | string;
  duration_ms: number | null;
  event_count: number;
  metadata: TraceExecutionMetadata;
  events: ReconstructedEvent[];
  root_event_ids: string[];
}

export interface ExecutionGraphNode {
  id: string;
  event_id: string;
  trace_id: string;
  event_type: string;
  label: string;
  timestamp: string;
  parent_event_id: string | null;
  depth: number;
  duration_ms: number | null;
  status: string | null;
  data: Record<string, unknown>;
  metadata: Record<string, unknown>;
}

export interface ExecutionGraphEdge {
  id: string;
  source: string;
  target: string;
  relationship: string;
}

export interface ExecutionGraph {
  trace_id: string;
  nodes: ExecutionGraphNode[];
  edges: ExecutionGraphEdge[];
  node_count: number;
  edge_count: number;
}

/**
 * Data passed to the custom React Flow graph node.
 */
export interface FlowNodeData extends Record<string, unknown> {
  rawNode: ExecutionGraphNode;
  isSelected?: boolean;
}
