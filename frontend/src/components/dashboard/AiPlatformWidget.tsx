import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { aiApi, AiUsageDashboard } from '../../services/aiApi';
import { Bot, Activity, DollarSign, Zap, Loader2 } from 'lucide-react';

export const AiPlatformWidget: React.FC = () => {
  const [data, setData] = useState<AiUsageDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    aiApi.usage(30).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Bot className="w-4 h-4 text-brand-400" /> AI Platform</h3>
        <button onClick={() => navigate('/ai')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No AI usage data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Activity className="w-3 h-3 text-brand-400" /> Requests</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.requests}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><DollarSign className="w-3 h-3 text-emerald-400" /> Cost 30d</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">${data.cost_usd}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Zap className="w-3 h-3 text-sky-400" /> Cache</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.cache_hit_rate}%</p>
          </div>
        </div>
      )}
    </div>
  );
};
