interface HeaderProps {
  apiStatus: 'healthy' | 'checking' | 'offline';
  selectedTraceId: string | null;
  activeView?: 'trace' | 'compare' | 'search';
  onSelectView?: (view: 'trace' | 'compare' | 'search') => void;
}

export function Header({
  apiStatus,
  selectedTraceId,
  activeView = 'trace',
  onSelectView,
}: HeaderProps) {
  return (
    <header className="h-14 bg-slate-950 border-b border-slate-800 px-4 flex items-center justify-between shrink-0 shadow-md">
      <div className="flex items-center gap-3">
        {/* Logo and Product Title */}
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-lg bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-purple-900/30">
            <span className="text-white font-bold text-sm">AL</span>
          </div>
          <div>
            <div className="flex items-center gap-2">
              <h1 className="text-sm font-bold text-slate-100 tracking-tight">AgentLens</h1>
              <span className="text-[10px] uppercase font-mono px-1.5 py-0.5 rounded bg-purple-950 border border-purple-800 text-purple-300">
                Observability
              </span>
            </div>
            <p className="text-[10px] text-slate-400">AI Agent Execution & Trace Debugger</p>
          </div>
        </div>

        {selectedTraceId && activeView === 'trace' && (
          <div className="hidden md:flex items-center gap-2 ml-4 pl-4 border-l border-slate-800 text-xs">
            <span className="text-slate-500 font-mono">Viewing:</span>
            <span className="text-slate-200 font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
              {selectedTraceId}
            </span>
          </div>
        )}
      </div>

      {/* Center Navigation Switcher */}
      <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 p-0.5 rounded-lg text-xs">
        <button
          onClick={() => onSelectView?.('trace')}
          className={`px-3 py-1 rounded-md font-medium transition flex items-center gap-1.5 ${
            activeView === 'trace'
              ? 'bg-purple-950/80 text-purple-200 border border-purple-700/60 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
          data-testid="nav-trace-view"
        >
          <span>📊</span>
          <span>Trace Inspector</span>
        </button>
        <button
          onClick={() => onSelectView?.('compare')}
          className={`px-3 py-1 rounded-md font-medium transition flex items-center gap-1.5 ${
            activeView === 'compare'
              ? 'bg-cyan-950/80 text-cyan-200 border border-cyan-700/60 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
          data-testid="nav-compare-view"
        >
          <span>🔄</span>
          <span>Run Comparison</span>
        </button>
        <button
          onClick={() => onSelectView?.('search')}
          className={`px-3 py-1 rounded-md font-medium transition flex items-center gap-1.5 ${
            activeView === 'search'
              ? 'bg-amber-950/80 text-amber-200 border border-amber-700/60 shadow-sm'
              : 'text-slate-400 hover:text-slate-200'
          }`}
          data-testid="nav-search-view"
        >
          <span>🔍</span>
          <span>Historical Failures</span>
        </button>
      </div>

      <div className="flex items-center gap-3 text-xs">
        {/* Backend health status pill */}
        <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-slate-900 border border-slate-800">
          <span
            className={`w-2 h-2 rounded-full ${
              apiStatus === 'healthy'
                ? 'bg-emerald-400 animate-pulse'
                : apiStatus === 'checking'
                ? 'bg-amber-400'
                : 'bg-rose-400'
            }`}
          />
          <span className="text-slate-400 text-[11px] font-mono">
            API: <span className="text-slate-200 font-semibold">{apiStatus}</span>
          </span>
        </div>
      </div>
    </header>
  );
}
