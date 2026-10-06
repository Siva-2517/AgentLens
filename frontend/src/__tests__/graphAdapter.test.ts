import { describe, it, expect } from 'vitest';
import { transformGraphToFlow } from '../utils/graphAdapter';
import { ExecutionGraph } from '../types/trace';

describe('ExecutionGraph -> React Flow Adapter', () => {
  const mockGraph: ExecutionGraph = {
    trace_id: 'trace_test_1',
    node_count: 3,
    edge_count: 2,
    nodes: [
      {
        id: 'evt_1',
        event_id: 'evt_1',
        trace_id: 'trace_test_1',
        event_type: 'AGENT_START',
        label: 'Agent Start',
        timestamp: '2026-01-01T12:00:00Z',
        parent_event_id: null,
        depth: 0,
        duration_ms: null,
        status: null,
        data: { input: 'hello' },
        metadata: {},
      },
      {
        id: 'evt_2',
        event_id: 'evt_2',
        trace_id: 'trace_test_1',
        event_type: 'LLM_CALL',
        label: 'LLM Call',
        timestamp: '2026-01-01T12:00:01Z',
        parent_event_id: 'evt_1',
        depth: 1,
        duration_ms: 450,
        status: null,
        data: { prompt: 'generate code' },
        metadata: {},
      },
      {
        id: 'evt_3',
        event_id: 'evt_3',
        trace_id: 'trace_test_1',
        event_type: 'CUSTOM_UNKNOWN_TYPE',
        label: 'Custom Step',
        timestamp: '2026-01-01T12:00:02Z',
        parent_event_id: 'evt_2',
        depth: 2,
        duration_ms: null,
        status: 'ok',
        data: {},
        metadata: {},
      },
    ],
    edges: [
      {
        id: 'edge_evt_1_evt_2',
        source: 'evt_1',
        target: 'evt_2',
        relationship: 'parent-child',
      },
      {
        id: 'edge_evt_2_evt_3',
        source: 'evt_2',
        target: 'evt_3',
        relationship: 'parent-child',
      },
    ],
  };

  it('transforms backend nodes into React Flow nodes with deterministic layout', () => {
    const { nodes, edges } = transformGraphToFlow(mockGraph, null);

    expect(nodes).toHaveLength(3);
    expect(edges).toHaveLength(2);

    // Node 0: depth 0, index 0
    expect(nodes[0].id).toBe('evt_1');
    expect(nodes[0].position.x).toBe(40);
    expect(nodes[0].position.y).toBe(40);
    expect(nodes[0].data.isSelected).toBe(false);

    // Node 1: depth 1, index 1
    expect(nodes[1].id).toBe('evt_2');
    expect(nodes[1].position.x).toBe(40 + 200); // 240
    expect(nodes[1].position.y).toBe(40 + 125); // 165

    // Node 2: depth 2, index 2
    expect(nodes[2].id).toBe('evt_3');
    expect(nodes[2].position.x).toBe(40 + 400); // 440
    expect(nodes[2].position.y).toBe(40 + 250); // 290
  });

  it('correctly marks selected node and highlights adjacent edges', () => {
    const { nodes, edges } = transformGraphToFlow(mockGraph, 'evt_2');

    expect(nodes[1].data.isSelected).toBe(true);
    expect(nodes[0].data.isSelected).toBe(false);

    // Both edges touch evt_2 (as target or source)
    expect(edges[0].animated).toBe(true);
    expect(edges[1].animated).toBe(true);
  });

  it('handles empty graph safely', () => {
    const emptyGraph: ExecutionGraph = {
      trace_id: 'empty',
      node_count: 0,
      edge_count: 0,
      nodes: [],
      edges: [],
    };

    const { nodes, edges } = transformGraphToFlow(emptyGraph, null);
    expect(nodes).toEqual([]);
    expect(edges).toEqual([]);
  });
});
