import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { whatsappApi, WaReport, WaConversation } from '../../services/whatsappApi';
import { MessageCircle, ArrowUpRight, ArrowDownLeft, Eye, Inbox, Loader2 } from 'lucide-react';

export const WhatsAppWidget: React.FC = () => {
  const [report, setReport] = useState<WaReport | null>(null);
  const [unread, setUnread] = useState<number>(0);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    const startOfDay = new Date();
    startOfDay.setHours(0, 0, 0, 0);
    Promise.all([
      whatsappApi.reports({ date_from: startOfDay.toISOString() }).catch(() => null),
      whatsappApi.conversations({ unread_only: true }).catch(() => [] as WaConversation[]),
    ]).then(([r, convos]) => {
      setReport(r);
      setUnread(convos.reduce((n, c) => n + (c.unread_count || 0), 0));
    }).finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><MessageCircle className="w-4 h-4 text-emerald-400" /> WhatsApp Today</h3>
        <button onClick={() => navigate('/whatsapp')} className="text-xs text-emerald-400 hover:text-emerald-300 cursor-pointer">Open</button>
      </div>
      {isLoading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : (
        <>
          {unread > 0 && (
            <p className="text-xs text-slate-400 mb-3 flex items-center gap-1.5"><Inbox className="w-3.5 h-3.5" /> <b className="text-slate-200">{unread}</b> unread message(s)</p>
          )}
          {!report || report.total === 0 ? (
            <p className="text-xs text-slate-500">No messages today.</p>
          ) : (
            <div className="grid grid-cols-2 gap-2">
              <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><ArrowUpRight className="w-3 h-3 text-emerald-400" /> Sent</p>
                <p className="text-lg font-bold text-slate-100 mt-0.5">{report.outbound}</p>
              </div>
              <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><ArrowDownLeft className="w-3 h-3 text-sky-400" /> Received</p>
                <p className="text-lg font-bold text-slate-100 mt-0.5">{report.inbound}</p>
              </div>
              <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><Eye className="w-3 h-3 text-brand-400" /> Read Rate</p>
                <p className="text-lg font-bold text-slate-100 mt-0.5">{report.read_rate}%</p>
              </div>
              <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Delivery</p>
                <p className="text-lg font-bold text-slate-100 mt-0.5">{report.delivery_rate}%</p>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
