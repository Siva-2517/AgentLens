import { useState } from 'react';
import { ReconstructedTrace } from '../../types/trace';
import { RealtimeConnectionState } from '../../types/realtime';
import { InvestigationStatus } from '../../types/investigation';
import { indexTraceFailures } from '../../services/api';
import {
  formatDuration,
  formatTimeWithMs,
  formatDateTime,
} from '../../utils/formatters';

interface TraceOverviewProps {
  trace: ReconstructedTrace;
  connectionState?: RealtimeConnectionState;
  onToggleInvestigation?: () => void;
  isInvestigationOpen?: boolean;
  investigationStatus?: InvestigationStatus | null;
  investigationConfidence?: number | null;
  onCompareTrace?: () => void;
  onIndexFailures?: () => void;
}

export function TraceOverview({
  trace,
  connectionState = 'disconnected',
  onToggleInvestigation,
  isInvestigationOpen = false,
  investigationStatus,
  investigationConfidence,
  onCompareTrace,
  onIndexFailures,
}: TraceOverviewProps) {
  const meta = trace.metadata;
  const [indexState, setIndexState] = useState<'idle' | 'indexing' | 'success' | 'no_findings' | 'error'>('idle');
  const [indexedCount, setIndexedCount] = useState<number | null>(null);

  const handleIndexFailures = async () => {
    if (indexState === 'indexing') return;
    setIndexState('indexing');
    try {
      const res = await indexTraceFailures(trace.trace_id);
      if (res.status === 'no_findings') {
        setIndexState('no_findings');
      } else {
        setIndexState('success');
        setIndexedCount(res.indexed_count);
      }
      onIndexFailures?.();
    } catch {
      setIndexState('error');
    }
  };

  // Status visual badge styling
  const statusStyles: Record<string, { bg: string; text: string; border: string; dot: string }> = {
    running: {
      bg: 'bg-amber-950/40',
      text: 'text-amber-400',
      border: 'border-amber-700/50',
      dot: 'bg-amber-400 animate-ping',
    },
    completed: {
      bg: 'bg-emerald-950/40',
      text: 'text-emerald-400',
      border: 'border-emerald-700/50',
      dot: 'bg-emerald-400',
    },
    failed: {
      bg: 'bg-rose-950/40',
      text: 'text-rose-400',
      border: 'border-rose-700/50',
      dot: 'bg-rose-400',
    },
  };

  const statusStyle = statusStyles[trace.status.toLowerCase()] || {
    bg: 'bg-slate-800',
    text: 'text-slate-300',
    border: 'border-slate-700',
    dot: 'bg-slate-400',
  };

  return (
    <div className="bg-slate-900 border-b border-slate-800 p-4 shrink-0 shadow-sm">
      {/* Top row: Name, Status, IDs */}
      <div className="flex flex-wrap items-center justify-between gap-3 mb-3">
        <div className="flex items-center gap-3">
          <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
            <span>{trace.name || 'Unnamed Trace'}</span>
          </h2>

          <div
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-medium border ${statusStyle.bg} ${statusStyle.text} ${statusStyle.border}`}
          >
            <span className={`w-1.5 h-1.5 rounded-full ${statusStyle.dot}`} />
            <span className="uppercase tracking-wider text-[11px] font-semibold">
              {trace.status}
            </span>
          </div>

          {/* Real-time streaming indicator */}
          <div
            className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[11px] font-mono border ${
              connectionState === 'connected'
                ? 'bg-emerald-950/60 text-emerald-300 border-emerald-600/60 shadow-sm shadow-emerald-900/30'
                : connectionState === 'connecting'
                ? 'bg-amber-950/40 text-amber-300 border-amber-700/50'
                : 'bg-slate-950/50 text-slate-400 border-slate-800'
            }`}
          >
            <span
              className={`w-2 h-2 rounded-full ${
                connectionState === 'connected'
                  ? 'bg-emerald-400 animate-pulse'
                  : connectionState === 'connecting'
                  ? 'bg-amber-400 animate-ping'
                  : 'bg-slate-500'
              }`}
            />
            <span>
              {connectionState === 'connected'
                ? 'Live'
                : connectionState === 'connecting'
                ? 'Connecting...'
                : 'Offline'}
            </span>
          </div>

          {trace.project_name && (
            <span className="px-2 py-0.5 rounded bg-slate-800 border border-slate-700 text-slate-300 text-xs font-mono">
              project: {trace.project_name}
            </span>
          )}

          {/* AI Investigation Trigger Button */}
          {onToggleInvestigation && (
            <button
              onClick={onToggleInvestigation}
              data-testid="toggle-investigation-btn"
              className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border transition shadow-sm ${
                isInvestigationOpen
                  ? 'bg-purple-600 text-white border-purple-400 shadow-purple-900/50'
                  : 'bg-purple-950/40 hover:bg-purple-900/50 text-purple-300 border-purple-700/60'
              }`}
              title="Toggle AI Root-Cause Investigation"
            >
              <span>🤖</span>
              <span>AI Investigation</span>
              {investigationStatus && (
                <span
                  className={`text-[10px] px-1.5 py-0.2 rounded font-mono uppercase ${
                    investigationStatus === 'investigated'
                      ? 'bg-purple-900/80 text-purple-200'
                      : investigationStatus === 'no_issue_detected'
                      ? 'bg-emerald-900/80 text-emerald-200'
                      : investigationStatus === 'insufficient_evidence'
                      ? 'bg-amber-900/80 text-amber-200'
                      : 'bg-rose-900/80 text-rose-200'
                  }`}
                >
                  {investigationStatus === 'no_issue_detected'
                    ? 'Clean'
                    : investigationStatus === 'investigated' && investigationConfidence != null
                    ? `${Math.round(investigationConfidence * 100)}%`
                    : investigationStatus.replace('_', ' ')}
                </span>
              )}
            </button>
          )}

          {/* Quick Compare Button */}
          {onCompareTrace && (
            <button
              onClick={onCompareTrace}
              data-testid="quick-compare-btn"
              className="inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border transition shadow-sm bg-cyan-950/40 hover:bg-cyan-900/50 text-cyan-300 border-cyan-700/60"
              title="Compare this run with another execution"
            >
              <span>🔄</span>
              <span>Compare Run</span>
            </button>
          )}

          {/* Historical Failure Indexing Button */}
          <button
            onClick={handleIndexFailures}
            disabled={indexState === 'indexing'}
            data-testid="index-failures-btn"
            className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold border transition shadow-sm ${
              indexState === 'indexing'
                ? 'bg-amber-950/40 text-amber-300 border-amber-700/60 cursor-wait'
                : indexState === 'success'
                ? 'bg-emerald-950/50 text-emerald-300 border-emerald-700/60'
                : indexState === 'no_findings'
                ? 'bg-slate-800 text-slate-300 border-slate-700'
                : indexState === 'error'
                ? 'bg-rose-950/50 text-rose-300 border-rose-700/60'
                : 'bg-indigo-950/40 hover:bg-indigo-900/50 text-indigo-300 border-indigo-700/60'
            }`}
            title="Index trace failures into pgvector for historical similarity search"
          >
            <span>{indexState === 'indexing' ? '⏳' : indexState === 'success' ? '✓' : indexState === 'error' ? '⚠️' : '📥'}</span>
            <span>
              {indexState === 'indexing'
                ? 'Indexing...'
                : indexState === 'success'
                ? `Indexed (${indexedCount})`
                : indexState === 'no_findings'
                ? 'Clean (0)'
                : indexState === 'error'
                ? 'Index Error'
                : 'Index Failures'}
            </span>
          </button>
        </div>

        <div className="flex items-center gap-3 text-xs text-slate-400 font-mono">
          <span className="text-slate-500">Trace ID:</span>
          <span className="bg-slate-950 px-2 py-1 rounded border border-slate-800 text-slate-300 select-all">
            {trace.trace_id}
          </span>
        </div>
      </div>

      {/* Metrics Row: Developer-tool summary cards */}
      <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-8 gap-2">
        <div className="bg-slate-950/60 border border-slate-800/80 rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Duration</div>
          <div className="text-sm font-semibold text-slate-200 mt-0.5 font-mono">
            {formatDuration(trace.duration_ms ?? meta.duration_ms)}
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Events</div>
          <div className="text-sm font-semibold text-slate-200 mt-0.5 font-mono">
            {meta.total_event_count}
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-blue-400 font-medium">LLM Calls</div>
          <div className="text-sm font-semibold text-blue-300 mt-0.5 font-mono">
            {meta.llm_call_count}
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-emerald-400 font-medium">Tool Calls</div>
          <div className="text-sm font-semibold text-emerald-300 mt-0.5 font-mono">
            {meta.tool_call_count}
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-rose-400 font-medium">Errors</div>
          <div className={`text-sm font-semibold mt-0.5 font-mono ${meta.error_count > 0 ? 'text-rose-400 font-bold' : 'text-slate-400'}`}>
            {meta.error_count}
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-orange-400 font-medium">Retries</div>
          <div className="text-sm font-semibold text-orange-300 mt-0.5 font-mono">
            {meta.retry_count}
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-amber-400 font-medium">State Changes</div>
          <div className="text-sm font-semibold text-amber-300 mt-0.5 font-mono">
            {meta.state_change_count}
          </div>
        </div>

        <div className="bg-slate-950/60 border border-slate-800/80 rounded p-2">
          <div className="text-[10px] uppercase tracking-wider text-slate-400 font-medium">Lifecycle</div>
          <div className="text-xs font-semibold mt-1 font-mono flex items-center gap-1">
            {meta.is_complete ? (
              <span className="text-emerald-400 flex items-center gap-1">
                <span>✓</span> Complete
              </span>
            ) : (
              <span className="text-amber-400 flex items-center gap-1">
                <span>⚠</span> Incomplete
              </span>
            )}
          </div>
        </div>
      </div>

      {/* Timing footer */}
      <div className="mt-2.5 flex items-center gap-4 text-[11px] text-slate-400 font-mono">
        <div>
          <span className="text-slate-500">Start:</span>{' '}
          {formatDateTime(trace.start_time)} ({formatTimeWithMs(trace.start_time)})
        </div>
        {trace.end_time && (
          <div>
            <span className="text-slate-500">End:</span>{' '}
            {formatDateTime(trace.end_time)} ({formatTimeWithMs(trace.end_time)})
          </div>
        )}
      </div>
    </div>
  );
}
