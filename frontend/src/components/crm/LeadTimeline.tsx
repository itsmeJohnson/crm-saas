import React, { useEffect, useState } from 'react';
import { leadApi, LeadTimelineEvent } from '../../services/leadApi';
import { activityApi } from '../../services/activityApi';
import { dashboardApi } from '../../services/dashboardApi';
import { useUserStore as useUsersListStore } from '../../store/userStore';
import {
  FileText, History, CheckSquare, Bell, Zap, Plus, CalendarClock,
  Loader2, AlertCircle, ArrowRightLeft, UserCheck, Trophy, Phone,
} from 'lucide-react';

interface Props { leadId: string; }

// Single source of truth for audit-action → human label (Sprint 3).
// LEAD_UPDATED is intentionally excluded: its label is field-dependent
// (stage vs owner vs generic) and is derived in labelFor().
const AUDIT_LABELS: Record<string, string> = {
  LEAD_CREATED: 'Lead created',
  LEAD_CONVERTED: 'Lead converted',
  LEAD_ARCHIVED: 'Lead archived',
  LEAD_RESTORED: 'Lead restored',
  LEAD_DELETED: 'Lead deleted',
  FOLLOW_UP_LOGGED: 'Follow-up logged',
  LEAD_BULK_UPDATED: 'Bulk update applied',
  LEAD_ATTACHMENT_ADDED: 'Attachment added',
  LEAD_ATTACHMENT_REMOVED: 'Attachment removed',
};

/**
 * Unified lead timeline (Sprint 3 A/D): renders the merged feed from
 * GET /leads/{id}/timeline — notes, activities, audit (incl. stage &
 * assignment changes and conversion), tasks, and reminders — chronologically.
 * Adds "Add Follow-up" (reuses POST /leads/{id}/follow-up) and preserves the
 * existing "Log Activity" quick action.
 */
