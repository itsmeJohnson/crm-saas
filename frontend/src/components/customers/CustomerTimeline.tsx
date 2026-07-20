import React, { useEffect, useMemo, useState } from 'react';
import { customerApi, TimelineEvent } from '../../services/customerApi';
import {
  Phone, MessageSquare, Mail, Users, CheckSquare, StickyNote, FileText, DollarSign,
  ShoppingCart, FileSignature, RefreshCw, UserPlus, Zap, Bell, Download, Search, Loader2, Activity as ActivityIcon,
} from 'lucide-react';

const TYPE_META: Record<string, { icon: any; color: string; label: string }> = {
  call: { icon: Phone, color: 'text-emerald-400', label: 'Call' },
  sms: { icon: MessageSquare, color: 'text-emerald-400', label: 'SMS' },
  whatsapp: { icon: MessageSquare, color: 'text-green-400', label: 'WhatsApp' },
  email: { icon: Mail, color: 'text-brand-400', label: 'Email' },
  meeting: { icon: Users, color: 'text-indigo-400', label: 'Meeting' },
  task: { icon: CheckSquare, color: 'text-amber-400', label: 'Task' },
  appointment: { icon: Users, color: 'text-indigo-400', label: 'Appointment' },
  note: { icon: StickyNote, color: 'text-slate-400', label: 'Note' },
  file: { icon: FileText, color: 'text-slate-400', label: 'File' },
  invoice: { icon: FileText, color: 'text-brand-400', label: 'Invoice' },
  payment: { icon: DollarSign, color: 'text-emerald-400', label: 'Payment' },
  order: { icon: ShoppingCart, color: 'text-indigo-400', label: 'Order' },
  contract: { icon: FileSignature, color: 'text-amber-400', label: 'Contract' },
  status_change: { icon: RefreshCw, color: 'text-sky-400', label: 'Status' },
  assignment: { icon: UserPlus, color: 'text-brand-400', label: 'Assignment' },
  workflow: { icon: Zap, color: 'text-purple-400', label: 'Workflow' },
  automation: { icon: Zap, color: 'text-purple-400', label: 'Automation' },
  notification: { icon: Bell, color: 'text-slate-400', label: 'Notification' },
  update: { icon: RefreshCw, color: 'text-slate-400', label: 'Update' },
  audit: { icon: ActivityIcon, color: 'text-slate-500', label: 'Audit' },
};

const FILTER_GROUPS = [
  { label: 'Comms', types: ['call', 'sms', 'whatsapp', 'email'] },
  { label: 'Meetings', types: ['meeting', 'appointment'] },
  { label: 'Tasks', types: ['task'] },
  { label: 'Notes', types: ['note'] },
  { label: 'Files', types: ['file'] },
  { label: 'Billing', types: ['invoice', 'payment', 'order', 'contract'] },
  { label: 'Changes', types: ['status_change', 'assignment', 'update'] },
  { label: 'Automation', types: ['workflow', 'automation'] },
  { label: 'Notifications', types: ['notification'] },
];

const meta = (t: string) => TYPE_META[t] || TYPE_META.audit;

export const CustomerTimeline: React.FC<{ companyId: string }> = ({ companyId }) => {
  const [events, setEvents] = useState<TimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [activeFilter, setActiveFilter] = useState<string | null>(null);

  const load = async () => {
    setIsLoading(true);
    try {
      const group = FILTER_GROUPS.find((g) => g.label === activeFilter);
      setEvents(await customerApi.getTimeline(companyId, {
        types: group ? group.types.join(',') : undefined,
        search: search.trim() || undefined,
      }));
    } catch { /* silent */ } finally { setIsLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, [companyId, activeFilter]);

  const handleExport = async () => {
    const group = FILTER_GROUPS.find((g) => g.label === activeFilter);
    const blob = await customerApi.exportTimeline(companyId, { types: group ? group.types.join(',') : undefined, search: search.trim() || undefined });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'timeline.csv'; document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(url);
  };

  const grouped = useMemo(() => {
    const map: Record<string, TimelineEvent[]> = {};
    for (const e of events) { (map[e.group] ||= []).push(e); }
    return Object.entries(map);
  }, [events]);

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><ActivityIcon className="w-4 h-4 text-brand-400" /> Timeline</h3>
        <button onClick={handleExport} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 cursor-pointer">
          <Download className="w-3.5 h-3.5" /> Export
        </button>
      </div>

      <div className="relative mb-3">
        <Search className="w-3.5 h-3.5 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') load(); }}
          placeholder="Search timeline…" className="w-full pl-9 pr-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50" />
      </div>

      <div className="flex flex-wrap gap-1.5 mb-4">
        <button onClick={() => setActiveFilter(null)} className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border cursor-pointer ${!activeFilter ? 'bg-brand-500/15 border-brand-500/30 text-brand-300' : 'bg-slate-950/40 border-slate-800 text-slate-400'}`}>All</button>
        {FILTER_GROUPS.map((g) => (
          <button key={g.label} onClick={() => setActiveFilter(g.label)} className={`px-2.5 py-1 rounded-lg text-[11px] font-semibold border cursor-pointer ${activeFilter === g.label ? 'bg-brand-500/15 border-brand-500/30 text-brand-300' : 'bg-slate-950/40 border-slate-800 text-slate-400'}`}>{g.label}</button>
        ))}
      </div>

      {isLoading ? (
        <div className="py-8 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : events.length === 0 ? (
        <p className="text-xs text-slate-500">No events.</p>
      ) : (
        <div className="space-y-5">
          {grouped.map(([day, dayEvents]) => (
            <div key={day}>
              <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2 sticky top-0">
                {new Date(day).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric', year: 'numeric' })}
              </p>
              <ul className="space-y-2 border-l border-slate-800 pl-4">
                {dayEvents.map((e) => {
                  const m = meta(e.type);
                  const Icon = m.icon;
                  return (
                    <li key={`${e.source}-${e.id}`} className="relative">
                      <span className="absolute -left-[22px] top-0.5 w-4 h-4 rounded-full bg-slate-900 border border-slate-700 flex items-center justify-center">
                        <Icon className={`w-2.5 h-2.5 ${m.color}`} />
                      </span>
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="text-xs font-medium text-slate-200">{e.title}</p>
                          {e.description && <p className="text-[11px] text-slate-500 line-clamp-2">{e.description}</p>}
                          <p className="text-[10px] text-slate-600 mt-0.5">
                            {m.label}{e.actor_name ? ` · ${e.actor_name}` : ''} · {new Date(e.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
                          </p>
                        </div>
                      </div>
                    </li>
                  );
                })}
              </ul>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
