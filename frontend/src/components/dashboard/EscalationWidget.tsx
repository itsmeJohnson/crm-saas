import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { escalationApi, EscalationDashboard } from '../../services/escalationApi';
import { TrendingUp, ListChecks, Zap, Loader2 } from 'lucide-react';

export const EscalationWidget: React.FC = () => {
  const [data, setData] = useState<EscalationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { escalationApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><TrendingUp className="w-4 h-4 text-brand-400" /> Escalation</h3>
        <button onClick={() => navigate('/escalation')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No escalation data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><ListChecks className="w-3 h-3 text-brand-400" /> Rules</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.active}/{data.rules}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Zap className="w-3 h-3 text-amber-400" /> 7-day</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.last_7_days}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase">Total</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.escalations}</p>
            </div>
          </div>
          {data.recent.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.recent.slice(0, 3).map((e) => (
                <li key={e.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{e.entity_type} · L{e.level}</span>
                  <span className="shrink-0 text-slate-500">{e.escalate_to?.replace(/_/g, ' ')}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
