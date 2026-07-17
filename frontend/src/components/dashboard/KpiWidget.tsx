import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { kpiApi, KpiDashboard } from '../../services/kpiApi';
import { Gauge, CheckCircle2, AlertTriangle, Bell, Loader2 } from 'lucide-react';

export const KpiWidget: React.FC = () => {
  const [data, setData] = useState<KpiDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    kpiApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const s = data?.summary;
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Gauge className="w-4 h-4 text-brand-400" /> KPIs</h3>
        <button onClick={() => navigate('/kpi')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !s ? (
        <p className="text-xs text-slate-500">No KPIs yet.</p>
      ) : s.total === 0 ? (
        <p className="text-xs text-slate-500">Create a KPI to start tracking.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400" /> On track</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{s.on_track}/{s.total}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> Critical</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{s.critical}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Bell className="w-3 h-3 text-amber-400" /> Alerts</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data!.open_alerts}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
