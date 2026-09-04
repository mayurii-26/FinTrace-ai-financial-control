import React, { useEffect } from 'react';
import { Link } from 'react-router-dom';
import {
  ArrowRight, CheckCircle, Shield, Activity, TrendingDown,
  GitBranch, Cpu, BookOpen, AlertTriangle,
} from 'lucide-react';

// ── Lifecycle stage data for the hero visual ──────────────────────────────────
const LIFECYCLE_STAGES = [
  { id: 'ORDER',       label: 'Order',       sub: 'Purchase initiated',   color: 'bg-blue-500',    text: 'text-blue-600' },
  { id: 'PAYMENT',     label: 'Payment',     sub: 'Gateway processed',    color: 'bg-blue-600',    text: 'text-blue-700' },
  { id: 'SETTLEMENT',  label: 'Settlement',  sub: 'Funds aggregated',     color: 'bg-indigo-600',  text: 'text-indigo-700' },
  { id: 'BANK',        label: 'Bank Credit', sub: 'Credited to account',  color: 'bg-emerald-600', text: 'text-emerald-700' },
];

const FEATURES = [
  {
    icon: <GitBranch className="h-5 w-5" />,
    title: 'Financial Lifecycle Trace',
    desc: 'Track every rupee from order through payment, refund, settlement fee and bank credit. Pinpoint exactly where the lifecycle breaks.',
  },
  {
    icon: <Cpu className="h-5 w-5" />,
    title: 'AI-Powered Investigation',
    desc: 'Automated root-cause analysis surfaces evidence, computes financial impact and suggests resolution — before a human ever sees the ticket.',
  },
  {
    icon: <TrendingDown className="h-5 w-5" />,
    title: 'Financial Exposure Prioritisation',
    desc: 'Exceptions are ranked by rupee exposure so your team focuses on the highest-value discrepancies, not the loudest alerts.',
  },
  {
    icon: <Shield className="h-5 w-5" />,
    title: 'Evidence-Backed Recommendations',
    desc: 'Every recommendation is grounded in transaction data, settlement records and gateway logs — not heuristics.',
  },
  {
    icon: <Activity className="h-5 w-5" />,
    title: 'Human-in-the-Loop Control',
    desc: 'Controllers approve, reject or escalate every exception. The AI assists; your team decides.',
  },
  {
    icon: <BookOpen className="h-5 w-5" />,
    title: 'Verification & Audit Trail',
    desc: 'Re-run deterministic controls after every action. Every state change is logged with actor, timestamp and delta.',
  },
];

const EXCEPTION_TYPES = [
  { label: 'Settlement Discrepancy',  color: 'border-l-red-500',    bg: 'bg-red-50' },
  { label: 'Refund Closure Failure',  color: 'border-l-orange-500', bg: 'bg-orange-50' },
  { label: 'Duplicate Event',         color: 'border-l-amber-500',  bg: 'bg-amber-50' },
  { label: 'Orphan Event',            color: 'border-l-purple-500', bg: 'bg-purple-50' },
  { label: 'Missing Downstream',      color: 'border-l-blue-500',   bg: 'bg-blue-50' },
  { label: 'Timing Anomaly',          color: 'border-l-teal-500',   bg: 'bg-teal-50' },
];

