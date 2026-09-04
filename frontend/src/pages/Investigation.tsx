import React, { useEffect, useState, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import {
  AlertTriangle, CheckCircle, XCircle, ArrowRight, Cpu, FileSearch,
  ThumbsUp, ThumbsDown, ArrowUpCircle, RefreshCw, ChevronLeft, Loader2,
  Shield, Info, TrendingDown, CircleDot, Clock,
} from 'lucide-react';
import { Badge, LoadingState, ErrorState, useToast } from '../components';
import {
  fetchExceptionDetail, runInvestigation, applyAction, verifyException,
} from '../api/endpoints';
import type {
  ExceptionDetail, InvestigateResponse, VerificationResult,
  LifecycleTrace, ControllerAction,
} from '../api/types';

// ── Labels ────────────────────────────────────────────────────────────────────
const TYPE_LABEL: Record<string, string> = {
  settlement_amount_discrepancy: 'Settlement Amount Discrepancy',
  refund_closure_failure:        'Refund Closure Failure',
  duplicate_financial_event:     'Duplicate Financial Event',
  orphan_financial_event:        'Orphan Financial Event',
  missing_downstream_event:      'Missing Downstream Event',
  settlement_timing_anomaly:     'Settlement Timing Anomaly',
};

// ── Lifecycle stage styling ────────────────────────────────────────────────────
const STAGE_STYLE: Record<string, {
  card: string; dot: string; label: string; amount: string; ring?: string;
}> = {
  VALID:   { card: 'bg-emerald-50 border-emerald-200',  dot: 'bg-emerald-500', label: 'text-emerald-700', amount: 'text-emerald-700' },
  WARNING: { card: 'bg-amber-50  border-amber-200',     dot: 'bg-amber-500',   label: 'text-amber-700',   amount: 'text-amber-700'   },
  BREAK:   { card: 'bg-red-50    border-red-300',       dot: 'bg-red-500',     label: 'text-red-700',     amount: 'text-red-700',    ring: 'ring-2 ring-red-400 ring-offset-1' },
  MISSING: { card: 'bg-slate-50  border-slate-200',     dot: 'bg-slate-300',   label: 'text-slate-400',   amount: 'text-slate-400'   },
};

// ── Confidence band styling ───────────────────────────────────────────────────
const CONF_BAND: Record<string, { color: string; bg: string; label: string; icon: React.ReactNode }> = {
  high_confidence:       { color: 'text-emerald-700', bg: 'bg-emerald-50 border-emerald-200',  label: 'High Confidence',       icon: <CheckCircle className="h-4 w-4" /> },
  requires_verification: { color: 'text-amber-700',   bg: 'bg-amber-50 border-amber-200',      label: 'Requires Verification', icon: <AlertTriangle className="h-4 w-4" /> },
  insufficient_evidence: { color: 'text-red-700',     bg: 'bg-red-50 border-red-200',          label: 'Insufficient Evidence', icon: <XCircle className="h-4 w-4" /> },
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function fmtInr(v: string | null) {
  if (!v) return '–';
  const n = parseFloat(v);
  if (isNaN(n)) return v;
  if (n >= 1_00_00_000) return '₹' + (n / 1_00_00_000).toFixed(2) + ' Cr';
  if (n >= 1_00_000)    return '₹' + (n / 1_00_000).toFixed(2) + ' L';
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2 });
}

function fmtTs(iso: string | null) {
  if (!iso) return '–';
  return new Date(iso).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
}

// ── Section title helper ──────────────────────────────────────────────────────
const SectionLabel: React.FC<{ icon?: React.ReactNode; title: string; sub?: string; right?: React.ReactNode }> = ({
  icon, title, sub, right,
}) => (
  <div className="flex items-start justify-between gap-4">
    <div className="flex items-start gap-2">
      {icon && <span className="mt-0.5 text-slate-400 shrink-0">{icon}</span>}
      <div>
        <h2 className="section-title">{title}</h2>
        {sub && <p className="section-subtitle">{sub}</p>}
      </div>
    </div>
    {right}
  </div>
);

