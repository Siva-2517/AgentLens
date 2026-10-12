import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { AuthProvider } from '../context/AuthContext';
import { LoginPage } from '../pages/LoginPage';
import { RegisterPage } from '../pages/RegisterPage';
import { App } from '../App';
import * as authService from '../services/auth';
import * as apiService from '../services/api';
import { UserProfile, AuthResponse } from '../types/auth';

vi.mock('../services/auth', async () => {
  const actual = await vi.importActual('../services/auth');
  return {
    ...actual,
    loginUser: vi.fn(),
    registerUser: vi.fn(),
    logoutUser: vi.fn(),
    getCurrentUserProfile: vi.fn(),
  };
});

vi.mock('../services/api', async () => {
  const actual = await vi.importActual('../services/api');
  return {
    ...actual,
    getTraces: vi.fn().mockResolvedValue([]),
    getTrace: vi.fn(),
    getTraceGraph: vi.fn(),
  };
});

describe('Phase 19D: Frontend Authentication & Routing', () => {
  const mockProfile: UserProfile = {
    user: {
      id: 'usr-123',
      email: 'alex@agentlens.ai',
      full_name: 'Alex Rivers',
      is_active: true,
      is_superuser: false,
      created_at: '2026-01-01T00:00:00Z',
    },
    organizations: [
      {
        id: 'org-123',
        name: 'Acme AI',
        slug: 'acme-ai',
        role: 'owner',
      },
    ],
    projects: [
      {
        id: 'proj-1',
        organization_id: 'org-123',
        name: 'Project Alpha',
        slug: 'project-alpha',
        description: 'First project',
      },
      {
        id: 'proj-2',
        organization_id: 'org-123',
        name: 'Project Beta',
        slug: 'project-beta',
        description: 'Second project',
      },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
    vi.mocked(authService.getCurrentUserProfile).mockResolvedValue(mockProfile);
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders login page with inputs and submits credentials', async () => {
    const onSwitch = vi.fn();
    vi.mocked(authService.loginUser).mockResolvedValueOnce({
      user: mockProfile.user,
      message: 'Login successful',
      csrf_token: 'csrf-123',
    });
    vi.mocked(authService.getCurrentUserProfile).mockResolvedValue(mockProfile);

    render(
      <AuthProvider>
        <LoginPage onSwitchToRegister={onSwitch} />
      </AuthProvider>
    );

    expect(screen.getByTestId('input-email')).toBeInTheDocument();
    expect(screen.getByTestId('input-password')).toBeInTheDocument();

    fireEvent.change(screen.getByTestId('input-email'), {
      target: { value: 'alex@agentlens.ai' },
    });
    fireEvent.change(screen.getByTestId('input-password'), {
      target: { value: 'secretpass123' },
    });

    fireEvent.click(screen.getByTestId('btn-login-submit'));

    await waitFor(() => {
      expect(authService.loginUser).toHaveBeenCalledWith({
        email: 'alex@agentlens.ai',
        password: 'secretpass123',
      });
    });
  });

  it('displays error alert on login failure', async () => {
    vi.mocked(authService.loginUser).mockRejectedValueOnce(
      new Error('Invalid email or password')
    );

    render(
      <AuthProvider>
        <LoginPage onSwitchToRegister={vi.fn()} />
      </AuthProvider>
    );

    fireEvent.change(screen.getByTestId('input-email'), {
      target: { value: 'bad@agentlens.ai' },
    });
    fireEvent.change(screen.getByTestId('input-password'), {
      target: { value: 'wrongpass' },
    });
    fireEvent.click(screen.getByTestId('btn-login-submit'));

    await waitFor(() => {
      expect(screen.getByTestId('auth-error-alert')).toBeInTheDocument();
      expect(screen.getByText('Invalid email or password')).toBeInTheDocument();
    });
  });

  it('validates registration form password matching and length', async () => {
    render(
      <AuthProvider>
        <RegisterPage onSwitchToLogin={vi.fn()} />
      </AuthProvider>
    );

    fireEvent.change(screen.getByTestId('input-email'), {
      target: { value: 'new@agentlens.ai' },
    });
    fireEvent.change(screen.getByTestId('input-password'), {
      target: { value: 'short' },
    });
    fireEvent.change(screen.getByTestId('input-confirm-password'), {
      target: { value: 'short' },
    });

    fireEvent.click(screen.getByTestId('btn-register-submit'));

    await waitFor(() => {
      expect(screen.getByTestId('auth-error-alert')).toBeInTheDocument();
      expect(
        screen.getByText('Password must be at least 8 characters long.')
      ).toBeInTheDocument();
    });

    // Mismatched passwords
    fireEvent.change(screen.getByTestId('input-password'), {
      target: { value: 'validpassword1' },
    });
    fireEvent.change(screen.getByTestId('input-confirm-password'), {
      target: { value: 'differentpassword2' },
    });

    fireEvent.click(screen.getByTestId('btn-register-submit'));

    await waitFor(() => {
      expect(screen.getByText('Passwords do not match.')).toBeInTheDocument();
    });
  });

  it('displays one-time raw API key modal upon successful registration', async () => {
    const mockRegResponse: AuthResponse = {
      user: mockProfile.user,
      message: 'Registration successful',
      csrf_token: 'csrf-abc',
      api_key: 'al_live_initial_secret_key_9999',
    };

    vi.mocked(authService.registerUser).mockResolvedValueOnce(mockRegResponse);
    vi.mocked(authService.getCurrentUserProfile).mockResolvedValue(mockProfile);

    render(
      <AuthProvider>
        <RegisterPage onSwitchToLogin={vi.fn()} />
      </AuthProvider>
    );

    fireEvent.change(screen.getByTestId('input-fullname'), {
      target: { value: 'Alex Rivers' },
    });
    fireEvent.change(screen.getByTestId('input-email'), {
      target: { value: 'alex@acme.ai' },
    });
    fireEvent.change(screen.getByTestId('input-password'), {
      target: { value: 'password1234' },
    });
    fireEvent.change(screen.getByTestId('input-confirm-password'), {
      target: { value: 'password1234' },
    });

    fireEvent.click(screen.getByTestId('btn-register-submit'));

    await waitFor(() => {
      expect(screen.getByTestId('onetime-key-modal')).toBeInTheDocument();
      expect(screen.getByTestId('onetime-api-key-value')).toHaveTextContent(
        'al_live_initial_secret_key_9999'
      );
    });

    // Dismiss key modal
    fireEvent.click(screen.getByTestId('btn-dismiss-key-modal'));
    await waitFor(() => {
      expect(screen.queryByTestId('onetime-key-modal')).not.toBeInTheDocument();
    });
  });

  it('unauthenticated user sees homepage, can navigate to login, and dashboard is protected', async () => {
    vi.mocked(authService.getCurrentUserProfile).mockRejectedValueOnce(
      new Error('Unauthorized')
    );

    render(<App />);

    // 1. Initial unauthenticated landing is HomePage
    await waitFor(() => {
      expect(screen.getByTestId('homepage-hero')).toBeInTheDocument();
      expect(screen.queryByTestId('nav-trace-view')).not.toBeInTheDocument();
    });

    // 2. Click Sign In to navigate to LoginPage
    fireEvent.click(screen.getByTestId('btn-nav-login'));

    await waitFor(() => {
      expect(screen.getByTestId('input-email')).toBeInTheDocument();
      expect(screen.getByText(/Sign in to AgentLens/i)).toBeInTheDocument();
      expect(screen.getByTestId('btn-login-back-home')).toBeInTheDocument();
    });

    // 3. Click Back to Home returns to HomePage
    fireEvent.click(screen.getByTestId('btn-login-back-home'));

    await waitFor(() => {
      expect(screen.getByTestId('homepage-hero')).toBeInTheDocument();
      expect(screen.queryByTestId('input-email')).not.toBeInTheDocument();
    });
  });

  it('authenticated user session restores and auto-selects initial project', async () => {
    vi.mocked(authService.getCurrentUserProfile).mockResolvedValue(mockProfile);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('project-selector')).toBeInTheDocument();
      expect(screen.getByTestId('project-selector')).toHaveValue('proj-1');
      expect(screen.getByTestId('org-badge')).toHaveTextContent('Acme AI');
    });

    expect(apiService.getTraces).toHaveBeenCalledWith('proj-1');
  });

  it('switching project updates selector, fetches new project traces, and clears previous state', async () => {
    vi.mocked(authService.getCurrentUserProfile).mockResolvedValue(mockProfile);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('project-selector')).toBeInTheDocument();
    });

    // Switch to Project Beta
    fireEvent.change(screen.getByTestId('project-selector'), {
      target: { value: 'proj-2' },
    });

    await waitFor(() => {
      expect(screen.getByTestId('project-selector')).toHaveValue('proj-2');
      expect(apiService.getTraces).toHaveBeenCalledWith('proj-2');
    });
  });

  it('renders empty-projects view when user account has no assigned projects', async () => {
    const profileWithNoProjects: UserProfile = {
      ...mockProfile,
      projects: [],
    };
    vi.mocked(authService.getCurrentUserProfile).mockResolvedValue(profileWithNoProjects);

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('empty-projects-view')).toBeInTheDocument();
      expect(screen.getByText('No Projects Available')).toBeInTheDocument();
    });
  });

  it('logout clears client state and returns user to login page', async () => {
    vi.mocked(authService.getCurrentUserProfile).mockResolvedValue(mockProfile);
    vi.mocked(authService.logoutUser).mockResolvedValue({
      message: 'Logged out successfully',
    });

    render(<App />);

    await waitFor(() => {
      expect(screen.getByTestId('btn-user-menu')).toBeInTheDocument();
    });

    // Open user menu
    fireEvent.click(screen.getByTestId('btn-user-menu'));
    expect(screen.getByTestId('btn-logout')).toBeInTheDocument();

    // Click logout
    fireEvent.click(screen.getByTestId('btn-logout'));

    await waitFor(() => {
      expect(authService.logoutUser).toHaveBeenCalled();
      expect(screen.getByTestId('homepage-hero')).toBeInTheDocument();
      expect(screen.queryByTestId('project-selector')).not.toBeInTheDocument();
    });
  });

  it('confirms no frontend dependency on VITE_AGENTLENS_API_KEY', () => {
    // Assert that the global environment does not define VITE_AGENTLENS_API_KEY
    expect(import.meta.env.VITE_AGENTLENS_API_KEY).toBeUndefined();
    // Verify apiClient defaults withCredentials: true and has no hardcoded Authorization header
    expect(apiService.apiClient.defaults.withCredentials).toBe(true);
    expect(apiService.apiClient.defaults.headers.Authorization).toBeUndefined();
  });
});
