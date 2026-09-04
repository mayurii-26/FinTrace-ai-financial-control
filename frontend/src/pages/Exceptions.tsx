import React, { useEffect, useState, useCallback } from 'react';
import { Search, ChevronRight, RefreshCw, AlertTriangle, SlidersHorizontal } from 'lucide-react';
import { useNavigate } from 'react-router-dom';
import { Badge, LoadingState, ErrorState, EmptyState } from '../components';
import { fetchExceptions } from '../api/endpoints';
import type { ExceptionListItem, Severity, ExceptionStatus } from '../api/types';

const TYPE_LABEL: Record<string, string> = {
  settlement_amount_discrepancy: 'Settlement Discrepancy',
  refund_closure_failure:        'Refund Closure Failure',
  duplicate_financial_event:     'Duplicate Event',
  orphan_financial_event:        'Orphan Event',
  missing_downstream_event:      'Missing Downstream',
  settlement_timing_anomaly:     'Timing Anomaly',
};

const SEVERITIES: Severity[]        = ['critical', 'high', 'medium', 'low'];
const STATUSES:   ExceptionStatus[] = ['open', 'approved', 'rejected', 'escalated', 'auto_resolved'];
const EXC_TYPES                     = Object.keys(TYPE_LABEL);
const PAGE_SIZE                     = 50;

// Severity sort order for display
const SEV_ORDER: Record<string, number> = { critical: 0, high: 1, medium: 2, low: 3 };

