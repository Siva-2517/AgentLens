import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';

interface LoginPageProps {
  onSwitchToRegister: () => void;
  onBackToHome?: () => void;
}

export function LoginPage({ onSwitchToRegister, onBackToHome }: LoginPageProps) {
  const { login, error: authError, clearError } = useAuth();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [localError, setLocalError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLocalError(null);
    clearError();

    const cleanEmail = email.trim();
    if (!cleanEmail) {
      setLocalError('Please enter your email address.');
      return;
    }
    if (!password) {
      setLocalError('Please enter your password.');
      return;
    }

    setIsSubmitting(true);
    try {
      await login({ email: cleanEmail, password });
    } catch (err: unknown) {
      if (err instanceof Error) {
        setLocalError(err.message);
      } else {
        setLocalError('Sign in failed. Please verify your credentials.');
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  const displayError = localError || authError;

  return (
    <div className="min-h-screen bg-slate-950 flex flex-col items-center justify-center p-4 relative overflow-hidden">
      {/* Background glow effects */}
      <div className="absolute top-1/4 left-1/3 w-96 h-96 bg-purple-900/20 rounded-full blur-3xl pointer-events-none" />
      <div className="absolute bottom-1/4 right-1/3 w-96 h-96 bg-cyan-900/15 rounded-full blur-3xl pointer-events-none" />

      <div className="w-full max-w-md bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl p-8 backdrop-blur-xl relative z-10">
        {onBackToHome && (
          <button
            onClick={onBackToHome}
            data-testid="btn-login-back-home"
            className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-purple-400 mb-4 transition font-medium"
          >
            <span>←</span>
            <span>Back to Home</span>
          </button>
        )}

        {/* Brand Header */}
        <div className="flex flex-col items-center text-center mb-8">
          <div className="w-12 h-12 rounded-xl bg-gradient-to-tr from-purple-600 via-indigo-600 to-cyan-400 flex items-center justify-center shadow-lg shadow-purple-900/40 mb-3">
            <span className="text-white font-extrabold text-xl tracking-tight">AL</span>
          </div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Sign in to AgentLens</h1>
          <p className="text-xs text-slate-400 mt-1">
            Enterprise Observability & Trace Debugger for AI Agents
          </p>
        </div>

        {/* Error Alert */}
        {displayError && (
          <div
            data-testid="auth-error-alert"
            className="mb-6 p-3 bg-rose-950/60 border border-rose-800/80 rounded-lg text-rose-200 text-xs flex items-start gap-2"
          >
            <span className="text-rose-400 font-bold shrink-0 mt-0.5">⚠️</span>
            <span>{displayError}</span>
          </div>
        )}

        {/* Login Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label
              htmlFor="login-email"
              className="block text-xs font-medium text-slate-300 mb-1.5"
            >
              Email Address
            </label>
            <input
              id="login-email"
              data-testid="input-email"
              type="email"
              autoComplete="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@agentlens.ai"
              required
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition"
            />
          </div>

          <div>
            <label
              htmlFor="login-password"
              className="block text-xs font-medium text-slate-300 mb-1.5"
            >
              Password
            </label>
            <input
              id="login-password"
              data-testid="input-password"
              type="password"
              autoComplete="current-password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              placeholder="••••••••••••"
              required
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-lg text-slate-100 text-sm placeholder-slate-600 focus:outline-none focus:ring-2 focus:ring-purple-500/50 focus:border-purple-500 transition"
            />
          </div>

          <button
            type="submit"
            data-testid="btn-login-submit"
            disabled={isSubmitting}
            className="w-full mt-2 py-2.5 px-4 bg-gradient-to-r from-purple-600 to-indigo-600 hover:from-purple-500 hover:to-indigo-500 text-white font-medium text-sm rounded-lg shadow-lg shadow-purple-900/30 transition disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {isSubmitting ? (
              <>
                <div className="w-4 h-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                <span>Signing in...</span>
              </>
            ) : (
              <span>Sign In</span>
            )}
          </button>
        </form>

        {/* Footer Switch to Register */}
        <div className="mt-6 pt-6 border-t border-slate-800/80 text-center">
          <p className="text-xs text-slate-400">
            Don't have an account?{' '}
            <button
              type="button"
              data-testid="link-switch-to-register"
              onClick={onSwitchToRegister}
              className="text-purple-400 hover:text-purple-300 font-medium underline underline-offset-2 transition"
            >
              Register here
            </button>
          </p>
        </div>
      </div>
    </div>
  );
}
