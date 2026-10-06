import { useMemo, useCallback } from 'react';
import {
  ReactFlow,
  Background,
  BackgroundVariant,
  NodeMouseHandler,
  Node,
  useReactFlow,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import { ExecutionGraph, ExecutionGraphNode, FlowNodeData } from '../../types/trace';
import { transformGraphToFlow } from '../../utils/graphAdapter';
import { GraphNode } from './GraphNode';

interface TraceGraphProps {
  graph: ExecutionGraph | null;
  selectedNodeId: string | null;
  onSelectNode: (node: ExecutionGraphNode) => void;
  onClearSelection: () => void;
}

/** Pure Tailwind zoom and fit-view toolbar using useReactFlow hook */
function CustomGraphControls() {
  const { zoomIn, zoomOut, fitView } = useReactFlow();

  return (
    <div className="absolute bottom-4 left-4 z-10 flex flex-col gap-1 p-1 bg-slate-900/90 backdrop-blur border border-slate-800 rounded-lg shadow-xl">
      <button
        type="button"
        onClick={() => zoomIn({ duration: 250 })}
        title="Zoom In"
        aria-label="Zoom In"
        className="w-7 h-7 flex items-center justify-center bg-slate-800/90 hover:bg-slate-700 text-slate-100 hover:text-white rounded border border-slate-700/60 hover:border-slate-600 transition shadow-sm active:scale-95"
      >
        <svg
          className="w-3.5 h-3.5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="12" y1="5" x2="12" y2="19" />
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      </button>
      <button
        type="button"
        onClick={() => zoomOut({ duration: 250 })}
        title="Zoom Out"
        aria-label="Zoom Out"
        className="w-7 h-7 flex items-center justify-center bg-slate-800/90 hover:bg-slate-700 text-slate-100 hover:text-white rounded border border-slate-700/60 hover:border-slate-600 transition shadow-sm active:scale-95"
      >
        <svg
          className="w-3.5 h-3.5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <line x1="5" y1="12" x2="19" y2="12" />
        </svg>
      </button>
      <button
        type="button"
        onClick={() => fitView({ padding: 0.2, duration: 350 })}
        title="Fit View"
        aria-label="Fit View"
        className="w-7 h-7 flex items-center justify-center bg-slate-800/90 hover:bg-slate-700 text-slate-100 hover:text-white rounded border border-slate-700/60 hover:border-slate-600 transition shadow-sm active:scale-95"
      >
        <svg
          className="w-3.5 h-3.5"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <path d="M8 3H5a2 2 0 0 0-2 2v3m18 0V5a2 2 0 0 0-2-2h-3m0 18h3a2 2 0 0 0 2-2v-3M3 16v3a2 2 0 0 0 2 2h3" />
        </svg>
      </button>
    </div>
  );
}

export function TraceGraph({
  graph,
  selectedNodeId,
  onSelectNode,
  onClearSelection,
}: TraceGraphProps) {
  // Register custom node type map
  const nodeTypes = useMemo(
    () => ({
      executionNode: GraphNode,
    }),
    []
  );

  // Transform graph data into React Flow nodes and edges
  const { nodes, edges } = useMemo(() => {
    if (!graph) return { nodes: [], edges: [] };
    return transformGraphToFlow(graph, selectedNodeId);
  }, [graph, selectedNodeId]);

  // Handle node click
  const handleNodeClick: NodeMouseHandler<Node<FlowNodeData>> = useCallback(
    (_, node) => {
      if (node.data?.rawNode) {
        onSelectNode(node.data.rawNode);
      }
    },
    [onSelectNode]
  );

  // Handle canvas background click
  const handlePaneClick = useCallback(() => {
    onClearSelection();
  }, [onClearSelection]);

  if (!graph || graph.nodes.length === 0) {
    return (
      <div className="h-full w-full flex flex-col items-center justify-center p-8 text-center bg-slate-950 text-slate-400">
        <div className="w-12 h-12 rounded-full bg-slate-900 border border-slate-800 flex items-center justify-center text-xl mb-3 text-slate-500">
          ∅
        </div>
        <p className="text-sm font-medium text-slate-300">No execution steps in graph</p>
        <p className="text-xs text-slate-500 mt-1">This trace does not contain any recorded execution events.</p>
      </div>
    );
  }

  return (
    <div className="h-full w-full relative bg-slate-950 select-none">
      <ReactFlow
        nodes={nodes}
        edges={edges}
        nodeTypes={nodeTypes}
        onNodeClick={handleNodeClick}
        onPaneClick={handlePaneClick}
        fitView
        fitViewOptions={{ padding: 0.2 }}
        minZoom={0.2}
        maxZoom={2}
        colorMode="dark"
        proOptions={{ hideAttribution: true }}
      >
        <Background
          variant={BackgroundVariant.Dots}
          gap={18}
          size={1}
          color="#334155"
          className="opacity-40"
        />
        <CustomGraphControls />
      </ReactFlow>

      {/* Graph metadata overlay badge */}
      <div className="absolute top-4 left-4 z-10 bg-slate-900/90 backdrop-blur border border-slate-800 rounded-md px-3 py-1.5 shadow-md flex items-center gap-3 text-xs text-slate-300 font-mono pointer-events-none">
        <span className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
          <span>Execution Graph</span>
        </span>
        <span className="text-slate-600">|</span>
        <span>{graph.node_count} nodes</span>
        <span className="text-slate-600">|</span>
        <span>{graph.edge_count} edges</span>
      </div>
    </div>
  );
}
