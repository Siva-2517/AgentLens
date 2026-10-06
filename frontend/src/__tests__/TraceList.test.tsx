import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { TraceList } from '../components/traces/TraceList';
import { TraceSummary } from '../types/trace';

describe('TraceList Component', () => {
  const mockTraces: TraceSummary[] = [
    {
      trace_id: 'trace_001',
      name: 'Agent Alpha',
      project_name: 'Core',
      status: 'completed',
      start_time: '2026-01-01T10:00:00Z',
      end_time: '2026-01-01T10:00:05Z',
      duration_ms: 5000,
      event_count: 7,
    },
    {
      trace_id: 'trace_002',
      name: 'Agent Beta',
      project_name: 'Core',
      status: 'failed',
      start_time: '2026-01-01T11:00:00Z',
      end_time: '2026-01-01T11:00:02Z',
      duration_ms: 2000,
      event_count: 3,
    },
  ];

  it('renders trace list correctly', () => {
    render(
      <TraceList
        traces={mockTraces}
        selectedTraceId={null}
        onSelectTrace={vi.fn()}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText('Agent Alpha')).toBeInTheDocument();
    expect(screen.getByText('Agent Beta')).toBeInTheDocument();
    expect(screen.getByText('trace_001')).toBeInTheDocument();
    expect(screen.getByText('trace_002')).toBeInTheDocument();
    expect(screen.getAllByText('completed').length).toBeGreaterThan(0);
    expect(screen.getAllByText('failed').length).toBeGreaterThan(0);
  });

  it('renders loading state when traces list is empty and loading', () => {
    render(
      <TraceList
        traces={[]}
        selectedTraceId={null}
        onSelectTrace={vi.fn()}
        isLoading={true}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText(/Loading traces.../i)).toBeInTheDocument();
  });

  it('renders empty trace list state', () => {
    render(
      <TraceList
        traces={[]}
        selectedTraceId={null}
        onSelectTrace={vi.fn()}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    expect(screen.getByText(/No traces recorded yet in AgentLens./i)).toBeInTheDocument();
  });

  it('handles trace selection callback', () => {
    const onSelectMock = vi.fn();
    render(
      <TraceList
        traces={mockTraces}
        selectedTraceId="trace_001"
        onSelectTrace={onSelectMock}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    fireEvent.click(screen.getByText('Agent Beta'));
    expect(onSelectMock).toHaveBeenCalledWith('trace_002');
  });

  it('filters traces by search query', () => {
    render(
      <TraceList
        traces={mockTraces}
        selectedTraceId={null}
        onSelectTrace={vi.fn()}
        isLoading={false}
        error={null}
        onRefresh={vi.fn()}
      />
    );

    const searchInput = screen.getByPlaceholderText(/Search by ID or name.../i);
    fireEvent.change(searchInput, { target: { value: 'Beta' } });

    expect(screen.queryByText('Agent Alpha')).not.toBeInTheDocument();
    expect(screen.getByText('Agent Beta')).toBeInTheDocument();
  });
});
