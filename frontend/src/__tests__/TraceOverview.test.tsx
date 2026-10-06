import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TraceOverview } from '../components/traces/TraceOverview';
import { ReconstructedTrace } from '../types/trace';

describe('TraceOverview Component', () => {
  const mockTrace: ReconstructedTrace = {
    trace_id: 'trace_overview_123',
    name: 'Customer Support Agent',
    project_name: 'SupportService',
    status: 'completed',
    start_time: '2026-01-01T10:00:00Z',
    end_time: '2026-01-01T10:00:04Z',
    duration_ms: 4000,
    event_count: 5,
    events: [],
    root_event_ids: [],
    metadata: {
      total_event_count: 5,
      duration_ms: 4000,
      llm_call_count: 2,
      llm_response_count: 2,
      tool_call_count: 1,
      tool_response_count: 1,
      error_count: 0,
      retry_count: 1,
      state_change_count: 1,
      first_event_timestamp: '2026-01-01T10:00:00Z',
      last_event_timestamp: '2026-01-01T10:00:04Z',
      has_agent_start: true,
      has_agent_end: true,
      is_complete: true,
      event_type_counts: {
        AGENT_START: 1,
        LLM_CALL: 2,
        LLM_RESPONSE: 2,
        TOOL_CALL: 1,
        AGENT_END: 1,
      },
    },
  };

  it('renders trace overview and metadata metrics properly', () => {
    render(<TraceOverview trace={mockTrace} />);

    expect(screen.getByText('Customer Support Agent')).toBeInTheDocument();
    expect(screen.getByText('trace_overview_123')).toBeInTheDocument();
    expect(screen.getByText(/project: SupportService/i)).toBeInTheDocument();
    expect(screen.getByText('completed')).toBeInTheDocument();
    expect(screen.getByText('Complete')).toBeInTheDocument();

    // Check counts
    expect(screen.getByText('2')).toBeInTheDocument(); // LLM calls
    expect(screen.getAllByText('1').length).toBeGreaterThan(0); // Tool calls, retries, etc.
  });

  it('visually distinguishes failed status and errors', () => {
    const failedTrace: ReconstructedTrace = {
      ...mockTrace,
      status: 'failed',
      metadata: {
        ...mockTrace.metadata,
        error_count: 3,
        is_complete: false,
      },
    };

    render(<TraceOverview trace={failedTrace} />);
    expect(screen.getByText('failed')).toBeInTheDocument();
    expect(screen.getByText('3')).toBeInTheDocument();
    expect(screen.getByText('Incomplete')).toBeInTheDocument();
  });

  it('renders AI Investigation action button and handles toggle click', () => {
    const handleToggle = vi.fn();
    render(
      <TraceOverview
        trace={mockTrace}
        investigationStatus="investigated"
        investigationConfidence={0.88}
        isInvestigationOpen={false}
        onToggleInvestigation={handleToggle}
      />
    );

    const btn = screen.getByTestId('toggle-investigation-btn');
    expect(btn).toBeInTheDocument();
    expect(screen.getByText('AI Investigation')).toBeInTheDocument();

    fireEvent.click(btn);
    expect(handleToggle).toHaveBeenCalledTimes(1);
  });
});
