import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { knowledgeApi, KbDashboard } from '../../services/knowledgeApi';
import { BookOpen, FileText, MessageCircleQuestion, Loader2, Layers } from 'lucide-react';

export const KnowledgeWidget: React.FC = () => {
  const [data, setData] = useState<KbDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    knowledgeApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><BookOpen className="w-4 h-4 text-brand-400" /> Knowledge Base</h3>
        <button onClick={() => navigate('/knowledge')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No knowledge data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><FileText className="w-3 h-3 text-brand-400" /> Published</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.totals.by_status.published || 0}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><MessageCircleQuestion className="w-3 h-3 text-amber-400" /> Pending</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.totals.by_status.pending_review || 0}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Layers className="w-3 h-3 text-sky-400" /> Indexed</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.totals.indexed_pct}%</p>
          </div>
        </div>
      )}
    </div>
  );
};
