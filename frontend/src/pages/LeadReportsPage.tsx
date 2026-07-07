import React, { useEffect, useState } from 'react';
import { leadApi, LeadReport, LeadReportBucket } from '../services/leadApi';
import { BarChart3, TrendingUp, Target, Star, Loader2 } from 'lucide-react';

const currency = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

const BreakdownCard: React.FC<{ title: string; buckets: { label: string; count: number; value: number }[] }> = ({
  title,
  buckets,
}) => {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  const sorted = [...buckets].sort((a, b) => b.count - a.count);
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4">{title}</h3>
      {sorted.length === 0 ? (
        <p className="text-xs text-slate-500">No data.</p>
      ) : (
        <ul className="space-y-3">
          {sorted.map((b) => (
            <li key={b.label}>
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-300 truncate">{b.label}</span>
                <span className="text-slate-400 shrink-0 ml-2">
                  {b.count} · {currency(b.value)}
                </span>
              </div>
              <div className="h-1.5 bg-slate-800/60 rounded-full overflow-hidden">
                <div
                  className="h-full bg-gradient-to-r from-brand-500 to-indigo-500 rounded-full"
                  style={{ width: `${(b.count / max) * 100}%` }}
                />
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

export const LeadReportsPage: React.FC = () => {
  const [report, setReport] = useState<LeadReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const load = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const params: { date_from?: string; date_to?: string } = {};
      if (dateFrom) params.date_from = new Date(dateFrom).toISOString();
      if (dateTo) params.date_to = new Date(dateTo + 'T23:59:59').toISOString();
      setReport(await leadApi.getReport(params));
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to load report');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const stats = report
    ? [
        { label: 'Total Leads', value: String(report.total_leads), icon: BarChart3, color: 'text-brand-400' },
        { label: 'Pipeline Value', value: currency(report.total_value), icon: TrendingUp, color: 'text-emerald-400' },
        { label: 'Conversion Rate', value: `${report.conversion_rate}%`, icon: Target, color: 'text-indigo-400' },
        { label: 'Avg. Score', value: String(report.avg_score), icon: Star, color: 'text-amber-400' },
      ]
    : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
            Lead Reports
          </h1>
          <p className="text-sm text-slate-400 mt-1">Analyze lead volume, value, and conversion across your team.</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
            />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
            />
          </div>
          <button
            onClick={load}
            className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer"
          >
            Apply
          </button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24 text-slate-400">
          <Loader2 className="w-6 h-6 animate-spin" />
        </div>
      ) : error ? (
        <div className="py-24 text-center text-red-400">{error}</div>
      ) : report ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {stats.map((s) => (
              <div key={s.label} className="glass-panel border border-slate-800/85 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-2">
                  <s.icon className={`w-4 h-4 ${s.color}`} />
                  <span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{s.label}</span>
                </div>
                <p className="text-2xl font-bold text-slate-100">{s.value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <BreakdownCard title="By Source" buckets={report.by_source} />
            <BreakdownCard title="By Status" buckets={report.by_status} />
            <BreakdownCard title="By Priority" buckets={report.by_priority} />
            <BreakdownCard title="By Stage" buckets={report.by_stage} />
          </div>

          <BreakdownCard
            title="By Owner"
            buckets={report.by_owner.map((o): LeadReportBucket => ({ label: o.name, count: o.count, value: o.value }))}
          />
        </>
      ) : null}
    </div>
  );
};
