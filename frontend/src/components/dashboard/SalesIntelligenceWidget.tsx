import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { salesIntelligenceApi, SalesIntelDashboard } from '../../services/salesIntelligenceApi';
import { Briefcase, TrendingUp, AlertTriangle, Loader2 } from 'lucide-react';

export const SalesIntelligenceWidget: React.FC = () => {
  const [data, setData] = useState<SalesIntelDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    salesIntelligenceApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const inr = (n: number) => `₹${Math.round(n).toLocaleString()}`;
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Briefcase className="w-4 h-4 text-brand-400" /> Sales Intelligence</h3>
        <button onClick={() => navigate('/sales-intelligence')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No sales data.</p>
      ) : data.open_deals === 0 ? (
        <p className="text-xs text-slate-500">No open deals to analyze.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Briefcase className="w-3 h-3 text-brand-400" /> Deals</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.open_deals}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Weighted</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{inr(data.weighted_pipeline_value)}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-red-400" /> At risk</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.by_health.at_risk || 0}</p>
          </div>
        </div>
      )}
    </div>
  );
};