// ── Lifecycle Trace ───────────────────────────────────────────────────────────
const TraceView: React.FC<{ trace: LifecycleTrace }> = ({ trace }) => {
  const stages = trace.stages;

  return (
    <div className="space-y-4">
      {/* Journey strip */}
      <div className="flex items-start gap-1 overflow-x-auto pb-2">
        {stages.map((stage, i) => {
          const st = STAGE_STYLE[stage.status] ?? STAGE_STYLE.MISSING;
          const isLast = i === stages.length - 1;
          const isBreak = stage.status === 'BREAK';
          const isMissing = stage.status === 'MISSING';

          return (
            <React.Fragment key={stage.stage}>
              {/* Stage card */}
              <div className={`relative flex flex-col items-center gap-1.5 px-3 py-3 rounded-xl border
                min-w-[90px] max-w-[120px] flex-shrink-0 transition-all
                ${st.card} ${st.ring ?? ''}`}
              >
                {/* Status dot */}
                <div className={`h-2 w-2 rounded-full ${st.dot}`} />

                {/* Stage name */}
                <span className={`text-[10px] font-bold text-center leading-tight uppercase tracking-wide ${st.label}`}>
                  {stage.stage.replace(/_/g, ' ')}
                </span>

                {/* Amount */}
                {stage.amount && (
                  <span className={`text-[11px] font-mono font-bold ${st.amount}`}>
                    {fmtInr(stage.amount)}
                  </span>
                )}

                {/* Timestamp */}
                {stage.timestamp && (
                  <span className="text-[9px] text-slate-400 text-center leading-tight font-medium">
                    {fmtTs(stage.timestamp)}
                  </span>
                )}

                {/* Status badge */}
                {isBreak && (
                  <span className="absolute -top-2 -right-1.5 bg-red-500 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full leading-none">
                    BREAK
                  </span>
                )}
                {isMissing && (
                  <span className="absolute -top-2 -right-1.5 bg-slate-400 text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full leading-none">
                    N/A
                  </span>
                )}
              </div>

              {/* Connector arrow */}
              {!isLast && (
                <div className="flex items-center pt-6 flex-shrink-0">
                  <div className={`h-px w-3 ${
                    isBreak || stages[i + 1]?.status === 'BREAK' ? 'bg-red-300'
                    : stage.status === 'MISSING' || stages[i + 1]?.status === 'MISSING' ? 'bg-slate-200'
                    : 'bg-emerald-300'
                  }`} />
                  <ArrowRight className={`h-3 w-3 flex-shrink-0 ${
                    isBreak || stages[i + 1]?.status === 'BREAK' ? 'text-red-400' : 'text-slate-300'
                  }`} />
                </div>
              )}
            </React.Fragment>
          );
        })}
      </div>

      {/* Annotation rows for non-VALID stages */}
      {stages
        .filter((s) => s.status !== 'VALID')
        .map((stage) => {
          const isBreak   = stage.status === 'BREAK';
          const isWarning = stage.status === 'WARNING';
          return (
            <div
              key={stage.stage + '_note'}
              className={`flex items-start gap-3 p-3.5 rounded-xl border text-sm
                ${isBreak   ? 'bg-red-50 border-red-200'    : ''}
                ${isWarning ? 'bg-amber-50 border-amber-200' : ''}
                ${!isBreak && !isWarning ? 'bg-slate-50 border-slate-200' : ''}
              `}
            >
              <Info className={`h-4 w-4 mt-0.5 shrink-0 ${isBreak ? 'text-red-500' : isWarning ? 'text-amber-500' : 'text-slate-400'}`} />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap mb-1">
                  <span className={`text-[11px] font-bold uppercase tracking-wide ${isBreak ? 'text-red-700' : isWarning ? 'text-amber-700' : 'text-slate-600'}`}>
                    {stage.stage.replace(/_/g, ' ')}
                  </span>
                  {stage.timestamp && (
                    <span className="text-[11px] text-slate-400 font-medium">{fmtTs(stage.timestamp)}</span>
                  )}
                  {stage.amount && (
                    <span className={`text-[11px] font-mono font-bold ${isBreak ? 'text-red-600' : 'text-amber-600'}`}>
                      {fmtInr(stage.amount)}
                    </span>
                  )}
                </div>
                {stage.notes && (
                  <p className={`text-[13px] leading-relaxed ${isBreak ? 'text-red-600' : isWarning ? 'text-amber-700' : 'text-slate-500'}`}>
                    {stage.notes}
                  </p>
                )}
              </div>
            </div>
          );
        })}
    </div>
  );
};

