import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { commIntelligenceApi, CommIntelDashboard } from '../../services/commIntelligenceApi';
import { MessagesSquare, Smile, Frown, ListChecks, Loader2 } from 'lucide-react';

export const CommIntelligenceWidget: React.FC = () => {
  const [data, setData] = useState<CommIntelDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    commIntelligenceApi.dashboard(30).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><MessagesSquare className="w-4 h-4 text-brand-400" /> Comm Intelligence</h3>
        <button onClick={() => navigate('/comm-intelligence')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No communication data.</p>
      ) : data.total === 0 ? (
        <p className="text-xs text-slate-500">No communications to analyze yet.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Smile className="w-3 h-3 text-emerald-400" /> Positive</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.positive_rate}%</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Frown className="w-3 h-3 text-red-400" /> Negative</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.sentiment.negative}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><ListChecks className="w-3 h-3 text-brand-400" /> Actions</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{data.action_items}</p>
          </div>
        </div>
      )}
    </div>
  );
};
