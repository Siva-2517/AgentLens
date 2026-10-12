import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { ApiKeyManagementModal } from '../components/settings/ApiKeyManagementModal';
import * as authService from '../services/auth';
import { ProjectBrief, OrganizationBrief, ApiKeyInfo, ApiKeyCreated } from '../types/auth';

vi.mock('../services/auth', async () => {
  const actual = await vi.importActual('../services/auth');
  return {
    ...actual,
    listProjectApiKeys: vi.fn(),
    createProjectApiKey: vi.fn(),
    revokeProjectApiKey: vi.fn(),
  };
});

describe('Phase 19D: Project API Key Management UI', () => {
  const mockProject: ProjectBrief = {
    id: 'proj-123',
    organization_id: 'org-123',
    name: 'Production AI App',
    slug: 'prod-ai-app',
    description: 'Production workloads',
  };

  const mockOrgOwner: OrganizationBrief = {
    id: 'org-123',
    name: 'Acme AI',
    slug: 'acme-ai',
    role: 'owner',
  };

  const mockOrgViewer: OrganizationBrief = {
    id: 'org-123',
    name: 'Acme AI',
    slug: 'acme-ai',
    role: 'viewer',
  };

  const mockKeys: ApiKeyInfo[] = [
    {
      id: 'key-1',
      project_id: 'proj-123',
      name: 'Python SDK Ingestion',
      key_prefix: 'al_live_py123',
      key_type: 'ingestion',
      scopes: ['ingest'],
      created_at: '2026-01-01T00:00:00Z',
      expires_at: '2026-04-01T00:00:00Z',
      last_used_at: '2026-01-02T12:00:00Z',
      is_revoked: false,
    },
    {
      id: 'key-2',
      project_id: 'proj-123',
      name: 'Old Agent Key',
      key_prefix: 'al_live_old456',
      key_type: 'ingestion',
      scopes: ['ingest'],
      created_at: '2025-10-01T00:00:00Z',
      expires_at: null,
      last_used_at: null,
      is_revoked: true,
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it('renders active and revoked API keys with metadata', async () => {
    vi.mocked(authService.listProjectApiKeys).mockResolvedValueOnce(mockKeys);

    render(
      <ApiKeyManagementModal
        project={mockProject}
        organization={mockOrgOwner}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText('Python SDK Ingestion')).toBeInTheDocument();
      expect(screen.getByText('al_live_py123...')).toBeInTheDocument();
      expect(screen.getByTestId('key-status-active-key-1')).toBeInTheDocument();

      expect(screen.getByText('Old Agent Key')).toBeInTheDocument();
      expect(screen.getByTestId('key-status-revoked-key-2')).toBeInTheDocument();
    });
  });

  it('generates new ingestion key and displays raw secret once', async () => {
    vi.mocked(authService.listProjectApiKeys).mockResolvedValue(mockKeys);

    const mockCreatedKey: ApiKeyCreated = {
      id: 'key-new',
      project_id: 'proj-123',
      name: 'Collector Key',
      key_prefix: 'al_live_coll789',
      api_key: 'al_live_secret_collector_key_plaintext_999',
      created_at: '2026-01-03T00:00:00Z',
      expires_at: '2026-04-03T00:00:00Z',
    };
    vi.mocked(authService.createProjectApiKey).mockResolvedValueOnce(mockCreatedKey);

    render(
      <ApiKeyManagementModal
        project={mockProject}
        organization={mockOrgOwner}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('btn-open-create-key')).toBeInTheDocument();
    });

    // Open creation form
    fireEvent.click(screen.getByTestId('btn-open-create-key'));
    expect(screen.getByTestId('form-create-api-key')).toBeInTheDocument();

    // Fill form
    fireEvent.change(screen.getByTestId('input-new-key-name'), {
      target: { value: 'Collector Key' },
    });
    fireEvent.change(screen.getByTestId('select-key-expiry'), {
      target: { value: '90' },
    });

    // Submit
    fireEvent.click(screen.getByTestId('btn-submit-create-key'));

    await waitFor(() => {
      expect(authService.createProjectApiKey).toHaveBeenCalledWith('proj-123', {
        name: 'Collector Key',
        expires_in_days: 90,
      });
      expect(screen.getByTestId('newly-created-key-card')).toBeInTheDocument();
      expect(screen.getByTestId('newly-created-key-value')).toHaveTextContent(
        'al_live_secret_collector_key_plaintext_999'
      );
    });

    // Dismissing card purges raw secret from UI
    fireEvent.click(screen.getByTestId('btn-dismiss-created-key'));
    await waitFor(() => {
      expect(screen.queryByTestId('newly-created-key-card')).not.toBeInTheDocument();
    });
  });

  it('revokes an active API key with confirmation', async () => {
    vi.mocked(authService.listProjectApiKeys).mockResolvedValue(mockKeys);
    vi.mocked(authService.revokeProjectApiKey).mockResolvedValueOnce({
      message: 'API key revoked successfully',
      id: 'key-1',
    });

    render(
      <ApiKeyManagementModal
        project={mockProject}
        organization={mockOrgOwner}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('btn-revoke-key-key-1')).toBeInTheDocument();
    });

    // Click revoke button -> shows confirmation
    fireEvent.click(screen.getByTestId('btn-revoke-key-key-1'));
    expect(screen.getByTestId('btn-confirm-revoke-key-1')).toBeInTheDocument();

    // Confirm revocation
    fireEvent.click(screen.getByTestId('btn-confirm-revoke-key-1'));

    await waitFor(() => {
      expect(authService.revokeProjectApiKey).toHaveBeenCalledWith('proj-123', 'key-1');
    });
  });

  it('restricts viewer roles from generating or revoking API keys', async () => {
    vi.mocked(authService.listProjectApiKeys).mockResolvedValueOnce(mockKeys);

    render(
      <ApiKeyManagementModal
        project={mockProject}
        organization={mockOrgViewer}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByText(/View-Only Access/i)).toBeInTheDocument();
      expect(screen.queryByTestId('btn-open-create-key')).not.toBeInTheDocument();
      expect(screen.getByTestId('btn-revoke-key-key-1')).toBeDisabled();
    });
  });

  it('displays 403 Forbidden or 404 error banners gracefully', async () => {
    vi.mocked(authService.listProjectApiKeys).mockRejectedValueOnce(
      new Error('Forbidden: Insufficient permissions for this operation.')
    );

    render(
      <ApiKeyManagementModal
        project={mockProject}
        organization={mockOrgOwner}
        isOpen={true}
        onClose={vi.fn()}
      />
    );

    await waitFor(() => {
      expect(screen.getByTestId('api-key-error-banner')).toBeInTheDocument();
      expect(
        screen.getByText('Forbidden: Insufficient permissions for this operation.')
      ).toBeInTheDocument();
    });
  });
});
