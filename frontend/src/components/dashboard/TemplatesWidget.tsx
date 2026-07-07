import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { templateApi, TemplateReport } from '../../services/templateApi';
import { LayoutTemplate, Clock, CheckCircle2, TrendingUp, Loader2 } from 'lucide-react';

export const TemplatesWidget: React.FC = () => {
  const [report, setReport] = useState<TemplateReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    templateApi.reports().then(setReport).catch(() => {}).finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><LayoutTemplate className="w-4 h-4 text-brand-400" /> Templates</h3>
        <button onClick={() => navigate('/templates')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {isLoading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !report || report.total === 0 ? (
        <p className="text-xs text-slate-500">No templates yet.</p>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><CheckCircle2 className="w-3 h-3 text-emerald-400" /> Approved</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{report.approved}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Clock className="w-3 h-3 text-amber-400" /> Pending</p>
              <p className="text-lg font-bold text-slate-100 mt-0.5">{report.pending_approval}</p>
            </div>
          </div>
          {report.most_used.length > 0 && (
            <div className="mt-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 mb-1.5"><TrendingUp className="w-3 h-3" /> Most used</p>
              <ul className="space-y-1">
                {report.most_used.slice(0, 3).map((t) => (
                  <li key={t.id} className="flex items-center justify-between text-xs">
                    <span className="text-slate-300 truncate">{t.name}</span>
                    <span className="text-slate-500 shrink-0">{t.usage_count}×</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}
    </div>
  );
};
