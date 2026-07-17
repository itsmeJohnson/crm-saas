import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { historyApi, HistDashboard } from '../../services/historyApi';
import { History, Camera, Layers, TrendingUp, Loader2 } from 'lucide-react';

export const HistoryWidget: React.FC = () => {
  const [data, setData] = useState<HistDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    historyApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><History className="w-4 h-4 text-brand-400" /> Historical Analytics</h3>
        <button onClick={() => navigate('/historical-analytics')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No data.</p>
      ) : data.days_covered === 0 ? (
        <p className="text-xs text-slate-500">Capture a snapshot to start building history.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Camera className="w-3 h-3 text-brand-400" /> Days</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.days_covered}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3 text-emerald-400" /> Metrics</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.metrics_tracked}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Layers className="w-3 h-3 text-amber-400" /> Archived</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.archived_rows}</p>
          </div>
        </div>
      )}
    </div>
  );
};
