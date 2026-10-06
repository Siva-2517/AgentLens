import { memo } from 'react';
import { Handle, Position, NodeProps, Node } from '@xyflow/react';
import { FlowNodeData } from '../../types/trace';
import {
  getEventTypeConfig,
  formatDuration,
  formatTimeWithMs,
} from '../../utils/formatters';

export const GraphNode = memo(({ data }: NodeProps<Node<FlowNodeData>>) => {
  const node = data.rawNode;
  const isSelected = data.isSelected;
  const config = getEventTypeConfig(node.event_type);
  const timeStr = formatTimeWithMs(node.timestamp);
  const durationStr = formatDuration(node.duration_ms);

  return (
    <div
      className={`relative min-w-[220px] max-w-[280px] rounded-lg border px-3 py-2.5 shadow-lg backdrop-blur transition-all duration-150 cursor-pointer ${
        config.cardBg
      } ${
        isSelected
          ? 'border-purple-400 ring-2 ring-purple-500/50 shadow-purple-500/20'
          : config.cardBorder
      }`}
    >
      {/* React Flow handles for edge connection */}
      <Handle
        type="target"
        position={Position.Top}
        className="!w-2 !h-2 !bg-slate-500 !border-slate-800"
      />
      <Handle
        type="source"
        position={Position.Bottom}
        className="!w-2 !h-2 !bg-slate-500 !border-slate-800"
      />

      {/* Header: Event Type Badge & Status/Duration */}
      <div className="flex items-center justify-between gap-1.5 mb-1.5">
        <span
          className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded text-[11px] font-semibold tracking-wide uppercase ${config.badgeBg} ${config.badgeText}`}
        >
          <span>{config.icon}</span>
          <span>{config.displayName}</span>
        </span>

        {node.duration_ms !== null && node.duration_ms !== undefined && (
          <span className="text-[11px] font-mono text-slate-300 bg-slate-800/90 px-1.5 py-0.5 rounded border border-slate-700/50">
            {durationStr}
          </span>
        )}
      </div>

      {/* Node label / title */}
      <div className="text-xs font-medium text-slate-100 truncate mb-1" title={node.label}>
        {node.label || config.displayName}
      </div>

      {/* Footer: Timestamp & Depth */}
      <div className="flex items-center justify-between text-[10px] text-slate-400 font-mono">
        <span>{timeStr}</span>
        {node.depth > 0 && (
          <span className="text-slate-500">depth: {node.depth}</span>
        )}
      </div>

      {/* Error flag if present */}
      {node.event_type === 'ERROR' && (
        <div className="mt-1.5 pt-1.5 border-t border-rose-800/50 text-[11px] text-rose-300 flex items-center gap-1 font-medium">
          <span>Failed Execution</span>
        </div>
      )}
    </div>
  );
});

GraphNode.displayName = 'GraphNode';
