import React from 'react';
import {
  InvestigationResult,
  InvestigationStatus,
} from '../../types/investigation';

interface InvestigationPanelProps {
  investigation: InvestigationResult | null;
  isLoading: boolean;
  error: string | null;
  onRetry: () => void;
  onSelectEventId: (eventId: string) => void;
  onClose?: () => void;
  selectedEventId?: string | null;
}

export const InvestigationPanel: React.FC<InvestigationPanelProps> = ({
  investigation,
  isLoading,
  error,
  onRetry,
  onSelectEventId,
  onClose,
  selectedEventId,
}) => {
  // Status badge visual styling
  const getStatusBadge = (status: InvestigationStatus) => {
    switch (status) {
      case 'investigated':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-950/60 text-purple-300 border border-purple-700/60 shadow-sm shadow-purple-900/30">
            <span className="w-1.5 h-1.5 rounded-full bg-purple-400 animate-pulse" />
            Investigated
          </span>
        );
      case 'no_issue_detected':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-950/60 text-emerald-300 border border-emerald-700/60">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            No Issue Detected
          </span>
        );
      case 'insufficient_evidence':
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-950/60 text-amber-300 border border-amber-700/60">
            <span className="w-1.5 h-1.5 rounded-full bg-amber-400" />
            Insufficient Evidence
          </span>
        );
      case 'failed':
      default:
        return (
          <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-rose-950/60 text-rose-300 border border-rose-700/60">
            <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
            Investigation Failed
          </span>
        );
    }
  };

  const getConfidenceBadge = (confidence: number) => {
    const pct = Math.round(confidence * 100);
    let color = 'text-emerald-400 border-emerald-700/60 bg-emerald-950/40';
    if (pct < 50) {
      color = 'text-rose-400 border-rose-700/60 bg-rose-950/40';
    } else if (pct < 80) {
      color = 'text-amber-400 border-amber-700/60 bg-amber-950/40';
    }

    return (
      <span
        className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-mono font-medium border ${color}`}
        title={`Investigation confidence score: ${pct}%`}
      >
        <span>Confidence:</span>
        <span className="font-bold">{pct}%</span>
      </span>
    );
  };

  const getPriorityBadge = (priority: string) => {
    switch (priority.toLowerCase()) {
      case 'high':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider bg-rose-950/60 text-rose-300 border border-rose-800/60">
            High Priority
          </span>
        );
      case 'medium':
        return (
          <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider bg-amber-950/60 text-amber-300 border border-amber-800/60">
            Medium Priority
          </span>
        );
      case 'low':
      default:
        return (
          <span className="px-2 py-0.5 rounded text-[10px] uppercase font-bold tracking-wider bg-slate-800 text-slate-300 border border-slate-700">
            Low Priority
          </span>
        );
    }
  };

  return (
    <div
      data-testid="investigation-panel"
      className="h-full flex flex-col bg-slate-900 border-l border-slate-800 overflow-hidden font-sans"
    >
      {/* Panel Header */}
      <div className="p-4 border-b border-slate-800 flex items-center justify-between shrink-0 bg-slate-900/95 backdrop-blur">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-lg bg-purple-950/80 border border-purple-700/60 flex items-center justify-center text-purple-300 text-sm shadow-inner">
            🤖
          </div>
          <div>
            <h3 className="font-semibold text-sm text-slate-100 flex items-center gap-2">
              <span>AI Root-Cause Investigation</span>
            </h3>
            {investigation?.model && (
              <p className="text-[10px] font-mono text-slate-400">
                model: {investigation.model}
              </p>
            )}
          </div>
        </div>

        <div className="flex items-center gap-2">
          {investigation && getStatusBadge(investigation.status)}
          {onClose && (
            <button
              onClick={onClose}
              className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 transition"
              title="Close Panel"
              aria-label="Close Investigation Panel"
            >
              ✕
            </button>
          )}
        </div>
      </div>

      {/* Main Content Area */}
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {/* Loading State */}
        {isLoading && (
          <div
            data-testid="investigation-loading"
            className="flex flex-col items-center justify-center p-8 text-center"
          >
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mb-3" />
            <p className="text-sm font-medium text-slate-300">
              Investigating Trace with AI...
            </p>
            <p className="text-xs text-slate-500 mt-1 max-w-xs">
              Synthesizing reconstructed events, graph hierarchy, and deterministic findings.
            </p>
          </div>
        )}

        {/* Error State */}
        {!isLoading && error && (
          <div
            data-testid="investigation-error"
            className="p-4 rounded-lg bg-rose-950/40 border border-rose-800/60 text-rose-200"
          >
            <div className="flex items-center gap-2 mb-1.5">
              <span className="text-rose-400 font-bold">⚠</span>
              <h4 className="font-semibold text-sm">Investigation Request Failed</h4>
            </div>
            <p className="text-xs text-rose-300 font-mono mb-3">{error}</p>
            <button
              onClick={onRetry}
              className="px-3 py-1 bg-rose-800 hover:bg-rose-700 text-white rounded text-xs font-medium transition"
            >
              Retry Investigation
            </button>
          </div>
        )}

        {/* Special State: No Issue Detected */}
        {!isLoading && !error && investigation?.status === 'no_issue_detected' && (
          <div
            data-testid="investigation-no-issue"
            className="p-5 rounded-lg bg-emerald-950/20 border border-emerald-800/40 text-slate-200 space-y-3"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-full bg-emerald-900/60 border border-emerald-700/60 flex items-center justify-center text-emerald-400 text-xs font-bold">
                ✓
              </div>
              <h4 className="font-semibold text-sm text-emerald-300">
                No Execution Failures Detected
              </h4>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              {investigation.summary ||
                'Deterministic analysis and AI investigation detected no failures, errors, or anomalies in this trace.'}
            </p>
            <div className="p-3 bg-slate-950/60 rounded border border-slate-800/80 text-[11px] text-slate-400 leading-relaxed">
              <span className="font-semibold text-slate-300">Note: </span>
              A clean execution trace confirms all lifecycle steps, tool calls, and LLM queries completed without uncaught exceptions or deterministic errors. It does not certify that the semantic answer satisfies specific business requirements.
            </div>
          </div>
        )}

        {/* Special State: Insufficient Evidence */}
        {!isLoading && !error && investigation?.status === 'insufficient_evidence' && (
          <div
            data-testid="investigation-insufficient-evidence"
            className="p-5 rounded-lg bg-amber-950/20 border border-amber-800/40 text-slate-200 space-y-3"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-full bg-amber-900/60 border border-amber-700/60 flex items-center justify-center text-amber-400 text-xs font-bold">
                ⚠
              </div>
              <h4 className="font-semibold text-sm text-amber-300">
                Insufficient Evidence for Root Cause
              </h4>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              {investigation.summary ||
                'Available trace data and event payloads were insufficient to establish a definitive root cause with high confidence.'}
            </p>
            <div className="text-[11px] text-slate-400">
              No artificial root cause was manufactured. Inspect individual event telemetry in the graph to gather additional context.
            </div>
          </div>
        )}

        {/* Special State: Failed */}
        {!isLoading && !error && investigation?.status === 'failed' && (
          <div
            data-testid="investigation-failed"
            className="p-5 rounded-lg bg-rose-950/20 border border-rose-800/40 text-slate-200 space-y-3"
          >
            <div className="flex items-center gap-2.5">
              <div className="w-6 h-6 rounded-full bg-rose-900/60 border border-rose-700/60 flex items-center justify-center text-rose-400 text-xs font-bold">
                ✕
              </div>
              <h4 className="font-semibold text-sm text-rose-300">
                Investigation Failed
              </h4>
            </div>
            <p className="text-xs text-rose-200 leading-relaxed">
              {investigation.summary ||
                'The investigation service encountered an error while processing trace reasoning.'}
            </p>
            <button
              onClick={onRetry}
              className="px-3 py-1 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded text-xs font-medium border border-slate-700 transition"
            >
              Re-run Investigation
            </button>
          </div>
        )}

        {/* Main Investigation Results (status === 'investigated' or has root cause) */}
        {!isLoading &&
          !error &&
          investigation &&
          investigation.status === 'investigated' && (
            <>
              {/* PRIMARY VISUAL FOCUS: Root Cause Card */}
              {investigation.root_cause && (
                <div
                  data-testid="root-cause-card"
                  className="p-4 rounded-xl bg-purple-950/25 border-2 border-purple-600/70 shadow-lg shadow-purple-950/40 space-y-3"
                >
                  <div className="flex flex-wrap items-center justify-between gap-2 border-b border-purple-800/40 pb-2.5">
                    <div className="flex items-center gap-2">
                      <span className="px-2.5 py-0.5 rounded text-[11px] font-bold uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/40">
                        Primary Root Cause
                      </span>
                      {investigation.root_cause.finding_id && (
                        <span
                          className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-[10px] font-mono text-slate-300"
                          title={`Associated Phase 11 finding: ${investigation.root_cause.finding_id}`}
                        >
                          finding: {investigation.root_cause.finding_id}
                        </span>
                      )}
                    </div>
                    {getConfidenceBadge(investigation.root_cause.confidence)}
                  </div>

                  <div>
                    <h4 className="text-sm font-semibold text-slate-100 leading-snug">
                      {investigation.root_cause.description}
                    </h4>
                  </div>

                  {investigation.first_failure_event_id && (
                    <div className="flex items-center gap-2 text-xs">
                      <span className="text-slate-400">First Failure Event:</span>
                      <button
                        onClick={() =>
                          onSelectEventId(investigation.first_failure_event_id!)
                        }
                        className={`px-2 py-0.5 rounded text-xs font-mono font-semibold transition border ${
                          selectedEventId === investigation.first_failure_event_id
                            ? 'bg-purple-600 text-white border-purple-400 shadow-sm'
                            : 'bg-slate-950 hover:bg-slate-800 text-purple-300 border-purple-800/60'
                        }`}
                        title="Focus this event in the execution graph"
                      >
                        ⚡ {investigation.first_failure_event_id}
                      </button>
                    </div>
                  )}

                  {investigation.root_cause.reasoning && (
                    <div className="p-3 bg-slate-950/70 rounded-lg border border-purple-900/40 text-xs text-slate-300 leading-relaxed font-sans">
                      <p className="text-[11px] font-semibold text-purple-400 uppercase tracking-wider mb-1">
                        Reasoning & Diagnosis:
                      </p>
                      <p>{investigation.root_cause.reasoning}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Summary Card */}
              {investigation.summary && (
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800 text-xs text-slate-300 leading-relaxed">
                  <span className="font-semibold text-slate-200">Summary: </span>
                  {investigation.summary}
                </div>
              )}

              {/* Evidence Items */}
              {investigation.evidence && investigation.evidence.length > 0 && (
                <div data-testid="evidence-section" className="space-y-2">
                  <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider flex items-center justify-between">
                    <span>Grounding Evidence ({investigation.evidence.length})</span>
                  </h4>

                  <div className="space-y-2">
                    {investigation.evidence.map((item, idx) => (
                      <div
                        key={idx}
                        className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 hover:border-slate-700 transition space-y-1.5"
                      >
                        <div className="flex flex-wrap items-center gap-2">
                          {item.event_id && (
                            <button
                              onClick={() => onSelectEventId(item.event_id!)}
                              className={`px-2 py-0.5 rounded text-[11px] font-mono font-medium transition border ${
                                selectedEventId === item.event_id
                                  ? 'bg-purple-600 text-white border-purple-400'
                                  : 'bg-slate-900 hover:bg-slate-800 text-purple-300 border-purple-800/50'
                              }`}
                              title="Focus node in graph"
                            >
                              ⚡ {item.event_id}
                            </button>
                          )}
                          {item.finding_id && (
                            <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-slate-900 text-slate-400 border border-slate-800">
                              finding: {item.finding_id}
                            </span>
                          )}
                        </div>
                        <p className="text-xs text-slate-300 leading-relaxed">
                          {item.description}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Downstream Effects */}
              {investigation.downstream_effects &&
                investigation.downstream_effects.length > 0 && (
                  <div data-testid="downstream-effects-section" className="space-y-2">
                    <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                      Downstream Symptoms ({investigation.downstream_effects.length})
                    </h4>

                    <div className="space-y-2">
                      {investigation.downstream_effects.map((effect, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 space-y-1.5"
                        >
                          <div className="flex items-center justify-between gap-2">
                            {effect.event_id && (
                              <button
                                onClick={() => onSelectEventId(effect.event_id!)}
                                className={`px-2 py-0.5 rounded text-[11px] font-mono font-medium transition border ${
                                  selectedEventId === effect.event_id
                                    ? 'bg-purple-600 text-white border-purple-400'
                                    : 'bg-slate-900 hover:bg-slate-800 text-rose-300 border-rose-800/50'
                                }`}
                                title="Focus node in graph"
                              >
                                ⚡ {effect.event_id}
                              </button>
                            )}
                            {effect.impact && (
                              <span className="px-2 py-0.5 rounded text-[10px] font-mono text-slate-400 bg-slate-900 border border-slate-800">
                                impact: {effect.impact}
                              </span>
                            )}
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed">
                            {effect.description}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Recommended Actions */}
              {investigation.recommended_actions &&
                investigation.recommended_actions.length > 0 && (
                  <div data-testid="recommended-actions-section" className="space-y-2">
                    <h4 className="text-xs font-semibold text-slate-300 uppercase tracking-wider">
                      Recommended Engineering Actions ({investigation.recommended_actions.length})
                    </h4>

                    <div className="space-y-2">
                      {investigation.recommended_actions.map((act, idx) => (
                        <div
                          key={idx}
                          className="p-3 rounded-lg bg-slate-950/60 border border-slate-800/80 space-y-2"
                        >
                          <div className="flex items-center justify-between gap-2">
                            <span className="text-xs font-semibold text-slate-200">
                              Action {idx + 1}
                            </span>
                            {getPriorityBadge(act.priority)}
                          </div>
                          <p className="text-xs text-slate-300 leading-relaxed">
                            {act.action}
                          </p>

                          {act.related_event_ids && act.related_event_ids.length > 0 && (
                            <div className="flex flex-wrap items-center gap-1.5 pt-1">
                              <span className="text-[10px] text-slate-500 uppercase tracking-wider">
                                Related Events:
                              </span>
                              {act.related_event_ids.map((evId) => (
                                <button
                                  key={evId}
                                  onClick={() => onSelectEventId(evId)}
                                  className={`px-1.5 py-0.5 rounded text-[10px] font-mono transition border ${
                                    selectedEventId === evId
                                      ? 'bg-purple-600 text-white border-purple-400'
                                      : 'bg-slate-900 hover:bg-slate-800 text-slate-300 border-slate-700'
                                  }`}
                                  title="Focus node in graph"
                                >
                                  ⚡ {evId}
                                </button>
                              ))}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </div>
                )}

              {/* Telemetry metadata footer */}
              <div className="pt-2 border-t border-slate-800/60 text-[11px] text-slate-500 font-mono flex flex-wrap items-center justify-between gap-2">
                <span>
                  Analyzed {investigation.analyzed_findings?.length ?? 0} findings,{' '}
                  {investigation.analyzed_event_ids?.length ?? 0} events
                </span>
                {investigation.created_at && (
                  <span>
                    {new Date(investigation.created_at).toLocaleTimeString([], {
                      hour: '2-digit',
                      minute: '2-digit',
                      second: '2-digit',
                    })}
                  </span>
                )}
              </div>
            </>
          )}
      </div>
    </div>
  );
};
