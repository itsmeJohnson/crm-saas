import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { recommendationApi, RecDashboard } from '../../services/recommendationApi';
import { Sparkles, Zap, Clock, Phone, UserCheck, Package, Workflow, Megaphone, BookOpen, ListChecks, Loader2 } from 'lucide-react';

const TYPE_ICON: Record<string, any> = {
  next_best_action: Zap, follow_up: Clock, call_time: Phone, agent: UserCheck,
  product: Package, workflow: Workflow, campaign: Megaphone, knowledge: BookOpen,
};

export const RecommendationsWidget: React.FC = () => {
  const [data, setData] = useState<RecDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    recommendationApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Sparkles className="w-4 h-4 text-brand-400" /> Recommendations</h3>
        <button onClick={() => navigate('/recommendations')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data || data.top_recommendations.length === 0 ? (
        <p className="text-xs text-slate-500">You're all caught up — no recommendations right now.</p>
      ) : (
        <div className="space-y-2">
          <p className="text-[11px] text-slate-500">{data.total} live · {data.my_pending} pending · {data.my_accepted} accepted</p>
          {data.top_recommendations.slice(0, 4).map(rec => {
            const Icon = TYPE_ICON[rec.rec_type] || ListChecks;
            return (
              <div key={rec.rec_key} className="flex items-center gap-2 text-xs p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <Icon className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                <span className="text-slate-300 truncate">{rec.title}</span>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
