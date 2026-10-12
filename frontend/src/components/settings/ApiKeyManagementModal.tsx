import React, { useState, useEffect, useCallback } from 'react';
import { ProjectBrief, OrganizationBrief, ApiKeyInfo, ApiKeyCreated } from '../../types/auth';
import {
  listProjectApiKeys,
  createProjectApiKey,
  revokeProjectApiKey,
  formatApiError,
} from '../../services/auth';

interface ApiKeyManagementModalProps {
  project: ProjectBrief;
  organization?: OrganizationBrief;
  isOpen: boolean;
  onClose: () => void;
}

export function ApiKeyManagementModal({
  project,
  organization,
  isOpen,
  onClose,
}: ApiKeyManagementModalProps) {
  const [keys, setKeys] = useState<ApiKeyInfo[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Creation State
  const [isCreating, setIsCreating] = useState(false);
  const [newKeyName, setNewKeyName] = useState('');
  const [expiresInDays, setExpiresInDays] = useState<number | ''>(90);
  const [isCreatingSubmitting, setIsCreatingSubmitting] = useState(false);

  // One-time key display state
  const [newlyCreatedKey, setNewlyCreatedKey] = useState<ApiKeyCreated | null>(null);
  const [hasCopiedSecret, setHasCopiedSecret] = useState(false);

  // Revocation Confirmation State
  const [revokingKeyId, setRevokingKeyId] = useState<string | null>(null);
  const [isRevokingSubmitting, setIsRevokingSubmitting] = useState(false);

  const isViewer = organization?.role === 'viewer';

  const fetchKeys = useCallback(async () => {
    if (!project?.id) return;
    setIsLoading(true);
    setError(null);
    try {
      const data = await listProjectApiKeys(project.id);
      setKeys(data);
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [project?.id]);

  useEffect(() => {
    if (isOpen && project?.id) {
      fetchKeys();
      setNewlyCreatedKey(null);
      setIsCreating(false);
      setRevokingKeyId(null);
    }
  }, [isOpen, project?.id, fetchKeys]);

  if (!isOpen) return null;

  const handleCreateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newKeyName.trim() || isViewer) return;

    setIsCreatingSubmitting(true);
    setError(null);
    try {
      const created = await createProjectApiKey(project.id, {
        name: newKeyName.trim(),
        expires_in_days: typeof expiresInDays === 'number' ? expiresInDays : undefined,
      });
      setNewlyCreatedKey(created);
      setNewKeyName('');
      setIsCreating(false);
      await fetchKeys();
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setIsCreatingSubmitting(false);
    }
  };

  const handleCopySecret = () => {
    if (newlyCreatedKey?.api_key) {
      navigator.clipboard.writeText(newlyCreatedKey.api_key);
      setHasCopiedSecret(true);
      setTimeout(() => setHasCopiedSecret(false), 3000);
    }
  };

  const handleConfirmRevoke = async (keyId: string) => {
    if (isViewer) return;
    setIsRevokingSubmitting(true);
    setError(null);
    try {
      await revokeProjectApiKey(project.id, keyId);
      setRevokingKeyId(null);
      await fetchKeys();
    } catch (err) {
      setError(formatApiError(err));
    } finally {
      setIsRevokingSubmitting(false);
    }
  };

  return (
    <div
      data-testid="api-key-modal"
      className="fixed inset-0 bg-black/75 backdrop-blur-sm flex items-center justify-center p-4 z-50 animate-fadeIn"
    >
      <div className="w-full max-w-2xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-800 flex items-center justify-between bg-slate-950/80">
          <div>
            <div className="flex items-center gap-2">
              <h2 className="text-base font-bold text-slate-100">Project API Keys</h2>
              <span className="text-[11px] font-mono px-2 py-0.5 rounded bg-purple-950/80 border border-purple-800 text-purple-300">
                {project.name}
              </span>
            </div>
            <p className="text-xs text-slate-400 mt-0.5">
              Manage project-scoped ingestion credentials for AI agents and the Python SDK
            </p>
          </div>
          <button
            onClick={onClose}
            className="text-slate-400 hover:text-slate-200 p-1.5 rounded-lg hover:bg-slate-800 transition"
            aria-label="Close API Keys modal"
          >
            ✕
          </button>
        </div>

        {/* Content Body */}
        <div className="p-6 overflow-y-auto space-y-6 flex-1">
          {/* Error Banner */}
          {error && (
            <div
              data-testid="api-key-error-banner"
              className="p-3 bg-rose-950/60 border border-rose-800/80 rounded-lg text-rose-200 text-xs flex items-start gap-2"
            >
              <span className="text-rose-400 font-bold shrink-0 mt-0.5">⚠️</span>
              <span>{error}</span>
            </div>
          )}

          {/* Newly Created Key Alert (One-Time Display) */}
          {newlyCreatedKey && (
            <div
              data-testid="newly-created-key-card"
              className="p-4 bg-purple-950/50 border border-purple-700/60 rounded-xl space-y-3"
            >
              <div className="flex items-start justify-between">
                <div>
                  <h4 className="text-xs font-bold text-purple-200 flex items-center gap-1.5">
                    <span>✨ Ingestion Key Created:</span>
                    <span className="text-white">{newlyCreatedKey.name}</span>
                  </h4>
                  <p className="text-[11px] text-purple-300/80 mt-0.5">
                    Copy this secret now. For security, it will <strong>never</strong> be shown again!
                  </p>
                </div>
                <button
                  type="button"
                  data-testid="btn-dismiss-created-key"
                  onClick={() => setNewlyCreatedKey(null)}
                  className="text-xs text-purple-400 hover:text-purple-200 underline"
                >
                  Dismiss
                </button>
              </div>

              <div className="flex items-center gap-2 bg-slate-950 border border-purple-800/60 p-2.5 rounded-lg">
                <code
                  data-testid="newly-created-key-value"
                  className="flex-1 font-mono text-xs text-emerald-400 select-all overflow-x-auto break-all"
                >
                  {newlyCreatedKey.api_key}
                </code>
                <button
                  type="button"
                  data-testid="btn-copy-new-key"
                  onClick={handleCopySecret}
                  className="px-3 py-1.5 bg-purple-900/60 hover:bg-purple-800 border border-purple-700 text-purple-100 text-xs font-medium rounded transition shrink-0 flex items-center gap-1.5"
                >
                  {hasCopiedSecret ? (
                    <>
                      <span className="text-emerald-400 font-bold">✓</span>
                      <span>Copied!</span>
                    </>
                  ) : (
                    <>
                      <span>📋</span>
                      <span>Copy</span>
                    </>
                  )}
                </button>
              </div>
            </div>
          )}

          {/* Creation Form OR Create Button */}
          {isViewer ? (
            <div className="p-3 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-400 flex items-center gap-2">
              <span>🔒</span>
              <span>
                View-Only Access: You belong to this organization as a Viewer. Only Admins and Owners can generate or revoke ingestion API keys.
              </span>
            </div>
          ) : isCreating ? (
            <form
              onSubmit={handleCreateSubmit}
              data-testid="form-create-api-key"
              className="p-4 bg-slate-950 border border-slate-800 rounded-xl space-y-4"
            >
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-slate-200">Generate Ingestion API Key</h4>
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  Cancel
                </button>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Key Name / Description
                  </label>
                  <input
                    type="text"
                    data-testid="input-new-key-name"
                    value={newKeyName}
                    onChange={(e) => setNewKeyName(e.target.value)}
                    placeholder="e.g., Python SDK Ingestion"
                    required
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 text-xs focus:ring-1 focus:ring-purple-500 focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-300 mb-1">
                    Expiration Period
                  </label>
                  <select
                    data-testid="select-key-expiry"
                    value={expiresInDays}
                    onChange={(e) => {
                      const val = e.target.value;
                      setExpiresInDays(val === '' ? '' : parseInt(val, 10));
                    }}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-slate-100 text-xs focus:ring-1 focus:ring-purple-500 focus:outline-none"
                  >
                    <option value={30}>30 Days</option>
                    <option value={90}>90 Days (Recommended)</option>
                    <option value={365}>1 Year</option>
                    <option value="">Never Expires</option>
                  </select>
                </div>
              </div>

              <div className="flex justify-end gap-2 pt-2">
                <button
                  type="button"
                  onClick={() => setIsCreating(false)}
                  className="px-3 py-1.5 text-xs text-slate-400 hover:text-slate-200 transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  data-testid="btn-submit-create-key"
                  disabled={isCreatingSubmitting || !newKeyName.trim()}
                  className="px-3.5 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium rounded-lg transition disabled:opacity-50"
                >
                  {isCreatingSubmitting ? 'Generating...' : 'Generate Key'}
                </button>
              </div>
            </form>
          ) : (
            <div className="flex justify-between items-center">
              <div>
                <h3 className="text-xs font-semibold text-slate-200">Active Ingestion Keys</h3>
                <p className="text-[11px] text-slate-400">
                  Keys scoped specifically to <span className="font-mono text-slate-300">{project.slug}</span>
                </p>
              </div>
              <button
                type="button"
                data-testid="btn-open-create-key"
                onClick={() => setIsCreating(true)}
                className="px-3 py-1.5 bg-purple-600 hover:bg-purple-500 text-white text-xs font-medium rounded-lg shadow-sm transition flex items-center gap-1.5"
              >
                <span>+</span>
                <span>Generate Ingestion Key</span>
              </button>
            </div>
          )}

          {/* Keys List Table */}
          {isLoading ? (
            <div className="py-8 flex flex-col items-center justify-center text-slate-400">
              <div className="w-5 h-5 border-2 border-purple-500 border-t-transparent rounded-full animate-spin mb-2" />
              <p className="text-xs">Loading keys...</p>
            </div>
          ) : keys.length === 0 ? (
            <div
              data-testid="empty-keys-state"
              className="py-10 text-center border border-dashed border-slate-800 rounded-xl"
            >
              <div className="text-2xl mb-2">🔑</div>
              <p className="text-xs font-medium text-slate-300">No Ingestion API Keys Found</p>
              <p className="text-[11px] text-slate-500 max-w-xs mx-auto mt-1">
                Create a project-scoped key to ingest agent execution traces via the AgentLens SDK or HTTP API.
              </p>
            </div>
          ) : (
            <div className="border border-slate-800 rounded-xl overflow-hidden">
              <table className="w-full text-left text-xs">
                <thead className="bg-slate-950/80 border-b border-slate-800 text-slate-400 text-[11px]">
                  <tr>
                    <th className="py-2.5 px-3 font-semibold">Name & Prefix</th>
                    <th className="py-2.5 px-3 font-semibold">Status</th>
                    <th className="py-2.5 px-3 font-semibold">Created / Expiry</th>
                    <th className="py-2.5 px-3 font-semibold text-right">Action</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {keys.map((k) => (
                    <tr
                      key={k.id}
                      data-testid={`key-row-${k.id}`}
                      className="hover:bg-slate-950/40 transition"
                    >
                      <td className="py-3 px-3">
                        <div className="font-sans font-medium text-slate-200">{k.name}</div>
                        <div className="text-[11px] text-purple-400/90 font-mono">
                          {k.key_prefix}...
                        </div>
                      </td>

                      <td className="py-3 px-3">
                        {k.is_revoked ? (
                          <span
                            data-testid={`key-status-revoked-${k.id}`}
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-sans font-medium bg-rose-950 border border-rose-800 text-rose-300"
                          >
                            Revoked
                          </span>
                        ) : (
                          <span
                            data-testid={`key-status-active-${k.id}`}
                            className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-sans font-medium bg-emerald-950 border border-emerald-800 text-emerald-300"
                          >
                            Active
                          </span>
                        )}
                      </td>

                      <td className="py-3 px-3 text-[11px] text-slate-400">
                        <div>Created: {new Date(k.created_at).toLocaleDateString()}</div>
                        <div className="text-slate-500">
                          {k.expires_at
                            ? `Expires: ${new Date(k.expires_at).toLocaleDateString()}`
                            : 'No expiration'}
                        </div>
                      </td>

                      <td className="py-3 px-3 text-right">
                        {k.is_revoked ? (
                          <span className="text-[11px] text-slate-600">—</span>
                        ) : revokingKeyId === k.id ? (
                          <div className="flex items-center justify-end gap-1.5 font-sans">
                            <button
                              type="button"
                              onClick={() => setRevokingKeyId(null)}
                              className="px-2 py-0.5 text-[11px] text-slate-400 hover:text-slate-200"
                            >
                              Cancel
                            </button>
                            <button
                              type="button"
                              data-testid={`btn-confirm-revoke-${k.id}`}
                              disabled={isRevokingSubmitting}
                              onClick={() => handleConfirmRevoke(k.id)}
                              className="px-2 py-0.5 text-[11px] bg-rose-900/80 hover:bg-rose-800 text-rose-100 rounded border border-rose-700"
                            >
                              {isRevokingSubmitting ? 'Revoking...' : 'Confirm'}
                            </button>
                          </div>
                        ) : (
                          <button
                            type="button"
                            data-testid={`btn-revoke-key-${k.id}`}
                            disabled={isViewer}
                            onClick={() => setRevokingKeyId(k.id)}
                            className="font-sans px-2.5 py-1 text-[11px] text-rose-400 hover:text-rose-300 hover:bg-rose-950/40 rounded transition border border-rose-900/40 disabled:opacity-30 disabled:cursor-not-allowed"
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-3 border-t border-slate-800 bg-slate-950/80 flex justify-end">
          <button
            type="button"
            data-testid="btn-close-modal"
            onClick={onClose}
            className="px-4 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
          >
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
