import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { performanceApi, PerformanceDashboard } from '../../services/performanceApi';
import { Trophy, Gauge, Award, TrendingUp, Loader2 } from 'lucide-react';

export const PerformanceWidget: React.FC = () => {
  const [data, setData] = useState<PerformanceDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { performanceApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Trophy className="w-4 h-4 text-brand-400" /> Performance</h3>
        <button onClick={() => navigate('/performance')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No performance data.</p>
      ) : (
        <>
          <div className="mb-3">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Gauge className="w-3 h-3 text-brand-400" /> My composite score (this month)</p>
            <p className="text-2xl font-bold text-brand-300 mt-0.5">{data.my_composite_score != null ? `${data.my_composite_score}%` : '—'}</p>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Revenue</p>
              <p className="text-sm font-bold text-slate-100 mt-0.5">₹{Math.round(data.my_metrics.sales_revenue || 0).toLocaleString()}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase">Goals</p>
              <p className="text-sm font-bold text-slate-100 mt-0.5">{data.my_open_goals}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Award className="w-3 h-3 text-amber-400" /> Wins</p>
              <p className="text-sm font-bold text-slate-100 mt-0.5">{data.my_achievements}</p>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
