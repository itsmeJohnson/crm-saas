import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { calendarApi, CalendarItem, CalendarEvent, CalendarReport } from '../services/calendarApi';
import { EventModal } from '../components/calendar/EventModal';
import { CalendarSettingsModal } from '../components/calendar/CalendarSettingsModal';
import { useAuthStore } from '../store/authStore';
import { Plus, ChevronLeft, ChevronRight, Loader2, Settings, CalendarDays, List as ListIcon } from 'lucide-react';

const SOURCE_COLOR: Record<string, string> = {
  event: 'bg-brand-500/15 border-brand-500/30 text-brand-200',
  task: 'bg-amber-500/15 border-amber-500/30 text-amber-200',
  activity: 'bg-indigo-500/15 border-indigo-500/30 text-indigo-200',
  followup: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-200',
  holiday: 'bg-red-500/15 border-red-500/30 text-red-200',
};

const LEGEND = [['event', 'Events'], ['task', 'Tasks'], ['activity', 'Meetings'], ['followup', 'Follow-ups'], ['holiday', 'Holidays']];

export const CalendarPage: React.FC = () => {
  const { user } = useAuthStore();
  const canManage = user?.role === 'OrgAdmin' || user?.role === 'Manager';
  const navigate = useNavigate();
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [items, setItems] = useState<CalendarItem[]>([]);
  const [report, setReport] = useState<CalendarReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [view, setView] = useState<'month' | 'agenda'>('month');
  const [modalOpen, setModalOpen] = useState(false);
  const [editEvent, setEditEvent] = useState<CalendarEvent | null>(null);
  const [defaultDate, setDefaultDate] = useState<Date | null>(null);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [searchParams, setSearchParams] = useSearchParams();

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const from = new Date(month.getFullYear(), month.getMonth() - 1, 20).toISOString();
      const to = new Date(month.getFullYear(), month.getMonth() + 1, 10, 23, 59).toISOString();
      const [it, rep] = await Promise.all([calendarApi.unified(from, to), calendarApi.report().catch(() => null)]);
      setItems(it); setReport(rep);
    } catch { /* silent */ } finally { setIsLoading(false); }
  }, [month]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const eid = searchParams.get('eventId');
    if (eid) { calendarApi.getEvent(eid).then((e) => { setEditEvent(e); setModalOpen(true); }).catch(() => {}); searchParams.delete('eventId'); setSearchParams(searchParams); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const openItem = (it: CalendarItem) => {
    if (it.source === 'event') { calendarApi.getEvent(it.id).then((e) => { setEditEvent(e); setModalOpen(true); }); }
    else if (it.link) navigate(it.link);
  };
  const newEventOn = (d: Date) => { setEditEvent(null); setDefaultDate(d); setModalOpen(true); };

  const monthItems = items.filter((i) => { const d = new Date(i.start); return d.getMonth() === month.getMonth() && d.getFullYear() === month.getFullYear(); });
  const byDay: Record<number, CalendarItem[]> = {};
  for (const it of monthItems) { const d = new Date(it.start).getDate(); (byDay[d] ||= []).push(it); }
  const startDay = new Date(month.getFullYear(), month.getMonth(), 1).getDay();
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const cells: (number | null)[] = [...Array(startDay).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];
  const todayN = new Date().getDate(); const isThisMonth = new Date().getMonth() === month.getMonth() && new Date().getFullYear() === month.getFullYear();

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">Calendar</h1>
          <p className="text-sm text-slate-400 mt-1">Events, tasks, meetings, follow-ups &amp; holidays in one place.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-xl overflow-hidden border border-slate-800">
            <button onClick={() => setView('month')} className={`flex items-center gap-1.5 px-3 py-2 text-sm font-semibold cursor-pointer ${view === 'month' ? 'bg-brand-500/15 text-brand-300' : 'bg-slate-900 text-slate-400'}`}><CalendarDays className="w-4 h-4" /> Month</button>
            <button onClick={() => setView('agenda')} className={`flex items-center gap-1.5 px-3 py-2 text-sm font-semibold cursor-pointer border-l border-slate-800 ${view === 'agenda' ? 'bg-brand-500/15 text-brand-300' : 'bg-slate-900 text-slate-400'}`}><ListIcon className="w-4 h-4" /> Agenda</button>
          </div>
          <button onClick={() => setSettingsOpen(true)} className="p-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-slate-300 cursor-pointer" title="Settings"><Settings className="w-4 h-4" /></button>
          <button onClick={() => newEventOn(new Date())} className="flex items-center gap-2 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-sm font-semibold shadow-lg shadow-brand-500/20 cursor-pointer"><Plus className="w-4 h-4" /> New Event</button>
        </div>
      </div>

      {report && (
        <div className="flex flex-wrap gap-4 text-xs">
          <span className="text-slate-400">Upcoming (7d): <b className="text-slate-200">{report.upcoming_7d}</b></span>
          <span className="text-slate-400">Tasks due (7d): <b className="text-slate-200">{report.tasks_due_7d}</b></span>
          <span className="text-slate-400">Total events: <b className="text-slate-200">{report.total_events}</b></span>
          <div className="flex flex-wrap gap-3 ml-auto">
            {LEGEND.map(([k, label]) => <span key={k} className="flex items-center gap-1.5 text-slate-500"><span className={`w-2.5 h-2.5 rounded-sm border ${SOURCE_COLOR[k]}`}></span>{label}</span>)}
          </div>
        </div>
      )}

      <div className="glass-panel rounded-2xl border border-slate-800/80 p-5">
        <div className="flex items-center justify-between mb-4">
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="p-1.5 text-slate-400 hover:text-slate-200 cursor-pointer"><ChevronLeft className="w-5 h-5" /></button>
          <h3 className="text-sm font-semibold text-slate-200">{month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}</h3>
          <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="p-1.5 text-slate-400 hover:text-slate-200 cursor-pointer"><ChevronRight className="w-5 h-5" /></button>
        </div>

        {isLoading ? <div className="py-16 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div> : view === 'month' ? (
          <div className="grid grid-cols-7 gap-1">
            {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => <div key={d} className="text-[10px] font-semibold text-slate-500 uppercase text-center py-1">{d}</div>)}
            {cells.map((day, idx) => (
              <div key={idx} className={`min-h-[92px] rounded-lg p-1 group ${day ? 'bg-slate-950/40 border border-slate-800/60' : ''} ${day && isThisMonth && day === todayN ? 'ring-1 ring-brand-500/40' : ''}`}>
                {day && (
                  <div className="flex items-center justify-between">
                    <span className="text-[11px] text-slate-500">{day}</span>
                    <button onClick={() => newEventOn(new Date(month.getFullYear(), month.getMonth(), day, 9))} className="opacity-0 group-hover:opacity-100 text-slate-500 hover:text-brand-300 cursor-pointer"><Plus className="w-3 h-3" /></button>
                  </div>
                )}
                <div className="space-y-0.5 mt-0.5">
                  {(byDay[day || -1] || []).slice(0, 4).map((it) => (
                    <button key={`${it.source}-${it.id}`} onClick={() => openItem(it)} className={`w-full text-left truncate px-1 py-0.5 rounded text-[10px] font-medium border cursor-pointer ${SOURCE_COLOR[it.source] || SOURCE_COLOR.event} ${it.status === 'Completed' || it.status === 'Done' ? 'opacity-50 line-through' : ''}`}>
                      {!it.all_day && new Date(it.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) + ' '}{it.title}
                    </button>
                  ))}
                  {(byDay[day || -1] || []).length > 4 && <p className="text-[9px] text-slate-500 px-1">+{(byDay[day || -1] || []).length - 4} more</p>}
                </div>
              </div>
            ))}
          </div>
        ) : (
          <AgendaView items={monthItems} onOpen={openItem} />
        )}
      </div>

      {modalOpen && <EventModal event={editEvent} defaultDate={defaultDate} onClose={() => { setModalOpen(false); setEditEvent(null); setDefaultDate(null); }} onSaved={load} />}
      {settingsOpen && <CalendarSettingsModal canManage={!!canManage} onClose={() => { setSettingsOpen(false); load(); }} />}
    </div>
  );
};

