import { describe, it, expect, vi } from 'vitest';
import { render, screen, fireEvent } from '@testing-library/react';
import { InvestigationPanel } from '../components/traces/InvestigationPanel';
import { InvestigationResult } from '../types/investigation';

describe('InvestigationPanel Component', () => {
  const mockInvestigated: InvestigationResult = {
    investigation_id: 'inv-test-001',
    trace_id: 'trace-123',
    status: 'investigated',
    summary: 'The execution failed due to an unhandled 402 Card Declined response from Stripe tool.',
    root_cause: {
      description: 'Stripe API returned 402 Card Declined on event tc-payment',
      event_id: 'tc-payment',
      finding_id: 'finding-tool-err-1',
      confidence: 0.92,
      reasoning: 'The customer card had insufficient funds, triggering repeated retries that exhausted attempts.',
    },
    first_failure_event_id: 'tc-payment',
    confidence: 0.90,
    evidence: [
      {
        event_id: 'tc-payment',
        finding_id: 'finding-tool-err-1',
        description: 'Tool call failed with card decline.',
      },
      {
        event_id: 'retry-1',
        finding_id: null,
        description: 'First retry attempt failed with identical error.',
      },
    ],
    downstream_effects: [
      {
        event_id: 'err-terminal',
        description: 'Terminal unhandled error emitted after retry exhaustion.',
        impact: 'Aborted execution',
      },
    ],
    recommended_actions: [
      {
        action: 'Implement fallback payment prompt for customer before aborting.',
        related_event_ids: ['tc-payment', 'err-terminal'],
        priority: 'high',
      },
      {
        action: 'Increase webhook retry backoff timeout.',
        related_event_ids: [],
        priority: 'low',
      },
    ],
    analyzed_findings: ['finding-tool-err-1'],
    analyzed_event_ids: ['start', 'tc-payment', 'retry-1', 'err-terminal', 'end'],
    model: 'groq:llama-3.3-70b-versatile',
    created_at: '2026-10-04T12:00:00Z',
  };

  it('renders complete investigated result with root cause as primary visual focus', () => {
    const handleSelectEvent = vi.fn();
    render(
      <InvestigationPanel
        investigation={mockInvestigated}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        onSelectEventId={handleSelectEvent}
      />
    );

    // Header and model
    expect(screen.getByText('AI Root-Cause Investigation')).toBeInTheDocument();
    expect(screen.getByText('model: groq:llama-3.3-70b-versatile')).toBeInTheDocument();
    expect(screen.getByText('Investigated')).toBeInTheDocument();

    // Primary Root Cause Card
    const rootCauseCard = screen.getByTestId('root-cause-card');
    expect(rootCauseCard).toBeInTheDocument();
    expect(screen.getByText('Primary Root Cause')).toBeInTheDocument();
    expect(screen.getByText('Stripe API returned 402 Card Declined on event tc-payment')).toBeInTheDocument();
    expect(screen.getByText(/The customer card had insufficient funds/i)).toBeInTheDocument();
    expect(screen.getByText('Confidence:')).toBeInTheDocument();
    expect(screen.getByText('92%')).toBeInTheDocument();

    // Summary
    expect(screen.getByText(/The execution failed due to an unhandled 402 Card Declined/i)).toBeInTheDocument();

    // Evidence
    expect(screen.getByTestId('evidence-section')).toBeInTheDocument();
    expect(screen.getByText('Tool call failed with card decline.')).toBeInTheDocument();

    // Downstream effects
    expect(screen.getByTestId('downstream-effects-section')).toBeInTheDocument();
    expect(screen.getByText('Terminal unhandled error emitted after retry exhaustion.')).toBeInTheDocument();
    expect(screen.getByText('impact: Aborted execution')).toBeInTheDocument();

    // Recommended actions
    expect(screen.getByTestId('recommended-actions-section')).toBeInTheDocument();
    expect(screen.getByText('Implement fallback payment prompt for customer before aborting.')).toBeInTheDocument();
    expect(screen.getByText('High Priority')).toBeInTheDocument();
    expect(screen.getByText('Low Priority')).toBeInTheDocument();
  });

  it('triggers onSelectEventId when clicking event pills across root cause, evidence, downstream, and actions', () => {
    const handleSelectEvent = vi.fn();
    render(
      <InvestigationPanel
        investigation={mockInvestigated}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        onSelectEventId={handleSelectEvent}
      />
    );

    // Click root cause first failure event
    const firstFailBtns = screen.getAllByText('⚡ tc-payment');
    fireEvent.click(firstFailBtns[0]);
    expect(handleSelectEvent).toHaveBeenCalledWith('tc-payment');

    // Click downstream effect event
    const downstreamBtns = screen.getAllByText('⚡ err-terminal');
    fireEvent.click(downstreamBtns[0]);
    expect(handleSelectEvent).toHaveBeenCalledWith('err-terminal');

    // Click evidence event
    const retryBtns = screen.getAllByText('⚡ retry-1');
    fireEvent.click(retryBtns[0]);
    expect(handleSelectEvent).toHaveBeenCalledWith('retry-1');
  });

  it('renders loading state cleanly without crashing', () => {
    render(
      <InvestigationPanel
        investigation={null}
        isLoading={true}
        error={null}
        onRetry={vi.fn()}
        onSelectEventId={vi.fn()}
      />
    );

    expect(screen.getByTestId('investigation-loading')).toBeInTheDocument();
    expect(screen.getByText('Investigating Trace with AI...')).toBeInTheDocument();
  });

  it('renders error state with retry button', () => {
    const handleRetry = vi.fn();
    render(
      <InvestigationPanel
        investigation={null}
        isLoading={false}
        error="LLM provider gateway timed out"
        onRetry={handleRetry}
        onSelectEventId={vi.fn()}
      />
    );

    expect(screen.getByTestId('investigation-error')).toBeInTheDocument();
    expect(screen.getByText('LLM provider gateway timed out')).toBeInTheDocument();

    const retryBtn = screen.getByText('Retry Investigation');
    fireEvent.click(retryBtn);
    expect(handleRetry).toHaveBeenCalled();
  });

  it('renders no_issue_detected state with clear messaging and disclaimer', () => {
    const cleanInvestigation: InvestigationResult = {
      investigation_id: 'inv-clean',
      trace_id: 'trace-clean',
      status: 'no_issue_detected',
      summary: 'Trace completed with zero detected errors or anomalies.',
      root_cause: null,
      first_failure_event_id: null,
      confidence: 1.0,
      evidence: [],
      downstream_effects: [],
      recommended_actions: [],
      analyzed_findings: [],
      analyzed_event_ids: ['start', 'llm', 'end'],
      model: 'deterministic:no_findings',
      created_at: '2026-10-04T12:00:00Z',
    };

    render(
      <InvestigationPanel
        investigation={cleanInvestigation}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        onSelectEventId={vi.fn()}
      />
    );

    expect(screen.getByTestId('investigation-no-issue')).toBeInTheDocument();
    expect(screen.getByText('No Issue Detected')).toBeInTheDocument();
    expect(screen.getByText(/A clean execution trace confirms all lifecycle steps/i)).toBeInTheDocument();
    expect(screen.queryByTestId('root-cause-card')).not.toBeInTheDocument();
  });

  it('renders insufficient_evidence state clearly', () => {
    const insufficientInvestigation: InvestigationResult = {
      investigation_id: 'inv-insufficient',
      trace_id: 'trace-trunc',
      status: 'insufficient_evidence',
      summary: 'Telemetry payload was abruptly severed.',
      root_cause: null,
      first_failure_event_id: null,
      confidence: 0.25,
      evidence: [],
      downstream_effects: [],
      recommended_actions: [],
      analyzed_findings: [],
      analyzed_event_ids: [],
      model: 'groq:llama-3.3-70b-versatile',
      created_at: '2026-10-04T12:00:00Z',
    };

    render(
      <InvestigationPanel
        investigation={insufficientInvestigation}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        onSelectEventId={vi.fn()}
      />
    );

    expect(screen.getByTestId('investigation-insufficient-evidence')).toBeInTheDocument();
    expect(screen.getByText('Insufficient Evidence')).toBeInTheDocument();
    expect(screen.getByText(/Telemetry payload was abruptly severed/i)).toBeInTheDocument();
  });

  it('renders failed state with re-run button', () => {
    const failedInvestigation: InvestigationResult = {
      investigation_id: 'inv-fail',
      trace_id: 'trace-f',
      status: 'failed',
      summary: 'Prompt analysis halted due to upstream parse rejection.',
      root_cause: null,
      first_failure_event_id: null,
      confidence: 0.0,
      evidence: [],
      downstream_effects: [],
      recommended_actions: [],
      analyzed_findings: [],
      analyzed_event_ids: [],
      model: 'groq:llama-3.3-70b-versatile',
      created_at: '2026-10-04T12:00:00Z',
    };

    const handleRetry = vi.fn();
    render(
      <InvestigationPanel
        investigation={failedInvestigation}
        isLoading={false}
        error={null}
        onRetry={handleRetry}
        onSelectEventId={vi.fn()}
      />
    );

    expect(screen.getByTestId('investigation-failed')).toBeInTheDocument();
    expect(screen.getAllByText('Investigation Failed').length).toBeGreaterThan(0);

    const rerunBtn = screen.getByText('Re-run Investigation');
    fireEvent.click(rerunBtn);
    expect(handleRetry).toHaveBeenCalled();
  });

  it('safely handles missing and optional fields without crashing', () => {
    const minimalInvestigation: InvestigationResult = {
      investigation_id: 'inv-min',
      trace_id: 'trace-m',
      status: 'investigated',
      summary: 'Minimal result',
      root_cause: null,
      first_failure_event_id: null,
      confidence: 0.7,
      evidence: [],
      downstream_effects: [],
      recommended_actions: [],
      analyzed_findings: [],
      analyzed_event_ids: [],
      model: 'mock',
      created_at: '',
    };

    render(
      <InvestigationPanel
        investigation={minimalInvestigation}
        isLoading={false}
        error={null}
        onRetry={vi.fn()}
        onSelectEventId={vi.fn()}
      />
    );

    expect(screen.getByText('Minimal result')).toBeInTheDocument();
    expect(screen.queryByTestId('root-cause-card')).not.toBeInTheDocument();
    expect(screen.queryByTestId('evidence-section')).not.toBeInTheDocument();
  });
});
