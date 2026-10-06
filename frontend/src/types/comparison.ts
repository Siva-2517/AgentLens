/**
 * TypeScript types for Phase 14 — Trace Comparison and Replay Alignment.
 * Matches backend Pydantic models in app/models/comparison.py.
 */

export interface Finding {
  finding_id: string;
  trace_id: string;
  rule: string;
  category: string;
  severity: 'critical' | 'error' | 'warning' | 'info' | string;
  message: string;
  evidence_event_ids: string[];
  evidence: Record<string, any>;
  detected_at: string;
}

export interface TraceComparisonSummary {
  trace_id: string;
  name: string;
  project_name: string | null;
  status: string;
  start_time: string;
  end_time: string | null;
  duration_ms: number | null;
  event_count: number;
  event_type_counts: Record<string, number>;
  findings_count: number;
  findings_severity_counts: Record<string, number>;
  is_complete: boolean;
  has_agent_start: boolean;
  has_agent_end: boolean;
}

export interface HighLevelDifferences {
  duration_diff_ms: number | null;
  event_count_diff: number;
  status_changed: boolean;
  status_a: string;
  status_b: string;
  findings_count_diff: number;
  event_type_diffs: Record<string, number>;
}

export interface ComparisonEventSummary {
  event_id: string;
  trace_id: string;
  event_type: string;
  timestamp: string;
  duration_ms: number | null;
  depth: number;
  parent_event_id: string | null;
  agent_name: string | null;
  data: Record<string, any>;
  metadata: Record<string, any>;
}

export interface EventComparisonStep {
  step_index: number;
  status: 'matched' | 'only_a' | 'only_b';
  event_a: ComparisonEventSummary | null;
  event_b: ComparisonEventSummary | null;
  duration_diff_ms: number | null;
  change_summary: string;
}

export interface FindingComparison {
  findings_only_a: Finding[];
  findings_only_b: Finding[];
  common_findings: Finding[];
  findings_count_diff: number;
}

export interface TraceComparisonResult {
  trace_a: TraceComparisonSummary;
  trace_b: TraceComparisonSummary;
  differences: HighLevelDifferences;
  sequence_comparison: EventComparisonStep[];
  findings_comparison: FindingComparison;
}
