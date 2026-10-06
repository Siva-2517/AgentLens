/**
 * Formatting utilities for timestamps, durations, and event styling.
 */

export interface EventTypeConfig {
  displayName: string;
  badgeBg: string;
  badgeText: string;
  cardBorder: string;
  cardBg: string;
  dotColor: string;
  icon: string;
}

export const EVENT_TYPE_CONFIG: Record<string, EventTypeConfig> = {
  AGENT_START: {
    displayName: 'Agent Start',
    badgeBg: 'bg-purple-950/80',
    badgeText: 'text-purple-300',
    cardBorder: 'border-purple-600/60 hover:border-purple-500',
    cardBg: 'bg-purple-950/20',
    dotColor: 'bg-purple-500',
    icon: '▶',
  },
  LLM_CALL: {
    displayName: 'LLM Call',
    badgeBg: 'bg-blue-950/80',
    badgeText: 'text-blue-300',
    cardBorder: 'border-blue-600/60 hover:border-blue-500',
    cardBg: 'bg-blue-950/20',
    dotColor: 'bg-blue-500',
    icon: '⚡',
  },
  LLM_RESPONSE: {
    displayName: 'LLM Response',
    badgeBg: 'bg-sky-950/80',
    badgeText: 'text-sky-300',
    cardBorder: 'border-sky-600/60 hover:border-sky-500',
    cardBg: 'bg-sky-950/20',
    dotColor: 'bg-sky-500',
    icon: '💬',
  },
  TOOL_CALL: {
    displayName: 'Tool Call',
    badgeBg: 'bg-emerald-950/80',
    badgeText: 'text-emerald-300',
    cardBorder: 'border-emerald-600/60 hover:border-emerald-500',
    cardBg: 'bg-emerald-950/20',
    dotColor: 'bg-emerald-500',
    icon: '🔧',
  },
  TOOL_RESPONSE: {
    displayName: 'Tool Response',
    badgeBg: 'bg-teal-950/80',
    badgeText: 'text-teal-300',
    cardBorder: 'border-teal-600/60 hover:border-teal-500',
    cardBg: 'bg-teal-950/20',
    dotColor: 'bg-teal-500',
    icon: '📥',
  },
  STATE_CHANGE: {
    displayName: 'State Change',
    badgeBg: 'bg-amber-950/80',
    badgeText: 'text-amber-300',
    cardBorder: 'border-amber-600/60 hover:border-amber-500',
    cardBg: 'bg-amber-950/20',
    dotColor: 'bg-amber-500',
    icon: '🔄',
  },
  RETRY: {
    displayName: 'Retry',
    badgeBg: 'bg-orange-950/80',
    badgeText: 'text-orange-300',
    cardBorder: 'border-orange-600/60 hover:border-orange-500',
    cardBg: 'bg-orange-950/20',
    dotColor: 'bg-orange-500',
    icon: '🔁',
  },
  ERROR: {
    displayName: 'Error',
    badgeBg: 'bg-rose-950/80',
    badgeText: 'text-rose-300',
    cardBorder: 'border-rose-600/80 hover:border-rose-500',
    cardBg: 'bg-rose-950/30',
    dotColor: 'bg-rose-500',
    icon: '⚠',
  },
  AGENT_END: {
    displayName: 'Agent End',
    badgeBg: 'bg-violet-950/80',
    badgeText: 'text-violet-300',
    cardBorder: 'border-violet-600/60 hover:border-violet-500',
    cardBg: 'bg-violet-950/20',
    dotColor: 'bg-violet-500',
    icon: '🏁',
  },
};

const DEFAULT_EVENT_CONFIG: EventTypeConfig = {
  displayName: 'Event',
  badgeBg: 'bg-slate-800',
  badgeText: 'text-slate-300',
  cardBorder: 'border-slate-700 hover:border-slate-600',
  cardBg: 'bg-slate-900/40',
  dotColor: 'bg-slate-500',
  icon: '•',
};

export function getEventTypeConfig(eventType: string): EventTypeConfig {
  const normalized = eventType.toUpperCase();
  return EVENT_TYPE_CONFIG[normalized] || {
    ...DEFAULT_EVENT_CONFIG,
    displayName: eventType.replace(/_/g, ' '),
  };
}

/**
 * Format duration in milliseconds to human-friendly unit.
 */
export function formatDuration(durationMs?: number | null): string {
  if (durationMs === null || durationMs === undefined || isNaN(durationMs)) {
    return '—';
  }
  if (durationMs < 1) {
    return '<1 ms';
  }
  if (durationMs < 1000) {
    return `${Math.round(durationMs)} ms`;
  }
  if (durationMs < 60000) {
    return `${(durationMs / 1000).toFixed(2)} s`;
  }
  const minutes = Math.floor(durationMs / 60000);
  const remainingSeconds = ((durationMs % 60000) / 1000).toFixed(1);
  return `${minutes}m ${remainingSeconds}s`;
}

/**
 * Format ISO timestamp into human-readable time with milliseconds.
 */
export function formatTimeWithMs(timestamp?: string | null): string {
  if (!timestamp) return '—';
  try {
    const d = new Date(timestamp);
    if (isNaN(d.getTime())) return timestamp;
    return d.toISOString().substring(11, 23); // HH:mm:ss.sss
  } catch {
    return timestamp;
  }
}

/**
 * Format full date and time.
 */
export function formatDateTime(timestamp?: string | null): string {
  if (!timestamp) return '—';
  try {
    const d = new Date(timestamp);
    if (isNaN(d.getTime())) return timestamp;
    return d.toLocaleString('en-US', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit',
      hour12: false,
    });
  } catch {
    return timestamp;
  }
}
