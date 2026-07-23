import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { promptStudioApi, PromptDashboard } from '../../services/promptStudioApi';
import { Wand2, FileText, Clock, Activity, Loader2 } from 'lucide-react';

export const PromptStudioWidget: React.FC = () => {
  const [data, setData] = useState<PromptDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    promptStudioApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Wand2 className="w-4 h-4 text-brand-400" /> Prompt Studio</h3>
        <button onClick={() => navigate('/prompt-studio')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No prompt data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><FileText className="w-3 h-3 text-brand-400" /> Prompts</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.prompts}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Clock className="w-3 h-3 text-amber-400" /> Pending</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.pending_review}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Activity className="w-3 h-3 text-emerald-400" /> Uses</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.total_usage}</p>
          </div>
        </div>
      )}
    </div>
  );
};
