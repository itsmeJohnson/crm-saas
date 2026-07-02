import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { communicationApi, Conversation, CommStats } from '../../services/communicationApi';
import { MessagesSquare, Phone, Mail, MessageSquare, Loader2, Inbox } from 'lucide-react';

const ICON: Record<string, any> = { Call: Phone, Email: Mail, SMS: MessageSquare, WhatsApp: MessageSquare, Note: MessageSquare };

export const CommunicationsWidget: React.FC = () => {
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [stats, setStats] = useState<CommStats | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  useEffect(() => {
    Promise.all([communicationApi.conversations().catch(() => []), communicationApi.stats().catch(() => null)])
      .then(([c, s]) => { setConvos(c.slice(0, 5)); setStats(s); })
      .finally(() => setIsLoading(false));
  }, []);

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><MessagesSquare className="w-4 h-4 text-brand-400" /> Communications</h3>
        <button onClick={() => navigate('/communications')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Open</button>
      </div>
      {stats && <p className="text-xs text-slate-400 mb-3 flex items-center gap-1.5"><Inbox className="w-3.5 h-3.5" /> <b className="text-slate-200">{stats.unread}</b> unread · {stats.this_week} this week</p>}
      {isLoading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : convos.length === 0 ? (
        <p className="text-xs text-slate-500">No conversations yet.</p>
      ) : (
        <ul className="space-y-2">
          {convos.map((c) => {
            const Icon = ICON[c.last_channel] || MessageSquare;
            return (
              <li key={`${c.entity_type}-${c.entity_id}`} onClick={() => navigate('/communications')} className="flex items-center gap-2.5 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg cursor-pointer hover:border-slate-700">
                <Icon className="w-4 h-4 text-slate-400 shrink-0" />
                <span className="text-xs text-slate-200 truncate flex-1">{c.name}</span>
                {c.unread_count > 0 && <span className="shrink-0 min-w-5 h-5 px-1.5 rounded-full bg-brand-500 text-[10px] font-black text-white flex items-center justify-center">{c.unread_count}</span>}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
};
