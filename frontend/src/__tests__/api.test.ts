import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import axios from 'axios';
import {
  getTraces,
  getTrace,
  getTraceGraph,
  getTraceInvestigation,
  compareTraces,
  formatApiError,
  apiClient,
} from '../services/api';

describe('Frontend API Client & Error Handling', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('fetches trace summaries via getTraces', async () => {
    const mockData = [
      {
        trace_id: 't1',
        name: 'Agent 1',
        status: 'completed',
        start_time: '2026-01-01T00:00:00Z',
        end_time: '2026-01-01T00:00:02Z',
        duration_ms: 2000,
        event_count: 5,
        project_name: null,
      },
    ];

    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: mockData });

    const result = await getTraces('my-proj', 50, 0);
    expect(result).toEqual(mockData);
    expect(apiClient.get).toHaveBeenCalledWith('/traces', {
      params: { project: 'my-proj', limit: 50, offset: 0 },
    });
  });

  it('fetches reconstructed trace via getTrace', async () => {
    const mockTrace = {
      trace_id: 't_abc',
      name: 'Agent ABC',
      start_time: '2026-01-01T00:00:00Z',
      status: 'completed',
      metadata: { total_event_count: 1 },
      events: [],
      root_event_ids: [],
    };

    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: mockTrace });

    const result = await getTrace('t_abc');
    expect(result).toEqual(mockTrace);
    expect(apiClient.get).toHaveBeenCalledWith('/traces/t_abc');
  });

  it('fetches execution graph via getTraceGraph', async () => {
    const mockGraph = {
      trace_id: 't_abc',
      nodes: [],
      edges: [],
      node_count: 0,
      edge_count: 0,
    };

    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: mockGraph });

    const result = await getTraceGraph('t_abc');
    expect(result).toEqual(mockGraph);
    expect(apiClient.get).toHaveBeenCalledWith('/traces/t_abc/graph');
  });

  it('fetches AI root-cause investigation via getTraceInvestigation', async () => {
    const mockInvestigation = {
      investigation_id: 'inv-123',
      trace_id: 't_abc',
      status: 'investigated',
      summary: 'Tool failure caused crash',
      root_cause: {
        description: 'Payment timeout',
        event_id: 'ev-1',
        finding_id: 'f-1',
        confidence: 0.95,
        reasoning: 'API did not respond',
      },
      first_failure_event_id: 'ev-1',
      confidence: 0.95,
      evidence: [],
      downstream_effects: [],
      recommended_actions: [],
      analyzed_findings: [],
      analyzed_event_ids: [],
      model: 'groq:llama-3.3-70b-versatile',
      created_at: '2026-01-01T00:00:00Z',
    };

    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: mockInvestigation });

    const result = await getTraceInvestigation('t_abc');
    expect(result).toEqual(mockInvestigation);
    expect(apiClient.get).toHaveBeenCalledWith('/traces/t_abc/investigation');
  });

  it('fetches side-by-side run comparison via compareTraces', async () => {
    const mockComparison = {
      trace_a: { trace_id: 't_a', name: 'Agent A' },
      trace_b: { trace_id: 't_b', name: 'Agent B' },
      differences: { duration_diff_ms: 100, event_count_diff: 1 },
      sequence_comparison: [],
      findings_comparison: { findings_only_a: [], findings_only_b: [], common_findings: [], findings_count_diff: 0 },
    };

    vi.spyOn(apiClient, 'get').mockResolvedValueOnce({ data: mockComparison });

    const result = await compareTraces('t_a', 't_b');
    expect(result).toEqual(mockComparison);
    expect(apiClient.get).toHaveBeenCalledWith('/traces/compare', {
      params: { trace_a: 't_a', trace_b: 't_b' },
    });
  });

  describe('formatApiError function', () => {
    it('formats 401 Unauthorized properly', () => {
      const error = new axios.AxiosError('Unauthorized');
      error.response = {
        status: 401,
        statusText: 'Unauthorized',
        data: { detail: 'Missing API key' },
        headers: {},
        config: {} as any,
      };

      const msg = formatApiError(error);
      expect(msg).toBe('Missing API key');
    });

    it('formats 404 Not Found properly', () => {
      const error = new axios.AxiosError('Not Found');
      error.response = {
        status: 404,
        statusText: 'Not Found',
        data: { detail: "Trace 'tr_123' not found" },
        headers: {},
        config: {} as any,
      };

      const msg = formatApiError(error);
      expect(msg).toBe("Trace 'tr_123' not found");
    });

    it('formats 500 Server Error properly', () => {
      const error = new axios.AxiosError('Server Error');
      error.response = {
        status: 500,
        statusText: 'Internal Server Error',
        data: { detail: 'Database connection failed' },
        headers: {},
        config: {} as any,
      };

      const msg = formatApiError(error);
      expect(msg).toBe('Database connection failed');
    });

    it('handles network connection error cleanly', () => {
      const error = new axios.AxiosError('Network Error');
      error.request = {}; // request sent but no response

      const msg = formatApiError(error);
      expect(msg).toContain('Cannot connect to AgentLens backend');
    });
  });
});
