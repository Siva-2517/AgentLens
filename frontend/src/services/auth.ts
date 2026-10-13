/**
 * Authentication & Project Management API Service (Phase 19D).
 *
 * Security Invariants:
 * 1. Uses HttpOnly cookies for session state - no JWTs or passwords in localStorage/sessionStorage.
 * 2. Double-submit CSRF protection on state-changing requests (X-CSRF-Token).
 * 3. Ingestion keys are strictly separated from user dashboard authentication.
 */

import { apiClient, formatApiError } from './api';
import {
  AuthResponse,
  LoginCredentials,
  RegisterCredentials,
  UserProfile,
  ProjectBrief,
  ApiKeyInfo,
  ApiKeyCreated,
  ApiKeyCreatePayload,
} from '../types/auth';

import {
  setCsrfToken,
  getCsrfToken,
  getEffectiveCsrfToken,
  setAccessToken,
  getAccessToken,
} from './csrf';

export {
  setCsrfToken,
  getCsrfToken,
  getEffectiveCsrfToken,
  setAccessToken,
  getAccessToken,
};

/**
 * Authenticate dashboard user with email and password.
 */
export async function loginUser(credentials: LoginCredentials): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>('/auth/login', credentials);
  if (response.data.access_token) {
    setAccessToken(response.data.access_token);
  }
  if (response.data.csrf_token) {
    setCsrfToken(response.data.csrf_token);
  }
  return response.data;
}

/**
 * Register new human user account.
 */
export async function registerUser(credentials: RegisterCredentials): Promise<AuthResponse> {
  const response = await apiClient.post<AuthResponse>('/auth/register', credentials);
  if (response.data.access_token) {
    setAccessToken(response.data.access_token);
  }
  if (response.data.csrf_token) {
    setCsrfToken(response.data.csrf_token);
  }
  return response.data;
}

/**
 * Refresh authenticated session using HttpOnly refresh cookie or Bearer header.
 */
export async function refreshSession(): Promise<{ message: string; access_token?: string; csrf_token?: string }> {
  const response = await apiClient.post<{ message: string; access_token?: string; csrf_token?: string }>('/auth/refresh');
  if (response.data.access_token) {
    setAccessToken(response.data.access_token);
  }
  if (response.data.csrf_token) {
    setCsrfToken(response.data.csrf_token);
  }
  return response.data;
}

/**
 * Log out user and clear session credentials.
 */
export async function logoutUser(): Promise<{ message: string }> {
  try {
    const response = await apiClient.post<{ message: string }>('/auth/logout');
    return response.data;
  } finally {
    setAccessToken(null);
    setCsrfToken(null);
  }
}

/**
 * Fetch authenticated user profile, organizations, and assigned projects.
 */
export async function getCurrentUserProfile(): Promise<UserProfile> {
  const response = await apiClient.get<UserProfile>('/auth/me');
  return response.data;
}

/**
 * List projects accessible by current user.
 */
export async function getUserProjects(): Promise<ProjectBrief[]> {
  const response = await apiClient.get<ProjectBrief[]>('/projects');
  return response.data;
}

/**
 * List API keys for a specific project.
 */
export async function listProjectApiKeys(projectId: string): Promise<ApiKeyInfo[]> {
  const response = await apiClient.get<ApiKeyInfo[]>(
    `/projects/${encodeURIComponent(projectId)}/api-keys`
  );
  return response.data;
}

/**
 * Create a new project-scoped ingestion API key.
 * The raw key is returned ONCE by the backend and never stored.
 */
export async function createProjectApiKey(
  projectId: string,
  payload: ApiKeyCreatePayload
): Promise<ApiKeyCreated> {
  const response = await apiClient.post<ApiKeyCreated>(
    `/projects/${encodeURIComponent(projectId)}/api-keys`,
    payload
  );
  return response.data;
}

/**
 * Revoke an API key immediately.
 */
export async function revokeProjectApiKey(
  projectId: string,
  keyId: string
): Promise<{ message: string; id: string }> {
  const response = await apiClient.delete<{ message: string; id: string }>(
    `/projects/${encodeURIComponent(projectId)}/api-keys/${encodeURIComponent(keyId)}`
  );
  return response.data;
}

export { formatApiError };