function fmtExposure(v: string) {
  const n = parseFloat(v);
  if (isNaN(n)) return '–';
  if (n >= 1_00_00_000) return '₹' + (n / 1_00_00_000).toFixed(2) + ' Cr';
  if (n >= 1_00_000)    return '₹' + (n / 1_00_000).toFixed(2) + ' L';
  return '₹' + n.toLocaleString('en-IN', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
}

function timeAgo(iso: string) {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  if (diff < 60)    return `${Math.round(diff)}s ago`;
  if (diff < 3600)  return `${Math.round(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.round(diff / 3600)}h ago`;
  return `${Math.round(diff / 86400)}d ago`;
}

function fmtDate(iso: string) {
  return new Date(iso).toLocaleString('en-IN', { dateStyle: 'short', timeStyle: 'short' });
}

export const Exceptions: React.FC = () => {
  const navigate = useNavigate();
  const [exceptions, setExceptions] = useState<ExceptionListItem[]>([]);
  const [loading, setLoading]       = useState(true);
  const [error, setError]           = useState<string | null>(null);
  const [search, setSearch]         = useState('');
  const [sev, setSev]               = useState('');
  const [type, setType]             = useState('');
  const [status, setStatus]         = useState('');
  const [page, setPage]             = useState(0);
  const [sortBy, setSortBy]         = useState<'exposure' | 'severity' | 'detected'>('exposure');

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const data = await fetchExceptions({
        severity:       sev    || undefined,
        exception_type: type   || undefined,
        status:         status || undefined,
        limit:          PAGE_SIZE,
        offset:         page * PAGE_SIZE,
      });
      setExceptions(data);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load exceptions.');
    } finally { setLoading(false); }
  }, [sev, type, status, page]);

  useEffect(() => { load(); }, [load]);

  // Client-side search filter
  const searched = exceptions.filter((e) => {
    if (!search) return true;
    const q = search.toLowerCase();
    return (
      e.transaction_id.toLowerCase().includes(q) ||
      e.exception_id.toLowerCase().includes(q)   ||
      e.exception_type.toLowerCase().includes(q)
    );
  });

  // Client-side sort
  const sorted = [...searched].sort((a, b) => {
    if (sortBy === 'exposure')  return parseFloat(b.financial_exposure) - parseFloat(a.financial_exposure);
    if (sortBy === 'severity')  return (SEV_ORDER[a.severity] ?? 4) - (SEV_ORDER[b.severity] ?? 4);
    if (sortBy === 'detected')  return new Date(b.detected_at).getTime() - new Date(a.detected_at).getTime();
    return 0;
  });

  const activeFilters = [sev, type, status].filter(Boolean).length;

  return (
    <div className="space-y-5">

      {/* ── Page Header ──────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="page-title">Exceptions</h1>
          <p className="page-subtitle">
            {loading ? 'Loading…' : `${sorted.length.toLocaleString()} exception${sorted.length !== 1 ? 's' : ''}`}
            {page > 0 && ` · Page ${page + 1}`}
          </p>
        </div>
        <button onClick={load} className="btn-ghost mt-1">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* ── Filter bar ───────────────────────────────────────── */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm px-4 py-3">
        <div className="flex flex-wrap gap-2.5 items-center">

          {/* Search */}
          <div className="relative flex-1 min-w-[240px]">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-slate-400 pointer-events-none" />
            <input
              className="input w-full pl-9 h-9 text-[13px]"
              placeholder="Search transaction ID, exception type…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-1.5 text-slate-400">
            <SlidersHorizontal className="h-3.5 w-3.5" />
          </div>

          {/* Severity filter */}
          <select
            className="select h-9 text-[13px]"
            value={sev}
            onChange={(e) => { setSev(e.target.value); setPage(0); }}
          >
            <option value="">All Severities</option>
            {SEVERITIES.map((s) => <option key={s} value={s}>{s[0].toUpperCase() + s.slice(1)}</option>)}
          </select>

          {/* Type filter */}
          <select
            className="select h-9 text-[13px]"
            value={type}
            onChange={(e) => { setType(e.target.value); setPage(0); }}
          >
            <option value="">All Types</option>
            {EXC_TYPES.map((t) => <option key={t} value={t}>{TYPE_LABEL[t]}</option>)}
          </select>

          {/* Status filter */}
          <select
            className="select h-9 text-[13px]"
            value={status}
            onChange={(e) => { setStatus(e.target.value); setPage(0); }}
          >
            <option value="">All Statuses</option>
            {STATUSES.map((s) => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
          </select>

          {/* Sort */}
          <select
            className="select h-9 text-[13px]"
            value={sortBy}
            onChange={(e) => setSortBy(e.target.value as typeof sortBy)}
          >
            <option value="exposure">Sort: Exposure</option>
            <option value="severity">Sort: Severity</option>
            <option value="detected">Sort: Newest</option>
          </select>

          {/* Clear filters */}
          {activeFilters > 0 && (
            <button
              onClick={() => { setSev(''); setType(''); setStatus(''); setPage(0); }}
              className="text-[13px] text-blue-600 hover:text-blue-700 font-semibold whitespace-nowrap"
            >
              Clear ({activeFilters})
            </button>
          )}
        </div>
      </div>

      {/* ── Summary strip ───────────────────────────────────── */}
      {!loading && !error && sorted.length > 0 && (
        <div className="grid grid-cols-4 gap-3">
          {SEVERITIES.map((s) => {
            const count = sorted.filter((e) => e.severity === s).length;
            return (
              <button
                key={s}
                onClick={() => { setSev(sev === s ? '' : s); setPage(0); }}
                className={`flex items-center justify-between px-4 py-2.5 rounded-lg border text-left transition-colors ${
                  sev === s
                    ? 'bg-blue-50 border-blue-300'
                    : 'bg-white border-slate-200 hover:border-slate-300'
                }`}
              >
                <Badge variant={s as Severity} dot>{s.toUpperCase()}</Badge>
                <span className="text-[16px] font-bold font-mono tabular-nums text-slate-800">{count}</span>
              </button>
            );
          })}
        </div>
      )}

      {/* ── Exceptions table ─────────────────────────────────── */}
      <div className="card overflow-hidden">
        {loading ? (
          <LoadingState />
        ) : error ? (
          <ErrorState message={error} onRetry={load} />
        ) : sorted.length === 0 ? (
          <EmptyState
            title="No exceptions found"
            description="Try adjusting your filters or refreshing."
            icon={<AlertTriangle className="h-10 w-10" />}
          />
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Transaction</th>
                  <th>Exception Type</th>
                  <th>Severity</th>
                  <th className="text-right pr-5">Exposure</th>
                  <th>Status</th>
                  <th>Detected</th>
                  <th className="w-6" />
                </tr>
              </thead>
              <tbody>
                {sorted.map((exc) => (
                  <tr
                    key={exc.exception_id}
                    onClick={() => navigate(`/investigation/${exc.exception_id}`)}
                    className="cursor-pointer group"
                  >
                    {/* Transaction */}
                    <td>
                      <div className="font-mono text-[13px] font-semibold text-slate-800 leading-tight">
                        {exc.transaction_id}
                      </div>
                      <div className="font-mono text-[11px] text-slate-400 leading-tight mt-0.5">
                        {exc.exception_id}
                      </div>
                    </td>

                    {/* Type */}
                    <td>
                      <span className="text-[13px] font-medium text-slate-700">
                        {TYPE_LABEL[exc.exception_type] ?? exc.exception_type}
                      </span>
                    </td>

                    {/* Severity */}
                    <td>
                      <Badge variant={exc.severity} dot>{exc.severity.toUpperCase()}</Badge>
                    </td>

                    {/* Exposure */}
                    <td className="text-right pr-5">
                      <span className="amount-negative text-[13px]">{fmtExposure(exc.financial_exposure)}</span>
                    </td>

                    {/* Status */}
                    <td>
                      <Badge variant={exc.status as Severity}>{exc.status.replace(/_/g, ' ')}</Badge>
                    </td>

                    {/* Detected */}
                    <td>
                      <span className="text-[12px] text-slate-500" title={fmtDate(exc.detected_at)}>
                        {timeAgo(exc.detected_at)}
                      </span>
                    </td>

                    {/* Arrow */}
                    <td>
                      <ChevronRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-slate-600 transition-colors" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Pagination ───────────────────────────────────────── */}
      {!loading && !error && (
        <div className="flex justify-between items-center">
          <span className="text-[13px] text-slate-500">
            {sorted.length > 0 ? `Showing ${sorted.length} of ${sorted.length}` : ''}
          </span>
          <div className="flex gap-2">
            {page > 0 && (
              <button onClick={() => setPage((p) => p - 1)} className="btn-ghost">
                ← Previous
              </button>
            )}
            {exceptions.length === PAGE_SIZE && (
              <button onClick={() => setPage((p) => p + 1)} className="btn-ghost">
                Next →
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
