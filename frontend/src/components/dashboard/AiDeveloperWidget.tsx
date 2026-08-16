import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { aiDeveloperApi, DevPortal } from '../../services/aiDeveloperApi';
import { Code2, KeyRound, Activity, Webhook, Loader2 } from 'lucide-react';

export const AiDeveloperWidget: React.FC = () => {
  const [data, setData] = useState<DevPortal | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    aiDeveloperApi.portal().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Code2 className="w-4 h-4 text-brand-400" /> AI API &amp; SDK</h3>
        <button onClick={() => navigate('/ai-developer')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No developer API data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><KeyRound className="w-3 h-3 text-emerald-400" /> Keys</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.keys_active}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Activity className="w-3 h-3 text-sky-400" /> Calls 30d</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.requests_30d}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Webhook className="w-3 h-3 text-amber-400" /> Webhooks</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.webhooks_active}</p>
          </div>
        </div>
      )}
    </div>
  );
};
