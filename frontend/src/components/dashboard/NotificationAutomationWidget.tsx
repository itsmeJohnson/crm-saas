import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { notificationAutomationApi, NotifAutomationDashboard } from '../../services/notificationAutomationApi';
import { BellRing, Send, AlertTriangle, Loader2 } from 'lucide-react';

export const NotificationAutomationWidget: React.FC = () => {
  const [data, setData] = useState<NotifAutomationDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => { notificationAutomationApi.dashboard().then(setData).catch(() => {}).finally(() => setLoading(false)); }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><BellRing className="w-4 h-4 text-brand-400" /> Notification Rules</h3>
        <button onClick={() => navigate('/notification-automation')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {loading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : !data ? (
        <p className="text-xs text-slate-500">No data.</p>
      ) : (
        <>
          <div className="grid grid-cols-3 gap-2">
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><BellRing className="w-3 h-3 text-brand-400" /> Rules</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.active_rules}/{data.rules}</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Send className="w-3 h-3 text-emerald-400" /> Delivered</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.delivery_rate}%</p>
            </div>
            <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-amber-400" /> Failed</p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{data.failed}</p>
            </div>
          </div>
          {data.recent.length > 0 && (
            <ul className="mt-3 space-y-1">
              {data.recent.slice(0, 3).map((d) => (
                <li key={d.id} className="flex items-center justify-between text-xs">
                  <span className="text-slate-300 truncate">{d.title || d.channel}</span>
                  <span className={`shrink-0 ${d.status === 'sent' ? 'text-emerald-400' : d.status === 'failed' ? 'text-red-400' : 'text-amber-400'}`}>{d.channel}</span>
                </li>
              ))}
            </ul>
          )}
        </>
      )}
    </div>
  );
};
