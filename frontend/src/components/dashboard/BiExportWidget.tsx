import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { biApi, BiDashboard } from '../../services/biApi';
import { DatabaseZap, KeyRound, RefreshCw, CheckCircle2, Loader2 } from 'lucide-react';

export const BiExportWidget: React.FC = () => {
  const [data, setData] = useState<BiDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    biApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><DatabaseZap className="w-4 h-4 text-brand-400" /> Export & BI</h3>
        <button onClick={() => navigate('/bi')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No data.</p>
      ) : data.exports === 0 && data.active_tokens === 0 ? (
        <p className="text-xs text-slate-500">Export data or create a BI feed token to get started.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400" /> Exports</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.exports}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><KeyRound className="w-3 h-3 text-brand-400" /> BI tokens</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.active_tokens}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><RefreshCw className="w-3 h-3 text-sky-400" /> Syncs</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.active_syncs}</p>
          </div>
        </div>
      )}
    </div>
  );
};
