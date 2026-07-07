import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { schedulerApi, SchedulerDashboard } from '../../services/schedulerApi';
import { CalendarClock, CheckCircle2, SkipForward, Loader2 } from 'lucide-react';

export const SchedulerWidget: React.FC = () => {
  const [data, setData] = useState<SchedulerDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { schedulerApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><CalendarClock className="w-4 h-4 text-brand-400" /> Scheduler</h3>
        <button onClick={() => navigate('/scheduler')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No scheduler data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CalendarClock className="w-3 h-3 text-brand-400" /> Active</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.active}/{data.total}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400" /> Success</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.success_rate}%</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><SkipForward className="w-3 h-3 text-amber-400" /> Skipped</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.skipped}</p>
            </div>
          </div>
          {data.upcoming.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.upcoming.slice(0, 3).map((s) => (
                <li key={s.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{s.name}</span>
                  <span className="shrink-0 text-slate-500">{s.next_run_at ? new Date(s.next_run_at).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : '—'}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
