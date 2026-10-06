import { Node, Edge, MarkerType } from '@xyflow/react';
import { ExecutionGraph, ExecutionGraphNode, FlowNodeData } from '../types/trace';

export interface GraphLayoutOptions {
  rowHeight?: number;
  depthIndent?: number;
  startX?: number;
  startY?: number;
}

const DEFAULT_OPTIONS: Required<GraphLayoutOptions> = {
  rowHeight: 125,
  depthIndent: 200,
  startX: 40,
  startY: 40,
};

/**
 * Transforms backend ExecutionGraph into React Flow Node[] and Edge[].
 *
 * Employs a deterministic waterfall layout:
 * - Chronological sequence determines vertical position (Y axis)
 * - Tree nesting depth determines horizontal indentation (X axis)
 * - Guaranteed zero overlap and intuitive agent execution flow
 */
export function transformGraphToFlow(
  graph: ExecutionGraph,
  selectedNodeId: string | null = null,
  options: GraphLayoutOptions = {}
): { nodes: Node<FlowNodeData>[]; edges: Edge[] } {
  const opts = { ...DEFAULT_OPTIONS, ...options };

  if (!graph || !graph.nodes) {
    return { nodes: [], edges: [] };
  }

  // Map nodes with deterministic coordinates
  const nodes: Node<FlowNodeData>[] = graph.nodes.map((node: ExecutionGraphNode, index: number) => {
    const x = opts.startX + (node.depth || 0) * opts.depthIndent;
    const y = opts.startY + index * opts.rowHeight;

    return {
      id: node.id,
      type: 'executionNode',
      position: { x, y },
      data: {
        rawNode: node,
        isSelected: selectedNodeId === node.id,
      },
    };
  });

  // Map edges with professional styling and arrows
  const edges: Edge[] = (graph.edges || []).map((edge) => {
    const isParentSelected = selectedNodeId === edge.source;
    const isTargetSelected = selectedNodeId === edge.target;
    const isHighlighted = isParentSelected || isTargetSelected;

    return {
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: 'smoothstep',
      animated: isHighlighted,
      style: {
        stroke: isHighlighted ? '#a855f7' : '#475569',
        strokeWidth: isHighlighted ? 2.5 : 1.75,
        opacity: isHighlighted ? 1 : 0.75,
      },
      markerEnd: {
        type: MarkerType.ArrowClosed,
        color: isHighlighted ? '#a855f7' : '#64748b',
        width: 14,
        height: 14,
      },
    };
  });

  return { nodes, edges };
}
