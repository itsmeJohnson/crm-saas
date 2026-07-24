import React from 'react';
import { EmployeeSummary } from '../../services/dashboardApi';
import {
  Phone, CalendarClock, AlertTriangle, FolderKanban, Flame, Users, ListTodo, Clock, LogIn,
} from 'lucide-react';

/**
 * Large, prominent "who am I / how's my day" card shown at the top of the
 * Employee Dashboard immediately after login. Reuses the existing
 * /dashboard/employee summary — no new endpoint.
 */
const fmtTime = (iso?: string | null) =>
  iso ? new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : '—';

const fmtDuration = (mins?: number) => {
  if (!mins || mins <= 0) return '—';
  const h = Math.floor(mins / 60);
  const m = mins % 60;
  return h ? `${h}h ${m}m` : `${m}m`;
};

export const EmployeeHeroCard: React.FC<{
  summary: EmployeeSummary | null;
  name: string;
  loading?: boolean;
}> = ({ summary, name, loading }) => {
  const online = !!summary?.is_online;

  const stats = [
    { label: 'Calls Today', value: summary?.calls_made_today ?? summary?.today_calls ?? 0, icon: Phone, tone: 'text-sky-400' },
    { label: "Today's Follow-ups", value: summary?.todays_follow_ups ?? 0, icon: CalendarClock, tone: 'text-brand-400' },
    { label: 'Overdue Follow-ups', value: summary?.overdue_follow_ups ?? 0, icon: AlertTriangle, tone: (summary?.overdue_follow_ups ?? 0) > 0 ? 'text-red-400' : 'text-slate-300' },
    { label: 'New Leads', value: summary?.new_leads ?? 0, icon: FolderKanban, tone: 'text-emerald-400' },
    { label: 'Interested Leads', value: summary?.interested_leads ?? 0, icon: Flame, tone: 'text-amber-400' },
    { label: 'Meetings Today', value: summary?.meetings_today ?? summary?.today_meetings_count ?? 0, icon: Users, tone: 'text-violet-400' },
    { label: 'Tasks Pending', value: summary?.tasks_pending ?? summary?.open_tasks ?? 0, icon: ListTodo, tone: 'text-cyan-400' },
  ];

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-6 sm:p-7 relative overflow-hidden">
      <div className="absolute top-0 right-0 w-[320px] h-[320px] bg-brand-500/10 rounded-full blur-[90px] pointer-events-none" />

      {/* identity + status row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-5">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-gradient-to-br from-brand-500/30 to-indigo-500/20 border border-brand-500/30 flex items-center justify-center text-xl font-extrabold text-brand-200">
            {(name || summary?.employee_name || '?').slice(0, 1).toUpperCase()}
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-slate-100 leading-tight">
              {summary?.employee_name || name || 'Welcome'}
            </h2>
            <div className="flex items-center gap-2 mt-1">
              <span className={`inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold ${online ? 'bg-emerald-500/15 text-emerald-300' : 'bg-slate-600/20 text-slate-400'}`}>
                <span className={`w-2 h-2 rounded-full ${online ? 'bg-emerald-400 animate-pulse' : 'bg-slate-500'}`} />
                {online ? 'Online' : 'Offline'}
              </span>
            </div>
          </div>
        </div>

        {/* check-in + working duration */}
        <div className="flex items-center gap-5">
          <div className="text-right">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 justify-end"><LogIn className="w-3 h-3" /> Check-In</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{fmtTime(summary?.check_in_at)}</p>
          </div>
          <div className="text-right">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 justify-end"><Clock className="w-3 h-3" /> Working</p>
            <p className="text-lg font-bold text-slate-100 mt-0.5">{fmtDuration(summary?.working_minutes)}</p>
          </div>
        </div>
      </div>

      {/* stat grid */}
      <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
        {stats.map((s) => (
          <div key={s.label} className="bg-slate-950/40 border border-slate-800/60 rounded-xl p-3">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wide flex items-center gap-1">
              <s.icon className={`w-3 h-3 ${s.tone}`} /> {s.label}
            </p>
            <p className={`text-2xl font-extrabold mt-1 ${loading ? 'text-slate-600 animate-pulse' : s.tone}`}>{s.value}</p>
          </div>
        ))}
      </div>
    </div>
  );
};
