import React, { useEffect, useState, useCallback } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, Cell,
} from 'recharts';
import {
  AlertTriangle, CheckCircle, DollarSign, RefreshCw,
  Database, ArrowRight, TrendingDown, Shield, Activity,
  Zap, Target, TrendingUp,
} from 'lucide-react';
import { KpiCard, LoadingState, ErrorState, Badge } from '../components';
import { fetchDashboard, fetchBenchmark, fetchExceptions } from '../api/endpoints';
import type { DashboardKPI, BenchmarkResult, ExceptionListItem } from '../api/types';
import { Link } from 'react-router-dom';

const TYPE_LABEL: Record<string, string> = {
  settlement_amount_discrepancy: 'Settlement Discrepancy',
  refund_closure_failure:        'Refund Closure',
  duplicate_financial_event:     'Duplicate Event',
  orphan_financial_event:        'Orphan Event',
  missing_downstream_event:      'Missing Downstream',
  settlement_timing_anomaly:     'Timing Anomaly',
};

function fmtInr(v: string | number) {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  if (isNaN(n)) return '–';
  if (n >= 1_00_00_000) return '₹' + (n / 1_00_00_000).toFixed(2) + ' Cr';
  if (n >= 1_00_000)    return '₹' + (n / 1_00_000).toFixed(2) + ' L';
  if (n >= 1_000)       return '₹' + (n / 1_000).toFixed(1) + 'K';
  return '₹' + n.toFixed(2);
}

const ChartTooltip = ({
  active, payload, label,
}: {
  active?: boolean;
  payload?: Array<{ fill?: string; name: string; value: number }>;
  label?: string;
}) => {
  if (!active || !payload?.length) return null;
  return (
    <div className="bg-white border border-slate-200 rounded-lg px-3 py-2.5 shadow-lg">
      <p className="text-[11px] text-slate-500 font-semibold mb-1 uppercase tracking-wide">{label}</p>
      {payload.map((p) => (
        <p key={p.name} style={{ color: p.fill }} className="text-sm font-bold font-mono">
          {p.value} exceptions
        </p>
      ))}
    </div>
  );
};

const BAR_COLORS = ['#2563EB', '#0891B2', '#D97706', '#DC2626', '#059669', '#7C3AED'];

interface MetricRowProps {
  label: string;
  value: string;
  good?: boolean;
  sub?: string;
}

const MetricRow: React.FC<MetricRowProps> = ({ label, value, good, sub }) => (
  <div className="flex items-center justify-between py-3 border-b border-slate-100 last:border-0">
    <span className="text-[13px] text-slate-600">{label}</span>
    <div className="text-right">
      <span className={`text-[14px] font-bold font-mono tabular-nums ${
        good === true ? 'text-emerald-600' : good === false ? 'text-red-600' : 'text-slate-900'
      }`}>{value}</span>
      {sub && <div className="text-[11px] text-slate-400 mt-0.5">{sub}</div>}
    </div>
  </div>
);

