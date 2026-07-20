import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { queueApi, QueueDashboard } from '../../services/queueApi';
import { Layers, PlayCircle, AlertOctagon, Loader2 } from 'lucide-react';

export const QueueWidget: React.FC = () => {
  const [data, setData] = useState<QueueDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { queueApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Layers className="w-4 h-4 text-brand-400" /> Background Queue</h3>
        <button onClick={() => navigate('/queue')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No queue data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Layers className="w-3 h-3 text-brand-400" /> Pending</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.pending}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><PlayCircle className="w-3 h-3 text-emerald-400" /> Workers</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.workers}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertOctagon className="w-3 h-3 text-amber-400" /> DLQ</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.dead_letter}</p>
            </div>
          </div>
          {data.recent.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.recent.slice(0, 3).map((j) => (
                <li key={j.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{j.job_type.replace(/_/g, ' ')} <span className="text-slate-600">· {j.queue}</span></span>
                  <span className={`shrink-0 ${j.status === 'succeeded' ? 'text-emerald-400' : j.status === 'dead_letter' || j.status === 'failed' ? 'text-red-400' : 'text-slate-500'}`}>{j.status}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
