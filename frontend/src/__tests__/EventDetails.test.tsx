import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { EventDetails } from '../components/traces/EventDetails';
import { ExecutionGraphNode } from '../types/trace';

describe('EventDetails Component', () => {
  const mockNode: ExecutionGraphNode = {
    id: 'evt_node_100',
    event_id: 'evt_node_100',
    trace_id: 'trace_test_xyz',
    event_type: 'TOOL_CALL',
    label: 'Tool: search_database',
    timestamp: '2026-01-01T12:00:03.123Z',
    parent_event_id: 'evt_node_099',
    depth: 2,
    duration_ms: 320,
    status: 'success',
    data: {
      query: 'SELECT * FROM users',
      limit: 10,
    },
    metadata: {
      cached: false,
    },
  };

  it('renders event details properly', () => {
    const onCloseMock = vi.fn();
    render(<EventDetails node={mockNode} onClose={onCloseMock} />);

    expect(screen.getByText('Tool: search_database')).toBeInTheDocument();
    expect(screen.getByText('evt_node_100')).toBeInTheDocument();
    expect(screen.getByText('trace_test_xyz')).toBeInTheDocument();
    expect(screen.getByText('evt_node_099')).toBeInTheDocument();
    expect(screen.getByText('320 ms')).toBeInTheDocument();
    expect(screen.getByText('success')).toBeInTheDocument();

    // Check payload data presence
    expect(screen.getByText(/"query": "SELECT \* FROM users"/i)).toBeInTheDocument();
  });

  it('handles unknown event types gracefully', () => {
    const unknownNode: ExecutionGraphNode = {
      ...mockNode,
      event_type: 'CUSTOM_AGENT_HOOK',
      label: 'Custom Hook Triggered',
    };

    render(<EventDetails node={unknownNode} onClose={vi.fn()} />);
    expect(screen.getByText('Custom Hook Triggered')).toBeInTheDocument();
    expect(screen.getByText(/CUSTOM AGENT HOOK/i)).toBeInTheDocument();
  });

  it('allows switching between payload data, metadata, and raw view', () => {
    render(<EventDetails node={mockNode} onClose={vi.fn()} />);

    const metadataTab = screen.getByText(/Metadata \(1\)/i);
    fireEvent.click(metadataTab);
    expect(screen.getByText(/"cached": false/i)).toBeInTheDocument();

    const rawTab = screen.getByText(/Raw Node/i);
    fireEvent.click(rawTab);
    expect(screen.getByText(/"id": "evt_node_100"/i)).toBeInTheDocument();
  });

  it('fires close callback when close button is clicked', () => {
    const onCloseMock = vi.fn();
    render(<EventDetails node={mockNode} onClose={onCloseMock} />);

    const closeBtn = screen.getByLabelText(/Close event details/i);
    fireEvent.click(closeBtn);
    expect(onCloseMock).toHaveBeenCalled();
  });
});