const AgendaView: React.FC<{ items: CalendarItem[]; onOpen: (i: CalendarItem) => void }> = ({ items, onOpen }) => {
  const groups: Record<string, CalendarItem[]> = {};
  for (const it of items) { const d = new Date(it.start).toISOString().slice(0, 10); (groups[d] ||= []).push(it); }
  const days = Object.entries(groups).sort(([a], [b]) => a.localeCompare(b));
  if (days.length === 0) return <p className="text-sm text-slate-500 py-8 text-center">No items this month.</p>;
  return (
    <div className="space-y-4">
      {days.map(([day, list]) => (
        <div key={day}>
          <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider mb-2">{new Date(day).toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })}</p>
          <ul className="space-y-1.5">
            {list.map((it) => (
              <li key={`${it.source}-${it.id}`} onClick={() => onOpen(it)} className="flex items-center gap-3 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg cursor-pointer hover:border-slate-700">
                <span className={`w-2 h-2 rounded-sm shrink-0 border ${SOURCE_COLOR[it.source] || SOURCE_COLOR.event}`}></span>
                <span className="text-xs text-slate-500 w-14 shrink-0">{it.all_day ? 'All day' : new Date(it.start).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                <span className={`text-sm text-slate-200 truncate flex-1 ${it.status === 'Completed' || it.status === 'Done' ? 'line-through text-slate-500' : ''}`}>{it.title}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
};
