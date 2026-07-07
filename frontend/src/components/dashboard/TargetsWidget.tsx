import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { targetApi, TargetDashboard } from '../../services/targetApi';
import { Target, Check, Gauge, Loader2 } from 'lucide-react';

export const TargetsWidget: React.FC = () => {
  const [data, setData] = useState<TargetDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { targetApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Target className="w-4 h-4 text-brand-400" /> Targets</h3>
        <button onClick={() => navigate('/targets')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data || data.total === 0 ? (
        <p className="text-xs text-slate-500">No targets set.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Check className="w-3 h-3 text-emerald-400" /> Achieved</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.achieved}<span className="text-[11px] text-slate-500">/{data.total}</span></p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Gauge className="w-3 h-3 text-brand-400" /> Avg attain.</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{data.avg_attainment}%</p>
            </div>
          </div>
          {data.at_risk > 0 && (
            <p className="text-[11px] text-amber-400/80 mt-3 flex items-center gap-1.5"><Gauge className="w-3.5 h-3.5" /> {data.at_risk} target(s) at risk</p>
          )}
          {data.at_risk_targets.length > 0 && (
            <ul className="mt-2 space-y-1">
              {data.at_risk_targets.slice(0, 3).map((t) => (
                <li key={`${t.scope}-${t.id}`} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{t.scope_name} · {t.name}</span>
                  <span className="text-amber-400 shrink-0">{t.attainment}%</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
