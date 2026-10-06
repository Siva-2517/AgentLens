import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, act } from '@testing-library/react';
import { App } from '../App';
import * as api from '../services/api';
import { ReconstructedTrace, ExecutionGraph, TraceSummary } from '../types/trace';

// Mock API module
vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    getTraces: vi.fn(),
    getTrace: vi.fn(),
    getTraceGraph: vi.fn(),
  };
});

describe('Real-Time Updates in App Dashboard', () => {
  const mockTraces: TraceSummary[] = [
    {
      trace_id: 'live_tr_1',
      name: 'Realtime Agent',
      project_name: 'LiveTest',
      status: 'running',
      start_time: '2026-01-01T10:00:00Z',
      end_time: null,
      duration_ms: null,
      event_count: 1,
    },
  ];

  const mockTrace: ReconstructedTrace = {
    trace_id: 'live_tr_1',
    name: 'Realtime Agent',
    project_name: 'LiveTest',
    start_time: '2026-01-01T10:00:00Z',
    end_time: null,
    status: 'running',
    duration_ms: null,
    event_count: 1,
    events: [
      {
        event_id: 'evt_start',
        trace_id: 'live_tr_1',
        parent_event_id: null,
        event_type: 'AGENT_START',
        timestamp: '2026-01-01T10:00:00Z',
        agent_name: 'Realtime Agent',
        data: {},
        metadata: {},
        depth: 0,
        children_ids: [],
        duration_ms: null,
      },
    ],
    root_event_ids: ['evt_start'],
    metadata: {
      total_event_count: 1,
      duration_ms: null,
      llm_call_count: 0,
      llm_response_count: 0,
      tool_call_count: 0,
      tool_response_count: 0,
      error_count: 0,
      retry_count: 0,
      state_change_count: 0,
      first_event_timestamp: '2026-01-01T10:00:00Z',
      last_event_timestamp: '2026-01-01T10:00:00Z',
      has_agent_start: true,
      has_agent_end: false,
      is_complete: false,
      event_type_counts: { AGENT_START: 1 },
    },
  };

  const mockGraph: ExecutionGraph = {
    trace_id: 'live_tr_1',
    node_count: 1,
    edge_count: 0,
    nodes: [
      {
        id: 'evt_start',
        event_id: 'evt_start',
        trace_id: 'live_tr_1',
        event_type: 'AGENT_START',
        label: 'Agent Start',
        timestamp: '2026-01-01T10:00:00Z',
        parent_event_id: null,
        depth: 0,
        duration_ms: null,
        status: null,
        data: {},
        metadata: {},
      },
    ],
    edges: [],
  };

  beforeEach(() => {
    vi.mocked(api.getTraces).mockResolvedValue(mockTraces);
    vi.mocked(api.getTrace).mockResolvedValue(mockTrace);
    vi.mocked(api.getTraceGraph).mockResolvedValue(mockGraph);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders initial trace snapshot with live connection indicator', async () => {
    await act(async () => {
      render(<App />);
    });

    expect(screen.getAllByText('Realtime Agent').length).toBeGreaterThan(0);
    expect(screen.getAllByText(/project: LiveTest/i).length).toBeGreaterThan(0);
    // Live indicator pill present
    expect(screen.getByText(/^(Live|Connecting\.\.\.|Offline)$/)).toBeInTheDocument();
  });
});
