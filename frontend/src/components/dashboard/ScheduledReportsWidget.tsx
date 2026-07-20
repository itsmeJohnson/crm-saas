import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { scheduledReportsApi, SchedDashboard } from '../../services/scheduledReportsApi';
import { CalendarClock, CheckCircle2, AlertTriangle, Send, Loader2 } from 'lucide-react';

export const ScheduledReportsWidget: React.FC = () => {
  const [data, setData] = useState<SchedDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    scheduledReportsApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><CalendarClock className="w-4 h-4 text-brand-400" /> Scheduled Reports</h3>
        <button onClick={() => navigate('/scheduled-reports')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No data.</p>
      ) : data.schedules === 0 ? (
        <p className="text-xs text-slate-500">Create a schedule to deliver reports automatically.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Send className="w-3 h-3 text-brand-400" /> Active</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.active}/{data.schedules}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400" /> Success</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.success_rate}%</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> Failed</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.by_status.failed}</p>
          </div>
        </div>
      )}
    </div>
  );
};
