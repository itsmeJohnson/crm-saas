import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { okrApi, OkrDashboard } from '../../services/okrApi';
import { Target, TrendingUp, AlertTriangle, CheckCircle2, Loader2 } from 'lucide-react';

export const OkrWidget: React.FC = () => {
  const [data, setData] = useState<OkrDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    okrApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Target className="w-4 h-4 text-brand-400" /> Goals & OKRs</h3>
        <button onClick={() => navigate('/okr')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No OKR data.</p>
      ) : data.total === 0 ? (
        <p className="text-xs text-slate-500">Create an objective to start tracking OKRs.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400" /> Achieved</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.achieved}/{data.total}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-400" /> At risk</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.at_risk}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-sky-400" /> Progress</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.avg_progress}%</p>
          </div>
        </div>
      )}
    </div>
  );
};
