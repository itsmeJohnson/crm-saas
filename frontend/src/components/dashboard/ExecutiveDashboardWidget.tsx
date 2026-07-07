import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { executiveDashboardApi, ExecDashboard } from '../../services/executiveDashboardApi';
import { LayoutDashboard, TrendingUp, ShieldCheck, Sparkles, Loader2 } from 'lucide-react';

const cur = (n: any) => (typeof n === 'number' ? `₹${Math.round(n).toLocaleString()}` : '—');

export const ExecutiveDashboardWidget: React.FC = () => {
  const [data, setData] = useState<ExecDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    executiveDashboardApi.dashboard({ persona: 'ceo' }).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const b = data?.blocks || {};
  const insights = b.ai_insights?.insights || [];

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><LayoutDashboard className="w-4 h-4 text-brand-400" /> Executive</h3>
        <button onClick={() => navigate('/executive-dashboard')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No executive data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Revenue</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{cur(b.revenue?.revenue)}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-brand-400" /> Forecast</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{cur(b.forecast?.projected_total)}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><ShieldCheck className="w-3 h-3 text-emerald-400" /> SLA</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{b.sla_compliance?.compliance_rate ?? 0}%</p>
            </div>
          </div>
          {insights.length > 0 && (
            <div className="mt-3 flex items-start gap-1.5 text-[11px] text-slate-400">
              <Sparkles className="w-3.5 h-3.5 text-brand-400 shrink-0 mt-0.5" />
              <span className="truncate">{insights[0].title} — {insights[0].detail}</span>
            </div>
          )}
        </>
      )}
    </div>
  );
};
