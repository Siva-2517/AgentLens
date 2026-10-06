import { describe, it, expect, vi } from 'vitest';
import { render, screen } from '@testing-library/react';
import { TraceGraph } from '../components/traces/TraceGraph';
import { ExecutionGraph } from '../types/trace';

describe('TraceGraph Component', () => {
  it('renders empty state when graph is null or empty', () => {
    render(
      <TraceGraph
        graph={null}
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        onClearSelection={vi.fn()}
      />
    );

    expect(screen.getByText(/No execution steps in graph/i)).toBeInTheDocument();
  });

  it('renders graph overlay with node and edge counts', () => {
    const mockGraph: ExecutionGraph = {
      trace_id: 'tr_test',
      node_count: 2,
      edge_count: 1,
      nodes: [
        {
          id: 'n1',
          event_id: 'n1',
          trace_id: 'tr_test',
          event_type: 'AGENT_START',
          label: 'Start Agent',
          timestamp: '2026-01-01T10:00:00Z',
          parent_event_id: null,
          depth: 0,
          duration_ms: null,
          status: null,
          data: {},
          metadata: {},
        },
        {
          id: 'n2',
          event_id: 'n2',
          trace_id: 'tr_test',
          event_type: 'AGENT_END',
          label: 'End Agent',
          timestamp: '2026-01-01T10:00:01Z',
          parent_event_id: 'n1',
          depth: 0,
          duration_ms: 1000,
          status: null,
          data: {},
          metadata: {},
        },
      ],
      edges: [
        {
          id: 'e1',
          source: 'n1',
          target: 'n2',
          relationship: 'parent-child',
        },
      ],
    };

    render(
      <TraceGraph
        graph={mockGraph}
        selectedNodeId={null}
        onSelectNode={vi.fn()}
        onClearSelection={vi.fn()}
      />
    );

    expect(screen.getByText('2 nodes')).toBeInTheDocument();
    expect(screen.getByText('1 edges')).toBeInTheDocument();
  });
});
