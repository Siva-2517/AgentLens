import axios, { AxiosError } from 'axios';
import {
  TraceSummary,
  ReconstructedTrace,
  ExecutionGraph,
} from '../types/trace';
import { InvestigationResult } from '../types/investigation';
import { TraceComparisonResult } from '../types/comparison';
import {
  HistoricalSearchResponse,
  TraceIndexingResponse,
  FailureSearchParams,
} from '../types/failureSearch';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || '/api/v1';

const API_KEY =
  import.meta.env.VITE_AGENTLENS_API_KEY || 'test_api_key_123';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${API_KEY}`,
  },
  timeout: 10000,
});

/**
 * Normalizes API error into a human-friendly message.
 */
export function formatApiError(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const axiosError = error as AxiosError<{ detail?: string }>;
    if (axiosError.response) {
      const status = axiosError.response.status;
      const detail = axiosError.response.data?.detail;

      if (status === 401) {
        return detail || 'Unauthorized: Invalid or missing API key.';
      }
      if (status === 404) {
        return detail || 'Resource not found.';
      }
      if (status >= 500) {
        return detail || 'AgentLens server error. Please check server logs.';
      }
      return detail || `Request failed with status ${status}.`;
    }
    if (axiosError.code === 'ECONNABORTED') {
      return 'Request timed out while contacting AgentLens API.';
    }
    if (axiosError.request) {
      return 'Cannot connect to AgentLens backend. Please ensure the server is running on port 8000.';
    }
  }

  if (error instanceof Error) {
    return error.message;
  }
  return 'An unexpected error occurred.';
}

/**
 * Fetch list of lightweight trace summaries.
 */
export async function getTraces(
  projectName?: string,
  limit: number = 100,
  offset: number = 0
): Promise<TraceSummary[]> {
  const params: Record<string, string | number> = { limit, offset };
  if (projectName) {
    params.project = projectName;
  }
  const response = await apiClient.get<TraceSummary[]>('/traces', { params });
  return response.data;
}

/**
 * Fetch reconstructed trace details and events by trace ID.
 */
export async function getTrace(traceId: string): Promise<ReconstructedTrace> {
  const response = await apiClient.get<ReconstructedTrace>(`/traces/${encodeURIComponent(traceId)}`);
  return response.data;
}

/**
 * Fetch execution graph for a trace.
 */
export async function getTraceGraph(traceId: string): Promise<ExecutionGraph> {
  const response = await apiClient.get<ExecutionGraph>(
    `/traces/${encodeURIComponent(traceId)}/graph`
  );
  return response.data;
}

/**
 * Fetch AI root-cause investigation for a trace.
 */
export async function getTraceInvestigation(traceId: string): Promise<InvestigationResult> {
  const response = await apiClient.get<InvestigationResult>(
    `/traces/${encodeURIComponent(traceId)}/investigation`
  );
  return response.data;
}

/**
 * Compare two reconstructed traces side-by-side.
 */
export async function compareTraces(
  traceAId: string,
  traceBId: string
): Promise<TraceComparisonResult> {
  const response = await apiClient.get<TraceComparisonResult>('/traces/compare', {
    params: {
      trace_a: traceAId,
      trace_b: traceBId,
    },
  });
  return response.data;
}

/**
 * Search historical failures using pgvector semantic similarity.
 */
export async function searchHistoricalFailures(
  params: FailureSearchParams
): Promise<HistoricalSearchResponse> {
  const queryParams: Record<string, string | number> = {
    q: params.q,
  };
  if (params.limit !== undefined) {
    queryParams.limit = params.limit;
  }
  if (params.severity) {
    queryParams.severity = params.severity;
  }
  if (params.rule) {
    queryParams.rule = params.rule;
  }
  if (params.project) {
    queryParams.project = params.project;
  }

  const response = await apiClient.get<HistoricalSearchResponse>(
    '/failures/search',
    { params: queryParams }
  );
  return response.data;
}

/**
 * Index a trace's failures into pgvector for historical similarity search.
 */
export async function indexTraceFailures(
  traceId: string
): Promise<TraceIndexingResponse> {
  const response = await apiClient.post<TraceIndexingResponse>(
    `/traces/${encodeURIComponent(traceId)}/index`
  );
  return response.data;
}

