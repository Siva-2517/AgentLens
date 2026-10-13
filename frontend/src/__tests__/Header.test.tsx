import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { Header } from '../components/layout/Header';

describe('Header Component', () => {
  it('renders Header with Trace toggle button and triggers onToggleTraceList', () => {
    const onToggleMock = vi.fn();
    render(
      <Header
        apiStatus="healthy"
        selectedTraceId="trace_test_123"
        activeView="trace"
        isTraceListVisible={true}
        onToggleTraceList={onToggleMock}
      />
    );

    const toggleBtn = screen.getByTestId('toggle-traces-sidebar-btn');
    expect(toggleBtn).toBeInTheDocument();
    expect(toggleBtn).toHaveAttribute('title', 'Hide Traces Sidebar');

    fireEvent.click(toggleBtn);
    expect(onToggleMock).toHaveBeenCalledTimes(1);
  });

  it('reflects collapsed state in toggle button tooltip and styling', () => {
    render(
      <Header
        apiStatus="healthy"
        selectedTraceId={null}
        activeView="trace"
        isTraceListVisible={false}
        onToggleTraceList={vi.fn()}
      />
    );

    const toggleBtn = screen.getByTestId('toggle-traces-sidebar-btn');
    expect(toggleBtn).toHaveAttribute('title', 'Show Traces Sidebar');
  });

  it('does not render Traces toggle when onToggleTraceList is not provided or activeView is not trace', () => {
    const { rerender } = render(
      <Header
        apiStatus="healthy"
        selectedTraceId={null}
        activeView="trace"
      />
    );
    expect(screen.queryByTestId('toggle-traces-sidebar-btn')).not.toBeInTheDocument();

    rerender(
      <Header
        apiStatus="healthy"
        selectedTraceId={null}
        activeView="compare"
        onToggleTraceList={vi.fn()}
      />
    );
    expect(screen.queryByTestId('toggle-traces-sidebar-btn')).not.toBeInTheDocument();
  });
});
