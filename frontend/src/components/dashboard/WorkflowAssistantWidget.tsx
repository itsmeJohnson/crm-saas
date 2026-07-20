import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { workflowAssistantApi, WaInsights } from '../../services/workflowAssistantApi';
import { Wand2, Activity, AlertOctagon, Lightbulb, Loader2 } from 'lucide-react';

export const WorkflowAssistantWidget: React.FC = () => {
  const [ins, setIns] = useState<WaInsights | null>(null);
  const [counts, setCounts] = useState<{ sugg: number; bott: number } | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([workflowAssistantApi.insights(), workflowAssistantApi.suggestions(), workflowAssistantApi.bottlenecks()])
      .then(([i, s, b]) => { setIns(i); setCounts({ sugg: s.count, bott: b.count }); })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Wand2 className="w-4 h-4 text-brand-400" /> Workflow Assistant</h3>
        <button onClick={() => navigate('/workflow-assistant')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !ins || !counts ? (
        <p className="text-xs text-slate-500">No assistant data.</p>
      ) : (
        <div className="grid grid-cols-3 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Lightbulb className="w-3 h-3 text-brand-400" /> Ideas</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{counts.sugg}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertOctagon className="w-3 h-3 text-red-400" /> Blockers</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{counts.bott}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Activity className="w-3 h-3 text-emerald-400" /> Success</p>
            <p className="text-base font-bold text-slate-100 mt-0.5">{ins.totals.success_rate}%</p>
          </div>
        </div>
      )}
    </div>
  );
};
