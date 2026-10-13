import { useState, useEffect, useCallback, useMemo } from 'react';
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
  apiClient,
} from './services/api';
import { getAccessToken } from './services/csrf';
import { RealtimeClient } from './services/realtime';
import { Header } from './components/layout/Header';
import { TraceList } from './components/traces/TraceList';
import { TraceOverview } from './components/traces/TraceOverview';
import { TraceGraph } from './components/traces/TraceGraph';
import { EventDetails } from './components/traces/EventDetails';
import { InvestigationPanel } from './components/traces/InvestigationPanel';
import { TraceComparisonView } from './components/traces/TraceComparisonView';
import { HistoricalSearchView } from './components/traces/HistoricalSearchView';
import { ApiKeyManagementModal } from './components/settings/ApiKeyManagementModal';
import { AuthProvider, useAuth } from './context/AuthContext';
import { HomePage } from './pages/HomePage';
import { LoginPage } from './pages/LoginPage';
import { RegisterPage } from './pages/RegisterPage';

function DashboardApp() {
  const {
    user,
    organizations,
    projects,
    selectedProject,
    setSelectedProject,
    isAuthenticated,
    isLoading: isAuthLoading,
    logout,
  } = useAuth();

  const [authView, setAuthView] = useState<'home' | 'login' | 'register'>('home');
  const [isApiKeyModalOpen, setIsApiKeyModalOpen] = useState(false);

  const [apiStatus, setApiStatus] = useState<'healthy' | 'checking' | 'offline'>('checking');
  const [traces, setTraces] = useState<TraceSummary[]>([]);
  const [isTracesLoading, setIsTracesLoading] = useState<boolean>(true);
  const [tracesError, setTracesError] = useState<string | null>(null);
  const [isTraceListVisible, setIsTraceListVisible] = useState<boolean>(true);

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

  // Trace Replay, Run Comparison, and Historical Failure Search State
  const [viewMode, setViewMode] = useState<'trace' | 'compare' | 'search'>('trace');
  const [traceAId, setTraceAId] = useState<string | null>(null);
  const [traceBId, setTraceBId] = useState<string | null>(null);
  const [comparison, setComparison] = useState<TraceComparisonResult | null>(null);
  const [isComparisonLoading, setIsComparisonLoading] = useState<boolean>(false);
  const [comparisonError, setComparisonError] = useState<string | null>(null);

  // Active Organization for Selected Project
  const currentOrg = useMemo(() => {
    if (!selectedProject) return organizations[0] || null;
    return organizations.find((o) => o.id === selectedProject.organization_id) || organizations[0] || null;
  }, [organizations, selectedProject]);

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
    apiClient
      .get('/health')
      .then((res) => {
        if (res.data?.status === 'healthy' || res.data?.status === 'degraded') {
          setApiStatus('healthy');
        } else {
          setApiStatus('offline');
        }
      })
      .catch(() => {
        setApiStatus('offline');
      });
  }, []);

  // Fetch traces list whenever selectedProject changes
  const fetchTraces = useCallback(async () => {
    if (!isAuthenticated || !selectedProject?.id) {
      setTraces([]);
      setIsTracesLoading(false);
      return;
    }

    setIsTracesLoading(true);
    setTracesError(null);
    try {
      const data = await getTraces(selectedProject.id);
      const safeData = Array.isArray(data) ? data : [];
      setTraces(safeData);
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
  }, [isAuthenticated, selectedProject?.id, selectedTraceId, traceAId, traceBId]);

  // Purge selected trace and cached trace state when selectedProject changes
  useEffect(() => {
    setSelectedTraceId(null);
    setSelectedTrace(null);
    setSelectedGraph(null);
    setSelectedNode(null);
    setInvestigation(null);
    setInvestigationError(null);
    setIsInvestigationOpen(false);
    setComparison(null);
    setComparisonError(null);
    setTraceAId(null);
    setTraceBId(null);
    fetchTraces();
  }, [selectedProject?.id]);

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
    setSelectedNode(null);

    fetchInvestigation(selectedTraceId);

    Promise.all([
      getTrace(selectedTraceId),
      getTraceGraph(selectedTraceId),
    ])
      .then(([traceData, graphData]) => {
        if (!isMounted) return;
        setSelectedTrace(traceData);
        setSelectedGraph(graphData);
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

  // Real-time WebSocket connection
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
          duration_ms: msg.duration_ms ?? prev.duration_ms,
        };
      });
    } else if (msg.type === 'event_created') {
      if (selectedTraceId) {
        getTrace(selectedTraceId).then(setSelectedTrace).catch(() => {});
        getTraceGraph(selectedTraceId).then(setSelectedGraph).catch(() => {});
      }
    }
  }, [selectedTraceId]);

  useEffect(() => {
    if (!selectedTraceId) {
      setRealtimeState('disconnected');
      return;
    }

    const client = new RealtimeClient({
      traceId: selectedTraceId,
      apiKey: getAccessToken() || undefined,
      onMessage: handleRealtimeMessage,
      onStateChange: setRealtimeState,
    });

    client.connect();

    return () => {
      client.disconnect();
    };
  }, [selectedTraceId, handleRealtimeMessage]);

  // Loading Splash Screen
  if (isAuthLoading) {
    return (
      <div
        data-testid="auth-loading-splash"
        className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 text-slate-300"
      >
        <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-purple-900/40 mb-4 animate-pulse">
          <span className="text-white font-extrabold text-xl">AL</span>
        </div>
        <div className="w-6 h-6 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mb-3" />
        <p className="text-xs font-mono text-slate-400">Authenticating AgentLens session...</p>
      </div>
    );
  }

  // Unauthenticated: Render HomePage, Login, or Register Page
  if (!isAuthenticated) {
    if (authView === 'login') {
      return (
        <LoginPage
          onSwitchToRegister={() => setAuthView('register')}
          onBackToHome={() => setAuthView('home')}
        />
      );
    }
    if (authView === 'register') {
      return (
        <RegisterPage
          onSwitchToLogin={() => setAuthView('login')}
          onRegistrationComplete={() => setAuthView('login')}
          onBackToHome={() => setAuthView('home')}
        />
      );
    }
    return (
      <HomePage
        onLogin={() => setAuthView('login')}
        onRegister={() => setAuthView('register')}
      />
    );
  }

  return (
    <div className="flex flex-col h-screen w-screen overflow-hidden bg-slate-950 text-slate-100 font-sans">
      {/* Top Header */}
      <Header
        apiStatus={apiStatus}
        selectedTraceId={selectedTraceId}
        activeView={viewMode}
        onSelectView={(mode) => setViewMode(mode)}
        isTraceListVisible={isTraceListVisible}
        onToggleTraceList={() => setIsTraceListVisible((prev) => !prev)}
        projects={projects}
        selectedProject={selectedProject}
        onSelectProject={(proj) => setSelectedProject(proj)}
        user={user}
        organization={currentOrg}
        onOpenProjectSettings={() => setIsApiKeyModalOpen(true)}
        onLogout={logout}
      />

      {/* Main Content Area */}
      <div className="flex-1 flex min-h-0 overflow-hidden relative">
        {projects.length === 0 ? (
          <div
            data-testid="empty-projects-view"
            className="flex-1 flex flex-col items-center justify-center p-8 text-center text-slate-400 bg-slate-950"
          >
            <div className="text-4xl mb-3">🏢</div>
            <h3 className="text-base font-semibold text-slate-200">No Projects Available</h3>
            <p className="text-xs text-slate-500 mt-1 max-w-md">
              Your account currently has no assigned projects. Please contact your organization
              administrator to be added to a project.
            </p>
            <button
              onClick={logout}
              className="mt-4 px-4 py-1.5 bg-slate-900 hover:bg-slate-800 text-slate-300 text-xs rounded-lg border border-slate-800 transition"
            >
              Sign Out
            </button>
          </div>
        ) : viewMode === 'compare' ? (
          <TraceComparisonView
            traces={traces}
            selectedTraceAId={traceAId}
            selectedTraceBId={traceBId}
            comparison={comparison}
            isLoading={isComparisonLoading}
            error={comparisonError}
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
            selectedProjectId={selectedProject?.id}
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
            {/* Left Sidebar: Traces List (Collapsible) */}
            {isTraceListVisible ? (
              <TraceList
                traces={traces}
                selectedTraceId={selectedTraceId}
                onSelectTrace={(id) => setSelectedTraceId(id)}
                isLoading={isTracesLoading}
                error={tracesError}
                onRefresh={fetchTraces}
                onToggleCollapse={() => setIsTraceListVisible(false)}
              />
            ) : (
              <aside
                data-testid="collapsed-traces-bar"
                className="w-10 h-full bg-slate-900 border-r border-slate-800 shrink-0 flex flex-col items-center py-3 select-none"
              >
                <button
                  onClick={() => setIsTraceListVisible(true)}
                  data-testid="expand-traces-btn"
                  className="p-1.5 text-slate-400 hover:text-purple-300 hover:bg-slate-800 rounded-lg border border-slate-800 hover:border-purple-800/60 transition flex flex-col items-center gap-2 group"
                  title="Expand Traces Sidebar"
                  aria-label="Expand Traces Sidebar"
                >
                  <svg
                    className="w-4 h-4 text-slate-400 group-hover:text-purple-300 transition-transform group-hover:translate-x-0.5"
                    viewBox="0 0 24 24"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2"
                  >
                    <polyline points="9 18 15 12 9 6" />
                  </svg>
                  <span className="[writing-mode:vertical-rl] text-[10px] uppercase font-mono tracking-wider font-semibold text-slate-400 group-hover:text-purple-300 mt-2">
                    Traces ({traces.length})
                  </span>
                </button>
              </aside>
            )}

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

      {/* Project API Keys Modal */}
      {selectedProject && (
        <ApiKeyManagementModal
          project={selectedProject}
          organization={currentOrg || undefined}
          isOpen={isApiKeyModalOpen}
          onClose={() => setIsApiKeyModalOpen(false)}
        />
      )}
    </div>
  );
}

export function App() {
  return (
    <AuthProvider>
      <DashboardApp />
    </AuthProvider>
  );
}

export default App;
