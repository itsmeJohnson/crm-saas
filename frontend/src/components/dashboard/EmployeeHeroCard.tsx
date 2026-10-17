import React, { useState } from 'react';
import { EmployeeSummary } from '../../services/dashboardApi';
import { attendanceApi } from '../../services/attendanceApi';
import {
  Phone, CalendarClock, AlertTriangle, FolderKanban, Flame, Users, ListTodo, Clock, LogIn, LogOut, RotateCcw,
} from 'lucide-react';

/**
 * Large, prominent "who am I / how's my day" card shown at the top of the
 * Employee Dashboard immediately after login.
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
  attendanceRecord?: { clock_in_at?: string | null; clock_out_at?: string | null } | null;
  onClockIn?: () => void;
  clockingIn?: boolean;
}> = ({ summary, name, loading, attendanceRecord, onClockIn, clockingIn }) => {
  const [confirmPunchOut, setConfirmPunchOut] = useState(false);
  const [actionBusy, setActionBusy] = useState(false);

  const checkInAt = attendanceRecord?.clock_in_at || summary?.check_in_at;
  const checkOutAt = attendanceRecord?.clock_out_at || summary?.check_out_at;

  const isPunchedIn = Boolean(checkInAt && !checkOutAt);
  const isPunchedOutToday = Boolean(checkInAt && checkOutAt);

  const workingMinutes = typeof summary?.working_minutes === 'number'
    ? summary.working_minutes
    : (checkInAt ? Math.max(0, Math.floor((Date.now() - new Date(checkInAt).getTime()) / 60000)) : 0);

  const handleExecutePunchOut = async () => {
    setActionBusy(true);
    try {
      await attendanceApi.clockOut();
      setConfirmPunchOut(false);
      window.dispatchEvent(new CustomEvent('attendance-updated'));
    } catch (e: any) {
      alert(e?.response?.data?.detail || e?.message || 'Punch-out failed');
    } finally {
      setActionBusy(false);
    }
  };

  const handleResumeShift = async () => {
    setActionBusy(true);
    try {
      await attendanceApi.resumeShift();
      window.dispatchEvent(new CustomEvent('attendance-updated'));
    } catch (e: any) {
      // Fallback to clock-in with resume=true
      try {
        await attendanceApi.clockIn({ resume: true });
        window.dispatchEvent(new CustomEvent('attendance-updated'));
      } catch (err: any) {
        alert(err?.response?.data?.detail || err?.message || 'Failed to resume shift');
      }
    } finally {
      setActionBusy(false);
    }
  };

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
              {isPunchedIn ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/15 text-emerald-300 border border-emerald-500/30">
                  <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
                  Punched In • On Duty
                </span>
              ) : isPunchedOutToday ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/15 text-amber-300 border border-amber-500/30">
                  <span className="w-2 h-2 rounded-full bg-amber-400" />
                  Punched Out • Shift Ended
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-600/20 text-slate-400 border border-slate-700/50">
                  <span className="w-2 h-2 rounded-full bg-slate-500" />
                  Not Punched In
                </span>
              )}
            </div>
          </div>
        </div>

        {/* Punch actions + attendance timestamps */}
        <div className="flex items-center gap-4 flex-wrap">
          {/* Action Button: Punch In / Punch Out / Resume Shift */}
          {isPunchedIn ? (
            <button
              onClick={() => setConfirmPunchOut(true)}
              disabled={actionBusy}
              className="px-4 py-2 bg-rose-500/15 hover:bg-rose-500/25 text-rose-300 border border-rose-500/30 font-semibold text-xs rounded-xl shadow-lg transition-all cursor-pointer flex items-center gap-2 disabled:opacity-50"
            >
              <LogOut className="w-4 h-4 text-rose-400" />
              Punch Out (End Shift)
            </button>
          ) : isPunchedOutToday ? (
            <div className="flex flex-col items-end gap-1">
              <button
                onClick={handleResumeShift}
                disabled={actionBusy}
                className="px-4 py-2 bg-gradient-to-r from-amber-500 to-emerald-600 hover:from-amber-400 hover:to-emerald-500 text-white font-semibold text-xs rounded-xl shadow-lg shadow-amber-500/20 transition-all cursor-pointer flex items-center gap-2 disabled:opacity-50"
              >
                <RotateCcw className={`w-4 h-4 ${actionBusy ? 'animate-spin' : ''}`} />
                {actionBusy ? 'Resuming Shift...' : 'Resume Shift (Re-Punch In)'}
              </button>
              <span className="text-[10px] text-slate-400">Accidentally punched out? Click to resume</span>
            </div>
          ) : (
            onClockIn && (
              <button
                onClick={onClockIn}
                disabled={clockingIn}
                className="px-4 py-2 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition-all cursor-pointer flex items-center gap-2 disabled:opacity-50"
              >
                <LogIn className="w-4 h-4" />
                {clockingIn ? 'Punching In...' : 'Punch In Now'}
              </button>
            )
          )}

          <div className="flex items-center gap-5 bg-slate-900/50 border border-slate-800/80 rounded-xl px-4 py-2">
            <div className="text-right">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 justify-end">
                <LogIn className="w-3 h-3 text-emerald-400" /> Punch-In
              </p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{fmtTime(checkInAt)}</p>
            </div>
            {isPunchedOutToday && (
              <>
                <div className="w-[1px] h-7 bg-slate-800" />
                <div className="text-right">
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 justify-end">
                    <LogOut className="w-3 h-3 text-rose-400" /> Punch-Out
                  </p>
                  <p className="text-base font-bold text-slate-100 mt-0.5">{fmtTime(checkOutAt)}</p>
                </div>
              </>
            )}
            <div className="w-[1px] h-7 bg-slate-800" />
            <div className="text-right">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 justify-end">
                <Clock className="w-3 h-3 text-brand-400" /> {isPunchedOutToday ? 'Worked' : 'Shift Hours'}
              </p>
              <p className="text-base font-bold text-slate-100 mt-0.5">{fmtDuration(workingMinutes)}</p>
            </div>
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

      {/* Confirmation Modal to Prevent Accidental Punch Out */}
      {confirmPunchOut && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm p-4">
          <div className="glass-panel border border-slate-700/80 rounded-2xl p-6 max-w-sm w-full bg-slate-900 shadow-2xl space-y-4">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 rounded-xl bg-rose-500/20 text-rose-400 border border-rose-500/30 flex items-center justify-center">
                <LogOut className="w-5 h-5" />
              </div>
              <div>
                <h3 className="text-base font-bold text-slate-100">Punch Out &amp; End Shift?</h3>
                <p className="text-xs text-slate-400 mt-0.5">Please confirm to conclude your shift</p>
              </div>
            </div>
            <p className="text-xs text-slate-300 leading-relaxed">
              Are you sure you want to punch out for today? This will record your logout time and pause your dialer cockpit.
            </p>
            <div className="flex items-center justify-end gap-2 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setConfirmPunchOut(false)}
                className="px-3.5 py-2 text-xs font-medium text-slate-300 hover:text-white bg-slate-800 hover:bg-slate-700 rounded-lg cursor-pointer transition"
              >
                Cancel (Keep Working)
              </button>
              <button
                type="button"
                onClick={handleExecutePunchOut}
                disabled={actionBusy}
                className="px-3.5 py-2 text-xs font-semibold text-white bg-gradient-to-r from-rose-500 to-red-600 hover:from-rose-400 hover:to-red-500 rounded-lg cursor-pointer transition shadow-lg shadow-rose-500/20 disabled:opacity-50"
              >
                {actionBusy ? 'Punching Out...' : 'Yes, Punch Out'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
