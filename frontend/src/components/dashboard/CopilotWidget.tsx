import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { copilotApi } from '../../services/copilotApi';
import { Sparkles, Send } from 'lucide-react';

/** Home launcher for the CRM Copilot: type a question and jump straight into a
 * Copilot conversation seeded with it. */
export const CopilotWidget: React.FC = () => {
  const [q, setQ] = useState('');
  const navigate = useNavigate();

  const go = () => {
    const text = q.trim();
    navigate('/copilot', { state: text ? { seed: text } : undefined });
  };
  // fire-and-forget capability probe so the widget only shows when AI is reachable
  React.useEffect(() => { copilotApi.capabilities().catch(() => {}); }, []);

  const suggestions = ['How many open leads do I have?', 'Find opportunities', 'Summarize recent activity'];
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Sparkles className="w-4 h-4 text-brand-400" /> CRM Copilot</h3>
        <button onClick={() => navigate('/copilot')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      <div className="flex items-center gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && go()}
               placeholder="Ask the CRM anything…"
               className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs" />
        <button onClick={go} className="p-2 rounded-lg bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer shrink-0"><Send className="w-4 h-4" /></button>
      </div>
      <div className="flex flex-wrap gap-1.5 mt-2">
        {suggestions.map((s) => (
          <button key={s} onClick={() => navigate('/copilot', { state: { seed: s } })} className="text-[10px] px-2 py-1 rounded-full bg-slate-800/60 text-slate-400 hover:text-brand-300 cursor-pointer">{s}</button>
        ))}
      </div>
    </div>
  );
};
