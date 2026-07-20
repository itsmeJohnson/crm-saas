import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { smsApi, SmsReport } from '../../services/smsApi';
import { MessageSquare, ArrowUpRight, ArrowDownLeft, Percent, XCircle, Loader2 } from 'lucide-react';

export const SmsWidget: React.FC = () => {
  const [report, setReport] = useState<SmsReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const startOfDay = new Date();
    startOfDay.setHours(0, 0, 0, 0);
    smsApi.reports({ date_from: startOfDay.toISOString() })
      .then(setReport)
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><MessageSquare className="w-4 h-4 text-brand-400" /> SMS Today</h3>
        <button onClick={() => navigate('/sms')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {isLoading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !report || report.total === 0 ? (
        <p className="text-xs text-slate-500">No messages today.</p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><ArrowUpRight className="w-3 h-3 text-emerald-400" /> Sent</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.outbound}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><ArrowDownLeft className="w-3 h-3 text-brand-400" /> Received</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.inbound}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Percent className="w-3 h-3 text-emerald-400" /> Delivered</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.delivery_rate}%</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><XCircle className="w-3 h-3 text-red-400" /> Failed</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.failed}</p>
          </div>
        </div>
      )}
    </div>
  );
};
