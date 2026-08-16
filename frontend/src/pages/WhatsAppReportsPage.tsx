import React, { useEffect, useState } from 'react';
import { whatsappApi, WaReport } from '../services/whatsappApi';
import { MessageCircle, CheckCheck, Eye, XCircle, Loader2, Clock, FileSpreadsheet, FileText } from 'lucide-react';

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
            <div className="h-1.5 bg-slate-800/60 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-emerald-500 to-teal-500 rounded-full" style={{ width: `${(b.count / max) * 100}%` }} /></div>
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
      <h3 className="text-sm font-semibold text-slate-200 mb-4">Messages per Day (Last 14 Days)</h3>
      {recent.length === 0 ? <p className="text-xs text-slate-500">No data.</p> : (
        <div className="flex items-end gap-1.5 h-28 pt-2">
          {recent.map((b) => (
            <div key={b.label} className="flex-1 flex flex-col items-center gap-1" title={`${b.label}: ${b.count}`}>
              <span className="text-[9px] text-slate-505">{b.count}</span>
              <div className="w-full bg-gradient-to-t from-emerald-500 to-teal-500 rounded-t-sm" style={{ height: `${(b.count / max) * 100}%`, minHeight: 2 }} />
              <span className="text-[8px] text-slate-500">{b.label.slice(5)}</span>
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

export const WhatsAppReportsPage: React.FC = () => {
  const [report, setReport] = useState<WaReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [range, setRange] = useState('30');

  const days = RANGES.find((r) => r.key === range)?.days || 0;
  const dateFrom = days ? new Date(Date.now() - days * 864e5).toISOString() : undefined;

  useEffect(() => {
    setIsLoading(true);
    const params = dateFrom ? { date_from: dateFrom } : {};
    whatsappApi.reports(params).then(setReport).catch(() => {}).finally(() => setIsLoading(false));
  }, [range, dateFrom]);

  const triggerExport = (format: 'excel' | 'pdf') => {
    const url = whatsappApi.exportReportsUrl(format, dateFrom, undefined);
    window.open(url, '_blank');
  };

  const stats = report ? [
    { label: 'Total Volume', value: String(report.total), icon: MessageCircle, color: 'text-emerald-400' },
    { label: 'Delivery Rate', value: `${report.delivery_rate}% (${report.delivered}/${report.outbound})`, icon: CheckCheck, color: 'text-sky-400' },
    { label: 'Read Rate', value: `${report.read_rate}% (${report.read}/${report.outbound})`, icon: Eye, color: 'text-indigo-400' },
    { label: 'Failed Deliveries', value: String(report.failed), icon: XCircle, color: 'text-rose-455' },
    { label: 'Avg Response SLA', value: `${report.response_time_avg_sec}s`, icon: Clock, color: 'text-amber-400' },
  ] : [];

  return (
    <div className="space-y-6 pb-16">
      <div className="border-b border-slate-800/60 pb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">WhatsApp Reports</h1>
          <p className="text-sm text-slate-400 mt-1">Delivery funnel, outbound success, response time latency metrics.</p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          <select value={range} onChange={(e) => setRange(e.target.value)}
                  className="bg-slate-850 border border-slate-800 text-slate-300 py-2 px-3.5 rounded-xl text-sm focus:outline-none focus:ring-1 focus:ring-emerald-500 cursor-pointer">
            {RANGES.map((r) => <option key={r.key} value={r.key}>{r.label}</option>)}
          </select>
          
          <button onClick={() => triggerExport('excel')} className="inline-flex items-center gap-1.5 bg-slate-850 hover:bg-slate-800 border border-slate-800 text-slate-200 py-2 px-3.5 rounded-xl text-sm transition font-medium cursor-pointer">
            <FileSpreadsheet className="w-4 h-4 text-emerald-400" /> Export Excel
          </button>
          <button onClick={() => triggerExport('pdf')} className="inline-flex items-center gap-1.5 bg-slate-850 hover:bg-slate-800 border border-slate-800 text-slate-200 py-2 px-3.5 rounded-xl text-sm transition font-medium cursor-pointer">
            <FileText className="w-4 h-4 text-rose-400" /> Export PDF
          </button>
        </div>
      </div>
      
      {isLoading ? <div className="py-24 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : report ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-4">
            {stats.map((s) => (
              <div key={s.label} className="glass-panel border border-slate-800/85 rounded-2xl p-5 shadow-sm">
                <div className="flex items-center gap-2 mb-2"><s.icon className={`w-4 h-4 ${s.color}`} /><span className="text-[10px] font-bold text-slate-450 uppercase tracking-wider">{s.label}</span></div>
                <p className="text-xl font-bold text-slate-100">{s.value}</p>
              </div>
            ))}
          </div>
          <DayTrend buckets={report.by_day} />
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Bar title="Volume by Status" buckets={report.by_status} />
            <Bar title="Volume by Direction" buckets={report.by_direction} />
            <Bar title="Volume by Media Type" buckets={report.by_media_type} />
          </div>
        </>
      ) : null}
    </div>
  );
};
