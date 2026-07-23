import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { aiGovernanceApi, GovDashboard } from '../../services/aiGovernanceApi';
import { ShieldCheck, Ban, EyeOff, Loader2 } from 'lucide-react';

export const AiGovernanceWidget: React.FC = () => {
  const [data, setData] = useState<GovDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    aiGovernanceApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-brand-400" /> AI Governance</h3>
        <button onClick={() => navigate('/ai-governance')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No governance data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-emerald-400" /> Controls</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.controls_active}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><EyeOff className="w-3 h-3 text-amber-400" /> Masked</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.masked_30d}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Ban className="w-3 h-3 text-red-400" /> Blocked</p>
            <p className={`text-base font-bold mt-0.5 ${data.blocked_30d > 0 ? 'text-red-400' : 'text-slate-100'}`}>{data.blocked_30d}</p>
          </div>
        </div>
      )}
    </div>
  );
};
