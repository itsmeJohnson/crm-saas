import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { callingApi, CallReport } from '../../services/callingApi';
import { PhoneCall, PhoneIncoming, PhoneOutgoing, PhoneMissed, Loader2, Percent } from 'lucide-react';

export const CallingWidget: React.FC = () => {
  const [report, setReport] = useState<CallReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const startOfDay = new Date();
    startOfDay.setHours(0, 0, 0, 0);
    callingApi.reports({ date_from: startOfDay.toISOString() })
      .then(setReport)
      .catch(() => {})
      .finally(() => setIsLoading(false));
  }, []);

  const dirCount = (label: string) => report?.by_direction.find((b) => b.label === label)?.count || 0;

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><PhoneCall className="w-4 h-4 text-brand-400" /> Calling Today</h3>
        <button onClick={() => navigate('/calling')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {isLoading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !report || report.total === 0 ? (
        <p className="text-xs text-slate-500">No calls logged today.</p>
      ) : (
        <div className="grid grid-cols-2 gap-2">
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><PhoneOutgoing className="w-3 h-3 text-emerald-400" /> Outbound</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{dirCount('OUTBOUND')}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><PhoneIncoming className="w-3 h-3 text-sky-400" /> Inbound</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{dirCount('INBOUND')}</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Percent className="w-3 h-3 text-brand-400" /> Connect Rate</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.connect_rate}%</p>
          </div>
          <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><PhoneMissed className="w-3 h-3 text-red-400" /> Missed</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{report.missed}</p>
          </div>
        </div>
      )}
    </div>
  );
};
