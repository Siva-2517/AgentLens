import { useState, useMemo } from 'react';
import { TraceSummary } from '../../types/trace';
import {
  formatDuration,
  formatDateTime,
} from '../../utils/formatters';

interface TraceListProps {
  traces: TraceSummary[];
  selectedTraceId: string | null;
  onSelectTrace: (traceId: string) => void;
  isLoading: boolean;
  error: string | null;
  onRefresh: () => void;
}

export function TraceList({
  traces,
  selectedTraceId,
  onSelectTrace,
  isLoading,
  error,
  onRefresh,
}: TraceListProps) {
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<string>('all');

  // Filter traces by search query and status
  const filteredTraces = useMemo(() => {
    return traces.filter((trace) => {
      const matchesSearch =
        searchQuery === '' ||
        trace.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        trace.trace_id.toLowerCase().includes(searchQuery.toLowerCase()) ||
        (trace.project_name &&
          trace.project_name.toLowerCase().includes(searchQuery.toLowerCase()));

      const matchesStatus =
        statusFilter === 'all' ||
        trace.status.toLowerCase() === statusFilter.toLowerCase();

      return matchesSearch && matchesStatus;
    });
  }, [traces, searchQuery, statusFilter]);

  const getStatusBadge = (status: string) => {
    const s = status.toLowerCase();
    if (s === 'completed') {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/40 border border-emerald-800/40 px-1.5 py-0.5 rounded">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
          completed
        </span>
      );
    }
    if (s === 'failed') {
      return (
        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-rose-400 bg-rose-950/40 border border-rose-800/40 px-1.5 py-0.5 rounded">
          <span className="w-1.5 h-1.5 rounded-full bg-rose-400" />
          failed
        </span>
      );
    }
    return (
      <span className="inline-flex items-center gap-1 text-[11px] font-medium text-amber-400 bg-amber-950/40 border border-amber-800/40 px-1.5 py-0.5 rounded">
        <span className="w-1.5 h-1.5 rounded-full bg-amber-400 animate-pulse" />
        running
      </span>
    );
  };

  return (
    <aside className="w-80 lg:w-96 h-full flex flex-col bg-slate-900 border-r border-slate-800 shrink-0">
      {/* Top Header */}
      <div className="p-3 border-b border-slate-800 flex items-center justify-between">
        <div>
          <h2 className="text-sm font-semibold text-slate-100 uppercase tracking-wider">
            Traces ({filteredTraces.length})
          </h2>
          <span className="text-[11px] text-slate-400">Recorded AI Agent Runs</span>
        </div>
        <button
          onClick={onRefresh}
          disabled={isLoading}
          className="text-xs bg-slate-800 hover:bg-slate-700 text-slate-300 px-2.5 py-1 rounded border border-slate-700 transition disabled:opacity-50 flex items-center gap-1"
          title="Reload traces from backend"
        >
          <span>↻</span> Refresh
        </button>
      </div>

      {/* Search & Filter Bar */}
      <div className="p-3 border-b border-slate-800 space-y-2 bg-slate-900/50">
        <div className="relative">
          <input
            type="text"
            placeholder="Search by ID or name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full bg-slate-950 border border-slate-800 rounded px-3 py-1.5 text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-purple-500"
          />
          {searchQuery && (
            <button
              onClick={() => setSearchQuery('')}
              className="absolute right-2 top-1.5 text-xs text-slate-500 hover:text-slate-300"
            >
              ✕
            </button>
          )}
        </div>

        {/* Filter buttons */}
        <div className="flex gap-1">
          {['all', 'completed', 'running', 'failed'].map((status) => (
            <button
              key={status}
              onClick={() => setStatusFilter(status)}
              className={`px-2 py-0.5 text-[11px] rounded capitalize transition ${
                statusFilter === status
                  ? 'bg-purple-900/60 text-purple-200 border border-purple-600/50 font-medium'
                  : 'bg-slate-950 text-slate-400 border border-slate-800 hover:text-slate-200'
              }`}
            >
              {status}
            </button>
          ))}
        </div>
      </div>

      {/* Trace List Body */}
      <div className="flex-1 overflow-y-auto divide-y divide-slate-800/60">
        {isLoading && traces.length === 0 && (
          <div className="p-8 text-center text-xs text-slate-400">
            <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mx-auto mb-2" />
            Loading traces...
          </div>
        )}

        {error && (
          <div className="p-4 m-3 rounded bg-rose-950/30 border border-rose-800/40 text-rose-300 text-xs">
            <p className="font-semibold mb-1">Failed to load traces</p>
            <p className="text-[11px] text-rose-400">{error}</p>
            <button
              onClick={onRefresh}
              className="mt-2 text-[11px] underline hover:text-rose-200"
            >
              Retry
            </button>
          </div>
        )}

        {!isLoading && !error && filteredTraces.length === 0 && (
          <div className="p-8 text-center text-slate-500 text-xs">
            {searchQuery || statusFilter !== 'all' ? (
              <p>No traces match the search or filter criteria.</p>
            ) : (
              <p>No traces recorded yet in AgentLens.</p>
            )}
          </div>
        )}

        {filteredTraces.map((trace) => {
          const isSelected = selectedTraceId === trace.trace_id;
          return (
            <div
              key={trace.trace_id}
              onClick={() => onSelectTrace(trace.trace_id)}
              className={`p-3 cursor-pointer transition-colors ${
                isSelected
                  ? 'bg-purple-950/30 border-l-4 border-l-purple-500'
                  : 'hover:bg-slate-800/50'
              }`}
            >
              {/* Row 1: Name and Status */}
              <div className="flex items-center justify-between gap-2 mb-1">
                <span
                  className="font-medium text-xs text-slate-100 truncate"
                  title={trace.name}
                >
                  {trace.name || 'Unnamed Trace'}
                </span>
                {getStatusBadge(trace.status)}
              </div>

              {/* Row 2: Trace ID */}
              <div className="text-[11px] font-mono text-slate-400 truncate mb-1">
                {trace.trace_id}
              </div>

              {/* Row 3: Metrics (Time, Duration, Events) */}
              <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
                <span>{formatDateTime(trace.start_time)}</span>
                <div className="flex items-center gap-2">
                  <span>{formatDuration(trace.duration_ms)}</span>
                  <span className="text-slate-500">•</span>
                  <span>{trace.event_count} evts</span>
                </div>
              </div>

              {trace.project_name && (
                <div className="mt-1 text-[10px] text-slate-500 font-mono truncate">
                  project: {trace.project_name}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </aside>
  );
}