export const LeadTimeline: React.FC<Props> = ({ leadId }) => {
  const [events, setEvents] = useState<LeadTimelineEvent[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { users, fetchUsers } = useUsersListStore();

  const [panel, setPanel] = useState<'none' | 'followup' | 'activity'>('none');
  const [busy, setBusy] = useState(false);

  // follow-up form
  const [fuType, setFuType] = useState('call');
  const [fuOutcome, setFuOutcome] = useState('Follow-up');
  const [fuRemarks, setFuRemarks] = useState('');
  const [fuWhen, setFuWhen] = useState('');
  const [fuPriority, setFuPriority] = useState('Medium');
  const [fuRemind, setFuRemind] = useState(true);
  // activity form
  const [actType, setActType] = useState('Call');
  const [actSubject, setActSubject] = useState('');
  const [actDesc, setActDesc] = useState('');

  const load = async () => {
    setIsLoading(true); setError(null);
    try {
      setEvents(await leadApi.getTimeline(leadId));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load timeline');
    } finally { setIsLoading(false); }
  };

  useEffect(() => {
    load();
    if (users.length === 0) fetchUsers();
  }, [leadId]);

  const actorName = (id: string | null) => {
    if (!id) return null;
    const u = users.find(x => x.id === id);
    return u ? (`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email) : null;
  };

  const submitFollowUp = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!fuWhen) return;
    setBusy(true);
    try {
      await dashboardApi.logFollowUp(leadId, {
        outcome: fuOutcome,
        follow_up_type: fuType,
        remarks: fuRemarks.trim() || undefined,
        next_follow_up_at: new Date(fuWhen).toISOString(),
        priority: fuPriority,
        reminder_minutes_before: fuRemind ? 30 : null,
      });
      setFuRemarks(''); setFuWhen(''); setPanel('none');
      await load();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to log follow-up');
    } finally { setBusy(false); }
  };

  const submitActivity = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!actSubject.trim()) return;
    setBusy(true);
    try {
      await activityApi.createActivity({
        activity_type: actType, subject: actSubject,
        description: actDesc.trim() || null, status: 'Completed',
        lead_id: leadId,
      });
      setActSubject(''); setActDesc(''); setPanel('none');
      await load();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to log activity');
    } finally { setBusy(false); }
  };

  const iconFor = (ev: LeadTimelineEvent) => {
    switch (ev.type) {
      case 'note': return <FileText className="w-4 h-4 text-sky-400" />;
      case 'task': return <CheckSquare className="w-4 h-4 text-purple-400" />;
      case 'reminder': return <Bell className="w-4 h-4 text-amber-400" />;
      case 'activity': return <Phone className="w-4 h-4 text-emerald-400" />;
      case 'audit': {
        const f = ev.event_metadata?.updated_fields || [];
        if (ev.title === 'LEAD_CONVERTED') return <Trophy className="w-4 h-4 text-yellow-400" />;
        if (f.includes?.('stage_id')) return <ArrowRightLeft className="w-4 h-4 text-indigo-400" />;
        if (f.includes?.('assigned_user_id')) return <UserCheck className="w-4 h-4 text-blue-400" />;
        return <History className="w-4 h-4 text-slate-400" />;
      }
      default: return <Zap className="w-4 h-4 text-slate-400" />;
    }
  };

  // Humanize audit actions from the centralized AUDIT_LABELS map, calling out
  // stage/owner changes and conversion (A). LEAD_UPDATED is field-dependent.
  const labelFor = (ev: LeadTimelineEvent): string => {
    if (ev.type !== 'audit') return ev.title;
    if (ev.title === 'LEAD_UPDATED') {
      const f: string[] = ev.event_metadata?.updated_fields || [];
      if (f.includes('stage_id')) return 'Pipeline stage changed';
      if (f.includes('assigned_user_id')) return 'Owner changed';
      return f.length ? `Updated: ${f.join(', ')}` : 'Lead updated';
    }
    return AUDIT_LABELS[ev.title] || ev.title.replace(/_/g, ' ').toLowerCase();
  };

  const inputCls = 'w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50';

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Activity Timeline</h3>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setPanel(panel === 'followup' ? 'none' : 'followup')}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-brand-500/10 border border-brand-500/30 hover:border-brand-500/50 rounded-xl text-xs font-semibold text-brand-300 transition-all cursor-pointer"
          >
            <CalendarClock className="w-3.5 h-3.5" /> Add Follow-up
          </button>
          <button
            onClick={() => setPanel(panel === 'activity' ? 'none' : 'activity')}
            className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-xs font-semibold text-slate-300 transition-all cursor-pointer"
          >
            <Plus className="w-3.5 h-3.5" /> Log Activity
          </button>
        </div>
      </div>

      {panel === 'followup' && (
        <form onSubmit={submitFollowUp} className="p-4 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Type</label>
              <select value={fuType} onChange={e => setFuType(e.target.value)} className={inputCls}>
                <option value="call">Call</option><option value="whatsapp">WhatsApp</option>
                <option value="email">Email</option><option value="meeting">Meeting</option>
                <option value="site_visit">Site visit</option><option value="other">Other</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Priority</label>
              <select value={fuPriority} onChange={e => setFuPriority(e.target.value)} className={inputCls}>
                <option>Low</option><option>Medium</option><option>High</option><option>Urgent</option>
              </select>
            </div>
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Outcome of this touch</label>
            <input value={fuOutcome} onChange={e => setFuOutcome(e.target.value)} className={inputCls} placeholder="Follow-up" />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Next follow-up at</label>
            <input type="datetime-local" value={fuWhen} onChange={e => setFuWhen(e.target.value)} className={inputCls} required />
          </div>
          <div>
            <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Remarks</label>
            <textarea value={fuRemarks} onChange={e => setFuRemarks(e.target.value)} className={`${inputCls} h-14 resize-none`} placeholder="What happened / next step..." />
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-400">
            <input type="checkbox" checked={fuRemind} onChange={e => setFuRemind(e.target.checked)} /> Remind me 30 min before
          </label>
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={() => setPanel('none')} className="px-3 py-1.5 border border-slate-800 rounded-lg text-xs font-semibold text-slate-400">Cancel</button>
            <button type="submit" disabled={busy} className="px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-lg text-xs font-semibold">
              {busy ? 'Saving...' : 'Schedule Follow-up'}
            </button>
          </div>
        </form>
      )}

      {panel === 'activity' && (
        <form onSubmit={submitActivity} className="p-4 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Type</label>
              <select value={actType} onChange={e => setActType(e.target.value)} className={inputCls}>
                <option>Call</option><option>Meeting</option><option>Email</option><option>Task</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Subject</label>
              <input value={actSubject} onChange={e => setActSubject(e.target.value)} className={inputCls} placeholder="e.g. Intro call" required />
            </div>
          </div>
          <textarea value={actDesc} onChange={e => setActDesc(e.target.value)} className={`${inputCls} h-14 resize-none`} placeholder="Notes..." />
          <div className="flex justify-end gap-2 pt-1">
            <button type="button" onClick={() => setPanel('none')} className="px-3 py-1.5 border border-slate-800 rounded-lg text-xs font-semibold text-slate-400">Cancel</button>
            <button type="submit" disabled={busy} className="px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-lg text-xs font-semibold">
              {busy ? 'Logging...' : 'Save Activity'}
            </button>
          </div>
        </form>
      )}

      {isLoading ? (
        <div className="py-12 flex justify-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin" /></div>
      ) : error ? (
        <div className="p-4 border border-red-500/20 bg-red-500/5 text-red-400 text-xs rounded-xl flex items-center gap-2">
          <AlertCircle className="w-4 h-4" /><p>{error}</p>
        </div>
      ) : events.length === 0 ? (
        <div className="p-8 border border-dashed border-slate-800 rounded-xl text-center text-xs text-slate-500">No activity yet.</div>
      ) : (
        <div className="relative border-l border-slate-800 pl-4.5 space-y-5 py-2">
          {events.map(ev => {
            const who = actorName(ev.actor_user_id);
            const meta = ev.event_metadata || {};
            return (
              <div key={`${ev.type}-${ev.id}`} className="relative group">
                <div className="absolute -left-[27px] top-0.5 bg-slate-950 p-1 border border-slate-800 rounded-full flex items-center justify-center">
                  {iconFor(ev)}
                </div>
                <div className="space-y-1">
                  <h4 className="text-sm font-semibold text-slate-200">{labelFor(ev)}</h4>
                  {ev.description && (
                    <p className="text-xs text-slate-400 leading-relaxed whitespace-pre-line">{ev.description}</p>
                  )}
                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500 pt-0.5">
                    <span>{new Date(ev.timestamp).toLocaleString()}</span>
                    {who && <span className="px-1.5 py-0.5 bg-slate-900 border border-slate-800 text-slate-400 rounded">{who}</span>}
                    {ev.type === 'task' && meta.status && (
                      <span className="px-1.5 py-0.5 bg-purple-500/10 border border-purple-500/20 text-purple-300 rounded">{meta.status}</span>
                    )}
                    {ev.type === 'reminder' && meta.remind_at && (
                      <span className="px-1.5 py-0.5 bg-amber-500/10 border border-amber-500/20 text-amber-300 rounded">
                        due {new Date(meta.remind_at).toLocaleString()}
                      </span>
                    )}
                    <span className="px-1.5 py-0.5 bg-slate-900/60 border border-slate-800/60 text-slate-600 rounded uppercase tracking-wide">{ev.type}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
