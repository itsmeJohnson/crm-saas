import React, { useEffect, useState } from 'react';
import { calendarApi, CalendarEvent } from '../../services/calendarApi';
import { useUserStore } from '../../store/userStore';
import { X, Loader2, Trash2 } from 'lucide-react';

const inputCls = 'w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50';
const local = (iso?: string | null) => (iso ? iso.slice(0, 16) : '');

export const EventModal: React.FC<{ event?: CalendarEvent | null; defaultDate?: Date | null; onClose: () => void; onSaved: () => void }> = ({ event, defaultDate, onClose, onSaved }) => {
  const { users, fetchUsers } = useUserStore();
  const activeUsers = users.filter((u) => u.is_active);

  const base = defaultDate || new Date();
  const [title, setTitle] = useState(event?.title || '');
  const [description, setDescription] = useState(event?.description || '');
  const [eventType, setEventType] = useState(event?.event_type || 'Meeting');
  const [location, setLocation] = useState(event?.location || '');
  const [startAt, setStartAt] = useState(event ? local(event.start_at) : local(new Date(base.getTime() + 3600000).toISOString()));
  const [endAt, setEndAt] = useState(event ? local(event.end_at) : local(new Date(base.getTime() + 7200000).toISOString()));
  const [allDay, setAllDay] = useState(event?.all_day || false);
  const [assignee, setAssignee] = useState(event?.assigned_user_id || '');
  const [recurrence, setRecurrence] = useState(event?.recurrence || 'none');
  const [recurUntil, setRecurUntil] = useState(event?.recurrence_until || '');
  const [remindAt, setRemindAt] = useState(local(event?.remind_at));
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { if (users.length === 0) fetchUsers(); }, []);

  const submit = async () => {
    if (!title.trim() || !startAt || !endAt) return;
    setSubmitting(true);
    try {
      const payload = {
        title, description: description || null, event_type: eventType, location: location || null,
        start_at: new Date(startAt).toISOString(), end_at: new Date(endAt).toISOString(), all_day: allDay,
        assigned_user_id: assignee || null, recurrence, recurrence_until: recurrence !== 'none' && recurUntil ? recurUntil : null,
        remind_at: remindAt ? new Date(remindAt).toISOString() : null,
      };
      if (event) await calendarApi.updateEvent(event.id, payload);
      else await calendarApi.createEvent({ ...payload, title, start_at: payload.start_at, end_at: payload.end_at });
      onSaved(); onClose();
    } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } finally { setSubmitting(false); }
  };

  const del = async () => {
    if (!event || !window.confirm('Delete this event?')) return;
    try { await calendarApi.deleteEvent(event.id); onSaved(); onClose(); } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-lg font-bold text-slate-100">{event ? 'Edit Event' : 'New Event'}</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
        </div>

        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Event title" className={inputCls} />
        <div className="grid grid-cols-2 gap-3">
          <div><label className="text-xs text-slate-400">Type</label>
            <select value={eventType} onChange={(e) => setEventType(e.target.value)} className={inputCls}>
              {['Meeting', 'Appointment', 'Call', 'Followup', 'Other'].map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
          </div>
          <div><label className="text-xs text-slate-400">Location</label><input value={location} onChange={(e) => setLocation(e.target.value)} className={inputCls} /></div>
          <div><label className="text-xs text-slate-400">Start</label><input type="datetime-local" value={startAt} onChange={(e) => setStartAt(e.target.value)} className={inputCls} /></div>
          <div><label className="text-xs text-slate-400">End</label><input type="datetime-local" value={endAt} onChange={(e) => setEndAt(e.target.value)} className={inputCls} /></div>
          <div><label className="text-xs text-slate-400">Assignee</label>
            <select value={assignee} onChange={(e) => setAssignee(e.target.value)} className={inputCls}>
              <option value="">Me</option>
              {activeUsers.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
            </select>
          </div>
          <div><label className="text-xs text-slate-400">Remind at</label><input type="datetime-local" value={remindAt} onChange={(e) => setRemindAt(e.target.value)} className={inputCls} /></div>
          <div><label className="text-xs text-slate-400">Recurrence</label>
            <select value={recurrence} onChange={(e) => setRecurrence(e.target.value)} className={inputCls}>
              {['none', 'daily', 'weekly', 'monthly'].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          {recurrence !== 'none' && <div><label className="text-xs text-slate-400">Repeat until</label><input type="date" value={recurUntil} onChange={(e) => setRecurUntil(e.target.value)} className={inputCls} /></div>}
        </div>
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" rows={2} className={inputCls} />
        <label className="flex items-center gap-2 text-sm text-slate-300"><input type="checkbox" checked={allDay} onChange={(e) => setAllDay(e.target.checked)} className="accent-brand-500" /> All day</label>

        <div className="flex justify-between items-center pt-3 border-t border-slate-800">
          {event ? <button onClick={del} className="flex items-center gap-1.5 px-3 py-2 text-red-400 hover:text-red-300 text-sm cursor-pointer"><Trash2 className="w-4 h-4" /> Delete</button> : <span />}
          <div className="flex gap-3">
            <button onClick={onClose} className="px-4 py-2 border border-slate-800 hover:border-slate-700 rounded-xl text-sm font-semibold text-slate-300 cursor-pointer">Cancel</button>
            <button onClick={submit} disabled={submitting} className="flex items-center gap-2 px-5 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-xl text-sm font-semibold cursor-pointer">
              {submitting && <Loader2 className="w-4 h-4 animate-spin" />} Save
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
