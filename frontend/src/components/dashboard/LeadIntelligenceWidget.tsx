import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { leadIntelligenceApi, LeadIntelDashboard } from '../../services/leadIntelligenceApi';
import { Brain, Flame, Snowflake, TrendingUp, Loader2 } from 'lucide-react';

export const LeadIntelligenceWidget: React.FC = () => {
  const [data, setData] = useState<LeadIntelDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    leadIntelligenceApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Brain className="w-4 h-4 text-brand-400" /> Lead Intelligence</h3>
        <button onClick={() => navigate('/lead-intelligence')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No lead data.</p>
      ) : data.total === 0 ? (
        <p className="text-xs text-slate-500">No leads to analyze yet.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Flame className="w-3 h-3 text-red-400" /> Hot</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.by_temperature.hot || 0}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Snowflake className="w-3 h-3 text-sky-400" /> Cold</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.by_temperature.cold || 0}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Avg conv.</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.avg_conversion_probability}%</p>
          </div>
        </div>
      )}
    </div>
  );
};