export const ControlCenter: React.FC = () => {
  const [kpi,           setKpi]           = useState<DashboardKPI | null>(null);
  const [bench,         setBench]         = useState<BenchmarkResult | null>(null);
  const [topExceptions, setTopExceptions] = useState<ExceptionListItem[]>([]);
  const [loading,       setLoading]       = useState(true);
  const [error,         setError]         = useState<string | null>(null);
  const [lastRefresh,   setLastRefresh]   = useState(new Date());

  const load = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [kpiData, benchData, excData] = await Promise.all([
        fetchDashboard(), fetchBenchmark(), fetchExceptions({ limit: 50 }),
      ]);
      setKpi(kpiData); setBench(benchData);
      setTopExceptions(
        [...excData]
          .sort((a, b) => parseFloat(b.financial_exposure) - parseFloat(a.financial_exposure))
          .slice(0, 8),
      );
      setLastRefresh(new Date());
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : 'Failed to load dashboard.');
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return <LoadingState message="Loading control center…" />;
  if (error)   return <ErrorState message={error} onRetry={load} />;
  if (!kpi || !bench) return null;

  const resolutionRate =
    bench.exception_count > 0
      ? ((bench.auto_resolved_exceptions + bench.approved_exceptions) / bench.exception_count) * 100
      : 0;

  const chartData = kpi.top_exception_types.map((t) => ({
    label: (TYPE_LABEL[t.exception_type] ?? t.exception_type)
      .split(' ').map((w) => w[0]).join('').toUpperCase(),
    fullLabel: TYPE_LABEL[t.exception_type] ?? t.exception_type,
    count: t.count,
  }));

  return (
    <div className="space-y-6">

      {/* ── Page Header ──────────────────────────────────────── */}
      <div className="flex items-start justify-between">
        <div>
          <h1 className="page-title">Finance Control Center</h1>
          <p className="page-subtitle">
            Reconciliation intelligence · Updated {lastRefresh.toLocaleTimeString('en-IN')}
          </p>
        </div>
        <button onClick={load} className="btn-ghost mt-1">
          <RefreshCw className="h-4 w-4" /> Refresh
        </button>
      </div>

      {/* ── Pipeline Strip ──────────────────────────────────── */}
      <div className="bg-white border border-slate-200 rounded-xl shadow-sm px-4 py-3.5">
        <div className="flex items-center gap-1 flex-wrap">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-widest mr-3">Pipeline</span>

          {[
            { label: 'Processed',  value: bench.total_records.toLocaleString(),                                             cls: 'text-slate-800', icon: <Database   className="h-3.5 w-3.5" /> },
            null,
            { label: 'Exceptions', value: kpi.exception_count.toLocaleString(),                                             cls: 'text-orange-600', icon: <AlertTriangle className="h-3.5 w-3.5" /> },
            null,
            { label: 'Exposure',   value: fmtInr(kpi.total_financial_exposure),                                             cls: 'text-red-600',   icon: <TrendingDown className="h-3.5 w-3.5" /> },
            null,
            { label: 'Open',       value: kpi.open_exceptions.toLocaleString(),                                             cls: 'text-amber-600', icon: <Activity     className="h-3.5 w-3.5" /> },
            null,
            { label: 'Resolved',   value: (bench.auto_resolved_exceptions + bench.approved_exceptions).toLocaleString(),    cls: 'text-emerald-600', icon: <CheckCircle  className="h-3.5 w-3.5" /> },
          ].map((item, i) =>
            item === null ? (
              <ArrowRight key={`arrow-${i}`} className="h-3.5 w-3.5 text-slate-300 shrink-0 mx-1" />
            ) : (
              <div key={item.label} className="flex items-center gap-2 px-3.5 py-2.5 bg-slate-50 border border-slate-200 rounded-lg">
                <span className={item.cls}>{item.icon}</span>
                <div>
                  <div className={`text-[15px] font-bold font-mono tabular-nums leading-tight ${item.cls}`}>{item.value}</div>
                  <div className="text-[10px] text-slate-400 font-semibold uppercase tracking-wide leading-tight mt-0.5">{item.label}</div>
                </div>
              </div>
            )
          )}
        </div>
      </div>

      {/* ── Primary KPI Cards ───────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="Total Processed"
          value={bench.total_records.toLocaleString()}
          sub={`${bench.throughput_records_per_sec.toFixed(0)} rec/s throughput`}
          icon={<Database className="h-4 w-4" />}
        />
        <KpiCard
          label="Gross Transaction Value"
          value={fmtInr(bench.total_financial_value)}
          sub="Total portfolio value"
          icon={<DollarSign className="h-4 w-4" />}
          accent="blue"
        />
        <KpiCard
          label="Financial Exposure"
          value={fmtInr(kpi.total_financial_exposure)}
          sub={`${kpi.exception_count} exceptions detected`}
          icon={<AlertTriangle className="h-4 w-4" />}
          accent={parseFloat(kpi.total_financial_exposure) > 500_000 ? 'red' : 'amber'}
        />
        <KpiCard
          label="Exception Rate"
          value={kpi.exception_rate_pct.toFixed(1) + '%'}
          sub={`${kpi.healthy_count.toLocaleString()} healthy transactions`}
          icon={<Activity className="h-4 w-4" />}
          accent={kpi.exception_rate_pct > 20 ? 'red' : 'green'}
        />
      </div>

      {/* ── Chart + Detection Quality ───────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-5">

        {/* Exception type breakdown chart */}
        <div className="card p-6 lg:col-span-2">
          <div className="mb-5">
            <h2 className="section-title">Exceptions by Type</h2>
            <p className="section-subtitle">Frequency per anomaly category</p>
          </div>
          {chartData.length === 0 ? (
            <div className="flex items-center justify-center h-44 text-slate-400 text-sm">No exceptions</div>
          ) : (
            <ResponsiveContainer width="100%" height={200}>
              <BarChart data={chartData} barSize={28}>
                <XAxis
                  dataKey="label"
                  tick={{ fill: '#94a3b8', fontSize: 11, fontWeight: 600 }}
                  axisLine={false}
                  tickLine={false}
                />
                <YAxis
                  tick={{ fill: '#94a3b8', fontSize: 11 }}
                  axisLine={false}
                  tickLine={false}
                  width={28}
                />
                <Tooltip content={<ChartTooltip />} cursor={{ fill: 'rgba(37,99,235,0.04)' }} />
                <Bar dataKey="count" name="Count" radius={[4, 4, 0, 0]}>
                  {chartData.map((_, i) => (
                    <Cell key={i} fill={BAR_COLORS[i % BAR_COLORS.length]} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          )}
        </div>

        {/* Detection quality metrics */}
        <div className="card p-6">
          <div className="mb-4">
            <h2 className="section-title">Detection Quality</h2>
            <p className="section-subtitle">Benchmark performance</p>
          </div>
          <MetricRow label="Precision"  value={(bench.precision * 100).toFixed(1) + '%'}  good={bench.precision > 0.8} />
          <MetricRow label="Recall"     value={(bench.recall * 100).toFixed(1) + '%'}     good={bench.recall > 0.8} />
          <MetricRow label="F1 Score"   value={(bench.f1_score * 100).toFixed(1) + '%'}   good={bench.f1_score > 0.8} />
          <MetricRow label="Match Rate" value={bench.match_rate_pct.toFixed(1) + '%'}     good={bench.match_rate_pct > 80} />
          <MetricRow
            label="Resolution"
            value={resolutionRate.toFixed(1) + '%'}
            sub={`${bench.open_exceptions} still open`}
            good={resolutionRate > 50}
          />
        </div>
      </div>

      {/* ── Priority Exceptions Table ────────────────────────── */}
      <div className="card overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-100 flex items-center justify-between">
          <div>
            <h2 className="section-title">Priority Exceptions</h2>
            <p className="section-subtitle">Ranked by financial exposure — top 8</p>
          </div>
          <Link to="/exceptions" className="text-[13px] text-blue-600 hover:text-blue-700 font-semibold">
            View all →
          </Link>
        </div>

        {topExceptions.length === 0 ? (
          <div className="py-16 text-center text-[13px] text-slate-400">No exceptions found</div>
        ) : (
          <div className="overflow-x-auto">
            <table className="data-table">
              <thead>
                <tr>
                  <th className="w-8">#</th>
                  <th>Transaction</th>
                  <th>Exception Type</th>
                  <th>Exposure</th>
                  <th>Severity</th>
                  <th>Status</th>
                  <th className="w-6" />
                </tr>
              </thead>
              <tbody>
                {topExceptions.map((exc, idx) => (
                  <Link
                    key={exc.exception_id}
                    to={`/investigation/${exc.exception_id}`}
                    className="contents group"
                    style={{ display: 'contents' }}
                  >
                    <tr
                      onClick={() => {}}
                      className="cursor-pointer"
                    >
                      <td>
                        <span className="text-[12px] font-mono text-slate-400 font-semibold">{idx + 1}</span>
                      </td>
                      <td>
                        <div className="font-mono text-[12px] font-semibold text-slate-800">{exc.transaction_id}</div>
                        <div className="font-mono text-[11px] text-slate-400 mt-0.5">{exc.exception_id}</div>
                      </td>
                      <td>
                        <span className="text-[13px] font-medium text-slate-800">
                          {TYPE_LABEL[exc.exception_type] ?? exc.exception_type}
                        </span>
                      </td>
                      <td>
                        <span className="amount-negative text-[14px]">{fmtInr(exc.financial_exposure)}</span>
                      </td>
                      <td><Badge variant={exc.severity} dot>{exc.severity.toUpperCase()}</Badge></td>
                      <td><Badge variant={exc.status as 'open'}>{exc.status.replace(/_/g, ' ')}</Badge></td>
                      <td>
                        <ArrowRight className="h-3.5 w-3.5 text-slate-300 group-hover:text-slate-600 transition-colors" />
                      </td>
                    </tr>
                  </Link>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* ── Secondary KPI Cards ─────────────────────────────── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <KpiCard
          label="True Positives"
          value={bench.true_positives.toLocaleString()}
          icon={<Shield className="h-4 w-4" />}
          accent="green"
        />
        <KpiCard
          label="False Positives"
          value={bench.false_positives.toLocaleString()}
          icon={<Zap className="h-4 w-4" />}
          accent="amber"
        />
        <KpiCard
          label="False Negatives"
          value={bench.false_negatives.toLocaleString()}
          icon={<Target className="h-4 w-4" />}
          accent="amber"
        />
        <KpiCard
          label="Auto Resolved"
          value={bench.auto_resolved_exceptions.toLocaleString()}
          icon={<TrendingUp className="h-4 w-4" />}
          accent="green"
        />
      </div>

    </div>
  );
};
