import { useState, useEffect, useCallback } from 'react';
import axios from 'axios';
import {
  TraceSummary,
  ReconstructedTrace,
  ExecutionGraph,
  ExecutionGraphNode,
} from './types/trace';
import {
  RealtimeMessage,
  RealtimeConnectionState,
} from './types/realtime';
import { InvestigationResult } from './types/investigation';
import { TraceComparisonResult } from './types/comparison';
import {
  getTraces,
  getTrace,
  getTraceGraph,
  getTraceInvestigation,
  compareTraces,
  formatApiError,
} from './services/api';
import { RealtimeClient } from './services/realtime';
import { Header } from './components/layout/Header';
import { TraceList } from './components/traces/TraceList';
import { TraceOverview } from './components/traces/TraceOverview';
import { TraceGraph } from './components/traces/TraceGraph';
import { EventDetails } from './components/traces/EventDetails';
import { InvestigationPanel } from './components/traces/InvestigationPanel';
import { TraceComparisonView } from './components/traces/TraceComparisonView';
import { HistoricalSearchView } from './components/traces/HistoricalSearchView';

export function App() {
  const [apiStatus, setApiStatus] = useState<'healthy' | 'checking' | 'offline'>('checking');
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [isTracesLoading, setIsTracesLoading] = useState<boolean>(true);
  const [tracesError, setTracesError] = useState<string | null>(null);

  const [selectedTraceId, setSelectedTraceId] = useState<string | null>(null);
  const [selectedTrace, setSelectedTrace] = useState<ReconstructedTrace | null>(null);
  const [selectedGraph, setSelectedGraph] = useState<ExecutionGraph | null>(null);
  const [isDetailLoading, setIsDetailLoading] = useState<boolean>(false);
  const [detailError, setDetailError] = useState<string | null>(null);

  const [selectedNode, setSelectedNode] = useState<ExecutionGraphNode | null>(null);
  const [realtimeState, setRealtimeState] = useState<RealtimeConnectionState>('disconnected');

  const [investigation, setInvestigation] = useState<InvestigationResult | null>(null);
  const [isInvestigationLoading, setIsInvestigationLoading] = useState<boolean>(false);
  const [investigationError, setInvestigationError] = useState<string | null>(null);
  const [isInvestigationOpen, setIsInvestigationOpen] = useState<boolean>(false);
  const [activeRightTab, setActiveRightTab] = useState<'investigation' | 'event'>('investigation');

  // Phase 14 & 15: Trace Replay, Run Comparison, and Historical Failure Search State
  const [viewMode, setViewMode] = useState<'trace' | 'compare' | 'search'>('trace');
  const [traceAId, setTraceAId] = useState<string | null>(null);
  const [traceBId, setTraceBId] = useState<string | null>(null);
  const [comparison, setComparison] = useState<TraceComparisonResult | null>(null);
  const [isComparisonLoading, setIsComparisonLoading] = useState<boolean>(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  // Fetch Run Comparison
  const fetchComparison = useCallback(async (idA: string, idB: string) => {
    if (!idA || !idB || idA === idB) return;
    setIsComparisonLoading(true);
    setComparisonError(null);
    try {
      const data = await compareTraces(idA, idB);
      setComparison(data);
    } catch (err) {
      setComparisonError(formatApiError(err));
      setComparison(null);
    } finally {
      setIsComparisonLoading(false);
    }
  }, []);

  // Fetch AI investigation
  const fetchInvestigation = useCallback(async (traceId: string) => {
    setIsInvestigationLoading(true);
    setInvestigationError(null);
    try {
      const data = await getTraceInvestigation(traceId);
      setInvestigation(data);
    } catch (err) {
      setInvestigationError(formatApiError(err));
      setInvestigation(null);
    } finally {
      setIsInvestigationLoading(false);
    }
  }, []);

  // Health check
  useEffect(() => {
    axios
      .get('/health')
      .then((res) => {
        if (res.data?.status === 'healthy') {
          setApiStatus('healthy');
        } else {
          setApiStatus('checking');
        }
      })
      .catch(() => {
        // Try direct backend port if proxy or test env differs
        fetch('http://localhost:8000/health')
          .then((res) => res.json())
          .then((data) => setApiStatus(data.status === 'healthy' ? 'healthy' : 'checking'))
          .catch(() => setApiStatus('offline'));
      });
  }, []);

  // Fetch traces list
  const fetchTraces = useCallback(async () => {
    setIsTracesLoading(true);
    setTracesError(null);
    try {
      const data = await getTraces();
      setTraces(data);
      // Auto-select first trace if none is selected yet and traces exist
      if (data.length > 0 && !selectedTraceId) {
        setSelectedTraceId(data[0].trace_id);
      }
      if (data.length > 0 && !traceAId) {
        setTraceAId(data[0].trace_id);
      }
      if (data.length > 1 && !traceBId) {
        setTraceBId(data[1].trace_id);
      }
    } catch (err) {
      setTracesError(formatApiError(err));
    } finally {
      setIsTracesLoading(false);
    }
  }, [selectedTraceId, traceAId, traceBId]);

  useEffect(() => {
    fetchTraces();
  }, [fetchTraces]);

  // Load trace details & graph when selectedTraceId changes
  useEffect(() => {
    if (!selectedTraceId) {
      setSelectedTrace(null);
      setSelectedGraph(null);
      setSelectedNode(null);
      setInvestigation(null);
      setInvestigationError(null);
      setIsInvestigationOpen(false);
      return;
    }

    let isMounted = true;
    setIsDetailLoading(true);
    setDetailError(null);
    setSelectedNode(null); // Clear selected event node on trace change

    // Fetch AI investigation asynchronously (does not block trace/graph rendering)
    fetchInvestigation(selectedTraceId);

    Promise.all([
      getTrace(selectedTraceId),
      getTraceGraph(selectedTraceId),
    ])
      .then(([traceData, graphData]) => {
        if (!isMounted) return;
        setSelectedTrace(traceData);
        setSelectedGraph(graphData);
        // Automatically open investigation panel if trace failed or has errors
        if (traceData.status === 'failed' || (traceData.metadata?.error_count ?? 0) > 0) {
          setIsInvestigationOpen(true);
          setActiveRightTab('investigation');
        }
      })
      .catch((err) => {
        if (!isMounted) return;
        setDetailError(formatApiError(err));
        setSelectedTrace(null);
        setSelectedGraph(null);
      })
      .finally(() => {
        if (isMounted) {
          setIsDetailLoading(false);
        }
      });

    return () => {
      isMounted = false;
    };
  }, [selectedTraceId, fetchInvestigation]);

  // Handle incoming real-time WebSocket messages
  const handleRealtimeMessage = useCallback((msg: RealtimeMessage) => {
    if (msg.type === 'trace_started') {
      setSelectedTrace((prev) => {
        if (!prev || prev.trace_id !== msg.trace_id) return prev;
        return { ...prev, status: msg.status || 'running' };
      });
    } else if (msg.type === 'trace_completed') {
      setSelectedTrace((prev) => {
        if (!prev || prev.trace_id !== msg.trace_id) return prev;
        return {
          ...prev,
          status: msg.status || 'completed',
          end_time: msg.end_time || prev.end_time,
          duration_ms: msg.duration_ms ?? prev.duration_ms,
          metadata: {
            ...prev.metadata,
            duration_ms: msg.duration_ms ?? prev.metadata.duration_ms,
            is_complete: msg.status === 'completed',
          },
        };
      });
    } else if (msg.type === 'event_created') {
      const rawEvt = msg.event;
      if (!rawEvt) return;

      // 1. Update trace events and metadata counters
      setSelectedTrace((prev) => {
        if (!prev || prev.trace_id !== msg.trace_id) return prev;
        // Avoid duplicate events
        if (prev.events.some((e) => e.event_id === rawEvt.event_id)) {
          return prev;
        }

        const updatedEvents = [
          ...prev.events,
          {
            event_id: rawEvt.event_id,
            trace_id: rawEvt.trace_id,
            parent_event_id: rawEvt.parent_event_id,
            event_type: rawEvt.event_type,
            timestamp: rawEvt.timestamp,
            agent_name: prev.name,
            data: rawEvt.data,
            metadata: rawEvt.metadata,
            depth: rawEvt.depth ?? 0,
            children_ids: [],
            duration_ms: rawEvt.duration_ms ?? null,
          },
        ];

        const normType = rawEvt.event_type.toUpperCase();
        const updatedMeta = { ...prev.metadata };
        updatedMeta.total_event_count += 1;
        if (normType === 'LLM_CALL') updatedMeta.llm_call_count += 1;
        if (normType === 'LLM_RESPONSE') updatedMeta.llm_response_count += 1;
        if (normType === 'TOOL_CALL') updatedMeta.tool_call_count += 1;
        if (normType === 'TOOL_RESPONSE') updatedMeta.tool_response_count += 1;
        if (normType === 'ERROR') updatedMeta.error_count += 1;
        if (normType === 'RETRY') updatedMeta.retry_count += 1;
        if (normType === 'STATE_CHANGE') updatedMeta.state_change_count += 1;
        if (normType === 'AGENT_START') updatedMeta.has_agent_start = true;
        if (normType === 'AGENT_END') {
          updatedMeta.has_agent_end = true;
          updatedMeta.is_complete = true;
        }
        updatedMeta.last_event_timestamp = rawEvt.timestamp;
        updatedMeta.event_type_counts = {
          ...updatedMeta.event_type_counts,
          [normType]: (updatedMeta.event_type_counts[normType] || 0) + 1,
        };

        return {
          ...prev,
          event_count: updatedEvents.length,
          events: updatedEvents,
          metadata: updatedMeta,
        };
      });

      // 2. Incrementally update execution graph nodes & edges
      setSelectedGraph((prevGraph) => {
        if (!prevGraph || prevGraph.trace_id !== msg.trace_id) return prevGraph;
        if (prevGraph.nodes.some((n) => n.id === rawEvt.event_id)) {
          return prevGraph;
        }

        let depth = rawEvt.depth ?? 0;
        if (rawEvt.parent_event_id) {
          const parentNode = prevGraph.nodes.find((n) => n.id === rawEvt.parent_event_id);
          if (parentNode) {
            depth = parentNode.depth + 1;
          }
        }

        let label = rawEvt.event_type.replace(/_/g, ' ');
        const normType = rawEvt.event_type.toUpperCase();
        if (normType === 'TOOL_CALL') {
          const toolName = rawEvt.data?.name || rawEvt.data?.tool || 'tool';
          label = `Tool: ${toolName}`;
        } else if (normType === 'LLM_CALL') {
          const model = rawEvt.data?.model;
          label = model ? `LLM Call (${model})` : 'LLM Call';
        } else if (normType === 'ERROR') {
          label = 'Execution Error';
        }

        const newNode: ExecutionGraphNode = {
          id: rawEvt.event_id,
          event_id: rawEvt.event_id,
          trace_id: rawEvt.trace_id,
          event_type: rawEvt.event_type,
          label,
          timestamp: rawEvt.timestamp,
          parent_event_id: rawEvt.parent_event_id,
          depth,
          duration_ms: rawEvt.duration_ms ?? null,
          status: normType === 'ERROR' ? 'failed' : null,
          data: rawEvt.data || {},
          metadata: rawEvt.metadata || {},
        };

        const updatedEdges = [...prevGraph.edges];
        if (rawEvt.parent_event_id) {
          const edgeId = `edge_${rawEvt.parent_event_id}_${rawEvt.event_id}`;
          if (!updatedEdges.some((e) => e.id === edgeId)) {
            updatedEdges.push({
              id: edgeId,
              source: rawEvt.parent_event_id,
              target: rawEvt.event_id,
              relationship: 'parent-child',
            });
          }
        }

        return {
          ...prevGraph,
          nodes: [...prevGraph.nodes, newNode],
          edges: updatedEdges,
          node_count: prevGraph.nodes.length + 1,
          edge_count: updatedEdges.length,
        };
      });

      // 3. Update inspected event details if this node is currently selected
      setSelectedNode((curr) => {
        if (curr && curr.id === rawEvt.event_id) {
          return {
            ...curr,
            data: rawEvt.data || curr.data,
            metadata: rawEvt.metadata || curr.metadata,
            duration_ms: rawEvt.duration_ms ?? curr.duration_ms,
          };
        }
        return curr;
      });
    }
  }, []);

  // Real-time WebSocket connection lifecycle
  useEffect(() => {
    if (!selectedTraceId) {
      setRealtimeState('disconnected');
      return;
    }

    const client = new RealtimeClient({
      traceId: selectedTraceId,
      onStateChange: (state) => setRealtimeState(state),
      onMessage: handleRealtimeMessage,
    });

    client.connect();

    return () => {
      client.disconnect();
    };
  }, [selectedTraceId, handleRealtimeMessage]);

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-950 text-slate-100 overflow-hidden font-sans">
      {/* Top Header */}
      <Header
        apiStatus={apiStatus}
        selectedTraceId={selectedTraceId}
        activeView={viewMode}
        onSelectView={(mode) => {
          setViewMode(mode);
          if (mode === 'compare' && !comparison && traceAId && traceBId && traceAId !== traceBId) {
            fetchComparison(traceAId, traceBId);
          }
        }}
      />

      {/* Main Workspace */}
      <div className="flex-1 flex min-h-0 overflow-hidden">
        {viewMode === 'compare' ? (
          <TraceComparisonView
            traces={traces}
            comparison={comparison}
            isLoading={isComparisonLoading}
            error={comparisonError}
            selectedTraceAId={traceAId}
            selectedTraceBId={traceBId}
            onSelectTraceA={(id) => {
              setTraceAId(id);
              setComparison(null);
            }}
            onSelectTraceB={(id) => {
              setTraceBId(id);
              setComparison(null);
            }}
            onCompare={() => {
              if (traceAId && traceBId) {
                fetchComparison(traceAId, traceBId);
              }
            }}
            onRetry={() => {
              if (traceAId && traceBId) {
                fetchComparison(traceAId, traceBId);
              }
            }}
          />
        ) : viewMode === 'search' ? (
          <HistoricalSearchView
            onSelectTrace={(traceId, findingId) => {
              setSelectedTraceId(traceId);
              setViewMode('trace');
              if (findingId) {
                setIsInvestigationOpen(true);
                setActiveRightTab('investigation');
              }
            }}
          />
        ) : (
          <>
            {/* Left Sidebar: Traces List */}
            <TraceList
              traces={traces}
              selectedTraceId={selectedTraceId}
              onSelectTrace={(id) => setSelectedTraceId(id)}
              isLoading={isTracesLoading}
              error={tracesError}
              onRefresh={fetchTraces}
            />

            {/* Center Canvas / Detail Area */}
            <main className="flex-1 flex flex-col min-w-0 bg-slate-950 relative overflow-hidden">
          {detailError && (
            <div className="p-6 m-4 bg-rose-950/40 border border-rose-800/60 rounded-lg text-rose-200">
              <h3 className="font-semibold text-base mb-1">Failed to Load Trace</h3>
              <p className="text-sm text-rose-300 font-mono mb-3">{detailError}</p>
              <button
                onClick={() => {
                  const id = selectedTraceId;
                  setSelectedTraceId(null);
                  setTimeout(() => setSelectedTraceId(id), 50);
                }}
                className="px-3 py-1 bg-rose-800 hover:bg-rose-700 text-white rounded text-xs transition"
              >
                Retry Request
              </button>
            </div>
          )}

          {isDetailLoading && (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-slate-400">
              <div className="w-8 h-8 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mb-3" />
              <p className="text-sm font-medium">Reconstructing trace & execution graph...</p>
            </div>
          )}

          {!isDetailLoading && !detailError && !selectedTraceId && (
            <div className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-500">
              <div className="text-4xl mb-3">🔍</div>
              <h3 className="text-base font-medium text-slate-300">No Trace Selected</h3>
              <p className="text-xs text-slate-500 mt-1 max-w-sm">
                Select an agent execution trace from the sidebar to inspect its lifecycle, execution graph, and event payloads.
              </p>
            </div>
          )}

          {!isDetailLoading && !detailError && selectedTrace && (
            <>
              {/* Trace Overview Header & Metrics */}
              <TraceOverview
                trace={selectedTrace}
                connectionState={realtimeState}
                onToggleInvestigation={() => {
                  setIsInvestigationOpen((prev) => !prev);
                  setActiveRightTab('investigation');
                }}
                isInvestigationOpen={isInvestigationOpen && activeRightTab === 'investigation'}
                investigationStatus={investigation?.status || null}
                investigationConfidence={investigation?.confidence ?? null}
                onCompareTrace={() => {
                  setTraceAId(selectedTrace.trace_id);
                  const other = traces.find((t) => t.trace_id !== selectedTrace.trace_id);
                  if (other) {
                    setTraceBId(other.trace_id);
                    fetchComparison(selectedTrace.trace_id, other.trace_id);
                  }
                  setViewMode('compare');
                }}
              />

              {/* Execution Graph & Right Inspection Panel Split Area */}
              <div className="flex-1 flex min-h-0 relative">
                {/* React Flow Graph */}
                <div className="flex-1 h-full min-w-0">
                  <TraceGraph
                    graph={selectedGraph}
                    selectedNodeId={selectedNode?.id || null}
                    onSelectNode={(node) => {
                      setSelectedNode(node);
                      setActiveRightTab('event');
                    }}
                    onClearSelection={() => setSelectedNode(null)}
                  />
                </div>

                {/* Right Inspection Panel: Event Details OR AI Investigation */}
                {(isInvestigationOpen || selectedNode) && (
                  <div
                    data-testid="right-inspection-panel"
                    className="w-[450px] max-w-[50vw] h-full flex flex-col border-l border-slate-800 bg-slate-900 shrink-0 z-20 shadow-xl"
                  >
                    {/* Top Tab Switcher */}
                    <div className="flex items-center justify-between border-b border-slate-800 bg-slate-950 px-3 py-1.5 text-xs shrink-0">
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => setActiveRightTab('investigation')}
                          data-testid="tab-ai-investigation"
                          className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition ${
                            activeRightTab === 'investigation'
                              ? 'bg-purple-950/80 text-purple-200 border border-purple-700/60 shadow-sm'
                              : 'text-slate-400 hover:text-slate-200'
                          }`}
                        >
                          <span>🤖</span>
                          <span>AI Investigation</span>
                          {investigation && (
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                investigation.status === 'no_issue_detected'
                                  ? 'bg-emerald-400'
                                  : investigation.status === 'investigated'
                                  ? 'bg-purple-400'
                                  : 'bg-amber-400'
                              }`}
                            />
                          )}
                        </button>

                        {selectedNode && (
                          <button
                            onClick={() => setActiveRightTab('event')}
                            data-testid="tab-event-details"
                            className={`px-2.5 py-1 rounded font-medium flex items-center gap-1.5 transition ${
                              activeRightTab === 'event'
                                ? 'bg-slate-800 text-slate-200 border border-slate-700 shadow-sm'
                                : 'text-slate-400 hover:text-slate-200'
                            }`}
                          >
                            <span>🔍</span>
                            <span>Event Details</span>
                            <span className="text-[10px] font-mono text-slate-400">
                              ({selectedNode.label || selectedNode.id})
                            </span>
                          </button>
                        )}
                      </div>

                      <button
                        onClick={() => {
                          setIsInvestigationOpen(false);
                          setSelectedNode(null);
                        }}
                        className="text-slate-400 hover:text-slate-200 p-1 rounded hover:bg-slate-800 text-xs transition"
                        title="Close Panel"
                        aria-label="Close Panel"
                      >
                        ✕
                      </button>
                    </div>

                    {/* Active Tab View */}
                    <div className="flex-1 min-h-0 overflow-hidden">
                      {activeRightTab === 'investigation' ? (
                        <InvestigationPanel
                          investigation={investigation}
                          isLoading={isInvestigationLoading}
                          error={investigationError}
                          onRetry={() => selectedTraceId && fetchInvestigation(selectedTraceId)}
                          onSelectEventId={(eventId) => {
                            const node = selectedGraph?.nodes.find(
                              (n) => n.event_id === eventId || n.id === eventId
                            );
                            if (node) {
                              setSelectedNode(node);
                            }
                          }}
                          onClose={() => setIsInvestigationOpen(false)}
                          selectedEventId={selectedNode?.id || selectedNode?.event_id || null}
                        />
                      ) : selectedNode ? (
                        <EventDetails
                          node={selectedNode}
                          onClose={() => {
                            if (isInvestigationOpen) {
                              setActiveRightTab('investigation');
                            } else {
                              setSelectedNode(null);
                            }
                          }}
                        />
                      ) : null}
                    </div>
                  </div>
                )}
              </div>
            </>
          )}
        </main>
          </>
        )}
      </div>
    </div>
  );
}

export default App;
