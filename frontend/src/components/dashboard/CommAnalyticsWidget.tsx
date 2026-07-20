import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { commAnalyticsApi, Overview, ResponseTime } from '../../services/commAnalyticsApi';
import { BarChart3, ArrowUpRight, ArrowDownLeft, Timer, MessageSquare, Loader2 } from 'lucide-react';

export const CommAnalyticsWidget: React.FC = () => {
  const [ov, setOv] = useState<Overview | null>(null);
  const [rt, setRt] = useState<ResponseTime | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const from = new Date(Date.now() - 30 * 864e5).toISOString();
    Promise.all([
      commAnalyticsApi.overview({ date_from: from }).catch(() => null),
      commAnalyticsApi.responseTime({ date_from: from }).catch(() => null),
    ]).then(([o, r]) => { setOv(o); setRt(r); }).finally(() => setLoading(false));
  }, []);

  const fmt = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m` : `${s}s`);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><BarChart3 className="w-4 h-4 text-brand-400" /> Comm Analytics</h3>
        <button onClick={() => navigate('/communication-analytics')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !ov || ov.total === 0 ? (
        <p className="text-xs text-slate-500">No communications in the last 30 days.</p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><ArrowUpRight className="w-3 h-3 text-emerald-400" /> Outbound</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{ov.outbound}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><ArrowDownLeft className="w-3 h-3 text-sky-400" /> Inbound</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{ov.inbound}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><MessageSquare className="w-3 h-3 text-emerald-400" /> Delivery</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{ov.delivery_rate}%</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Timer className="w-3 h-3 text-indigo-400" /> Avg Reply</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{rt ? fmt(rt.avg_response_seconds) : '—'}</p>
          </div>
        </div>
      )}
    </div>
  );
};
