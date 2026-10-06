import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TraceComparisonView } from '../components/traces/TraceComparisonView';
import { TraceComparisonResult } from '../types/comparison';
import { TraceSummary } from '../types/trace';

describe('TraceComparisonView Component (Phase 14 Replay / Comparison)', () => {
  const mockTraces: TraceSummary[] = [
    {
      trace_id: 'trace-a-123',
      name: 'Agent Run A',
      project_name: 'ProjectAlpha',
      status: 'completed',
      start_time: '2026-01-01T12:00:00Z',
      end_time: '2026-01-01T12:00:02Z',
      duration_ms: 2000,
      event_count: 4,
    },
    {
      trace_id: 'trace-b-456',
      name: 'Agent Run B',
      project_name: 'ProjectAlpha',
      status: 'failed',
      start_time: '2026-01-01T12:05:00Z',
      end_time: '2026-01-01T12:05:05Z',
      duration_ms: 5000,
      event_count: 6,
    },
  ];

  const mockComparison: TraceComparisonResult = {
    trace_a: {
      trace_id: 'trace-a-123',
      name: 'Agent Run A',
      project_name: 'ProjectAlpha',
      status: 'completed',
      start_time: '2026-01-01T12:00:00Z',
      end_time: '2026-01-01T12:00:02Z',
      duration_ms: 2000,
      event_count: 4,
      event_type_counts: { AGENT_START: 1, LLM_CALL: 1, TOOL_CALL: 1, AGENT_END: 1 },
      findings_count: 0,
      findings_severity_counts: {},
      is_complete: true,
      has_agent_start: true,
      has_agent_end: true,
    },
    trace_b: {
      trace_id: 'trace-b-456',
      name: 'Agent Run B',
      project_name: 'ProjectAlpha',
      status: 'failed',
      start_time: '2026-01-01T12:05:00Z',
      end_time: '2026-01-01T12:05:05Z',
      duration_ms: 5000,
      event_count: 6,
      event_type_counts: { AGENT_START: 1, LLM_CALL: 1, TOOL_CALL: 1, ERROR: 1, RETRY: 1, AGENT_END: 1 },
      findings_count: 1,
      findings_severity_counts: { error: 1 },
      is_complete: true,
      has_agent_start: true,
      has_agent_end: true,
    },
    differences: {
      duration_diff_ms: 3000,
      event_count_diff: 2,
      status_changed: true,
      status_a: 'completed',
      status_b: 'failed',
      findings_count_diff: 1,
      event_type_diffs: { ERROR: 1, RETRY: 1 },
    },
    sequence_comparison: [
      {
        step_index: 1,
        status: 'matched',
        event_a: {
          event_id: 'ea-1',
          trace_id: 'trace-a-123',
          event_type: 'AGENT_START',
          timestamp: '2026-01-01T12:00:00Z',
          duration_ms: null,
          depth: 0,
          parent_event_id: null,
          agent_name: 'Agent Run A',
          data: { role: 'assistant' },
          metadata: {},
        },
        event_b: {
          event_id: 'eb-1',
          trace_id: 'trace-b-456',
          event_type: 'AGENT_START',
          timestamp: '2026-01-01T12:05:00Z',
          duration_ms: null,
          depth: 0,
          parent_event_id: null,
          agent_name: 'Agent Run B',
          data: { role: 'assistant' },
          metadata: {},
        },
        duration_diff_ms: null,
        change_summary: 'Matched AGENT_START',
      },
      {
        step_index: 2,
        status: 'matched',
        event_a: {
          event_id: 'ea-2',
          trace_id: 'trace-a-123',
          event_type: 'LLM_CALL',
          timestamp: '2026-01-01T12:00:01Z',
          duration_ms: 400,
          depth: 1,
          parent_event_id: 'ea-1',
          agent_name: 'Agent Run A',
          data: { model: 'gpt-4o' },
          metadata: {},
        },
        event_b: {
          event_id: 'eb-2',
          trace_id: 'trace-b-456',
          event_type: 'LLM_CALL',
          timestamp: '2026-01-01T12:05:01Z',
          duration_ms: 950,
          depth: 1,
          parent_event_id: 'eb-1',
          agent_name: 'Agent Run B',
          data: { model: 'gpt-4o' },
          metadata: {},
        },
        duration_diff_ms: 550,
        change_summary: 'Matched LLM_CALL (+550.0ms)',
      },
      {
        step_index: 3,
        status: 'only_b',
        event_a: null,
        event_b: {
          event_id: 'eb-err',
          trace_id: 'trace-b-456',
          event_type: 'ERROR',
          timestamp: '2026-01-01T12:05:02Z',
          duration_ms: null,
          depth: 1,
          parent_event_id: 'eb-1',
          agent_name: 'Agent Run B',
          data: { error_type: 'TimeoutError', message: 'API Gateway Timeout' },
          metadata: {},
        },
        duration_diff_ms: null,
        change_summary: 'Event only in Run B: ERROR',
      },
    ],
    findings_comparison: {
      findings_only_a: [],
      findings_only_b: [
        {
          finding_id: 'finding-err-1',
          trace_id: 'trace-b-456',
          rule: 'explicit_error',
          category: 'explicit_error' as any,
          severity: 'error' as any,
          message: 'Explicit ERROR event detected in execution trace',
          evidence_event_ids: ['eb-err'],
          evidence: {},
          detected_at: '2026-01-01T12:05:06Z',
        },
      ],
      common_findings: [],
      findings_count_diff: 1,
    },
  };

  it('renders trace selection dropdowns and disables compare button until valid selection', () => {
    const handleCompare = vi.fn();
    const handleSelectA = vi.fn();
    const handleSelectB = vi.fn();

    const { rerender } = render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={null}
        isLoading={false}
        error={null}
        selectedTraceAId={null}
        selectedTraceBId={null}
        onSelectTraceA={handleSelectA}
        onSelectTraceB={handleSelectB}
        onCompare={handleCompare}
        onRetry={vi.fn()}
      />
    );

    const compareBtn = screen.getByTestId('compare-runs-btn');
    expect(compareBtn).toBeDisabled();

    // Select Trace A
    const selectA = screen.getByTestId('select-trace-a');
    fireEvent.change(selectA, { target: { value: 'trace-a-123' } });
    expect(handleSelectA).toHaveBeenCalledWith('trace-a-123');

    // Rerender with identical A and B
    rerender(
      <TraceComparisonView
        traces={mockTraces}
        comparison={null}
        isLoading={false}
        error={null}
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-a-123"
        onSelectTraceA={handleSelectA}
        onSelectTraceB={handleSelectB}
        onCompare={handleCompare}
        onRetry={vi.fn()}
      />
    );

    // Should be disabled because trace A === trace B
    expect(screen.getByTestId('compare-runs-btn')).toBeDisabled();
    expect(screen.getByText(/Trace A and Trace B are identical/i)).toBeInTheDocument();

    // Rerender with distinct valid selection
    rerender(
      <TraceComparisonView
        traces={mockTraces}
        comparison={null}
        isLoading={false}
        error={null}
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-b-456"
        onSelectTraceA={handleSelectA}
        onSelectTraceB={handleSelectB}
        onCompare={handleCompare}
        onRetry={vi.fn()}
      />
    );

    const activeCompareBtn = screen.getByTestId('compare-runs-btn');
    expect(activeCompareBtn).not.toBeDisabled();
    fireEvent.click(activeCompareBtn);
    expect(handleCompare).toHaveBeenCalledTimes(1);
  });

  it('renders swap button and swaps Trace A and Trace B', () => {
    const handleSelectA = vi.fn();
    const handleSelectB = vi.fn();

    render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={null}
        isLoading={false}
        error={null}
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-b-456"
        onSelectTraceA={handleSelectA}
        onSelectTraceB={handleSelectB}
        onCompare={vi.fn()}
        onRetry={vi.fn()}
      />
    );

    const swapBtn = screen.getByTestId('swap-traces-btn');
    fireEvent.click(swapBtn);
    expect(handleSelectA).toHaveBeenCalledWith('trace-b-456');
    expect(handleSelectB).toHaveBeenCalledWith('trace-a-123');
  });

  it('renders high-level differences and side-by-side run cards', () => {
    render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={mockComparison}
        isLoading={false}
        error={null}
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-b-456"
        onSelectTraceA={vi.fn()}
        onSelectTraceB={vi.fn()}
        onCompare={vi.fn()}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByTestId('high-level-differences')).toBeInTheDocument();
    expect(screen.getByText(/Status Changed: completed → failed/i)).toBeInTheDocument();
    expect(screen.getByText('+3.00 s')).toBeInTheDocument();
    expect(screen.getByText('+2 events')).toBeInTheDocument();
    expect(screen.getByText('+1 findings')).toBeInTheDocument();

    // Verify run cards
    expect(screen.getByText('Run A (Baseline)')).toBeInTheDocument();
    expect(screen.getByText('Run B (Comparison)')).toBeInTheDocument();
  });

  it('renders execution sequence replay steps and handles step filtering', () => {
    render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={mockComparison}
        isLoading={false}
        error={null}
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-b-456"
        onSelectTraceA={vi.fn()}
        onSelectTraceB={vi.fn()}
        onCompare={vi.fn()}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByTestId('execution-sequence-comparison')).toBeInTheDocument();
    expect(screen.getByTestId('replay-step-1')).toBeInTheDocument();
    expect(screen.getByTestId('replay-step-2')).toBeInTheDocument();
    expect(screen.getByTestId('replay-step-3')).toBeInTheDocument();

    expect(screen.getAllByText('MATCHED').length).toBe(2);
    expect(screen.getByText('RUN B ONLY')).toBeInTheDocument();
    expect(screen.getByText('+550ms')).toBeInTheDocument();

    // Filter to Differences Only
    const diffsBtn = screen.getByText('Differences Only');
    fireEvent.click(diffsBtn);
    expect(screen.getByTestId('replay-step-2')).toBeInTheDocument(); // has +550ms duration diff
    expect(screen.getByTestId('replay-step-3')).toBeInTheDocument(); // is only_b
  });

  it('opens event payload modal when clicking an event button and closes on request', () => {
    render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={mockComparison}
        isLoading={false}
        error={null}
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-b-456"
        onSelectTraceA={vi.fn()}
        onSelectTraceB={vi.fn()}
        onCompare={vi.fn()}
        onRetry={vi.fn()}
      />
    );

    // Click Run B ERROR event
    const errBtn = screen.getByText('ID: eb-err');
    fireEvent.click(errBtn);

    const modal = screen.getByTestId('inspected-event-modal');
    expect(modal).toBeInTheDocument();
    expect(screen.getByText(/TimeoutError/i)).toBeInTheDocument();

    // Close modal
    const closeBtn = screen.getByText('Close');
    fireEvent.click(closeBtn);
    expect(screen.queryByTestId('inspected-event-modal')).not.toBeInTheDocument();
  });

  it('renders deterministic findings comparison accurately', () => {
    render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={mockComparison}
        isLoading={false}
        error={null}
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-b-456"
        onSelectTraceA={vi.fn()}
        onSelectTraceB={vi.fn()}
        onCompare={vi.fn()}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByTestId('findings-comparison-section')).toBeInTheDocument();
    expect(screen.getByText('Unique to Run B (1)')).toBeInTheDocument();
    expect(screen.getByText('explicit_error')).toBeInTheDocument();
    expect(screen.getByText('Explicit ERROR event detected in execution trace')).toBeInTheDocument();
  });

  it('renders loading state clearly', () => {
    render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={null}
        isLoading={true}
        error={null}
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-b-456"
        onSelectTraceA={vi.fn()}
        onSelectTraceB={vi.fn()}
        onCompare={vi.fn()}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByTestId('comparison-loading')).toBeInTheDocument();
    expect(screen.getByText(/Comparing Traces & Replaying Execution/i)).toBeInTheDocument();
  });

  it('renders error state with actionable retry button', () => {
    const handleRetry = vi.fn();
    render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={null}
        isLoading={false}
        error="Trace 'trace-b-456' not found in database"
        selectedTraceAId="trace-a-123"
        selectedTraceBId="trace-b-456"
        onSelectTraceA={vi.fn()}
        onSelectTraceB={vi.fn()}
        onCompare={vi.fn()}
        onRetry={handleRetry}
      />
    );

    expect(screen.getByTestId('comparison-error')).toBeInTheDocument();
    expect(screen.getByText(/Trace 'trace-b-456' not found in database/i)).toBeInTheDocument();

    const retryBtn = screen.getByText('Retry');
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalled();
  });

  it('handles optional and missing fields safely without crashing', () => {
    const minimalComparison: TraceComparisonResult = {
      trace_a: {
        trace_id: 't-min-a',
        name: 'Min A',
        project_name: null,
        status: 'running',
        start_time: '2026-01-01T00:00:00Z',
        end_time: null,
        duration_ms: null,
        event_count: 0,
        event_type_counts: {},
        findings_count: 0,
        findings_severity_counts: {},
        is_complete: false,
        has_agent_start: false,
        has_agent_end: false,
      },
      trace_b: {
        trace_id: 't-min-b',
        name: 'Min B',
        project_name: null,
        status: 'running',
        start_time: '2026-01-01T00:00:00Z',
        end_time: null,
        duration_ms: null,
        event_count: 0,
        event_type_counts: {},
        findings_count: 0,
        findings_severity_counts: {},
        is_complete: false,
        has_agent_start: false,
        has_agent_end: false,
      },
      differences: {
        duration_diff_ms: null,
        event_count_diff: 0,
        status_changed: false,
        status_a: 'running',
        status_b: 'running',
        findings_count_diff: 0,
        event_type_diffs: {},
      },
      sequence_comparison: [],
      findings_comparison: {
        findings_only_a: [],
        findings_only_b: [],
        common_findings: [],
        findings_count_diff: 0,
      },
    };

    render(
      <TraceComparisonView
        traces={mockTraces}
        comparison={minimalComparison}
        isLoading={false}
        error={null}
        selectedTraceAId="t-min-a"
        selectedTraceBId="t-min-b"
        onSelectTraceA={vi.fn()}
        onSelectTraceB={vi.fn()}
        onCompare={vi.fn()}
        onRetry={vi.fn()}
      />
    );

    expect(screen.getByText('Min A')).toBeInTheDocument();
    expect(screen.getByText('Min B')).toBeInTheDocument();
    expect(screen.getByText(/No deterministic failure findings detected/i)).toBeInTheDocument();
  });
});
