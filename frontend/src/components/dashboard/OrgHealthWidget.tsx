import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { orgAnalyticsApi, OrgHealth } from '../../services/orgAnalyticsApi';
import { HeartPulse, Loader2 } from 'lucide-react';

const ratingTone = (r: string) => r === 'Excellent' ? 'text-emerald-400' : r === 'Good' ? 'text-brand-300' : r === 'Fair' ? 'text-amber-400' : 'text-red-400';

export const OrgHealthWidget: React.FC = () => {
  const [data, setData] = useState<OrgHealth | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { orgAnalyticsApi.health().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><HeartPulse className="w-4 h-4 text-brand-400" /> Org Health</h3>
        <button onClick={() => navigate('/org-analytics')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No data.</p>
      ) : (
        <>
          <div className="flex items-baseline gap-2">
            <p className="text-3xl font-extrabold text-slate-100">{data.score}%</p>
            <p className={`text-sm font-semibold ${ratingTone(data.rating)}`}>{data.rating}</p>
          </div>
          <div className="mt-3 space-y-1.5">
            {data.components.map((c) => (
              <div key={c.name}>
                <div className="flex items-center justify-between text-[10px] text-slate-500"><span>{c.name}</span><span>{c.score}%</span></div>
                <div className="h-1 bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-brand-500" style={{ width: `${Math.min(100, c.score)}%` }} /></div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
};
