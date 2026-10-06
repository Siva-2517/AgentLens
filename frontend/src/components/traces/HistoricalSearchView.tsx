import React, { useState } from 'react';
import {
  HistoricalSearchResponse,
} from '../../types/failureSearch';
import { searchHistoricalFailures, formatApiError } from '../../services/api';
import { formatDateTime } from '../../utils/formatters';

interface HistoricalSearchViewProps {
  onSelectTrace: (traceId: string, findingId?: string) => void;
}

const SAMPLE_QUERIES = [
  'payment API card declined after retry exhaustion',
  'checkout payment rejected by provider',
  'looping repeated tool calls without progress',
  'LLM schema validation failure or timeout',
];

export function HistoricalSearchView({ onSelectTrace }: HistoricalSearchViewProps) {
  const [query, setQuery] = useState('');
  const [severityFilter, setSeverityFilter] = useState<string>('all');
  const [ruleFilter, setRuleFilter] = useState<string>('');
  const [projectFilter, setProjectFilter] = useState<string>('');
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hasSearched, setHasSearched] = useState(false);
  const [searchResponse, setSearchResponse] = useState<HistoricalSearchResponse | null>(null);
  const [expandedTextIds, setExpandedTextIds] = useState<Set<string>>(new Set());

  const handleSearch = async (e?: React.FormEvent, overrideQuery?: string) => {
    if (e) e.preventDefault();
    const q = (overrideQuery !== undefined ? overrideQuery : query).trim();
    if (!q) return;

    if (overrideQuery !== undefined) {
      setQuery(overrideQuery);
    }

    setIsLoading(true);
    setError(null);
    setHasSearched(true);

    try {
      const resp = await searchHistoricalFailures({
        q,
        severity: severityFilter !== 'all' ? severityFilter : undefined,
        rule: ruleFilter.trim() || undefined,
        project: projectFilter.trim() || undefined,
        limit: 20,
      });
      setSearchResponse(resp);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setIsLoading(false);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedTextIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  };

  const getSeverityBadgeColor = (severity: string) => {
    switch (severity.toLowerCase()) {
      case 'critical':
        return 'bg-rose-950/80 text-rose-300 border-rose-800';
      case 'error':
        return 'bg-rose-900/40 text-rose-300 border-rose-700/60';
      case 'warning':
        return 'bg-amber-950/80 text-amber-300 border-amber-800';
      default:
        return 'bg-slate-800 text-slate-300 border-slate-700';
    }
  };

  const getSimilarityBadge = (score: number) => {
    let colorClass = 'bg-slate-800 text-slate-300 border-slate-700';
    if (score >= 0.85) {
      colorClass = 'bg-emerald-950/80 text-emerald-300 border-emerald-700/80';
    } else if (score >= 0.7) {
      colorClass = 'bg-cyan-950/80 text-cyan-300 border-cyan-700/80';
    } else if (score >= 0.5) {
      colorClass = 'bg-amber-950/80 text-amber-300 border-amber-700/80';
    }

    return (
      <span
        className={`px-2 py-0.5 rounded text-xs font-mono font-medium border flex items-center gap-1 ${colorClass}`}
        title={`Semantic Cosine Similarity: ${score.toFixed(4)}`}
      >
        <span>Similarity:</span>
        <span className="font-bold">{score.toFixed(3)}</span>
      </span>
    );
  };

  return (
    <div className="flex-1 flex flex-col bg-slate-950 text-slate-100 overflow-y-auto">
      {/* Header Banner */}
      <div className="border-b border-slate-800 bg-slate-900/60 p-6">
        <div className="max-w-5xl mx-auto space-y-4">
          <div className="flex items-center justify-between">
            <div>
              <div className="flex items-center gap-2">
                <span className="text-xl">🔍</span>
                <h2 className="text-lg font-bold text-slate-100">Historical Failure Search</h2>
                <span className="text-[10px] uppercase font-mono px-2 py-0.5 rounded bg-purple-950/80 border border-purple-800 text-purple-300">
                  pgvector
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-1">
                Find past AgentLens traces with semantically similar failure modes using vector embeddings.
              </p>
            </div>
            {searchResponse && (
              <div className="text-right">
                <span className="text-xs font-mono text-slate-400">
                  {searchResponse.total_results} match{searchResponse.total_results === 1 ? '' : 'es'} found
                </span>
              </div>
            )}
          </div>

          {/* Search Form */}
          <form onSubmit={handleSearch} className="space-y-3">
            <div className="flex items-center gap-2">
              <div className="relative flex-1">
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Describe failure in natural language (e.g., 'payment card declined after retry exhaustion')..."
                  className="w-full bg-slate-900 border border-slate-700 focus:border-purple-500 rounded-lg px-4 py-2.5 text-sm text-slate-100 placeholder-slate-500 outline-none transition shadow-inner font-sans"
                  data-testid="failure-search-input"
                />
                {query && (
                  <button
                    type="button"
                    onClick={() => setQuery('')}
                    className="absolute right-3 top-2.5 text-slate-400 hover:text-slate-200 text-sm"
                  >
                    ×
                  </button>
                )}
              </div>
              <button
                type="submit"
                disabled={isLoading || !query.trim()}
                className="px-5 py-2.5 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white text-sm font-semibold rounded-lg shadow-md transition flex items-center gap-2 shrink-0"
                data-testid="failure-search-button"
              >
                {isLoading ? (
                  <>
                    <span className="w-4 h-4 border-2 border-white/20 border-t-white rounded-full animate-spin" />
                    <span>Searching...</span>
                  </>
                ) : (
                  <>
                    <span>Search Failures</span>
                    <span>→</span>
                  </>
                )}
              </button>
            </div>

            {/* Quick Sample Queries */}
            <div className="flex items-center gap-2 flex-wrap text-xs">
              <span className="text-slate-500 font-mono text-[11px]">Suggestions:</span>
              {SAMPLE_QUERIES.map((sample, idx) => (
                <button
                  key={idx}
                  type="button"
                  onClick={() => handleSearch(undefined, sample)}
                  className="px-2 py-0.5 rounded bg-slate-900/80 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-400 hover:text-purple-300 transition text-[11px] font-mono text-left"
                >
                  "{sample}"
                </button>
              ))}
            </div>

            {/* Filters Row */}
            <div className="flex items-center gap-3 pt-1 border-t border-slate-800/80 flex-wrap text-xs">
              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 font-medium">Severity:</span>
                <select
                  value={severityFilter}
                  onChange={(e) => setSeverityFilter(e.target.value)}
                  className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-300 outline-none focus:border-purple-500 text-xs"
                  data-testid="filter-severity"
                >
                  <option value="all">All Severities</option>
                  <option value="critical">Critical</option>
                  <option value="error">Error</option>
                  <option value="warning">Warning</option>
                  <option value="info">Info</option>
                </select>
              </div>

              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 font-medium">Rule:</span>
                <input
                  type="text"
                  value={ruleFilter}
                  onChange={(e) => setRuleFilter(e.target.value)}
                  placeholder="e.g. retry_exhaustion"
                  className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-300 placeholder-slate-600 outline-none focus:border-purple-500 text-xs font-mono w-40"
                  data-testid="filter-rule"
                />
              </div>

              <div className="flex items-center gap-1.5">
                <span className="text-slate-400 font-medium">Project:</span>
                <input
                  type="text"
                  value={projectFilter}
                  onChange={(e) => setProjectFilter(e.target.value)}
                  placeholder="e.g. BillingService"
                  className="bg-slate-900 border border-slate-800 rounded px-2 py-1 text-slate-300 placeholder-slate-600 outline-none focus:border-purple-500 text-xs w-36"
                  data-testid="filter-project"
                />
              </div>
            </div>
          </form>
        </div>
      </div>

      {/* Main Content Area */}
      <div className="max-w-5xl mx-auto w-full p-6 flex-1 flex flex-col">
        {/* Error Alert */}
        {error && (
          <div
            className="mb-6 p-4 rounded-lg bg-rose-950/50 border border-rose-800 text-rose-300 text-xs flex items-center justify-between"
            data-testid="search-error-alert"
          >
            <div className="flex items-center gap-2">
              <span className="text-base">⚠️</span>
              <div>
                <p className="font-semibold">Search Failed</p>
                <p className="text-rose-400">{error}</p>
              </div>
            </div>
            <button
              onClick={() => handleSearch()}
              className="px-3 py-1 bg-rose-900 hover:bg-rose-800 text-rose-100 rounded font-medium transition"
            >
              Retry
            </button>
          </div>
        )}

        {/* Loading Skeleton */}
        {isLoading && (
          <div className="space-y-4" data-testid="search-loading-skeleton">
            {[1, 2, 3].map((i) => (
              <div
                key={i}
                className="p-5 rounded-xl bg-slate-900/60 border border-slate-800/80 animate-pulse space-y-3"
              >
                <div className="flex items-center justify-between">
                  <div className="h-4 bg-slate-800 rounded w-1/4" />
                  <div className="h-5 bg-slate-800 rounded w-28" />
                </div>
                <div className="h-4 bg-slate-800 rounded w-3/4" />
                <div className="h-3 bg-slate-800/60 rounded w-1/2" />
              </div>
            ))}
          </div>
        )}

        {/* Initial / Empty State Before Search */}
        {!hasSearched && !isLoading && (
          <div className="flex-1 flex flex-col items-center justify-center text-center py-16 px-4">
            <div className="w-14 h-14 rounded-2xl bg-purple-950/60 border border-purple-800/60 flex items-center justify-center text-2xl mb-4 shadow-lg shadow-purple-950/40">
              ⚡
            </div>
            <h3 className="text-base font-semibold text-slate-200">
              Query Historical Agent Failures
            </h3>
            <p className="text-xs text-slate-400 max-w-md mt-1.5 leading-relaxed">
              Use vector-based semantic search to find previous failures that share root causes, error symptoms, or tool breakdowns with your current issue.
            </p>
            <div className="mt-6 flex flex-wrap gap-2 justify-center max-w-lg">
              {SAMPLE_QUERIES.map((sample, idx) => (
                <button
                  key={idx}
                  onClick={() => handleSearch(undefined, sample)}
                  className="px-3 py-1.5 rounded-lg bg-slate-900 hover:bg-purple-950/60 border border-slate-800 hover:border-purple-800/80 text-slate-300 hover:text-purple-200 text-xs font-mono transition"
                >
                  "{sample}"
                </button>
              ))}
            </div>
          </div>
        )}

        {/* No Results Found */}
        {hasSearched && !isLoading && searchResponse?.results.length === 0 && !error && (
          <div className="flex-1 flex flex-col items-center justify-center text-center py-16 px-4" data-testid="search-no-results">
            <div className="w-12 h-12 rounded-xl bg-slate-900 border border-slate-800 flex items-center justify-center text-xl mb-3 text-slate-500">
              ∅
            </div>
            <h3 className="text-sm font-semibold text-slate-300">No Matching Failures Found</h3>
            <p className="text-xs text-slate-500 max-w-sm mt-1">
              No historical failures matched the query "{query}". Try adjusting keywords, clearing filters, or index recent traces.
            </p>
          </div>
        )}

        {/* Results List */}
        {hasSearched && !isLoading && searchResponse && searchResponse.results.length > 0 && (
          <div className="space-y-4" data-testid="search-results-list">
            {searchResponse.results.map((result) => {
              const resultKey = `${result.trace_id}-${result.finding_id}`;
              const isExpanded = expandedTextIds.has(resultKey);

              return (
                <div
                  key={resultKey}
                  className="p-5 rounded-xl bg-slate-900/80 border border-slate-800 hover:border-slate-700 transition shadow-sm space-y-3"
                  data-testid="search-result-card"
                >
                  {/* Top Bar: Trace info & Similarity Badge */}
                  <div className="flex items-center justify-between gap-4 flex-wrap">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-semibold text-sm text-slate-100">
                        {result.trace_name || result.trace_id}
                      </span>
                      {result.project_name && (
                        <span className="px-2 py-0.5 rounded bg-slate-800 text-[11px] text-slate-300 border border-slate-700 font-mono">
                          {result.project_name}
                        </span>
                      )}
                      <span className="text-[11px] text-slate-500">
                        {formatDateTime(result.created_at)}
                      </span>
                    </div>

                    <div className="flex items-center gap-2">
                      {getSimilarityBadge(result.similarity)}
                      <span
                        className={`px-2 py-0.5 rounded text-[11px] font-mono uppercase font-semibold border ${getSeverityBadgeColor(
                          result.severity
                        )}`}
                      >
                        {result.severity}
                      </span>
                    </div>
                  </div>

                  {/* Finding Message & Rule */}
                  <div className="space-y-1">
                    <div className="flex items-center gap-2">
                      <span className="px-2 py-0.5 rounded bg-purple-950/60 border border-purple-800/60 text-purple-300 text-[11px] font-mono">
                        {result.rule}
                      </span>
                    </div>
                    <p className="text-sm text-slate-200 font-medium leading-relaxed">
                      {result.message}
                    </p>
                  </div>

                  {/* Searchable Text Preview & Toggle */}
                  {result.searchable_text && (
                    <div className="text-xs bg-slate-950/80 rounded-lg p-3 border border-slate-800/80 font-mono">
                      <div className="flex items-center justify-between text-slate-400 text-[11px] mb-1">
                        <span>Searchable Vector Context:</span>
                        <button
                          type="button"
                          onClick={() => toggleExpand(resultKey)}
                          className="text-purple-400 hover:text-purple-300 underline"
                        >
                          {isExpanded ? 'Collapse' : 'Expand full'}
                        </button>
                      </div>
                      <p className={`text-slate-300 ${isExpanded ? '' : 'line-clamp-2'} text-[11px] leading-relaxed whitespace-pre-wrap`}>
                        {result.searchable_text}
                      </p>
                    </div>
                  )}

                  {/* Evidence IDs & Action */}
                  <div className="flex items-center justify-between pt-2 border-t border-slate-800/60 text-xs">
                    <div className="flex items-center gap-2 text-slate-400 font-mono text-[11px]">
                      <span>Evidence Events:</span>
                      {result.evidence_event_ids?.length > 0 ? (
                        <span className="text-slate-300">
                          {result.evidence_event_ids.join(', ')}
                        </span>
                      ) : (
                        <span className="text-slate-600">none</span>
                      )}
                    </div>

                    <button
                      onClick={() => onSelectTrace(result.trace_id, result.finding_id)}
                      className="px-3 py-1.5 bg-purple-900/60 hover:bg-purple-800 border border-purple-700/60 text-purple-200 hover:text-white rounded-lg font-medium transition flex items-center gap-1.5 shadow-sm"
                      data-testid="view-trace-button"
                    >
                      <span>Inspect Trace</span>
                      <span>→</span>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
