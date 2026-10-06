import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { HistoricalSearchView } from '../components/traces/HistoricalSearchView';
import { TraceOverview } from '../components/traces/TraceOverview';
import * as api from '../services/api';
import { HistoricalSearchResponse, TraceIndexingResponse } from '../types/failureSearch';
import { ReconstructedTrace } from '../types/trace';

vi.mock('../services/api', () => ({
  searchHistoricalFailures: vi.fn(),
  indexTraceFailures: vi.fn(),
  formatApiError: vi.fn((err: any) => err?.message || 'Error occurred'),
}));

describe('Historical Failure Search (Phase 15 pgvector)', () => {
  const mockSearchResult: HistoricalSearchResponse = {
    query: 'payment card declined',
    total_results: 1,
    results: [
      {
        trace_id: 'trace-pay-99',
        finding_id: 'find-card-fail',
        rule: 'explicit_error',
        category: 'explicit_error',
        severity: 'error',
        message: 'Stripe card declined after 3 attempts',
        searchable_text: 'Trace context: Stripe card declined...',
        similarity: 0.8954,
        trace_name: 'PaymentCheckoutAgent',
        project_name: 'BillingService',
        created_at: '2026-01-01T12:00:00Z',
        evidence_event_ids: ['ev-err-1', 'ev-err-2'],
        metadata: {},
      },
    ],
  };

  const mockTrace: ReconstructedTrace = {
    trace_id: 'trace-pay-99',
    name: 'PaymentCheckoutAgent',
    project_name: 'BillingService',
    start_time: '2026-01-01T12:00:00Z',
    end_time: '2026-01-01T12:00:05Z',
    duration_ms: 5000,
    status: 'failed',
    event_count: 6,
    metadata: {
      total_event_count: 6,
      duration_ms: 5000,
      llm_call_count: 1,
      llm_response_count: 1,
      tool_call_count: 1,
      tool_response_count: 1,
      error_count: 1,
      retry_count: 1,
      state_change_count: 0,
      first_event_timestamp: '2026-01-01T12:00:00Z',
      last_event_timestamp: '2026-01-01T12:00:05Z',
      is_complete: true,
      has_agent_start: true,
      has_agent_end: true,
      event_type_counts: {},
    },
    events: [],
    root_event_ids: [],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('renders initial welcome state and suggestion pills', () => {
    const onSelect = vi.fn();
    render(<HistoricalSearchView onSelectTrace={onSelect} />);

    expect(screen.getByText('Historical Failure Search')).toBeInTheDocument();
    expect(screen.getByText('Query Historical Agent Failures')).toBeInTheDocument();
    expect(screen.getByTestId('failure-search-input')).toBeInTheDocument();
    expect(screen.getByTestId('failure-search-button')).toBeInTheDocument();
  });

  it('executes search and displays ranked results with similarity score (not labeled confidence)', async () => {
    vi.mocked(api.searchHistoricalFailures).mockResolvedValueOnce(mockSearchResult);
    const onSelect = vi.fn();
    render(<HistoricalSearchView onSelectTrace={onSelect} />);

    const input = screen.getByTestId('failure-search-input');
    fireEvent.change(input, { target: { value: 'payment card declined' } });

    const searchBtn = screen.getByTestId('failure-search-button');
    fireEvent.click(searchBtn);

    await waitFor(() => {
      expect(api.searchHistoricalFailures).toHaveBeenCalledWith({
        q: 'payment card declined',
        severity: undefined,
        rule: undefined,
        project: undefined,
        limit: 20,
      });
    });

    // Check result card is rendered
    expect(await screen.findByText('PaymentCheckoutAgent')).toBeInTheDocument();
    expect(screen.getByText('Stripe card declined after 3 attempts')).toBeInTheDocument();
    expect(screen.getByText('explicit_error')).toBeInTheDocument();
    expect(screen.getByText('BillingService')).toBeInTheDocument();

    // Verify similarity score label explicitly says "Similarity: 0.895" and NOT "Confidence"
    expect(screen.getByText('Similarity:')).toBeInTheDocument();
    expect(screen.getByText('0.895')).toBeInTheDocument();
    expect(screen.queryByText(/Confidence:/i)).not.toBeInTheDocument();
  });

  it('navigates to trace when clicking Inspect Trace button', async () => {
    vi.mocked(api.searchHistoricalFailures).mockResolvedValueOnce(mockSearchResult);
    const onSelect = vi.fn();
    render(<HistoricalSearchView onSelectTrace={onSelect} />);

    const input = screen.getByTestId('failure-search-input');
    fireEvent.change(input, { target: { value: 'payment card declined' } });
    fireEvent.click(screen.getByTestId('failure-search-button'));

    const inspectBtn = await screen.findByTestId('view-trace-button');
    fireEvent.click(inspectBtn);

    expect(onSelect).toHaveBeenCalledWith('trace-pay-99', 'find-card-fail');
  });

  it('applies filters (severity, rule, project) to the search request', async () => {
    vi.mocked(api.searchHistoricalFailures).mockResolvedValueOnce(mockSearchResult);
    render(<HistoricalSearchView onSelectTrace={vi.fn()} />);

    // Type query
    fireEvent.change(screen.getByTestId('failure-search-input'), {
      target: { value: 'retry failure' },
    });

    // Select severity
    fireEvent.change(screen.getByTestId('filter-severity'), {
      target: { value: 'critical' },
    });

    // Type rule
    fireEvent.change(screen.getByTestId('filter-rule'), {
      target: { value: 'retry_exhaustion' },
    });

    // Type project
    fireEvent.change(screen.getByTestId('filter-project'), {
      target: { value: 'BillingService' },
    });

    fireEvent.click(screen.getByTestId('failure-search-button'));

    await waitFor(() => {
      expect(api.searchHistoricalFailures).toHaveBeenCalledWith({
        q: 'retry failure',
        severity: 'critical',
        rule: 'retry_exhaustion',
        project: 'BillingService',
        limit: 20,
      });
    });
  });

  it('renders no results found state', async () => {
    vi.mocked(api.searchHistoricalFailures).mockResolvedValueOnce({
      query: 'nonexistent problem',
      total_results: 0,
      results: [],
    });

    render(<HistoricalSearchView onSelectTrace={vi.fn()} />);

    fireEvent.change(screen.getByTestId('failure-search-input'), {
      target: { value: 'nonexistent problem' },
    });
    fireEvent.click(screen.getByTestId('failure-search-button'));

    expect(await screen.findByTestId('search-no-results')).toBeInTheDocument();
    expect(screen.getByText('No Matching Failures Found')).toBeInTheDocument();
  });

  it('renders error state and handles retry', async () => {
    vi.mocked(api.searchHistoricalFailures).mockRejectedValueOnce(
      new Error('Embedding provider connection failure')
    );

    render(<HistoricalSearchView onSelectTrace={vi.fn()} />);

    fireEvent.change(screen.getByTestId('failure-search-input'), {
      target: { value: 'test query' },
    });
    fireEvent.click(screen.getByTestId('failure-search-button'));

    expect(await screen.findByTestId('search-error-alert')).toBeInTheDocument();
    expect(screen.getByText('Embedding provider connection failure')).toBeInTheDocument();

    // Now mock success for retry
    vi.mocked(api.searchHistoricalFailures).mockResolvedValueOnce(mockSearchResult);
    const retryBtn = screen.getByText('Retry');
    fireEvent.click(retryBtn);

    expect(await screen.findByText('PaymentCheckoutAgent')).toBeInTheDocument();
  });

  it('toggles vector context expanded/collapsed', async () => {
    vi.mocked(api.searchHistoricalFailures).mockResolvedValueOnce(mockSearchResult);
    render(<HistoricalSearchView onSelectTrace={vi.fn()} />);

    fireEvent.change(screen.getByTestId('failure-search-input'), {
      target: { value: 'card' },
    });
    fireEvent.click(screen.getByTestId('failure-search-button'));

    const expandBtn = await screen.findByText('Expand full');
    fireEvent.click(expandBtn);
    expect(screen.getByText('Collapse')).toBeInTheDocument();
  });

  it('TraceOverview Index Failures button indexes trace successfully', async () => {
    const mockIndexResp: TraceIndexingResponse = {
      trace_id: 'trace-pay-99',
      indexed_count: 2,
      status: 'indexed',
      finding_ids: ['f1', 'f2'],
      message: 'Indexed 2 failures',
    };
    vi.mocked(api.indexTraceFailures).mockResolvedValueOnce(mockIndexResp);

    render(<TraceOverview trace={mockTrace} />);

    const indexBtn = screen.getByTestId('index-failures-btn');
    expect(indexBtn).toHaveTextContent('Index Failures');

    fireEvent.click(indexBtn);

    await waitFor(() => {
      expect(api.indexTraceFailures).toHaveBeenCalledWith('trace-pay-99');
    });

    expect(await screen.findByText('Indexed (2)')).toBeInTheDocument();
  });

  it('TraceOverview Index Failures shows Clean (0) when trace has no findings', async () => {
    const mockNoFindings: TraceIndexingResponse = {
      trace_id: 'trace-pay-99',
      indexed_count: 0,
      status: 'no_findings',
      finding_ids: [],
      message: 'Trace has no findings to index',
    };
    vi.mocked(api.indexTraceFailures).mockResolvedValueOnce(mockNoFindings);

    render(<TraceOverview trace={mockTrace} />);

    const indexBtn = screen.getByTestId('index-failures-btn');
    fireEvent.click(indexBtn);

    expect(await screen.findByText('Clean (0)')).toBeInTheDocument();
  });

  it('TraceOverview Index Failures shows Index Error when API rejects', async () => {
    vi.mocked(api.indexTraceFailures).mockRejectedValueOnce(new Error('Network error'));

    render(<TraceOverview trace={mockTrace} />);

    const indexBtn = screen.getByTestId('index-failures-btn');
    fireEvent.click(indexBtn);

    expect(await screen.findByText('Index Error')).toBeInTheDocument();
  });
});
