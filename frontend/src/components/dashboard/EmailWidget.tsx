import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { emailApi, EmailReport } from '../../services/emailApi';
import { Mail, Send, ArrowDownLeft, Eye, MousePointerClick, Loader2 } from 'lucide-react';

export const EmailWidget: React.FC = () => {
  const [report, setReport] = useState<EmailReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const startOfDay = new Date();
    startOfDay.setHours(0, 0, 0, 0);
    emailApi.reports({ date_from: startOfDay.toISOString() })
      .then(setReport)
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Mail className="w-4 h-4 text-brand-400" /> Email Today</h3>
        <button onClick={() => navigate('/email')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {isLoading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !report || report.total === 0 ? (
        <p className="text-xs text-slate-500">No emails today.</p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Send className="w-3 h-3 text-emerald-400" /> Sent</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.sent}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><ArrowDownLeft className="w-3 h-3 text-sky-400" /> Received</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.inbound}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Eye className="w-3 h-3 text-emerald-400" /> Open Rate</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.open_rate}%</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><MousePointerClick className="w-3 h-3 text-brand-400" /> Click Rate</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.click_rate}%</p>
          </div>
        </div>
      )}
    </div>
  );
};
