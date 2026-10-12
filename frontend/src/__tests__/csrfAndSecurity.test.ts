import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { setCsrfToken, getCsrfToken, getEffectiveCsrfToken } from '../services/csrf';
import { apiClient } from '../services/api';
import { RealtimeClient } from '../services/realtime';

describe('Phase 19D: CSRF Protection & Ingestion Secret Separation', () => {
  beforeEach(() => {
    setCsrfToken(null);
  });

  afterEach(() => {
    setCsrfToken(null);
  });

  it('stores and retrieves in-memory CSRF token', () => {
    expect(getCsrfToken()).toBeNull();
    setCsrfToken('csrf-token-abc');
    expect(getCsrfToken()).toBe('csrf-token-abc');
    expect(getEffectiveCsrfToken()).toBe('csrf-token-abc');
  });

  it('extracts CSRF token from document.cookie when in-memory cache is empty', () => {
    Object.defineProperty(document, 'cookie', {
      writable: true,
      value: 'other_cookie=xyz; agentlens_csrf_token=cookie-csrf-999; session=123',
    });

    expect(getEffectiveCsrfToken()).toBe('cookie-csrf-999');
  });

  it('apiClient uses withCredentials and does not have hardcoded Authorization header', () => {
    expect(apiClient.defaults.withCredentials).toBe(true);
    expect(apiClient.defaults.headers.Authorization).toBeUndefined();
  });

  it('attaches X-CSRF-Token header to state-changing requests', async () => {
    setCsrfToken('active-csrf-token-555');

    // Spy on interceptor behavior
    const requestInterceptor = (apiClient.interceptors.request as any).handlers[0].fulfilled;

    const postConfig = { method: 'post', headers: {} } as any;
    const modifiedPost = requestInterceptor(postConfig);
    expect(modifiedPost.headers['X-CSRF-Token']).toBe('active-csrf-token-555');

    const deleteConfig = { method: 'DELETE', headers: {} } as any;
    const modifiedDelete = requestInterceptor(deleteConfig);
    expect(modifiedDelete.headers['X-CSRF-Token']).toBe('active-csrf-token-555');

    const getConfig = { method: 'get', headers: {} } as any;
    const modifiedGet = requestInterceptor(getConfig);
    expect(modifiedGet.headers['X-CSRF-Token']).toBeUndefined();
  });

  it('RealtimeClient constructs WebSocket URL without hardcoded API key or secrets', () => {
    const client = new RealtimeClient({
      traceId: 'trace-123',
      onMessage: vi.fn(),
      onStateChange: vi.fn(),
    });

    // Inspect private wsBaseUrl or connect url structure
    // When no apiKey option is provided, it connects via cookie without ?token=
    expect((client as any).apiKey).toBe('');
  });
});
