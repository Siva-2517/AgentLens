import axios, { AxiosError, InternalAxiosRequestConfig } from 'axios';
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
import { getEffectiveCsrfToken, setCsrfToken } from './csrf';

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || '/api/v1';

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
  timeout: 10000,
});

// Listener for session expiration (401 that cannot be refreshed)
type SessionExpiredListener = () => void;
const sessionExpiredListeners: Set<SessionExpiredListener> = new Set();

export function onSessionExpired(listener: SessionExpiredListener): () => void {
  sessionExpiredListeners.add(listener);
  return () => {
    sessionExpiredListeners.delete(listener);
  };
}

function notifySessionExpired(): void {
  sessionExpiredListeners.forEach((fn) => {
    try {
      fn();
    } catch {
      // safe
    }
  });
}

// Request interceptor: attach X-CSRF-Token on state-changing requests
apiClient.interceptors.request.use((config: InternalAxiosRequestConfig) => {
  const method = config.method?.toUpperCase();
  if (method && ['POST', 'PUT', 'DELETE', 'PATCH'].includes(method)) {
    const csrfToken = getEffectiveCsrfToken();
    if (csrfToken && config.headers) {
      config.headers['X-CSRF-Token'] = csrfToken;
    }
  }
  return config;
});

// Response interceptor: auto-refresh on 401 with loop protection
let isRefreshing = false;
let failedQueue: Array<{
  resolve: (value?: unknown) => void;
  reject: (reason?: unknown) => void;
}> = [];

const processQueue = (error: unknown) => {
  failedQueue.forEach((prom) => {
    if (error) {
      prom.reject(error);
    } else {
      prom.resolve();
    }
  });
  failedQueue = [];
};

apiClient.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const originalRequest = error.config as (InternalAxiosRequestConfig & { _retry?: boolean }) | undefined;

    const url = originalRequest?.url || '';
    const isAuthRoute =
      url.includes('/auth/login') ||
      url.includes('/auth/register') ||
      url.includes('/auth/refresh') ||
      url.includes('/auth/logout');

    if (error.response?.status === 401 && !isAuthRoute && originalRequest && !originalRequest._retry) {
      if (isRefreshing) {
        return new Promise((resolve, reject) => {
          failedQueue.push({ resolve, reject });
        })
          .then(() => apiClient(originalRequest))
          .catch((err) => Promise.reject(err));
      }

      originalRequest._retry = true;
      isRefreshing = true;

      try {
        const refreshRes = await axios.post<{ message: string; csrf_token?: string }>(
          `${API_BASE_URL}/auth/refresh`,
          {},
          { withCredentials: true }
        );
        if (refreshRes.data?.csrf_token) {
          setCsrfToken(refreshRes.data.csrf_token);
        }
        processQueue(null);
        return apiClient(originalRequest);
      } catch (refreshErr) {
        processQueue(refreshErr);
        notifySessionExpired();
        return Promise.reject(refreshErr);
      } finally {
        isRefreshing = false;
      }
    }

    return Promise.reject(error);
  }
);

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
        return detail || 'Unauthorized: Please log in to continue.';
      }
      if (status === 403) {
        return detail || 'Forbidden: Insufficient permissions for this operation.';
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