// ── Main Investigation Page ───────────────────────────────────────────────────
export const Investigation: React.FC = () => {
  const { exceptionId } = useParams<{ exceptionId: string }>();
  const navigate = useNavigate();
  const { toast } = useToast();

  const [exc,           setExc]           = useState<ExceptionDetail | null>(null);
  const [inv,           setInv]           = useState<InvestigateResponse | null>(null);
  const [verify,        setVerify]        = useState<VerificationResult | null>(null);
  const [loading,       setLoading]       = useState(true);
  const [investigating, setInvestigating] = useState(false);
  const [actioning,     setActioning]     = useState(false);
  const [verifying,     setVerifying]     = useState(false);
  const [error,         setError]         = useState<string | null>(null);
  const [showTools,     setShowTools]     = useState(false);

  const load = useCallback(async () => {
    if (!exceptionId) return;
    setLoading(true); setError(null);
    try {
      setExc(await fetchExceptionDetail(exceptionId));
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load exception.');
    } finally {
      setLoading(false);
    }
  }, [exceptionId]);

  useEffect(() => { load(); }, [load]);

  const handleInvestigate = async () => {
    if (!exceptionId) return;
    setInvestigating(true);
    try {
      setInv(await runInvestigation(exceptionId, 'mock'));
      toast('success', 'Investigation complete.');
    } catch (e: unknown) {
      toast('error', e instanceof Error ? e.message : 'Investigation failed.');
    } finally {
      setInvestigating(false);
    }
  };

  const handleAction = async (action: ControllerAction) => {
    if (!exceptionId) return;
    setActioning(true);
    try {
      await applyAction(exceptionId, action);
      toast('success', `Exception ${action}d successfully.`);
      await load();
    } catch (e: unknown) {
      toast('error', e instanceof Error ? e.message : 'Action failed.');
    } finally {
      setActioning(false);
    }
  };

  const handleVerify = async () => {
    if (!exceptionId) return;
    setVerifying(true);
    try {
      const result = await verifyException(exceptionId);
      setVerify(result);
      toast('info', `Verification: ${result.verification_status}.`);
    } catch (e: unknown) {
      toast('error', e instanceof Error ? e.message : 'Verification failed.');
    } finally {
      setVerifying(false);
    }
  };

  if (loading) return <LoadingState message="Loading exception…" />;
  if (error)   return <ErrorState message={error} onRetry={load} />;
  if (!exc)    return null;

  const invData       = inv?.investigation;
  const bandInfo      = invData ? CONF_BAND[invData.confidence_band] : null;
  const isActionable  = exc.status === 'open' || exc.status === 'auto_resolved';
  const exposure      = parseFloat(exc.financial_exposure);

  return (
    <div className="space-y-5 max-w-[1100px]">

      {/* ── Back navigation ──────────────────────────────────── */}
      <button onClick={() => navigate('/exceptions')} className="btn-ghost -ml-1">
        <ChevronLeft className="h-4 w-4" /> Back to Exceptions
      </button>

      {/* ═══════════════════════════════════════════════════════
          HERO HEADER — Exception identity + exposure
      ════════════════════════════════════════════════════════ */}
      <div className="card p-0 overflow-hidden">
        {/* Top accent bar per severity */}
        <div className={`h-1 w-full ${
          exc.severity === 'critical' ? 'bg-red-500'
          : exc.severity === 'high'   ? 'bg-orange-500'
          : exc.severity === 'medium' ? 'bg-amber-400'
          : 'bg-slate-300'
        }`} />

        <div className="p-6">
          <div className="flex flex-wrap items-start gap-6">
            {/* Identity block */}
            <div className="flex-1 min-w-0">
              {/* Badges row */}
              <div className="flex items-center gap-2 mb-3 flex-wrap">
                <Badge variant={exc.severity} dot>{exc.severity.toUpperCase()}</Badge>
                <Badge variant={exc.status as 'open'}>{exc.status.replace(/_/g, ' ')}</Badge>
                <span className="text-[11px] font-mono text-slate-400 bg-slate-100 px-2 py-0.5 rounded">
                  {exc.exception_id}
                </span>
              </div>

              {/* Exception type */}
              <h1 className="text-[26px] font-bold text-slate-900 tracking-tight leading-tight mb-2">
                {TYPE_LABEL[exc.exception_type] ?? exc.exception_type}
              </h1>

              {/* Transaction ID */}
              <div className="flex items-center gap-2">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest">TXN</span>
                <span className="text-[14px] font-mono font-semibold text-slate-600">{exc.transaction_id}</span>
              </div>
            </div>

            {/* Financial exposure block */}
            <div className="shrink-0">
              <div className={`border rounded-xl px-6 py-4 text-center ${
                exposure > 500_000 ? 'bg-red-50 border-red-200'
                : exposure > 100_000 ? 'bg-orange-50 border-orange-200'
                : 'bg-amber-50 border-amber-200'
              }`}>
                <div className="stat-label mb-1.5">Financial Exposure</div>
                <div className={`text-[32px] font-bold font-mono tabular-nums leading-none ${
                  exposure > 500_000 ? 'text-red-600'
                  : exposure > 100_000 ? 'text-orange-600'
                  : 'text-amber-700'
                }`}>
                  {fmtInr(exc.financial_exposure)}
                </div>
              </div>
            </div>
          </div>

          {/* Meta row */}
          <div className="mt-5 pt-4 border-t border-slate-100 flex flex-wrap gap-x-8 gap-y-2">
            <div>
              <span className="stat-label">Detected</span>
              <div className="text-[13px] font-medium text-slate-700 mt-0.5">{fmtTs(exc.detected_at)}</div>
            </div>
            {exc.ground_truth_type && (
              <div>
                <span className="stat-label">Ground Truth</span>
                <div className="text-[13px] font-medium text-slate-700 mt-0.5">
                  {TYPE_LABEL[exc.ground_truth_type] ?? exc.ground_truth_type}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════
          FINANCIAL LIFECYCLE TRACE — Hero section
      ════════════════════════════════════════════════════════ */}
      <div className="card overflow-hidden">
        {/* Section header */}
        <div className="px-6 py-4 border-b border-slate-100 bg-slate-900 flex items-center justify-between">
          <div>
            <h2 className="text-[14px] font-bold text-white tracking-tight">Financial Lifecycle Trace</h2>
            <p className="text-[11px] text-slate-400 mt-0.5 font-medium">
              ORDER → PAYMENT → REFUND → FEE / TAX → EXPECTED SETTLEMENT → ACTUAL SETTLEMENT → BANK CREDIT
            </p>
          </div>
          {inv?.lifecycle_trace?.overall_status && (
            <div className={`px-3 py-1.5 rounded-lg text-[11px] font-bold uppercase tracking-wide border ${
              inv.lifecycle_trace.overall_status === 'VALID' ? 'bg-emerald-900/40 text-emerald-300 border-emerald-700'
              : inv.lifecycle_trace.overall_status === 'BREAK' ? 'bg-red-900/40 text-red-300 border-red-700'
              : 'bg-amber-900/40 text-amber-300 border-amber-700'
            }`}>
              {inv.lifecycle_trace.overall_status}
            </div>
          )}
        </div>

        <div className="p-6">
          {inv?.lifecycle_trace ? (
            <TraceView trace={inv.lifecycle_trace} />
          ) : (
            <div className="flex flex-col items-center justify-center py-10 gap-3">
              <div className="flex items-center gap-1.5 opacity-25">
                {['ORDER', 'PAYMENT', 'REFUND', 'SETTLEMENT', 'BANK'].map((s, i, arr) => (
                  <React.Fragment key={s}>
                    <div className="flex flex-col items-center gap-1">
                      <CircleDot className="h-5 w-5 text-slate-400" />
                      <span className="text-[9px] text-slate-400 font-bold uppercase tracking-wide">{s}</span>
                    </div>
                    {i < arr.length - 1 && <ArrowRight className="h-3 w-3 text-slate-300" />}
                  </React.Fragment>
                ))}
              </div>
              <p className="text-[13px] text-slate-400 font-medium">
                Run investigation to reveal the financial lifecycle trace
              </p>
            </div>
          )}
        </div>
      </div>

      {/* ═══════════════════════════════════════════════════════
          AI INVESTIGATION — Root cause, evidence, recommendation
      ════════════════════════════════════════════════════════ */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <SectionLabel
            icon={<Cpu className="h-4 w-4" />}
            title="AI Investigation"
            sub="Evidence-based root cause analysis"
          />
          {!invData && (
            <button
              onClick={handleInvestigate}
              disabled={investigating}
              className="btn-primary disabled:opacity-60"
            >
              {investigating
                ? <Loader2 className="h-4 w-4 animate-spin" />
                : <Cpu className="h-4 w-4" />}
              {investigating ? 'Investigating…' : 'Run Investigation'}
            </button>
          )}
        </div>

        {invData ? (
          <div className="p-6 space-y-6">

            {/* Confidence band */}
            {bandInfo && (
              <div className={`flex items-center gap-3 px-4 py-3 rounded-xl border font-medium ${bandInfo.color} ${bandInfo.bg}`}>
                {bandInfo.icon}
                <span className="text-[14px] font-semibold">{bandInfo.label}</span>
                <span className="ml-auto text-[14px] font-mono font-bold">
                  {Math.round(invData.confidence * 100)}% confidence
                </span>
              </div>
            )}

            {/* Root cause + Financial impact — 2 col on larger screens */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              {/* Root cause */}
              <div>
                <div className="stat-label mb-2">Root Cause</div>
                <div className="bg-red-50 border-l-[3px] border-red-500 rounded-r-xl p-4">
                  <p className="text-[14px] text-slate-800 leading-relaxed font-medium">{invData.root_cause}</p>
                </div>
              </div>

              {/* Financial impact */}
              {invData.impact_summary && (
                <div>
                  <div className="stat-label mb-2">Financial Impact</div>
                  <div className="bg-orange-50 border-l-[3px] border-orange-400 rounded-r-xl p-4">
                    <p className="text-[14px] text-slate-800 leading-relaxed">{invData.impact_summary}</p>
                  </div>
                </div>
              )}
            </div>

            {/* Evidence grid */}
            {Object.keys(invData.evidence ?? {}).length > 0 && (
              <div>
                <div className="stat-label mb-3">Evidence</div>
                <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
                  {Object.entries(invData.evidence ?? {}).map(([k, v]) =>
                    v != null && typeof v !== 'object' ? (
                      <div key={k} className="bg-slate-50 border border-slate-200 rounded-lg px-3 py-2.5">
                        <div className="text-[10px] text-slate-400 uppercase tracking-wide font-semibold mb-1">
                          {k.replace(/_/g, ' ')}
                        </div>
                        <div className="text-[13px] font-mono text-slate-800 font-semibold truncate">{String(v)}</div>
                      </div>
                    ) : null
                  )}
                </div>
              </div>
            )}

            {/* Missing evidence */}
            {invData.missing_evidence.length > 0 && (
              <div>
                <div className="stat-label mb-2">Missing Evidence</div>
                <div className="flex flex-wrap gap-2">
                  {invData.missing_evidence.map((m) => (
                    <span
                      key={m}
                      className="text-[12px] px-2.5 py-1 bg-amber-50 text-amber-700 border border-amber-200 rounded-lg font-medium"
                    >
                      {m.replace(/_/g, ' ')}
                    </span>
                  ))}
                </div>
              </div>
            )}

            {/* Recommendation */}
            <div>
              <div className="stat-label mb-2">Recommendation</div>
              <div className="bg-blue-50 border border-blue-200 rounded-xl p-4">
                <div className="flex items-center gap-2 mb-3">
                  <Shield className="h-4 w-4 text-blue-600" />
                  <span className="text-[11px] font-bold uppercase tracking-widest text-blue-700">
                    Recommended Action
                  </span>
                  <span className="ml-auto px-2.5 py-1 bg-blue-600 text-white text-[11px] font-bold uppercase tracking-wide rounded-lg">
                    {invData.recommended_action.replace(/_/g, ' ')}
                  </span>
                </div>
                <p className="text-[14px] text-slate-700 leading-relaxed">{invData.explanation}</p>
              </div>
            </div>

            {/* Human review flag */}
            {invData.requires_human_review && (
              <div className="flex items-center gap-2.5 px-4 py-3 bg-purple-50 border border-purple-200 rounded-xl">
                <AlertTriangle className="h-4 w-4 text-purple-600 shrink-0" />
                <span className="text-[13px] font-semibold text-purple-800">Human review required</span>
              </div>
            )}

            {/* Agent tool trace — collapsible */}
            <div>
              <button
                onClick={() => setShowTools((v) => !v)}
                className="flex items-center gap-2 text-[12px] text-slate-500 hover:text-slate-700 transition-colors font-semibold"
              >
                <FileSearch className="h-3.5 w-3.5" />
                {showTools ? 'Hide' : 'Show'} agent tool trace ({invData.tool_calls.length} calls)
              </button>
              {showTools && (
                <div className="mt-3 space-y-2">
                  {invData.tool_calls.map((tc, i) => (
                    <div key={i} className="bg-slate-50 border border-slate-200 rounded-xl p-3.5">
                      <div className="flex items-center gap-2 mb-1.5 flex-wrap">
                        <span className="text-[12px] font-mono text-blue-600 font-bold">{tc.tool_name}</span>
                        <span className="text-[11px] text-slate-400 font-mono">
                          ({Object.entries(tc.arguments).map(([k, v]) => `${k}=${v}`).join(', ')})
                        </span>
                      </div>
                      <p className="text-[12px] text-slate-600 leading-relaxed">{tc.result_summary}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ) : (
          <div className="px-6 py-14 text-center">
            <Cpu className="h-10 w-10 text-slate-200 mx-auto mb-3" />
            <p className="text-[14px] text-slate-500 font-medium mb-1">No investigation run yet</p>
            <p className="text-[13px] text-slate-400">
              Click Run Investigation to analyse root cause, evidence and financial impact.
            </p>
          </div>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════
          CONTROLLER ACTIONS — Approve / Reject / Escalate
      ════════════════════════════════════════════════════════ */}
      {isActionable && (
        <div className="card p-6">
          <div className="mb-4">
            <SectionLabel
              icon={<Shield className="h-4 w-4" />}
              title="Controller Actions"
              sub="Synthetic state transitions — no real money movement"
            />
          </div>

          <div className="flex gap-3 flex-wrap">
            {([
              {
                action: 'approve' as ControllerAction,
                label:  'Approve',
                cls:    'bg-emerald-600 hover:bg-emerald-700 text-white border-emerald-600',
                icon:   <ThumbsUp className="h-4 w-4" />,
              },
              {
                action: 'reject' as ControllerAction,
                label:  'Reject',
                cls:    'bg-red-600 hover:bg-red-700 text-white border-red-600',
                icon:   <ThumbsDown className="h-4 w-4" />,
              },
              {
                action: 'escalate' as ControllerAction,
                label:  'Escalate',
                cls:    'bg-purple-600 hover:bg-purple-700 text-white border-purple-600',
                icon:   <ArrowUpCircle className="h-4 w-4" />,
              },
            ]).map(({ action, label, cls, icon }) => (
              <button
                key={action}
                onClick={() => handleAction(action)}
                disabled={actioning}
                className={`inline-flex items-center gap-2 px-5 py-2.5 border text-[13px] font-bold rounded-lg transition-colors disabled:opacity-60 ${cls}`}
              >
                {actioning ? <Loader2 className="h-4 w-4 animate-spin" /> : icon}
                {label}
              </button>
            ))}
          </div>
        </div>
      )}

      {/* ═══════════════════════════════════════════════════════
          VERIFICATION — Before/after exposure
      ════════════════════════════════════════════════════════ */}
      <div className="card p-6">
        <div className="flex items-start justify-between mb-5">
          <SectionLabel
            icon={<CheckCircle className="h-4 w-4" />}
            title="Verification"
            sub="Re-run deterministic control to confirm resolution"
          />
          <button onClick={handleVerify} disabled={verifying} className="btn-ghost">
            {verifying ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
            Verify
          </button>
        </div>

        {verify ? (
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 items-center">
            {/* Before */}
            <div className="bg-red-50 border border-red-200 rounded-xl p-5 text-center">
              <div className="stat-label text-red-500 mb-2">Before</div>
              <div className="text-[26px] font-bold font-mono tabular-nums text-red-600 leading-none">
                {fmtInr(verify.before_exposure)}
              </div>
              <div className="text-[11px] text-red-400 mt-1.5 font-medium">
                {verify.before_exception_type
                  ? (TYPE_LABEL[verify.before_exception_type] ?? verify.before_exception_type)
                  : '—'}
              </div>
            </div>

            {/* Arrow */}
            <div className="flex flex-col items-center gap-2">
              <ArrowRight className="h-6 w-6 text-slate-300" />
              <div className={`px-4 py-2 rounded-xl text-[13px] font-bold border text-center ${
                verify.verification_status === 'resolved' ? 'bg-emerald-50 text-emerald-700 border-emerald-300'
                : verify.verification_status === 'improved' ? 'bg-amber-50 text-amber-700 border-amber-300'
                : 'bg-red-50 text-red-700 border-red-300'
              }`}>
                {verify.verification_status === 'resolved' && <CheckCircle className="h-4 w-4 inline mr-1.5 -mt-0.5" />}
                {verify.verification_status.toUpperCase()}
              </div>
            </div>

            {/* After */}
            <div className={`border rounded-xl p-5 text-center ${
              parseFloat(verify.after_exposure) < parseFloat(verify.before_exposure)
                ? 'bg-emerald-50 border-emerald-200'
                : 'bg-red-50 border-red-200'
            }`}>
              <div className={`stat-label mb-2 ${
                parseFloat(verify.after_exposure) < parseFloat(verify.before_exposure)
                  ? 'text-emerald-500' : 'text-red-500'
              }`}>After</div>
              <div className={`text-[26px] font-bold font-mono tabular-nums leading-none ${
                parseFloat(verify.after_exposure) < parseFloat(verify.before_exposure)
                  ? 'text-emerald-600' : 'text-red-600'
              }`}>
                {fmtInr(verify.after_exposure)}
              </div>
              <div className={`text-[11px] mt-1.5 font-medium ${
                parseFloat(verify.after_exposure) < parseFloat(verify.before_exposure)
                  ? 'text-emerald-400' : 'text-red-400'
              }`}>
                {verify.after_exception_type
                  ? (TYPE_LABEL[verify.after_exception_type] ?? verify.after_exception_type)
                  : '—'}
              </div>
            </div>
          </div>
        ) : (
          <div className="flex items-center gap-3 py-6 text-slate-400">
            <Clock className="h-5 w-5 shrink-0" />
            <p className="text-[13px]">Click Verify to run a fresh control check on this exception.</p>
          </div>
        )}
      </div>

      {/* ═══════════════════════════════════════════════════════
          CONTROL EVIDENCE — Raw JSON, collapsible
      ════════════════════════════════════════════════════════ */}
      <details className="card overflow-hidden group">
        <summary className="px-6 py-4 border-b border-slate-100 cursor-pointer flex items-center gap-2.5 text-[13px] text-slate-600 hover:text-slate-900 transition-colors select-none">
          <TrendingDown className="h-4 w-4 text-slate-400 shrink-0" />
          <span className="font-semibold">Control Engine Evidence</span>
          <span className="ml-auto text-[11px] text-slate-400 font-medium group-open:hidden">Show raw data</span>
          <span className="ml-auto text-[11px] text-slate-400 font-medium hidden group-open:inline">Hide</span>
        </summary>
        <div className="p-6">
          <pre className="text-[11px] font-mono text-slate-600 bg-slate-50 border border-slate-200 rounded-xl p-4 overflow-x-auto whitespace-pre-wrap leading-relaxed max-h-80 overflow-y-auto">
            {JSON.stringify(exc.control_evidence, null, 2)}
          </pre>
        </div>
      </details>

    </div>
  );
};
