import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Eye, EyeOff, ArrowRight, AlertCircle, CheckCircle } from 'lucide-react';
import { useAuth } from '../context/AuthContext';

export const Register: React.FC = () => {
  const { signUp } = useAuth();
  const navigate   = useNavigate();

  const [email,    setEmail]    = useState('');
  const [password, setPassword] = useState('');
  const [confirm,  setConfirm]  = useState('');
  const [showPw,   setShowPw]   = useState(false);
  const [loading,  setLoading]  = useState(false);
  const [error,    setError]    = useState('');
  const [done,     setDone]     = useState(false);

  // Password strength
  const strength = {
    length:  password.length >= 8,
    upper:   /[A-Z]/.test(password),
    number:  /[0-9]/.test(password),
  };
  const strongEnough = strength.length && strength.upper && strength.number;

  const validate = (): string => {
    if (!email.trim())    return 'Email is required.';
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) return 'Enter a valid email address.';
    if (!password)        return 'Password is required.';
    if (!strongEnough)    return 'Password must be 8+ characters and include an uppercase letter and a number.';
    if (password !== confirm) return 'Passwords do not match.';
    return '';
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const err = validate();
    if (err) { setError(err); return; }

    setLoading(true);
    setError('');
    try {
      await signUp(email.trim(), password);
      // Supabase may require email confirmation — show confirmation state
      setDone(true);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Sign-up failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  // ── Confirmation screen ────────────────────────────────────────────────────
  if (done) {
    return (
      <div className="min-h-screen bg-slate-50 flex flex-col">
        <header className="bg-white border-b border-slate-100">
          <div className="max-w-6xl mx-auto px-6 h-14 flex items-center">
            <Link to="/" className="flex items-center gap-2">
              <div className="h-7 w-7 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm">
                <span className="text-white font-bold text-[11px] leading-none select-none">FT</span>
              </div>
              <span className="text-[15px] font-bold text-slate-900 tracking-tight">FinTrace</span>
            </Link>
          </div>
        </header>

        <main className="flex-1 flex items-center justify-center px-4 py-16">
          <div className="w-full max-w-[400px] text-center">
            <div className="h-14 w-14 bg-emerald-100 rounded-full flex items-center justify-center mx-auto mb-5">
              <CheckCircle className="h-7 w-7 text-emerald-600" />
            </div>
            <h1 className="text-[24px] font-bold text-slate-900 mb-3">Check your inbox</h1>
            <p className="text-[14px] text-slate-500 leading-relaxed mb-6">
              We sent a confirmation email to <span className="font-semibold text-slate-700">{email}</span>.
              Click the link to activate your account.
            </p>
            <p className="text-[13px] text-slate-400 mb-6">
              If you don't see it, check your spam folder.
            </p>
            <button
              onClick={() => navigate('/login')}
              className="inline-flex items-center gap-2 px-6 py-2.5 bg-blue-600 hover:bg-blue-700 text-white text-[13px] font-bold rounded-xl transition-colors shadow-sm"
            >
              Go to Sign In <ArrowRight className="h-4 w-4" />
            </button>
          </div>
        </main>
      </div>
    );
  }

  // ── Registration form ──────────────────────────────────────────────────────
  return (
    <div className="min-h-screen bg-slate-50 flex flex-col">

      {/* Top bar */}
      <header className="bg-white border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-6 h-14 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-7 w-7 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm">
              <span className="text-white font-bold text-[11px] leading-none select-none">FT</span>
            </div>
            <span className="text-[15px] font-bold text-slate-900 tracking-tight">FinTrace</span>
          </Link>
          <span className="text-[13px] text-slate-500">
            Already have an account?{' '}
            <Link to="/login" className="text-blue-600 hover:text-blue-700 font-semibold">
              Sign in
            </Link>
          </span>
        </div>
      </header>

      {/* Main */}
      <main className="flex-1 flex items-center justify-center px-4 py-16">
        <div className="w-full max-w-[400px]">

          {/* Heading */}
          <div className="mb-8">
            <h1 className="text-[28px] font-bold text-slate-900 tracking-tight mb-2">
              Create your account
            </h1>
            <p className="text-[14px] text-slate-500">
              Get access to the FinTrace operations platform.
            </p>
          </div>

          {/* Error banner */}
          {error && (
            <div className="flex items-start gap-3 px-4 py-3 bg-red-50 border border-red-200 rounded-xl mb-6">
              <AlertCircle className="h-4 w-4 text-red-500 shrink-0 mt-0.5" />
              <p className="text-[13px] text-red-700 font-medium leading-snug">{error}</p>
            </div>
          )}

          {/* Form */}
          <form onSubmit={handleSubmit} noValidate className="space-y-4">

            {/* Email */}
            <div>
              <label className="block text-[13px] font-semibold text-slate-700 mb-1.5" htmlFor="reg-email">
                Work email
              </label>
              <input
                id="reg-email"
                type="email"
                autoComplete="email"
                value={email}
                onChange={(e) => { setEmail(e.target.value); setError(''); }}
                placeholder="you@company.com"
                className="input w-full h-11 text-[14px]"
                disabled={loading}
              />
            </div>

            {/* Password */}
            <div>
              <label className="block text-[13px] font-semibold text-slate-700 mb-1.5" htmlFor="reg-password">
                Password
              </label>
              <div className="relative">
                <input
                  id="reg-password"
                  type={showPw ? 'text' : 'password'}
                  autoComplete="new-password"
                  value={password}
                  onChange={(e) => { setPassword(e.target.value); setError(''); }}
                  placeholder="Create a strong password"
                  className="input w-full h-11 text-[14px] pr-11"
                  disabled={loading}
                />
                <button
                  type="button"
                  onClick={() => setShowPw((v) => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 transition-colors"
                  tabIndex={-1}
                >
                  {showPw ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>

              {/* Password strength hints */}
              {password.length > 0 && (
                <div className="mt-2 flex items-center gap-4">
                  {[
                    { ok: strength.length, label: '8+ chars' },
                    { ok: strength.upper,  label: 'Uppercase' },
                    { ok: strength.number, label: 'Number' },
                  ].map(({ ok, label }) => (
                    <div key={label} className={`flex items-center gap-1 text-[11px] font-medium ${ok ? 'text-emerald-600' : 'text-slate-400'}`}>
                      <div className={`h-1.5 w-1.5 rounded-full ${ok ? 'bg-emerald-500' : 'bg-slate-300'}`} />
                      {label}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Confirm password */}
            <div>
              <label className="block text-[13px] font-semibold text-slate-700 mb-1.5" htmlFor="reg-confirm">
                Confirm password
              </label>
              <input
                id="reg-confirm"
                type={showPw ? 'text' : 'password'}
                autoComplete="new-password"
                value={confirm}
                onChange={(e) => { setConfirm(e.target.value); setError(''); }}
                placeholder="Repeat your password"
                className={`input w-full h-11 text-[14px] ${
                  confirm && confirm !== password ? 'border-red-300 focus:border-red-400 focus:ring-red-300' : ''
                }`}
                disabled={loading}
              />
              {confirm && confirm !== password && (
                <p className="text-[12px] text-red-500 mt-1 font-medium">Passwords do not match.</p>
              )}
            </div>

            {/* Submit */}
            <button
              type="submit"
              disabled={loading}
              className="w-full h-11 mt-2 inline-flex items-center justify-center gap-2
                bg-blue-600 hover:bg-blue-700 active:bg-blue-800
                text-white text-[14px] font-bold rounded-xl
                transition-colors shadow-sm disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {loading ? (
                <span className="h-4 w-4 border-2 border-white/30 border-t-white rounded-full animate-spin" />
              ) : (
                <>Create Account <ArrowRight className="h-4 w-4" /></>
              )}
            </button>
          </form>

          {/* Footer links */}
          <div className="mt-6 text-center space-y-2">
            <p className="text-[13px] text-slate-500">
              Already have an account?{' '}
              <Link to="/login" className="text-blue-600 hover:text-blue-700 font-semibold">
                Sign in →
              </Link>
            </p>
            <Link to="/" className="block text-[12px] text-slate-400 hover:text-slate-600 transition-colors">
              ← Back to homepage
            </Link>
          </div>
        </div>
      </main>
    </div>
  );
};
