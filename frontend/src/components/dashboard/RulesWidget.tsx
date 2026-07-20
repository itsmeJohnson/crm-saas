import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { ruleApi, RuleDashboard } from '../../services/ruleApi';
import { Filter, CheckCircle2, Percent, Loader2 } from 'lucide-react';

export const RulesWidget: React.FC = () => {
  const [data, setData] = useState<RuleDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { ruleApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Filter className="w-4 h-4 text-brand-400" /> Rule Engine</h3>
        <button onClick={() => navigate('/rules')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No rule data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Filter className="w-3 h-3 text-brand-400" /> Rules</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.total}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400" /> Active</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.active}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Percent className="w-3 h-3 text-brand-400" /> Match</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.match_rate}%</p>
            </div>
          </div>
          {data.top.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.top.slice(0, 3).map((r) => (
                <li key={r.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{r.name}</span>
                  <span className="shrink-0 text-slate-500">P{r.priority} · {r.match_count}✓</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
