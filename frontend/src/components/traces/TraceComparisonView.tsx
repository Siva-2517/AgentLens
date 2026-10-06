import { useState, useMemo } from 'react';
import { TraceSummary } from '../../types/trace';
import {
  TraceComparisonResult,
  ComparisonEventSummary,
  Finding,
} from '../../types/comparison';
import { formatDuration, formatDateTime } from '../../utils/formatters';

interface TraceComparisonViewProps {
  traces: TraceSummary[];
  comparison: TraceComparisonResult | null;
  isLoading: boolean;
  error: string | null;
  selectedTraceAId: string | null;
  selectedTraceBId: string | null;
  onSelectTraceA: (traceId: string) => void;
  onSelectTraceB: (traceId: string) => void;
  onCompare: () => void;
  onRetry: () => void;
}

export function TraceComparisonView({
  traces,
  comparison,
  isLoading,
  error,
  selectedTraceAId,
  selectedTraceBId,
  onSelectTraceA,
  onSelectTraceB,
  onCompare,
  onRetry,
}: TraceComparisonViewProps) {
  const [filterMode, setFilterMode] = useState<'all' | 'diffs' | 'matched'>('all');
  const [inspectedEvent, setInspectedEvent] = useState<ComparisonEventSummary | null>(null);

  const canCompare = Boolean(
    selectedTraceAId &&
      selectedTraceBId &&
      selectedTraceAId !== selectedTraceBId &&
      !isLoading
  );

  const isSameTraceSelected = Boolean(
    selectedTraceAId && selectedTraceBId && selectedTraceAId === selectedTraceBId
  );

  // Filter steps according to user selection
  const filteredSteps = useMemo(() => {
    if (!comparison) return [];
    if (filterMode === 'diffs') {
      return comparison.sequence_comparison.filter(
        (s) => s.status !== 'matched' || (s.duration_diff_ms !== null && Math.abs(s.duration_diff_ms) > 100)
      );
    }
    if (filterMode === 'matched') {
      return comparison.sequence_comparison.filter((s) => s.status === 'matched');
    }
    return comparison.sequence_comparison;
  }, [comparison, filterMode]);

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'completed') {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-2 py-0.5 rounded">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          completed
        </span>
      );
    }
    if (s === 'failed') {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-400 bg-rose-950/40 border border-rose-800/40 px-2 py-0.5 rounded">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
          failed
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-950/40 border border-amber-800/40 px-2 py-0.5 rounded">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
        {status}
      </span>
    );
  };

  const getSeverityBadge = (severity: string) => {
    const sev = severity.toLowerCase();
    const colors: Record<string, string> = {
      critical: 'bg-rose-950/80 text-rose-300 border-rose-700/60',
      error: 'bg-rose-900/40 text-rose-300 border-rose-800/50',
      warning: 'bg-amber-950/60 text-amber-300 border-amber-700/50',
      info: 'bg-blue-950/60 text-blue-300 border-blue-700/50',
    };
    return (
      <span
        className={`px-1.5 py-0.5 text-[10px] uppercase font-mono font-semibold rounded border ${
          colors[sev] || colors.info
        }`}
      >
        {severity}
      </span>
    );
  };

  return (
    <div className="flex-1 flex flex-col h-full bg-slate-950 text-slate-100 overflow-y-auto">
      {/* 1. Header & Replay Disclaimer */}
      <div className="p-4 bg-slate-900 border-b border-slate-800 shrink-0">
        <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
          <div>
            <div className="flex items-center gap-2">
              <span className="text-xl">🔄</span>
              <h2 className="text-base font-bold text-slate-100">
                Trace Replay & Run Comparison
              </h2>
              <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-purple-950 border border-purple-800 text-purple-300">
                Phase 14
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Compare two completed agent runs side-by-side to understand execution branching, timing differences, and failure root causes.
            </p>
          </div>

          {/* Replay Semantics Disclaimer */}
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-lg bg-slate-950/80 border border-slate-800 text-[11px] text-slate-400 font-sans">
            <span className="text-amber-400 font-bold">ℹ</span>
            <span>
              <strong>Observability Replay:</strong> Comparison is derived strictly from recorded telemetry. No agent, tool, or LLM is re-executed.
            </span>
          </div>
        </div>

        {/* 2. Run Selectors Bar */}
        <div className="grid grid-cols-1 md:grid-cols-12 gap-3 items-center bg-slate-950/80 p-3 rounded-xl border border-slate-800">
          {/* Trace A Selector */}
          <div className="md:col-span-5 space-y-1">
            <label className="text-[11px] font-semibold text-purple-300 uppercase tracking-wider flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-purple-400" />
              Trace A (Baseline)
            </label>
            <select
              value={selectedTraceAId || ''}
              onChange={(e) => onSelectTraceA(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-purple-500"
              data-testid="select-trace-a"
            >
              <option value="">-- Choose Trace A --</option>
              {traces.map((t) => (
                <option key={t.trace_id} value={t.trace_id}>
                  {t.name} ({t.trace_id.slice(0, 10)}...) [{t.status}] - {formatDuration(t.duration_ms)}
                </option>
              ))}
            </select>
          </div>

          {/* Swap Button */}
          <div className="md:col-span-1 flex justify-center">
            <button
              onClick={() => {
                if (selectedTraceAId && selectedTraceBId) {
                  const a = selectedTraceAId;
                  const b = selectedTraceBId;
                  onSelectTraceA(b);
                  onSelectTraceB(a);
                }
              }}
              disabled={!selectedTraceAId || !selectedTraceBId || isLoading}
              className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-300 disabled:opacity-40 transition"
              title="Swap Trace A and Trace B"
              data-testid="swap-traces-btn"
            >
              ⇄
            </button>
          </div>

          {/* Trace B Selector */}
          <div className="md:col-span-5 space-y-1">
            <label className="text-[11px] font-semibold text-cyan-300 uppercase tracking-wider flex items-center gap-1.5">
              <span className="w-2 h-2 rounded-full bg-cyan-400" />
              Trace B (Comparison)
            </label>
            <select
              value={selectedTraceBId || ''}
              onChange={(e) => onSelectTraceB(e.target.value)}
              className="w-full bg-slate-900 border border-slate-700/80 rounded px-2.5 py-1.5 text-xs text-slate-200 focus:outline-none focus:border-cyan-500"
              data-testid="select-trace-b"
            >
              <option value="">-- Choose Trace B --</option>
              {traces.map((t) => (
                <option key={t.trace_id} value={t.trace_id}>
                  {t.name} ({t.trace_id.slice(0, 10)}...) [{t.status}] - {formatDuration(t.duration_ms)}
                </option>
              ))}
            </select>
          </div>

          {/* Compare Action Button */}
          <div className="md:col-span-1 flex justify-end">
            <button
              onClick={onCompare}
              disabled={!canCompare}
              className={`w-full py-2 px-3 rounded-lg text-xs font-bold transition shadow-md flex items-center justify-center gap-1.5 ${
                canCompare
                  ? 'bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white cursor-pointer'
                  : 'bg-slate-800 text-slate-500 border border-slate-700/60 cursor-not-allowed'
              }`}
              data-testid="compare-runs-btn"
            >
              <span>⚡</span> Compare
            </button>
          </div>
        </div>

        {isSameTraceSelected && (
          <div className="mt-2 text-[11px] text-amber-400 font-mono flex items-center gap-1">
            <span>⚠</span>
            <span>Trace A and Trace B are identical. Please choose two distinct runs to compare execution differences.</span>
          </div>
        )}
      </div>

      {/* 3. Main Body */}
      <div className="p-4 space-y-5">
        {/* Loading State */}
        {isLoading && (
          <div
            data-testid="comparison-loading"
            className="p-12 text-center flex flex-col items-center justify-center text-slate-400"
          >
            <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mb-3" />
            <h3 className="text-sm font-semibold text-slate-200">Comparing Traces & Replaying Execution...</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-sm">
              Aligning execution sequences, computing timing deltas, and evaluating deterministic failure findings.
            </p>
          </div>
        )}

        {/* Error State */}
        {error && !isLoading && (
          <div
            data-testid="comparison-error"
            className="p-5 rounded-xl bg-rose-950/40 border border-rose-800/60 text-rose-200"
          >
            <div className="flex items-center justify-between mb-2">
              <h3 className="text-sm font-semibold flex items-center gap-2">
                <span>⚠</span> Comparison Request Failed
              </h3>
              <button
                onClick={onRetry}
                className="px-3 py-1 bg-rose-800 hover:bg-rose-700 text-white rounded text-xs transition"
              >
                Retry
              </button>
            </div>
            <p className="text-xs text-rose-300 font-mono">{error}</p>
          </div>
        )}

        {/* Empty / Unselected State */}
        {!isLoading && !error && !comparison && (
          <div
            data-testid="comparison-empty"
            className="p-16 text-center text-slate-500 flex flex-col items-center justify-center"
          >
            <div className="text-4xl mb-3">⚖</div>
            <h3 className="text-base font-semibold text-slate-300">Ready to Compare Agent Runs</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md leading-relaxed">
              Select two execution traces above (for instance, a successful run vs a failed run) and click <strong>Compare</strong> to see execution divergence, step-by-step replay alignment, and deterministic findings.
            </p>
          </div>
        )}

        {/* Comparison Content */}
        {!isLoading && !error && comparison && (
          <div data-testid="comparison-content" className="space-y-5">
            {/* High-Level Differences Banner */}
            <div
              data-testid="high-level-differences"
              className="p-4 rounded-xl bg-slate-900 border border-slate-800 shadow-md space-y-3"
            >
              <div className="flex items-center justify-between border-b border-slate-800 pb-2">
                <h3 className="text-xs font-bold text-slate-300 uppercase tracking-wider flex items-center gap-2">
                  <span>📊</span> High-Level Deltas (Trace B vs Trace A)
                </h3>
                {comparison.differences.status_changed ? (
                  <span className="px-2 py-0.5 rounded text-[11px] font-bold uppercase bg-rose-950/60 text-rose-300 border border-rose-800/60">
                    Status Changed: {comparison.differences.status_a} → {comparison.differences.status_b}
                  </span>
                ) : (
                  <span className="px-2 py-0.5 rounded text-[11px] font-mono text-emerald-400 bg-emerald-950/40 border border-emerald-800/40">
                    Status Consistent: {comparison.differences.status_a}
                  </span>
                )}
              </div>

              {/* Metric Delta Badges */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {/* Duration Delta */}
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-[10px] uppercase font-semibold text-slate-400">Duration Delta</div>
                  <div
                    className={`text-sm font-bold font-mono mt-0.5 ${
                      comparison.differences.duration_diff_ms === null
                        ? 'text-slate-400'
                        : comparison.differences.duration_diff_ms > 0
                        ? 'text-amber-400'
                        : comparison.differences.duration_diff_ms < 0
                        ? 'text-emerald-400'
                        : 'text-slate-200'
                    }`}
                  >
                    {comparison.differences.duration_diff_ms !== null
                      ? `${comparison.differences.duration_diff_ms > 0 ? '+' : ''}${(
                          comparison.differences.duration_diff_ms / 1000
                        ).toFixed(2)} s`
                      : 'N/A'}
                  </div>
                </div>

                {/* Event Count Delta */}
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-[10px] uppercase font-semibold text-slate-400">Event Count Delta</div>
                  <div
                    className={`text-sm font-bold font-mono mt-0.5 ${
                      comparison.differences.event_count_diff > 0
                        ? 'text-purple-300'
                        : comparison.differences.event_count_diff < 0
                        ? 'text-cyan-300'
                        : 'text-slate-200'
                    }`}
                  >
                    {comparison.differences.event_count_diff > 0 ? '+' : ''}
                    {comparison.differences.event_count_diff} events
                  </div>
                </div>

                {/* Findings Delta */}
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-[10px] uppercase font-semibold text-slate-400">Findings Delta</div>
                  <div
                    className={`text-sm font-bold font-mono mt-0.5 ${
                      comparison.differences.findings_count_diff > 0
                        ? 'text-rose-400'
                        : comparison.differences.findings_count_diff < 0
                        ? 'text-emerald-400'
                        : 'text-slate-200'
                    }`}
                  >
                    {comparison.differences.findings_count_diff > 0 ? '+' : ''}
                    {comparison.differences.findings_count_diff} findings
                  </div>
                </div>

                {/* Lifecycle Delta */}
                <div className="p-3 bg-slate-950/60 rounded-lg border border-slate-800">
                  <div className="text-[10px] uppercase font-semibold text-slate-400">Lifecycle Outcome</div>
                  <div className="text-xs font-mono mt-1 text-slate-300 flex items-center gap-1.5">
                    <span className={comparison.trace_a.is_complete ? 'text-emerald-400' : 'text-rose-400'}>
                      A: {comparison.trace_a.is_complete ? '✓ Complete' : '✗ Incomplete'}
                    </span>
                    <span>vs</span>
                    <span className={comparison.trace_b.is_complete ? 'text-emerald-400' : 'text-rose-400'}>
                      B: {comparison.trace_b.is_complete ? '✓ Complete' : '✗ Incomplete'}
                    </span>
                  </div>
                </div>
              </div>

              {/* Event Type Differences Breakdown */}
              {Object.keys(comparison.differences.event_type_diffs).length > 0 && (
                <div className="pt-2 border-t border-slate-800/80">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider block mb-1.5">
                    Event Type Variance (B - A):
                  </span>
                  <div className="flex flex-wrap gap-1.5">
                    {Object.entries(comparison.differences.event_type_diffs).map(([type, delta]) => {
                      if (delta === 0) return null;
                      return (
                        <span
                          key={type}
                          className={`px-2 py-0.5 rounded text-[11px] font-mono border ${
                            delta > 0
                              ? 'bg-purple-950/40 text-purple-300 border-purple-800/50'
                              : 'bg-slate-950 text-slate-400 border-slate-800'
                          }`}
                        >
                          {type}: {delta > 0 ? `+${delta}` : delta}
                        </span>
                      );
                    })}
                  </div>
                </div>
              )}
            </div>

            {/* Side-by-Side Trace Overview Cards */}
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {/* Trace A Card */}
              <div className="p-4 rounded-xl bg-purple-950/15 border-2 border-purple-900/40 shadow-sm space-y-2">
                <div className="flex items-center justify-between border-b border-purple-900/30 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-purple-500/20 text-purple-300 border border-purple-500/40">
                      Run A (Baseline)
                    </span>
                    <h4 className="text-xs font-bold text-slate-100 truncate" title={comparison.trace_a.name}>
                      {comparison.trace_a.name}
                    </h4>
                  </div>
                  {getStatusBadge(comparison.trace_a.status)}
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs font-mono pt-1">
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase block">Duration</span>
                    <span className="text-slate-200 font-semibold">{formatDuration(comparison.trace_a.duration_ms)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase block">Events</span>
                    <span className="text-slate-200 font-semibold">{comparison.trace_a.event_count}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase block">Findings</span>
                    <span className={comparison.trace_a.findings_count > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                      {comparison.trace_a.findings_count}
                    </span>
                  </div>
                </div>

                <div className="text-[10px] font-mono text-slate-400 pt-1 border-t border-purple-900/20 truncate">
                  ID: <span className="text-slate-300">{comparison.trace_a.trace_id}</span>
                </div>
              </div>

              {/* Trace B Card */}
              <div className="p-4 rounded-xl bg-cyan-950/15 border-2 border-cyan-900/40 shadow-sm space-y-2">
                <div className="flex items-center justify-between border-b border-cyan-900/30 pb-2">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-cyan-500/20 text-cyan-300 border border-cyan-500/40">
                      Run B (Comparison)
                    </span>
                    <h4 className="text-xs font-bold text-slate-100 truncate" title={comparison.trace_b.name}>
                      {comparison.trace_b.name}
                    </h4>
                  </div>
                  {getStatusBadge(comparison.trace_b.status)}
                </div>

                <div className="grid grid-cols-3 gap-2 text-xs font-mono pt-1">
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase block">Duration</span>
                    <span className="text-slate-200 font-semibold">{formatDuration(comparison.trace_b.duration_ms)}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase block">Events</span>
                    <span className="text-slate-200 font-semibold">{comparison.trace_b.event_count}</span>
                  </div>
                  <div>
                    <span className="text-slate-500 text-[10px] uppercase block">Findings</span>
                    <span className={comparison.trace_b.findings_count > 0 ? 'text-rose-400 font-bold' : 'text-emerald-400'}>
                      {comparison.trace_b.findings_count}
                    </span>
                  </div>
                </div>

                <div className="text-[10px] font-mono text-slate-400 pt-1 border-t border-cyan-900/20 truncate">
                  ID: <span className="text-slate-300">{comparison.trace_b.trace_id}</span>
                </div>
              </div>
            </div>

            {/* 4. Execution Sequence Replay / Alignment */}
            <div
              data-testid="execution-sequence-comparison"
              className="p-4 rounded-xl bg-slate-900 border border-slate-800 shadow-md space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2 border-b border-slate-800 pb-2.5">
                <div>
                  <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                    <span>🔁</span> Aligned Execution Replay ({filteredSteps.length} Steps)
                  </h3>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Deterministic sequence alignment comparing corresponding steps between Run A and Run B.
                  </p>
                </div>

                {/* Filter buttons */}
                <div className="flex items-center gap-1 text-xs">
                  <button
                    onClick={() => setFilterMode('all')}
                    className={`px-2.5 py-1 rounded transition text-xs ${
                      filterMode === 'all'
                        ? 'bg-purple-900/70 text-purple-200 border border-purple-600 font-medium'
                        : 'bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200'
                    }`}
                  >
                    All ({comparison.sequence_comparison.length})
                  </button>
                  <button
                    onClick={() => setFilterMode('diffs')}
                    className={`px-2.5 py-1 rounded transition text-xs ${
                      filterMode === 'diffs'
                        ? 'bg-purple-900/70 text-purple-200 border border-purple-600 font-medium'
                        : 'bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200'
                    }`}
                  >
                    Differences Only
                  </button>
                  <button
                    onClick={() => setFilterMode('matched')}
                    className={`px-2.5 py-1 rounded transition text-xs ${
                      filterMode === 'matched'
                        ? 'bg-purple-900/70 text-purple-200 border border-purple-600 font-medium'
                        : 'bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200'
                    }`}
                  >
                    Matched Only
                  </button>
                </div>
              </div>

              {/* Step Sequence Table / List */}
              <div className="divide-y divide-slate-800/60 overflow-hidden border border-slate-800/80 rounded-lg">
                {filteredSteps.map((step) => {
                  const isMatched = step.status === 'matched';
                  const isOnlyA = step.status === 'only_a';
                  const isOnlyB = step.status === 'only_b';

                  return (
                    <div
                      key={step.step_index}
                      className={`p-3 grid grid-cols-1 md:grid-cols-12 gap-3 items-center text-xs transition ${
                        isMatched
                          ? 'bg-slate-950/40 hover:bg-slate-900/60'
                          : isOnlyA
                          ? 'bg-amber-950/15 hover:bg-amber-950/25 border-l-4 border-l-amber-500'
                          : 'bg-rose-950/15 hover:bg-rose-950/25 border-l-4 border-l-rose-500'
                      }`}
                      data-testid={`replay-step-${step.step_index}`}
                    >
                      {/* Step index & alignment status */}
                      <div className="md:col-span-2 flex items-center gap-2">
                        <span className="font-mono text-slate-500 text-[11px] w-6">#{step.step_index}</span>
                        {isMatched && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-emerald-950/60 text-emerald-400 border border-emerald-800/50">
                            MATCHED
                          </span>
                        )}
                        {isOnlyA && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-amber-950/60 text-amber-300 border border-amber-800/50">
                            RUN A ONLY
                          </span>
                        )}
                        {isOnlyB && (
                          <span className="px-1.5 py-0.5 rounded text-[10px] font-semibold bg-rose-950/60 text-rose-300 border border-rose-800/50">
                            RUN B ONLY
                          </span>
                        )}
                      </div>

                      {/* Event A Column */}
                      <div className="md:col-span-4">
                        {step.event_a ? (
                          <button
                            onClick={() => setInspectedEvent(step.event_a)}
                            className="w-full text-left p-2 rounded bg-slate-900/90 border border-slate-800 hover:border-purple-600/60 transition group"
                            title="Click to inspect Run A event payload"
                          >
                            <div className="flex items-center justify-between gap-1 mb-0.5">
                              <span className="font-mono font-semibold text-purple-300 group-hover:text-purple-200">
                                {step.event_a.event_type}
                              </span>
                              {step.event_a.duration_ms !== null && (
                                <span className="font-mono text-[10px] text-slate-400">
                                  {step.event_a.duration_ms.toFixed(0)}ms
                                </span>
                              )}
                            </div>
                            <div className="text-[10px] font-mono text-slate-400 truncate">
                              ID: {step.event_a.event_id}
                            </div>
                          </button>
                        ) : (
                          <div className="p-2 rounded bg-slate-950/40 border border-dashed border-slate-800 text-slate-600 text-center font-mono text-[11px]">
                            — Bypassed in Run A —
                          </div>
                        )}
                      </div>

                      {/* Delta Indicator Column */}
                      <div className="md:col-span-2 text-center">
                        {isMatched && step.duration_diff_ms !== null ? (
                          <div className="text-[11px] font-mono font-semibold">
                            <span
                              className={
                                step.duration_diff_ms > 0
                                  ? 'text-amber-400'
                                  : step.duration_diff_ms < 0
                                  ? 'text-emerald-400'
                                  : 'text-slate-400'
                              }
                            >
                              {step.duration_diff_ms > 0 ? `+${step.duration_diff_ms}ms` : `${step.duration_diff_ms}ms`}
                            </span>
                          </div>
                        ) : (
                          <span className="text-[10px] text-slate-500 font-mono">
                            {isOnlyA ? 'Bypassed in B' : isOnlyB ? 'Branched in B' : '—'}
                          </span>
                        )}
                      </div>

                      {/* Event B Column */}
                      <div className="md:col-span-4">
                        {step.event_b ? (
                          <button
                            onClick={() => setInspectedEvent(step.event_b)}
                            className="w-full text-left p-2 rounded bg-slate-900/90 border border-slate-800 hover:border-cyan-600/60 transition group"
                            title="Click to inspect Run B event payload"
                          >
                            <div className="flex items-center justify-between gap-1 mb-0.5">
                              <span className="font-mono font-semibold text-cyan-300 group-hover:text-cyan-200">
                                {step.event_b.event_type}
                              </span>
                              {step.event_b.duration_ms !== null && (
                                <span className="font-mono text-[10px] text-slate-400">
                                  {step.event_b.duration_ms.toFixed(0)}ms
                                </span>
                              )}
                            </div>
                            <div className="text-[10px] font-mono text-slate-400 truncate">
                              ID: {step.event_b.event_id}
                            </div>
                          </button>
                        ) : (
                          <div className="p-2 rounded bg-slate-950/40 border border-dashed border-slate-800 text-slate-600 text-center font-mono text-[11px]">
                            — Bypassed in Run B —
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* 5. Deterministic Findings Comparison */}
            <div
              data-testid="findings-comparison-section"
              className="p-4 rounded-xl bg-slate-900 border border-slate-800 shadow-md space-y-3"
            >
              <div className="border-b border-slate-800 pb-2">
                <h3 className="text-xs font-bold text-slate-200 uppercase tracking-wider flex items-center gap-2">
                  <span>🔎</span> Deterministic Findings Comparison
                </h3>
                <p className="text-[11px] text-slate-400 mt-0.5">
                  Phase 11 deterministic failure and anomaly findings detected across both runs.
                </p>
              </div>

              {comparison.findings_comparison.findings_only_a.length === 0 &&
              comparison.findings_comparison.findings_only_b.length === 0 &&
              comparison.findings_comparison.common_findings.length === 0 ? (
                <div className="p-4 rounded-lg bg-slate-950/60 border border-slate-800 text-center text-xs text-slate-400">
                  <span className="text-emerald-400 mr-1.5 font-bold">✓</span>
                  No deterministic failure findings detected in either run. Both runs executed cleanly.
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {/* Findings Only in Run A */}
                  <div className="space-y-2">
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-purple-300 flex items-center gap-1.5">
                      <span>Unique to Run A ({comparison.findings_comparison.findings_only_a.length})</span>
                    </h4>
                    {comparison.findings_comparison.findings_only_a.length === 0 ? (
                      <p className="text-[11px] text-slate-500 italic p-3 bg-slate-950/40 rounded border border-slate-800">
                        None detected in Run A.
                      </p>
                    ) : (
                      comparison.findings_comparison.findings_only_a.map((f: Finding) => (
                        <div
                          key={f.finding_id}
                          className="p-3 rounded-lg bg-slate-950/80 border border-purple-900/40 space-y-1.5"
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-mono text-xs font-semibold text-slate-200">{f.rule}</span>
                            {getSeverityBadge(f.severity)}
                          </div>
                          <p className="text-xs text-slate-300 leading-snug">{f.message}</p>
                          {f.evidence_event_ids.length > 0 && (
                            <div className="text-[10px] font-mono text-slate-400">
                              Evidence: {f.evidence_event_ids.join(', ')}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>

                  {/* Findings Only in Run B */}
                  <div className="space-y-2">
                    <h4 className="text-[11px] font-bold uppercase tracking-wider text-rose-300 flex items-center gap-1.5">
                      <span>Unique to Run B ({comparison.findings_comparison.findings_only_b.length})</span>
                    </h4>
                    {comparison.findings_comparison.findings_only_b.length === 0 ? (
                      <p className="text-[11px] text-slate-500 italic p-3 bg-slate-950/40 rounded border border-slate-800">
                        None detected in Run B.
                      </p>
                    ) : (
                      comparison.findings_comparison.findings_only_b.map((f: Finding) => (
                        <div
                          key={f.finding_id}
                          className="p-3 rounded-lg bg-slate-950/80 border border-rose-900/40 space-y-1.5"
                        >
                          <div className="flex items-center justify-between gap-1">
                            <span className="font-mono text-xs font-semibold text-slate-200">{f.rule}</span>
                            {getSeverityBadge(f.severity)}
                          </div>
                          <p className="text-xs text-slate-300 leading-snug">{f.message}</p>
                          {f.evidence_event_ids.length > 0 && (
                            <div className="text-[10px] font-mono text-slate-400">
                              Evidence: {f.evidence_event_ids.join(', ')}
                            </div>
                          )}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>

      {/* 6. Event Details Inspection Modal */}
      {inspectedEvent && (
        <div
          data-testid="inspected-event-modal"
          className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4"
        >
          <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-xl max-h-[85vh] flex flex-col shadow-2xl overflow-hidden">
            {/* Modal Header */}
            <div className="p-4 border-b border-slate-800 flex items-center justify-between bg-slate-950">
              <div>
                <h4 className="font-bold text-sm text-slate-100 flex items-center gap-2">
                  <span>🔍</span>
                  <span>{inspectedEvent.event_type}</span>
                </h4>
                <p className="text-[11px] font-mono text-slate-400 mt-0.5">
                  ID: {inspectedEvent.event_id} • Trace: {inspectedEvent.trace_id}
                </p>
              </div>
              <button
                onClick={() => setInspectedEvent(null)}
                className="p-1 rounded text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition"
              >
                ✕
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-4 space-y-3 overflow-y-auto flex-1 font-mono text-xs">
              <div className="grid grid-cols-2 gap-2 text-[11px]">
                <div className="p-2 bg-slate-950 rounded border border-slate-800">
                  <span className="text-slate-500 block">Timestamp</span>
                  <span className="text-slate-300">{formatDateTime(inspectedEvent.timestamp)}</span>
                </div>
                <div className="p-2 bg-slate-950 rounded border border-slate-800">
                  <span className="text-slate-500 block">Duration</span>
                  <span className="text-slate-300">
                    {inspectedEvent.duration_ms !== null ? `${inspectedEvent.duration_ms.toFixed(1)} ms` : 'N/A'}
                  </span>
                </div>
              </div>

              {/* Payload Data */}
              <div>
                <span className="text-[11px] text-slate-400 font-sans font-semibold uppercase tracking-wider block mb-1">
                  Payload Data
                </span>
                <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] text-slate-300 overflow-x-auto">
                  {JSON.stringify(inspectedEvent.data, null, 2)}
                </pre>
              </div>

              {/* Metadata */}
              {Object.keys(inspectedEvent.metadata).length > 0 && (
                <div>
                  <span className="text-[11px] text-slate-400 font-sans font-semibold uppercase tracking-wider block mb-1">
                    Metadata
                  </span>
                  <pre className="p-3 bg-slate-950 rounded-lg border border-slate-800 text-[11px] text-slate-300 overflow-x-auto">
                    {JSON.stringify(inspectedEvent.metadata, null, 2)}
                  </pre>
                </div>
              )}
            </div>

            {/* Modal Footer */}
            <div className="p-3 border-t border-slate-800 bg-slate-950 flex justify-end">
              <button
                onClick={() => setInspectedEvent(null)}
                className="px-3 py-1.5 rounded bg-slate-800 hover:bg-slate-700 text-xs font-semibold text-slate-200 transition"
              >
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
