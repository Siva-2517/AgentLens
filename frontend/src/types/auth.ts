/**
 * Authentication, Organization, Project, and API Key types (Phase 19D).
 */

export interface User {
  id: string;
  email: string;
  full_name?: string | null;
  is_active: boolean;
  is_superuser: boolean;
  created_at: string;
}

export interface OrganizationBrief {
  id: string;
  name: string;
  slug: string;
  role: 'owner' | 'admin' | 'member' | 'viewer' | string;
}

export interface ProjectBrief {
  id: string;
  organization_id: string;
  name: string;
  slug: string;
  description?: string | null;
}

export interface UserProfile {
  user: User;
  organizations: OrganizationBrief[];
  projects: ProjectBrief[];
}

export interface AuthResponse {
  user: User;
  message: string;
  access_token?: string;
  token_type?: string;
  csrf_token?: string;
  api_key?: string; // Returned ONCE upon registration
}

export interface LoginCredentials {
  email: string;
  password: string;
}

export interface RegisterCredentials {
  email: string;
  password: string;
  full_name?: string;
}

export interface ApiKeyInfo {
  id: string;
  project_id: string;
  name: string;
  key_prefix: string;
  key_type: string;
  scopes: string[];
  last_used_at?: string | null;
  expires_at?: string | null;
  is_revoked: boolean;
  created_at: string;
}

export interface ApiKeyCreated {
  id: string;
  project_id: string;
  name: string;
  key_prefix: string;
  api_key: string; // Plaintext secret displayed ONCE
  created_at: string;
  expires_at?: string | null;
}

export interface ApiKeyCreatePayload {
  name: string;
  expires_in_days?: number;
}
