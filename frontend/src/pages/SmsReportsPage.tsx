import React, { useEffect, useState } from 'react';
import { smsApi, SmsReport } from '../services/smsApi';
import { MessageSquare, XCircle, Percent, Loader2, Layers } from 'lucide-react';

const Bar: React.FC<{ title: string; buckets: { label: string; count: number }[] }> = ({ title, buckets }) => {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  const sorted = [...buckets].sort((a, b) => b.count - a.count);
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4">{title}</h3>
      {sorted.length === 0 ? <p className="text-xs text-slate-500">No data.</p> : (
        <ul className="space-y-3">{sorted.map((b) => (
          <li key={b.label}>
            <div className="flex justify-between text-xs mb-1"><span className="text-slate-300">{b.label}</span><span className="text-slate-400">{b.count}</span></div>
            <div className="h-1.5 bg-slate-800/60 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-brand-500 to-indigo-500 rounded-full" style={{ width: `${(b.count / max) * 100}%` }} /></div>
          </li>
        ))}</ul>
      )}
    </div>
  );
};

const DayTrend: React.FC<{ buckets: { label: string; count: number }[] }> = ({ buckets }) => {
  const recent = buckets.slice(-14);
  const max = Math.max(1, ...recent.map((b) => b.count));
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4">Messages per Day</h3>
      {recent.length === 0 ? <p className="text-xs text-slate-500">No data.</p> : (
        <div className="flex items-end gap-1.5 h-28">
          {recent.map((b) => (
            <div key={b.label} className="flex-1 flex flex-col items-center gap-1" title={`${b.label}: ${b.count}`}>
              <span className="text-[9px] text-slate-500">{b.count}</span>
              <div className="w-full bg-gradient-to-t from-brand-500 to-indigo-500 rounded-t-sm" style={{ height: `${(b.count / max) * 100}%`, minHeight: 2 }} />
              <span className="text-[8px] text-slate-600">{b.label.slice(5)}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const RANGES = [
  { key: '7', label: 'Last 7 days', days: 7 },
  { key: '30', label: 'Last 30 days', days: 30 },
  { key: '90', label: 'Last 90 days', days: 90 },
  { key: 'all', label: 'All time', days: 0 },
];

export const SmsReportsPage: React.FC = () => {
  const [report, setReport] = useState<SmsReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [range, setRange] = useState('30');

  useEffect(() => {
    setIsLoading(true);
    const days = RANGES.find((r) => r.key === range)?.days || 0;
    const params = days ? { date_from: new Date(Date.now() - days * 864e5).toISOString() } : {};
    smsApi.reports(params).then(setReport).catch(() => {}).finally(() => setIsLoading(false));
  }, [range]);

  const stats = report ? [
    { label: 'Total', value: String(report.total), icon: MessageSquare, color: 'text-brand-400' },
    { label: 'Delivery Rate', value: `${report.delivery_rate}% (${report.delivered}/${report.outbound})`, icon: Percent, color: 'text-emerald-400' },
    { label: 'Failed', value: String(report.failed), icon: XCircle, color: 'text-red-400' },
    { label: 'Segments', value: String(report.segments), icon: Layers, color: 'text-amber-400' },
  ] : [];

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">SMS Reports</h1>
          <p className="text-sm text-slate-400 mt-1">Delivery performance, volume, and message segments.</p>
        </div>
        <select value={range} onChange={(e) => setRange(e.target.value)}
                className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
          {RANGES.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
        </select>
      </div>
      {isLoading ? <div className="py-24 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : report ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {stats.map((s) => (
              <div key={s.label} className="glass-panel border border-slate-800/85 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-2"><s.icon className={`w-4 h-4 ${s.color}`} /><span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{s.label}</span></div>
                <p className="text-xl font-bold text-slate-100">{s.value}</p>
              </div>
            ))}
          </div>
          <DayTrend buckets={report.by_day} />
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <Bar title="By Status" buckets={report.by_status} />
            <Bar title="By Direction" buckets={report.by_direction} />
          </div>
        </>
      ) : null}
    </div>
  );
};
