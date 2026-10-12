import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface RegisterPageProps {
  onSwitchToLogin: () => void;
  onRegistrationComplete?: () => void;
  onBackToHome?: () => void;
}

export function RegisterPage({ onSwitchToLogin, onRegistrationComplete, onBackToHome }: RegisterPageProps) {
  const { register, error: authError, clearError } = useAuth();
  const [fullName, setFullName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirmPassword, setConfirmPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  // One-time key display state after successful registration
  const [createdApiKey, setCreatedApiKey] = useState<string | null>(null);
  const [hasCopiedKey, setHasCopiedKey] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setLocalError('Please enter your email address.');
      return;
    }
    if (password.length < 8) {
      setLocalError('Password must be at least 8 characters long.');
      return;
    }
    if (password !== confirmPassword) {
      setLocalError('Passwords do not match.');
      return;
    }

    setIsSubmitting(true);
    try {
      const response = await register({
        email: cleanEmail,
        password,
        full_name: fullName.trim() || undefined,
      });

      if (response.api_key) {
        // Show one-time secret modal before proceeding to dashboard
        setCreatedApiKey(response.api_key);
      } else {
        onRegistrationComplete?.();
      }
    } catch (err: unknown) {
      if (err instanceof Error) {
        setLocalError(err.message);
      } else {
        setLocalError('Registration failed. Please try again.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCopyKey = () => {
    if (createdApiKey) {
      navigator.clipboard.writeText(createdApiKey);
      setHasCopiedKey(true);
      setTimeout(() => setHasCopiedKey(false), 3000);
    }
  };

  const handleDismissKeyModal = () => {
    setCreatedApiKey(null);
    onRegistrationComplete?.();
  };

  const displayError = localError || authError;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/4 right-1/3 w-96 h-96 bg-purple-900/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 left-1/3 w-96 h-96 bg-cyan-900/15 rounded-full blur-3xl pointer-events-none" />

      {/* One-Time Ingestion Key Modal */}
      {createdApiKey && (
        <div
          data-testid="onetime-key-modal"
          className="fixed inset-0 bg-black/80 backdrop-blur-md flex items-center justify-center p-4 z-50 animate-fadeIn"
        >
          <div className="w-full max-w-lg bg-slate-900 border border-purple-500/50 rounded-2xl p-6 shadow-2xl relative">
            <div className="w-10 h-10 rounded-xl bg-purple-950 border border-purple-800 text-purple-300 flex items-center justify-center mb-4 text-xl">
              🔑
            </div>

            <h2 className="text-xl font-bold text-slate-100 tracking-tight">
              Account Created Successfully!
            </h2>
            <p className="text-xs text-slate-300 mt-1">
              Your default workspace and initial ingestion API key have been provisioned.
            </p>

            <div className="mt-4 p-3 bg-amber-950/60 border border-amber-700/60 rounded-lg text-amber-200 text-xs flex items-start gap-2.5">
              <span className="text-amber-400 font-bold shrink-0 mt-0.5">⚠️</span>
              <div>
                <p className="font-semibold text-amber-100">Store this key securely now!</p>
                <p className="text-amber-300/90 text-[11px] mt-0.5">
                  This raw ingestion secret is only displayed <strong>once</strong>. If you lose it,
                  you will need to generate a new key from Project Settings.
                </p>
              </div>
            </div>

            <div className="mt-4">
              <label className="block text-[11px] font-semibold uppercase tracking-wider text-slate-400 mb-1.5">
                Initial Ingestion API Key
              </label>
              <div className="flex items-center gap-2 bg-slate-950 border border-slate-800 p-2.5 rounded-lg">
                <code
                  data-testid="onetime-api-key-value"
                  className="flex-1 font-mono text-xs text-emerald-400 select-all overflow-x-auto break-all"
                >
                  {createdApiKey}
                </code>
                <button
                  type="button"
                  data-testid="btn-copy-onetime-key"
                  onClick={handleCopyKey}
                  className="px-3 py-1.5 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded transition shrink-0 flex items-center gap-1.5"
                >
                  {hasCopiedKey ? (
                    <>
                      <span className="text-emerald-400">✓</span>
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

            <div className="mt-6 flex justify-end">
              <button
                type="button"
                data-testid="btn-dismiss-key-modal"
                onClick={handleDismissKeyModal}
                className="px-4 py-2 bg-purple-600 hover:bg-purple-500 text-white text-xs font-semibold rounded-lg shadow-lg shadow-purple-900/30 transition"
              >
                Proceed to Dashboard →
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Registration Card */}
      <div className="w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl p-8 backdrop-blur-xl relative z-10">
        {onBackToHome && (
          <button
            onClick={onBackToHome}
            data-testid="btn-register-back-home"
            className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-purple-400 mb-4 transition font-medium"
          >
            <span>←</span>
            <span>Back to Home</span>
          </button>
        )}

        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-purple-900/40 mb-3">
            <span className="text-white font-extrabold text-xl tracking-tight">AL</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Create AgentLens Account</h1>
          <p className="text-xs text-slate-400 mt-1">
            Start observing, tracing, and debugging AI agent executions
          </p>
        </div>

        {displayError && (
          <div
            data-testid="auth-error-alert"
            className="mb-6 p-3 bg-rose-950/60 border border-rose-800/80 rounded-lg text-rose-200 text-xs flex items-start gap-2"
          >
            <span className="text-rose-400 font-bold shrink-0 mt-0.5">⚠️</span>
            <span>{displayError}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="reg-name"
              className="block text-xs font-medium text-slate-300 mb-1.5"
            >
              Full Name (Optional)
            </label>
            <input
              id="reg-name"
              data-testid="input-fullname"
              type="text"
              autoComplete="name"
              value={fullName}
              onChange={(e) => setFullName(e.target.value)}
              placeholder="Alex Rivers"
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition"
            />
          </div>

          <div>
            <label
              htmlFor="reg-email"
              className="block text-xs font-medium text-slate-300 mb-1.5"
            >
              Email Address
            </label>
            <input
              id="reg-email"
              data-testid="input-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="alex@acme.ai"
              required
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition"
            />
          </div>

          <div>
            <label
              htmlFor="reg-password"
              className="block text-xs font-medium text-slate-300 mb-1.5"
            >
              Password (min. 8 characters)
            </label>
            <input
              id="reg-password"
              data-testid="input-password"
              type="password"
              autoComplete="new-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              minLength={8}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition"
            />
          </div>

          <div>
            <label
              htmlFor="reg-confirm-password"
              className="block text-xs font-medium text-slate-300 mb-1.5"
            >
              Confirm Password
            </label>
            <input
              id="reg-confirm-password"
              data-testid="input-confirm-password"
              type="password"
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              minLength={8}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition"
            />
          </div>

          <button
            type="submit"
            data-testid="btn-register-submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2.5 px-4 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-medium text-sm rounded-lg shadow-lg shadow-purple-900/30 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Creating Account...</span>
              </>
            ) : (
              <span>Create Account</span>
            )}
          </button>
        </form>

        <div className="mt-6 pt-6 border-t border-slate-800/80 text-center">
          <p className="text-xs text-slate-400">
            Already have an account?{' '}
            <button
              type="button"
              data-testid="link-switch-to-login"
              onClick={onSwitchToLogin}
              className="text-purple-400 hover:text-purple-300 font-medium underline underline-offset-2 transition"
            >
              Sign in here
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
