import React, { useEffect, useState, useCallback } from 'react';
import {
  Search, RefreshCw, Activity, Cpu, Shield,
  CheckCircle, AlertCircle, Clock, Filter,
} from 'lucide-react';
import { LoadingState, ErrorState, EmptyState } from '../components';
import { fetchRecentAudit } from '../api/endpoints';
import type { AuditLogEntry } from '../api/types';

// ── Action metadata ───────────────────────────────────────────────────────────
interface ActionMeta {
  label: string;
  icon: React.ReactNode;
  dot: string;
  text: string;
  bg: string;
  ring: string;
}

const ACTION_META: Record<string, ActionMeta> = {
  exception_detected:       { label: 'Exception Detected',         icon: <AlertCircle className="h-3.5 w-3.5" />,  dot: 'bg-red-500',      text: 'text-red-600',     bg: 'bg-red-50',    ring: 'ring-red-200'   },
  transaction_healthy:      { label: 'Healthy Transaction',        icon: <CheckCircle className="h-3.5 w-3.5" />,  dot: 'bg-emerald-500',  text: 'text-emerald-600', bg: 'bg-emerald-50', ring: 'ring-emerald-200' },
  investigation_created:    { label: 'Investigation Created',      icon: <Cpu className="h-3.5 w-3.5" />,          dot: 'bg-blue-500',     text: 'text-blue-600',    bg: 'bg-blue-50',   ring: 'ring-blue-200'  },
  investigation_tool_call:  { label: 'Tool Call',                  icon: <Activity className="h-3.5 w-3.5" />,     dot: 'bg-slate-400',    text: 'text-slate-500',   bg: 'bg-slate-50',  ring: 'ring-slate-200' },
  controller_approve:       { label: 'Approved',                   icon: <Shield className="h-3.5 w-3.5" />,       dot: 'bg-emerald-500',  text: 'text-emerald-600', bg: 'bg-emerald-50', ring: 'ring-emerald-200' },
  controller_reject:        { label: 'Rejected',                   icon: <Shield className="h-3.5 w-3.5" />,       dot: 'bg-red-500',      text: 'text-red-600',     bg: 'bg-red-50',    ring: 'ring-red-200'   },
  controller_escalate:      { label: 'Escalated',                  icon: <Shield className="h-3.5 w-3.5" />,       dot: 'bg-purple-500',   text: 'text-purple-600',  bg: 'bg-purple-50', ring: 'ring-purple-200' },
  verification_run:         { label: 'Verification Run',           icon: <CheckCircle className="h-3.5 w-3.5" />,  dot: 'bg-cyan-500',     text: 'text-cyan-600',    bg: 'bg-cyan-50',   ring: 'ring-cyan-200'  },
  reconciliation_exception: { label: 'Reconciliation — Exception', icon: <AlertCircle className="h-3.5 w-3.5" />,  dot: 'bg-orange-500',   text: 'text-orange-600',  bg: 'bg-orange-50', ring: 'ring-orange-200' },
  reconciliation_healthy:   { label: 'Reconciliation — Healthy',   icon: <CheckCircle className="h-3.5 w-3.5" />,  dot: 'bg-teal-500',     text: 'text-teal-600',    bg: 'bg-teal-50',   ring: 'ring-teal-200'  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────
function timeAgo(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)    return `${Math.round(diff)}s ago`;
  if (diff < 3600)  return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return new Date(iso).toLocaleDateString('en-IN', { dateStyle: 'medium' });
}

function fmtTs(iso: string) {
  return new Date(iso).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
}

const FILTER_ACTIONS = Object.keys(ACTION_META);

// ── Component ─────────────────────────────────────────────────────────────────
export const AuditTrail: React.FC = () => {
  const [logs,         setLogs]         = useState<AuditLogEntry[]>([]);
  const [loading,      setLoading]      = useState(true);
  const [error,        setError]        = useState<string | null>(null);
  const [search,       setSearch]       = useState('');
  const [actionFilter, setActionFilter] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await fetchRecentAudit({
        action: actionFilter || undefined,
        limit:  200,
      });
      setLogs(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load audit trail.');
    } finally {
      setLoading(false);
    }
  }, [actionFilter]);

  useEffect(() => { load(); }, [load]);

  const filtered = logs.filter((l) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      (l.transaction_id ?? '').toLowerCase().includes(q) ||
      (l.exception_id   ?? '').toLowerCase().includes(q) ||
      l.action.toLowerCase().includes(q)                 ||
      l.message.toLowerCase().includes(q)
    );
  });

  // Group events by calendar date
  const groups: { date: string; items: AuditLogEntry[] }[] = [];
  filtered.forEach((log) => {
    const date = new Date(log.created_at).toLocaleDateString('en-IN', { dateStyle: 'long' });
    const last = groups[groups.length - 1];
    if (last && last.date === date) {
      last.items.push(log);
    } else {
      groups.push({ date, items: [log] });
    }
  });

  // Event counts for summary strip
  const criticalCount     = filtered.filter((l) => l.action === 'exception_detected').length;
  const actionCount       = filtered.filter((l) => ['controller_approve', 'controller_reject', 'controller_escalate'].includes(l.action)).length;
  const investigationCount = filtered.filter((l) => l.action === 'investigation_created').length;

  return (
    <div className="space-y-5">

      {/* ── Page header ──────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="page-title">Audit Trail</h1>
          <p className="page-subtitle">
            {loading ? 'Loading…' : `${filtered.length.toLocaleString()} event${filtered.length !== 1 ? 's' : ''}`}
          </p>
        </div>
        <button onClick={load} className="btn-ghost mt-1">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* ── Summary strip ───────────────────────────────────── */}
      {!loading && !error && filtered.length > 0 && (
        <div className="grid grid-cols-3 gap-3">
          {[
            { label: 'Exceptions',     value: criticalCount,       color: 'text-red-600',    border: 'border-l-red-500'    },
            { label: 'Investigations', value: investigationCount,  color: 'text-blue-600',   border: 'border-l-blue-500'   },
            { label: 'Controller',     value: actionCount,         color: 'text-purple-600', border: 'border-l-purple-500' },
          ].map((s) => (
            <div key={s.label} className={`bg-white border border-slate-200 border-l-[3px] ${s.border} rounded-xl px-5 py-3 shadow-sm`}>
              <div className="stat-label mb-1">{s.label}</div>
              <div className={`text-[28px] font-bold font-mono tabular-nums leading-none ${s.color}`}>{s.value}</div>
            </div>
          ))}
        </div>
      )}

      {/* ── Filter bar ───────────────────────────────────────── */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm px-4 py-3">
        <div className="flex flex-wrap gap-2.5 items-center">
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
            <input
              className="input w-full pl-9 h-9 text-[13px]"
              placeholder="Search transaction, exception, message…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="flex items-center gap-1.5 text-slate-400">
            <Filter className="h-3.5 w-3.5" />
          </div>
          <select
            className="select h-9 text-[13px]"
            value={actionFilter}
            onChange={(e) => setActionFilter(e.target.value)}
          >
            <option value="">All Actions</option>
            {FILTER_ACTIONS.map((a) => (
              <option key={a} value={a}>{ACTION_META[a]?.label ?? a}</option>
            ))}
          </select>
          {(search || actionFilter) && (
            <button
              onClick={() => { setSearch(''); setActionFilter(''); }}
              className="text-[13px] text-blue-600 hover:text-blue-700 font-semibold"
            >
              Clear
            </button>
          )}
        </div>
      </div>

      {/* ── Timeline ─────────────────────────────────────────── */}
      {loading ? (
        <div className="card"><LoadingState /></div>
      ) : error ? (
        <div className="card"><ErrorState message={error} onRetry={load} /></div>
      ) : filtered.length === 0 ? (
        <div className="card">
          <EmptyState
            title="No audit events found"
            description="Seed the database and run a reconciliation to generate events."
          />
        </div>
      ) : (
        <div className="space-y-6">
          {groups.map((group) => (
            <div key={group.date}>
              {/* Date divider */}
              <div className="flex items-center gap-3 mb-3">
                <div className="h-px flex-1 bg-slate-200" />
                <span className="text-[11px] font-bold text-slate-400 uppercase tracking-widest whitespace-nowrap px-1">
                  {group.date}
                </span>
                <div className="h-px flex-1 bg-slate-200" />
              </div>

              {/* Events card */}
              <div className="card overflow-hidden">
                <table className="data-table">
                  <thead>
                    <tr>
                      <th className="w-[180px]">Action</th>
                      <th>Message</th>
                      <th className="w-[160px]">Transaction</th>
                      <th className="w-[140px]">Details</th>
                      <th className="w-[100px] text-right pr-5">Time</th>
                    </tr>
                  </thead>
                  <tbody>
                    {group.items.map((log) => {
                      const meta      = ACTION_META[log.action];
                      const isHealthy = log.action === 'transaction_healthy' || log.action === 'reconciliation_healthy';
                      const isToolCall = log.action === 'investigation_tool_call';
                      const dimRow    = isHealthy || isToolCall;

                      return (
                        <tr key={log.audit_id} className={dimRow ? 'opacity-50' : ''}>
                          {/* Action */}
                          <td>
                            <div className="flex items-center gap-2">
                              <span className={`h-6 w-6 rounded-full ring-1 flex items-center justify-center shrink-0 bg-white ${meta?.ring ?? 'ring-slate-200'} ${meta?.text ?? 'text-slate-400'}`}>
                                {meta?.icon ?? <Clock className="h-3 w-3" />}
                              </span>
                              <span className={`text-[12px] font-semibold whitespace-nowrap ${meta?.text ?? 'text-slate-500'}`}>
                                {meta?.label ?? log.action}
                              </span>
                            </div>
                          </td>

                          {/* Message */}
                          <td>
                            <p className="text-[12px] text-slate-600 leading-snug line-clamp-2">
                              {log.message || '—'}
                            </p>
                          </td>

                          {/* Transaction / exception IDs */}
                          <td>
                            {log.transaction_id && (
                              <div className="text-[11px] font-mono text-slate-500 leading-tight">
                                {log.transaction_id}
                              </div>
                            )}
                            {log.exception_id && (
                              <div className="text-[10px] font-mono text-slate-400 leading-tight mt-0.5">
                                {log.exception_id}
                              </div>
                            )}
                          </td>

                          {/* Detail chips */}
                          <td>
                            {!dimRow && Object.keys(log.details).length > 0 ? (
                              <div className="flex flex-wrap gap-1">
                                {Object.entries(log.details)
                                  .filter(([, v]) => v != null && typeof v !== 'object')
                                  .slice(0, 2)
                                  .map(([k, v]) => (
                                    <span
                                      key={k}
                                      className="text-[10px] bg-slate-100 border border-slate-200 text-slate-500 px-1.5 py-0.5 rounded font-mono whitespace-nowrap"
                                    >
                                      {k.replace(/_/g, ' ')}={String(v)}
                                    </span>
                                  ))}
                              </div>
                            ) : (
                              <span className="text-slate-300">—</span>
                            )}
                          </td>

                          {/* Timestamp */}
                          <td className="text-right pr-5">
                            <span
                              className="text-[11px] text-slate-400 font-medium whitespace-nowrap"
                              title={fmtTs(log.created_at)}
                            >
                              {timeAgo(log.created_at)}
                            </span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
