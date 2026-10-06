/**
 * TypeScript definitions for Phase 12 AI Root-Cause Investigation.
 * Matches backend Pydantic models in backend/app/models/investigation.py.
 */

export type InvestigationStatus =
  | 'investigated'
  | 'no_issue_detected'
  | 'insufficient_evidence'
  | 'failed';

export interface RootCause {
  description: string;
  event_id: string | null;
  finding_id: string | null;
  confidence: number;
  reasoning: string;
}

export interface EvidenceItem {
  event_id: string | null;
  finding_id: string | null;
  description: string;
}

export interface DownstreamEffect {
  event_id: string | null;
  description: string;
  impact: string;
}

export interface RecommendedAction {
  action: string;
  related_event_ids: string[];
  priority: 'high' | 'medium' | 'low' | string;
}

export interface InvestigationResult {
  investigation_id: string;
  trace_id: string;
  status: InvestigationStatus;
  summary: string;
  root_cause: RootCause | null;
  first_failure_event_id: string | null;
  confidence: number;
  evidence: EvidenceItem[];
  downstream_effects: DownstreamEffect[];
  recommended_actions: RecommendedAction[];
  analyzed_findings: string[];
  analyzed_event_ids: string[];
  model: string;
  created_at: string;
}
