import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { integrationApi, IntegrationDashboard } from '../../services/integrationApi';
import { Plug, CheckCircle2, AlertTriangle, Loader2 } from 'lucide-react';

export const IntegrationsWidget: React.FC = () => {
  const [data, setData] = useState<IntegrationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    integrationApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const unhealthy = (data?.degraded || 0) + (data?.down || 0);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Plug className="w-4 h-4 text-brand-400" /> Integrations</h3>
        <button onClick={() => navigate('/integrations')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No integration data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Plug className="w-3 h-3 text-sky-400" /> Total</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.total}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400" /> Healthy</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.healthy}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-400" /> Issues</p>
            <p className={`text-base font-bold mt-0.5 ${unhealthy > 0 ? 'text-amber-400' : 'text-slate-100'}`}>{unhealthy}</p>
          </div>
        </div>
      )}
    </div>
  );
};
