import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import {
  User,
  OrganizationBrief,
  ProjectBrief,
  LoginCredentials,
  RegisterCredentials,
  AuthResponse,
} from '../types/auth';
import {
  loginUser,
  registerUser,
  logoutUser,
  getCurrentUserProfile,
  formatApiError,
} from '../services/auth';
import { onSessionExpired } from '../services/api';

export interface AuthContextType {
  user: User | null;
  organizations: OrganizationBrief[];
  projects: ProjectBrief[];
  selectedProject: ProjectBrief | null;
  setSelectedProject: (project: ProjectBrief | null) => void;
  isAuthenticated: boolean;
  isLoading: boolean;
  error: string | null;
  clearError: () => void;
  login: (credentials: LoginCredentials) => Promise<void>;
  register: (credentials: RegisterCredentials) => Promise<AuthResponse>;
  logout: () => Promise<void>;
  refreshProfile: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [organizations, setOrganizations] = useState<OrganizationBrief[]>([]);
  const [projects, setProjects] = useState<ProjectBrief[]>([]);
  const [selectedProject, setSelectedProject] = useState<ProjectBrief | null>(null);
  const [isAuthenticated, setIsAuthenticated] = useState<boolean>(false);
  const [isLoading, setIsLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);

  const clearError = useCallback(() => setError(null), []);

  const refreshProfile = useCallback(async () => {
    try {
      const profile = await getCurrentUserProfile();
      if (!profile || typeof profile !== 'object' || !profile.user || !profile.user.id) {
        throw new Error('Not authenticated');
      }
      setUser(profile.user);
      setOrganizations(profile.organizations || []);
      setProjects(profile.projects || []);
      setIsAuthenticated(true);
      setError(null);

      // Auto-select project if not currently set or if currently selected project no longer exists
      setSelectedProject((prev) => {
        if (prev && profile.projects.some((p) => p.id === prev.id)) {
          return prev;
        }
        return profile.projects.length > 0 ? profile.projects[0] : null;
      });
    } catch (err) {
      setUser(null);
      setOrganizations([]);
      setProjects([]);
      setSelectedProject(null);
      setIsAuthenticated(false);
      throw err;
    }
  }, []);

  // Check initial session on application mount
  useEffect(() => {
    let isMounted = true;
    setIsLoading(true);

    Promise.resolve()
      .then(() => getCurrentUserProfile())
      .then((profile) => {
        if (!isMounted || !profile) return;
        if (typeof profile !== 'object' || !profile.user || !profile.user.id) {
          throw new Error('Not authenticated');
        }
        setUser(profile.user);
        setOrganizations(profile.organizations || []);
        setProjects(profile.projects || []);
        setIsAuthenticated(true);
        if (profile.projects && profile.projects.length > 0) {
          setSelectedProject(profile.projects[0]);
        }
      })
      .catch(() => {
        if (!isMounted) return;
        setUser(null);
        setOrganizations([]);
        setProjects([]);
        setSelectedProject(null);
        setIsAuthenticated(false);
      })
      .finally(() => {
        if (isMounted) {
          setIsLoading(false);
        }
      });

    // Listen for unrecoverable 401 session expirations from API client
    const unsubscribe = onSessionExpired(() => {
      if (!isMounted) return;
      setUser(null);
      setOrganizations([]);
      setProjects([]);
      setSelectedProject(null);
      setIsAuthenticated(false);
      setError('Your session has expired. Please sign in again.');
    });

    return () => {
      isMounted = false;
      unsubscribe();
    };
  }, []);

  const login = useCallback(
    async (credentials: LoginCredentials) => {
      setIsLoading(true);
      setError(null);
      try {
        await loginUser(credentials);
        await refreshProfile();
      } catch (err) {
        const msg = formatApiError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [refreshProfile]
  );

  const register = useCallback(
    async (credentials: RegisterCredentials): Promise<AuthResponse> => {
      setIsLoading(true);
      setError(null);
      try {
        const response = await registerUser(credentials);
        await refreshProfile();
        return response;
      } catch (err) {
        const msg = formatApiError(err);
        setError(msg);
        throw new Error(msg);
      } finally {
        setIsLoading(false);
      }
    },
    [refreshProfile]
  );

  const logout = useCallback(async () => {
    setIsLoading(true);
    try {
      await logoutUser();
    } catch {
      // Clear client state even if logout network request fails
    } finally {
      setUser(null);
      setOrganizations([]);
      setProjects([]);
      setSelectedProject(null);
      setIsAuthenticated(false);
      setError(null);
      setIsLoading(false);
    }
  }, []);

  return (
    <AuthContext.Provider
      value={{
        user,
        organizations,
        projects,
        selectedProject,
        setSelectedProject,
        isAuthenticated,
        isLoading,
        error,
        clearError,
        login,
        register,
        logout,
        refreshProfile,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth(): AuthContextType {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