// ── Main component ────────────────────────────────────────────────────────────
export const Landing: React.FC = () => {

  // Animate lifecycle stages in sequence
  const [activeStage, setActiveStage] = React.useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setActiveStage((prev) => (prev + 1) % LIFECYCLE_STAGES.length);
    }, 1800);
    return () => clearInterval(timer);
  }, []);

  return (
    <div className="min-h-screen bg-white text-slate-900 font-sans">

      {/* ── Top Navigation ──────────────────────────────────────── */}
      <header className="sticky top-0 z-50 bg-white/95 backdrop-blur-sm border-b border-slate-100">
        <div className="max-w-6xl mx-auto px-6 h-16 flex items-center justify-between">
          {/* Logo */}
          <div className="flex items-center gap-2.5">
            <div className="h-8 w-8 bg-blue-600 rounded-lg flex items-center justify-center shadow-sm">
              <span className="text-white font-bold text-sm leading-none select-none">FT</span>
            </div>
            <span className="text-[17px] font-bold text-slate-900 tracking-tight">FinTrace</span>
          </div>

          {/* Nav actions */}
          <div className="flex items-center gap-3">
            <Link
              to="/login"
              className="text-[13px] font-semibold text-slate-600 hover:text-slate-900 transition-colors px-3 py-2"
            >
              Sign In
            </Link>
            <Link
              to="/register"
              className="inline-flex items-center gap-1.5 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white text-[13px] font-semibold rounded-lg transition-colors shadow-sm"
            >
              Get Started <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>
      </header>

      {/* ════════════════════════════════════════════════════════
          HERO
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-6xl mx-auto px-6 pt-20 pb-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

          {/* Left: copy */}
          <div>
            {/* Label pill */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-50 border border-blue-200 rounded-full mb-6">
              <span className="h-1.5 w-1.5 rounded-full bg-blue-500" />
              <span className="text-[12px] font-semibold text-blue-700 tracking-wide">Financial Lifecycle Intelligence</span>
            </div>

            <h1 className="text-[44px] font-bold text-slate-900 leading-[1.1] tracking-tight mb-5">
              AI-powered financial<br />
              <span className="text-blue-600">exception control</span>
            </h1>

            <p className="text-[17px] text-slate-600 leading-relaxed mb-8 max-w-[480px]">
              FinTrace traces every rupee through the full financial lifecycle — order to bank credit — and
              automatically investigates settlement discrepancies, refund failures and downstream anomalies
              before they become losses.
            </p>

            <div className="flex items-center gap-3 flex-wrap">
              <Link
                to="/register"
                className="inline-flex items-center gap-2 px-6 py-3 bg-blue-600 hover:bg-blue-700 text-white text-[14px] font-bold rounded-xl transition-colors shadow-sm"
              >
                Get Started <ArrowRight className="h-4 w-4" />
              </Link>
              <Link
                to="/login"
                className="inline-flex items-center gap-2 px-6 py-3 border border-slate-200 hover:border-slate-300 text-slate-700 hover:text-slate-900 text-[14px] font-semibold rounded-xl transition-colors"
              >
                Sign In
              </Link>
            </div>

            {/* Trust indicators */}
            <div className="mt-10 flex items-center gap-6 flex-wrap">
              {[
                'AI root-cause analysis',
                'Human-in-the-loop control',
                'Full audit trail',
              ].map((item) => (
                <div key={item} className="flex items-center gap-1.5">
                  <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0" />
                  <span className="text-[13px] text-slate-600 font-medium">{item}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Right: lifecycle visualisation */}
          <div className="relative">
            {/* Card container */}
            <div className="bg-slate-50 border border-slate-200 rounded-2xl p-6 shadow-sm">

              {/* Section label */}
              <div className="flex items-center gap-2 mb-5">
                <div className="h-px flex-1 bg-slate-200" />
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest px-2">
                  Financial Lifecycle
                </span>
                <div className="h-px flex-1 bg-slate-200" />
              </div>

              {/* Stage flow */}
              <div className="flex items-center gap-2 overflow-x-auto pb-1">
                {LIFECYCLE_STAGES.map((stage, i) => {
                  const isActive  = activeStage === i;
                  const isPast    = activeStage > i;
                  const isLast    = i === LIFECYCLE_STAGES.length - 1;
                  return (
                    <React.Fragment key={stage.id}>
                      <div
                        className={`flex flex-col items-center gap-2 px-4 py-3 rounded-xl border-2 min-w-[90px] transition-all duration-500 ${
                          isActive
                            ? 'border-blue-500 bg-blue-50 shadow-sm'
                            : isPast
                            ? 'border-emerald-300 bg-emerald-50'
                            : 'border-slate-200 bg-white'
                        }`}
                      >
                        <div className={`h-2.5 w-2.5 rounded-full transition-all duration-500 ${
                          isActive ? 'bg-blue-500 scale-125' : isPast ? 'bg-emerald-500' : stage.color + ' opacity-30'
                        }`} />
                        <span className={`text-[10px] font-bold uppercase tracking-wide text-center leading-tight transition-colors ${
                          isActive ? 'text-blue-700' : isPast ? 'text-emerald-700' : 'text-slate-400'
                        }`}>
                          {stage.label}
                        </span>
                        <span className="text-[9px] text-slate-400 text-center leading-tight">{stage.sub}</span>
                      </div>

                      {!isLast && (
                        <ArrowRight className={`h-3.5 w-3.5 shrink-0 transition-colors duration-500 ${
                          isPast ? 'text-emerald-400' : 'text-slate-300'
                        }`} />
                      )}
                    </React.Fragment>
                  );
                })}
              </div>

              {/* Exception types strip */}
              <div className="mt-5 pt-4 border-t border-slate-200">
                <div className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mb-3">
                  Exception types detected
                </div>
                <div className="grid grid-cols-2 gap-2">
                  {EXCEPTION_TYPES.map((t) => (
                    <div
                      key={t.label}
                      className={`flex items-center gap-2 px-3 py-2 border-l-[3px] rounded-r-lg ${t.color} ${t.bg}`}
                    >
                      <AlertTriangle className="h-3 w-3 text-slate-400 shrink-0" />
                      <span className="text-[11px] font-medium text-slate-700 leading-tight">{t.label}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {/* Floating badge */}
            <div className="absolute -top-3 -right-3 bg-blue-600 text-white text-[11px] font-bold px-3 py-1.5 rounded-full shadow-md">
              Live Tracing
            </div>
          </div>
        </div>
      </section>

      {/* ── Divider ─────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6">
        <div className="h-px bg-slate-100" />
      </div>

      {/* ════════════════════════════════════════════════════════
          FEATURES
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="text-center mb-14">
          <h2 className="text-[32px] font-bold text-slate-900 tracking-tight mb-3">
            Every layer of financial control
          </h2>
          <p className="text-[16px] text-slate-500 max-w-xl mx-auto">
            From automated detection to AI investigation to human sign-off and immutable audit — one platform, end to end.
          </p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
          {FEATURES.map((feat) => (
            <div
              key={feat.title}
              className="bg-white border border-slate-200 rounded-xl p-6 hover:shadow-sm hover:border-slate-300 transition-all"
            >
              <div className="h-9 w-9 bg-blue-50 rounded-lg flex items-center justify-center text-blue-600 mb-4">
                {feat.icon}
              </div>
              <h3 className="text-[15px] font-bold text-slate-900 mb-2">{feat.title}</h3>
              <p className="text-[13px] text-slate-500 leading-relaxed">{feat.desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* ── Divider ─────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6">
        <div className="h-px bg-slate-100" />
      </div>

      {/* ════════════════════════════════════════════════════════
          LIFECYCLE DETAIL SECTION
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

          {/* Left: detailed lifecycle table */}
          <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden shadow-sm">
            {/* Header */}
            <div className="bg-slate-900 px-6 py-4">
              <h3 className="text-[14px] font-bold text-white">Financial Lifecycle Trace</h3>
              <p className="text-[11px] text-slate-400 mt-0.5">
                TXN · order_a1b2c3 · BREAK detected
              </p>
            </div>

            {/* Stage rows */}
            <div className="divide-y divide-slate-100">
              {[
                { stage: 'ORDER',               status: 'VALID',   amount: '₹12,500.00', time: '09:14:02' },
                { stage: 'PAYMENT',             status: 'VALID',   amount: '₹12,500.00', time: '09:14:08' },
                { stage: 'REFUND',              status: 'VALID',   amount: '₹2,500.00',  time: '10:22:41' },
                { stage: 'EXPECTED SETTLEMENT', status: 'VALID',   amount: '₹9,812.50',  time: '—' },
                { stage: 'ACTUAL SETTLEMENT',   status: 'BREAK',   amount: '₹9,200.00',  time: '14:05:17' },
                { stage: 'BANK CREDIT',         status: 'MISSING', amount: '—',           time: '—' },
              ].map(({ stage, status, amount, time }) => (
                <div key={stage} className={`flex items-center gap-3 px-5 py-3 ${
                  status === 'BREAK' ? 'bg-red-50' : status === 'MISSING' ? 'bg-slate-50 opacity-60' : ''
                }`}>
                  <div className={`h-2 w-2 rounded-full shrink-0 ${
                    status === 'VALID' ? 'bg-emerald-500'
                    : status === 'BREAK' ? 'bg-red-500'
                    : 'bg-slate-300'
                  }`} />
                  <div className="flex-1 min-w-0">
                    <span className={`text-[11px] font-bold uppercase tracking-wide ${
                      status === 'BREAK' ? 'text-red-700'
                      : status === 'MISSING' ? 'text-slate-400'
                      : 'text-slate-700'
                    }`}>{stage}</span>
                  </div>
                  <span className={`text-[12px] font-mono font-semibold ${
                    status === 'BREAK' ? 'text-red-600'
                    : status === 'MISSING' ? 'text-slate-400'
                    : 'text-slate-700'
                  }`}>{amount}</span>
                  <span className="text-[10px] text-slate-400 w-14 text-right shrink-0">{time}</span>
                  {status === 'BREAK' && (
                    <span className="text-[9px] font-bold bg-red-500 text-white px-1.5 py-0.5 rounded-full leading-none shrink-0">
                      BREAK
                    </span>
                  )}
                </div>
              ))}
            </div>

            {/* Exposure summary */}
            <div className="px-6 py-4 bg-red-50 border-t border-red-200">
              <div className="flex items-center justify-between">
                <span className="text-[12px] font-semibold text-red-600 uppercase tracking-wide">
                  Exposure Detected
                </span>
                <span className="text-[20px] font-bold font-mono tabular-nums text-red-600">₹612.50</span>
              </div>
            </div>
          </div>

          {/* Right: copy */}
          <div>
            <div className="text-[11px] font-bold text-blue-600 uppercase tracking-widest mb-3">
              Lifecycle Integrity
            </div>
            <h2 className="text-[30px] font-bold text-slate-900 tracking-tight leading-tight mb-5">
              Know exactly where money diverges
            </h2>
            <p className="text-[15px] text-slate-600 leading-relaxed mb-6">
              Traditional reconciliation compares two spreadsheets at month-end. FinTrace builds a live
              graph of every financial event — order, payment, refund, fee, settlement, bank credit — and
              detects divergence the moment it occurs.
            </p>
            <ul className="space-y-3">
              {[
                'Settlement amount mismatches flagged at row level',
                'Refund closures verified against gateway records',
                'Orphan events and missing downstream stages surfaced automatically',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span className="text-[14px] text-slate-700">{item}</span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      {/* ── Divider ─────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6">
        <div className="h-px bg-slate-100" />
      </div>

      {/* ════════════════════════════════════════════════════════
          AI INVESTIGATION SECTION
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-6xl mx-auto px-6 py-20">
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-16 items-center">

          {/* Left: copy */}
          <div>
            <div className="text-[11px] font-bold text-blue-600 uppercase tracking-widest mb-3">
              AI Investigation
            </div>
            <h2 className="text-[30px] font-bold text-slate-900 tracking-tight leading-tight mb-5">
              Root cause, not just a flag
            </h2>
            <p className="text-[15px] text-slate-600 leading-relaxed mb-6">
              When an exception is detected, an AI agent gathers evidence, identifies the root cause,
              quantifies the financial impact and recommends an action — all before a controller opens the ticket.
            </p>
            <ul className="space-y-3">
              {[
                'Structured evidence collection via deterministic tool calls',
                'Confidence-banded output: High / Requires Verification / Insufficient Evidence',
                'Recommended action: approve, reject or escalate with justification',
                'Human controller has final say — AI assists, not decides',
              ].map((item) => (
                <li key={item} className="flex items-start gap-2.5">
                  <CheckCircle className="h-4 w-4 text-emerald-500 shrink-0 mt-0.5" />
                  <span className="text-[14px] text-slate-700">{item}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Right: AI investigation card mock */}
          <div className="space-y-3">
            {/* Confidence band */}
            <div className="flex items-center gap-3 px-4 py-3 bg-amber-50 border border-amber-200 rounded-xl">
              <AlertTriangle className="h-4 w-4 text-amber-600 shrink-0" />
              <span className="text-[13px] font-semibold text-amber-700">Requires Verification</span>
              <span className="ml-auto text-[13px] font-mono font-bold text-amber-700">72% confidence</span>
            </div>

            {/* Root cause */}
            <div className="bg-white border border-slate-200 rounded-xl p-4 shadow-sm">
              <div className="text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-2">Root Cause</div>
              <div className="bg-red-50 border-l-[3px] border-red-500 rounded-r-lg p-3">
                <p className="text-[13px] text-slate-700 leading-relaxed">
                  Settlement amount ₹612.50 below expected due to unmatched MDR deduction applied after
                  partial refund. Bank credit not yet received.
                </p>
              </div>
            </div>

            {/* Recommendation */}
            <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
              <div className="flex items-center gap-2 mb-2">
                <Shield className="h-4 w-4 text-blue-600" />
                <span className="text-[10px] font-bold text-blue-700 uppercase tracking-widest">Recommendation</span>
                <span className="ml-auto px-2 py-0.5 bg-blue-600 text-white text-[10px] font-bold uppercase tracking-wide rounded-md">
                  ESCALATE
                </span>
              </div>
              <p className="text-[12px] text-slate-700 leading-relaxed">
                Refer to settlement desk for manual MDR reconciliation. Flag bank credit absence for T+2 follow-up.
              </p>
            </div>
          </div>
        </div>
      </section>

      {/* ── Divider ─────────────────────────────────────────────── */}
      <div className="max-w-6xl mx-auto px-6">
        <div className="h-px bg-slate-100" />
      </div>

      {/* ════════════════════════════════════════════════════════
          FINAL CTA
      ════════════════════════════════════════════════════════ */}
      <section className="max-w-6xl mx-auto px-6 py-24">
        <div className="bg-slate-900 rounded-2xl px-10 py-16 text-center">
          <div className="inline-flex items-center gap-2 px-3 py-1.5 bg-blue-900/60 border border-blue-700 rounded-full mb-6">
            <span className="h-1.5 w-1.5 rounded-full bg-blue-400" />
            <span className="text-[12px] font-semibold text-blue-300 tracking-wide">Financial Operations Platform</span>
          </div>
          <h2 className="text-[36px] font-bold text-white tracking-tight leading-tight mb-5 max-w-xl mx-auto">
            Take control of your financial lifecycle
          </h2>
          <p className="text-[16px] text-slate-400 mb-10 max-w-lg mx-auto leading-relaxed">
            Sign in to your FinTrace workspace to start investigating exceptions, reviewing AI recommendations
            and auditing every financial action taken.
          </p>
          <div className="flex items-center justify-center gap-4 flex-wrap">
            <Link
              to="/register"
              className="inline-flex items-center gap-2 px-7 py-3.5 bg-blue-600 hover:bg-blue-500 text-white text-[14px] font-bold rounded-xl transition-colors shadow-md"
            >
              Get Started <ArrowRight className="h-4 w-4" />
            </Link>
            <Link
              to="/login"
              className="inline-flex items-center gap-2 px-7 py-3.5 border border-slate-600 hover:border-slate-400 text-slate-300 hover:text-white text-[14px] font-semibold rounded-xl transition-colors"
            >
              Sign In
            </Link>
          </div>
        </div>
      </section>

      {/* ── Footer ──────────────────────────────────────────────── */}
      <footer className="border-t border-slate-100 bg-white">
        <div className="max-w-6xl mx-auto px-6 py-6 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="h-6 w-6 bg-blue-600 rounded-md flex items-center justify-center">
              <span className="text-white font-bold text-[10px] leading-none">FT</span>
            </div>
            <span className="text-[13px] font-semibold text-slate-700">FinTrace</span>
          </div>
          <span className="text-[12px] text-slate-400">Financial Lifecycle Intelligence · v1.1.0</span>
        </div>
      </footer>

    </div>
  );
};
