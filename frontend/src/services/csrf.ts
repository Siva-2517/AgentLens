/**
 * CSRF Token Management (Phase 19D).
 *
 * Keeps CSRF token in memory and falls back to reading the non-HttpOnly
 * agentlens_csrf_token cookie provided by the backend.
 */

let inMemoryCsrfToken: string | null = null;

let inMemoryAccessToken: string | null =
  typeof window !== 'undefined' ? localStorage.getItem('agentlens_access_token') : null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
  if (typeof window !== 'undefined') {
    if (token) {
      localStorage.setItem('agentlens_access_token', token);
    } else {
      localStorage.removeItem('agentlens_access_token');
    }
  }
}

export function getAccessToken(): string | null {
  if (!inMemoryAccessToken && typeof window !== 'undefined') {
    inMemoryAccessToken = localStorage.getItem('agentlens_access_token');
  }
  return inMemoryAccessToken;
}

export function setCsrfToken(token: string | null): void {
  inMemoryCsrfToken = token;
}

export function getCsrfToken(): string | null {
  return inMemoryCsrfToken;
}

export function getEffectiveCsrfToken(): string | null {
  if (inMemoryCsrfToken) {
    return inMemoryCsrfToken;
  }
  if (typeof document !== 'undefined' && document.cookie) {
    const match = document.cookie.match(/(^|;)\s*agentlens_csrf_token=([^;]+)/);
    if (match && match[2]) {
      return decodeURIComponent(match[2]);
    }
  }
  return null;
}
