import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { automationApi, AutomationDashboard } from '../../services/automationApi';
import { Cog, Activity, AlertTriangle, Loader2 } from 'lucide-react';

export const AutomationWidget: React.FC = () => {
  const [data, setData] = useState<AutomationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { automationApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Cog className="w-4 h-4 text-brand-400" /> Automation</h3>
        <button onClick={() => navigate('/automation')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No automation data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Cog className="w-3 h-3 text-brand-400" /> Jobs</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.enabled}/{data.jobs}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Activity className="w-3 h-3 text-emerald-400" /> Success</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.success_rate}%</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-400" /> Breaches</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.open_breaches}</p>
            </div>
          </div>
          {data.recent.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.recent.slice(0, 3).map((r) => (
                <li key={r.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{r.job_key.replace(/_/g, ' ')}</span>
                  <span className={`shrink-0 ${r.status === 'success' ? 'text-emerald-400' : r.status === 'failed' ? 'text-red-400' : 'text-slate-500'}`}>{r.status}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
