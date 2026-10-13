import { useState, useRef, useEffect } from 'react';
import { ProjectBrief, OrganizationBrief, User } from '../../types/auth';

interface HeaderProps {
  apiStatus: 'healthy' | 'checking' | 'offline';
  selectedTraceId: string | null;
  activeView?: 'trace' | 'compare' | 'search';
  onSelectView?: (view: 'trace' | 'compare' | 'search') => void;
  isTraceListVisible?: boolean;
  onToggleTraceList?: () => void;
  // Phase 19D Multi-Tenant Project & Auth Props
  projects?: ProjectBrief[];
  selectedProject?: ProjectBrief | null;
  onSelectProject?: (project: ProjectBrief) => void;
  user?: User | null;
  organization?: OrganizationBrief | null;
  onOpenProjectSettings?: () => void;
  onLogout?: () => void;
}

export function Header({
  apiStatus,
  selectedTraceId,
  activeView = 'trace',
  onSelectView,
  isTraceListVisible = true,
  onToggleTraceList,
  projects = [],
  selectedProject = null,
  onSelectProject,
  user = null,
  organization = null,
  onOpenProjectSettings,
  onLogout,
}: HeaderProps) {
  const [isUserMenuOpen, setIsUserMenuOpen] = useState(false);
  const userMenuRef = useRef<HTMLDivElement>(null);

  // Close user dropdown on outside click
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (userMenuRef.current && !userMenuRef.current.contains(event.target as Node)) {
        setIsUserMenuOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  return (
    <header className="h-14 bg-slate-950 border-b border-slate-800 px-4 flex items-center justify-between shrink-0 shadow-md z-30 relative">
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

        {/* Phase 19D Project Selector */}
        {projects.length > 0 && selectedProject && (
          <div className="hidden lg:flex items-center ml-2 pl-3 border-l border-slate-800">
            <div className="flex items-center gap-1.5 bg-slate-900 border border-slate-800 px-2.5 py-1 rounded-lg text-xs">
              <span className="text-slate-500 font-mono text-[11px]">Project:</span>
              <select
                data-testid="project-selector"
                value={selectedProject.id}
                onChange={(e) => {
                  const target = projects.find((p) => p.id === e.target.value);
                  if (target && onSelectProject) {
                    onSelectProject(target);
                  }
                }}
                className="bg-transparent text-slate-200 font-semibold text-xs focus:outline-none cursor-pointer pr-1"
                aria-label="Select Project"
              >
                {projects.map((p) => (
                  <option key={p.id} value={p.id} className="bg-slate-900 text-slate-100">
                    {p.name} ({p.slug})
                  </option>
                ))}
              </select>
              {organization && (
                <span
                  data-testid="org-badge"
                  className="text-[10px] px-1.5 py-0.2 rounded bg-purple-950/60 border border-purple-800/80 text-purple-300 ml-1"
                >
                  {organization.name}
                </span>
              )}
            </div>
          </div>
        )}

        {selectedTraceId && activeView === 'trace' && (
          <div className="hidden xl:flex items-center gap-2 ml-2 pl-3 border-l border-slate-800 text-xs">
            <span className="text-slate-500 font-mono">Viewing:</span>
            <span className="text-slate-200 font-mono bg-slate-900 px-2 py-0.5 rounded border border-slate-800">
              {selectedTraceId}
            </span>
          </div>
        )}

        {/* Traces Sidebar Toggle Button */}
        {activeView === 'trace' && onToggleTraceList && (
          <div className="hidden sm:flex items-center ml-2 pl-3 border-l border-slate-800">
            <button
              onClick={onToggleTraceList}
              data-testid="toggle-traces-sidebar-btn"
              className={`px-2.5 py-1 text-xs rounded-lg border transition flex items-center gap-1.5 font-medium ${
                isTraceListVisible
                  ? 'bg-slate-900 text-purple-300 border-purple-800/70 hover:bg-purple-950/40 shadow-sm'
                  : 'bg-slate-900/80 text-slate-400 border-slate-800 hover:text-slate-200 hover:bg-slate-800'
              }`}
              title={isTraceListVisible ? 'Hide Traces Sidebar' : 'Show Traces Sidebar'}
              aria-label={isTraceListVisible ? 'Hide Traces Sidebar' : 'Show Traces Sidebar'}
            >
              <svg className="w-3.5 h-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <rect x="3" y="3" width="18" height="18" rx="2" />
                <line x1="9" y1="3" x2="9" y2="21" />
              </svg>
              <span>Traces</span>
              <span className={`w-1.5 h-1.5 rounded-full ${isTraceListVisible ? 'bg-purple-400' : 'bg-slate-500'}`} />
            </button>
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

      {/* Right Controls: API Status, API Keys, User Menu */}
      <div className="flex items-center gap-3 text-xs">
        {/* API Keys Shortcut */}
        {selectedProject && onOpenProjectSettings && (
          <button
            type="button"
            data-testid="btn-open-project-settings"
            onClick={onOpenProjectSettings}
            className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-300 hover:text-white transition"
            title="Manage Project API Keys"
          >
            <span>🔑</span>
            <span className="hidden sm:inline">API Keys</span>
          </button>
        )}

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

        {/* User Profile & Logout Dropdown */}
        {user && (
          <div className="relative" ref={userMenuRef}>
            <button
              type="button"
              data-testid="btn-user-menu"
              onClick={() => setIsUserMenuOpen((prev) => !prev)}
              className="flex items-center gap-2 p-1 pl-2 rounded-lg bg-slate-900 hover:bg-slate-800 border border-slate-800 text-slate-200 transition"
            >
              <div className="w-5 h-5 rounded-full bg-purple-700 text-white font-bold text-[10px] flex items-center justify-center">
                {user.email ? user.email[0].toUpperCase() : 'U'}
              </div>
              <span className="hidden md:inline text-xs font-medium max-w-[120px] truncate">
                {user.full_name || user.email.split('@')[0]}
              </span>
              <span className="text-slate-500 text-[10px]">▼</span>
            </button>

            {isUserMenuOpen && (
              <div
                data-testid="user-dropdown-menu"
                className="absolute right-0 mt-2 w-56 bg-slate-900 border border-slate-800 rounded-xl shadow-2xl py-2 z-50 text-xs"
              >
                <div className="px-3 py-2 border-b border-slate-800/80">
                  <p className="font-semibold text-slate-100 truncate">{user.full_name || 'User'}</p>
                  <p className="text-slate-400 font-mono text-[11px] truncate">{user.email}</p>
                  {organization && (
                    <div className="mt-1 flex items-center gap-1">
                      <span className="text-[10px] text-slate-500">Org:</span>
                      <span className="text-[10px] text-purple-300 font-medium">
                        {organization.name} ({organization.role})
                      </span>
                    </div>
                  )}
                </div>

                {onOpenProjectSettings && (
                  <button
                    type="button"
                    data-testid="menu-item-api-keys"
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      onOpenProjectSettings();
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-slate-800 text-slate-200 flex items-center gap-2 transition"
                  >
                    <span>🔑</span>
                    <span>Project API Keys</span>
                  </button>
                )}

                {onLogout && (
                  <button
                    type="button"
                    data-testid="btn-logout"
                    onClick={() => {
                      setIsUserMenuOpen(false);
                      onLogout();
                    }}
                    className="w-full text-left px-3 py-2 hover:bg-rose-950/40 text-rose-300 hover:text-rose-200 flex items-center gap-2 transition border-t border-slate-800/60 mt-1"
                  >
                    <span>🚪</span>
                    <span>Sign Out</span>
                  </button>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </header>
  );
}
