import React, { useEffect, useState } from 'react';
import { taskApi, TaskReport } from '../services/taskApi';
import { ListChecks, CheckCircle2, AlertTriangle, Clock, Loader2 } from 'lucide-react';

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

export const TaskReportsPage: React.FC = () => {
  const [report, setReport] = useState<TaskReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => { taskApi.report().then(setReport).catch(() => {}).finally(() => setIsLoading(false)); }, []);

  const stats = report ? [
    { label: 'Total', value: String(report.total), icon: ListChecks, color: 'text-brand-400' },
    { label: 'Completed', value: `${report.completed} (${report.completion_rate}%)`, icon: CheckCircle2, color: 'text-emerald-400' },
    { label: 'Overdue', value: String(report.overdue), icon: AlertTriangle, color: 'text-red-400' },
    { label: 'Due Today', value: String(report.due_today), icon: Clock, color: 'text-amber-400' },
  ] : [];

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">Task Reports</h1>
        <p className="text-sm text-slate-400 mt-1">Workload, completion, and overdue tracking.</p>
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
          <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
            <Bar title="By Status" buckets={report.by_status} />
            <Bar title="By Priority" buckets={report.by_priority} />
            <Bar title="By Assignee" buckets={report.by_assignee} />
          </div>
        </>
      ) : null}
    </div>
  );
};
