import { useState } from 'react';
import { ExecutionGraphNode } from '../../types/trace';
import {
  getEventTypeConfig,
  formatDuration,
  formatTimeWithMs,
  formatDateTime,
} from '../../utils/formatters';

interface EventDetailsProps {
  node: ExecutionGraphNode;
  onClose: () => void;
}

export function EventDetails({ node, onClose }: EventDetailsProps) {
  const [activeTab, setActiveTab] = useState<'data' | 'metadata' | 'raw'>('data');
  const [copied, setCopied] = useState<boolean>(false);

  const config = getEventTypeConfig(node.event_type);

  const handleCopyJson = (content: unknown) => {
    navigator.clipboard.writeText(JSON.stringify(content, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="h-full flex flex-col bg-slate-900 border-l border-slate-800 shadow-2xl text-slate-200 w-full sm:w-[420px] lg:w-[480px] shrink-0">
      {/* Header */}
      <div className="p-4 border-b border-slate-800 flex items-start justify-between gap-3 bg-slate-900/90 backdrop-blur">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded text-xs font-semibold uppercase ${config.badgeBg} ${config.badgeText}`}
            >
              <span>{config.icon}</span>
              <span>{config.displayName}</span>
            </span>
            {node.duration_ms !== null && node.duration_ms !== undefined && (
              <span className="text-xs font-mono text-slate-300 bg-slate-800 px-2 py-0.5 rounded border border-slate-700">
                {formatDuration(node.duration_ms)}
              </span>
            )}
          </div>
          <h3 className="text-sm font-semibold text-slate-100 truncate" title={node.label}>
            {node.label}
          </h3>
        </div>

        <button
          onClick={onClose}
          className="text-slate-400 hover:text-slate-200 p-1.5 rounded hover:bg-slate-800 transition"
          aria-label="Close event details"
        >
          ✕
        </button>
      </div>

      {/* Metadata properties table */}
      <div className="p-4 border-b border-slate-800 bg-slate-950/40 space-y-2 text-xs font-mono">
        <div className="flex justify-between items-center py-0.5">
          <span className="text-slate-400">Event ID</span>
          <span className="text-slate-200 select-all font-semibold">{node.event_id}</span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-slate-400">Trace ID</span>
          <span className="text-slate-300 select-all">{node.trace_id}</span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-slate-400">Timestamp</span>
          <span className="text-slate-300">
            {formatDateTime(node.timestamp)} ({formatTimeWithMs(node.timestamp)})
          </span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-slate-400">Parent Event ID</span>
          <span className="text-slate-300 font-mono">
            {node.parent_event_id || <span className="text-slate-500 italic">None (Root)</span>}
          </span>
        </div>
        <div className="flex justify-between items-center py-0.5">
          <span className="text-slate-400">Hierarchy Depth</span>
          <span className="text-slate-300">{node.depth}</span>
        </div>
        {node.status && (
          <div className="flex justify-between items-center py-0.5">
            <span className="text-slate-400">Outcome Status</span>
            <span className="text-slate-200 font-semibold">{node.status}</span>
          </div>
        )}
      </div>

      {/* Payload Inspection Tabs */}
      <div className="flex items-center justify-between px-4 pt-3 border-b border-slate-800 bg-slate-900">
        <div className="flex gap-2">
          <button
            onClick={() => setActiveTab('data')}
            className={`pb-2 px-1 text-xs font-medium border-b-2 transition ${
              activeTab === 'data'
                ? 'border-purple-500 text-purple-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Payload Data ({Object.keys(node.data || {}).length})
          </button>
          <button
            onClick={() => setActiveTab('metadata')}
            className={`pb-2 px-1 text-xs font-medium border-b-2 transition ${
              activeTab === 'metadata'
                ? 'border-purple-500 text-purple-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Metadata ({Object.keys(node.metadata || {}).length})
          </button>
          <button
            onClick={() => setActiveTab('raw')}
            className={`pb-2 px-1 text-xs font-medium border-b-2 transition ${
              activeTab === 'raw'
                ? 'border-purple-500 text-purple-300'
                : 'border-transparent text-slate-400 hover:text-slate-200'
            }`}
          >
            Raw Node
          </button>
        </div>

        <button
          onClick={() =>
            handleCopyJson(
              activeTab === 'data'
                ? node.data
                : activeTab === 'metadata'
                ? node.metadata
                : node
            )
          }
          className="text-[11px] font-mono text-slate-400 hover:text-purple-300 pb-2 flex items-center gap-1"
        >
          {copied ? '✓ Copied' : 'Copy JSON'}
        </button>
      </div>

      {/* JSON Viewer Body */}
      <div className="flex-1 overflow-auto p-4 bg-slate-950 font-mono text-xs">
        {activeTab === 'data' && (
          Object.keys(node.data || {}).length === 0 ? (
            <div className="text-slate-500 italic p-4 text-center">No data payload provided for this event.</div>
          ) : (
            <pre className="text-emerald-400 whitespace-pre-wrap break-all leading-relaxed">
              {JSON.stringify(node.data, null, 2)}
            </pre>
          )
        )}

        {activeTab === 'metadata' && (
          Object.keys(node.metadata || {}).length === 0 ? (
            <div className="text-slate-500 italic p-4 text-center">No metadata attributes attached.</div>
          ) : (
            <pre className="text-sky-300 whitespace-pre-wrap break-all leading-relaxed">
              {JSON.stringify(node.metadata, null, 2)}
            </pre>
          )
        )}

        {activeTab === 'raw' && (
          <pre className="text-amber-300 whitespace-pre-wrap break-all leading-relaxed">
            {JSON.stringify(node, null, 2)}
          </pre>
        )}
      </div>
    </div>
  );
}
