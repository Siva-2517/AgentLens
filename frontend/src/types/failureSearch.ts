/**
 * Types for Phase 15 — Historical Failure Search with pgvector.
 */

export interface HistoricalFailureSearchResult {
  trace_id: string;
  finding_id: string;
  rule: string;
  category: string;
  severity: string;
  message: string;
  searchable_text: string;
  similarity: number;
  trace_name: string;
  project_name: string;
  created_at: string;
  evidence_event_ids: string[];
  metadata: Record<string, any>;
}

export interface HistoricalSearchResponse {
  query: string;
  total_results: number;
  results: HistoricalFailureSearchResult[];
  embedding_model?: string;
}

export interface TraceIndexingResponse {
  trace_id: string;
  indexed_count: number;
  status: 'indexed' | 'no_findings' | 'error';
  finding_ids: string[];
  message: string;
}

export interface FailureSearchParams {
  q: string;
  limit?: number;
  severity?: string;
  rule?: string;
  project?: string;
}
