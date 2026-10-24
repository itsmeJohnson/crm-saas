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

  const checkInAt = attendanceRecord ? attendanceRecord.clock_in_at : (summary?.is_online ? summary?.check_in_at : null);
  const checkOutAt = attendanceRecord ? attendanceRecord.clock_out_at : null;

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
    { label: 'Calls Today', value: summary?.calls_made_today ?? summary?.today_calls ?? 0, icon: Phone, isAlert: false },
    { label: "Today's Follow-ups", value: summary?.todays_follow_ups ?? 0, icon: CalendarClock, isAlert: false },
    { label: 'Overdue Follow-ups', value: summary?.overdue_follow_ups ?? 0, icon: AlertTriangle, isAlert: (summary?.overdue_follow_ups ?? 0) > 0 },
    { label: 'New Leads', value: summary?.new_leads ?? 0, icon: FolderKanban, isAlert: false },
    { label: 'Interested Leads', value: summary?.interested_leads ?? 0, icon: Flame, isAlert: false },
    { label: 'Meetings Today', value: summary?.meetings_today ?? summary?.today_meetings_count ?? 0, icon: Users, isAlert: false },
    { label: 'Tasks Pending', value: summary?.tasks_pending ?? summary?.open_tasks ?? 0, icon: ListTodo, isAlert: false },
  ];

  return (
    <div className="glass-panel border border-slate-200 dark:border-slate-800/85 rounded-2xl p-6 sm:p-7 relative overflow-hidden shadow-card">
      <div className="absolute top-0 right-0 w-[320px] h-[320px] bg-indigo-500/5 rounded-full blur-[90px] pointer-events-none" />

      {/* identity + status row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-5">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 flex items-center justify-center text-xl font-extrabold text-indigo-600 dark:text-indigo-300 shadow-xs">
            {(name || summary?.employee_name || '?').slice(0, 1).toUpperCase()}
          </div>
          <div>
            <h2 className="text-2xl font-extrabold text-slate-900 dark:text-slate-100 leading-tight">
              {summary?.employee_name || name || 'Welcome'}
            </h2>
            <div className="flex items-center gap-2 mt-1">
              {isPunchedIn ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 dark:bg-emerald-950/50 text-emerald-700 dark:text-emerald-300 border border-emerald-200 dark:border-emerald-800">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  Punched In • On Duty
                </span>
              ) : isPunchedOutToday ? (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border border-slate-200 dark:border-slate-700">
                  <span className="w-2 h-2 rounded-full bg-slate-400" />
                  Punched Out • Shift Ended
                </span>
              ) : (
                <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-100 dark:bg-slate-800 text-slate-600 dark:text-slate-400 border border-slate-200 dark:border-slate-700">
                  <span className="w-2 h-2 rounded-full bg-slate-400" />
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
              className="px-4 py-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 border border-slate-200 dark:border-slate-700 font-semibold text-xs rounded-xl shadow-xs transition-all cursor-pointer flex items-center gap-2 disabled:opacity-50"
            >
              <LogOut className="w-4 h-4 text-rose-500" />
              Punch Out (End Shift)
            </button>
          ) : isPunchedOutToday ? (
            <div className="flex flex-col items-end gap-1">
              <button
                onClick={handleResumeShift}
                disabled={actionBusy}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white font-semibold text-xs rounded-xl shadow-xs transition-all cursor-pointer flex items-center gap-2 disabled:opacity-50"
              >
                <RotateCcw className={`w-4 h-4 ${actionBusy ? 'animate-spin' : ''}`} />
                {actionBusy ? 'Resuming Shift...' : 'Resume Shift (Re-Punch In)'}
              </button>
              <span className="text-[10px] text-slate-500 dark:text-slate-400">Accidentally punched out? Click to resume</span>
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

          <div className="flex items-center gap-5 bg-slate-50 dark:bg-slate-900/50 border border-slate-200 dark:border-slate-800/80 rounded-xl px-4 py-2">
            <div className="text-right">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 justify-end">
                <LogIn className="w-3 h-3 text-emerald-500" /> Punch-In
              </p>
              <p className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">{fmtTime(checkInAt)}</p>
            </div>
            {isPunchedOutToday && (
              <>
                <div className="w-[1px] h-7 bg-slate-200 dark:bg-slate-800" />
                <div className="text-right">
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 justify-end">
                    <LogOut className="w-3 h-3 text-rose-500" /> Punch-Out
                  </p>
                  <p className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">{fmtTime(checkOutAt)}</p>
                </div>
              </>
            )}
            <div className="w-[1px] h-7 bg-slate-200 dark:bg-slate-800" />
            <div className="text-right">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1 justify-end">
                <Clock className="w-3 h-3 text-brand-500" /> {isPunchedOutToday ? 'Worked' : 'Shift Hours'}
              </p>
              <p className="text-base font-bold text-slate-900 dark:text-slate-100 mt-0.5">{fmtDuration(workingMinutes)}</p>
            </div>
          </div>
        </div>
      </div>

      {/* active agent metrics counter block */}
      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <p className="text-[11px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400 flex items-center gap-1.5">
            <span className={`w-2 h-2 rounded-full ${isPunchedIn ? 'bg-emerald-500 animate-pulse' : 'bg-slate-400'}`} />
            {isPunchedIn ? 'Live Agent Metrics • Calling Session Active' : 'Agent Daily Metrics Overview'}
          </p>
          {isPunchedIn && (
            <span className="text-[10px] font-semibold text-emerald-700 dark:text-emerald-300 bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 px-2 py-0.5 rounded-full">
              Punched In • On Duty
            </span>
          )}
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-7 gap-3">
          {stats.map((s) => (
            <div key={s.label} className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl p-3 shadow-xs transition-all hover:border-slate-300 dark:hover:border-slate-700">
              <p className="text-[10px] font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wide flex items-center gap-1 truncate">
                <s.icon className={`w-3.5 h-3.5 shrink-0 ${s.isAlert ? 'text-rose-500' : 'text-slate-400 dark:text-slate-500'}`} /> {s.label}
              </p>
              <p className={`text-2xl font-bold mt-1 ${loading ? 'text-slate-300 dark:text-slate-700 animate-pulse' : s.isAlert ? 'text-rose-600 dark:text-rose-400' : 'text-slate-900 dark:text-slate-100'}`}>
                {s.value}
              </p>
            </div>
          ))}
        </div>
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
                className="px-3.5 py-2 text-xs font-semibold text-slate-700 hover:text-slate-900 dark:text-slate-300 dark:hover:text-white bg-slate-100 hover:bg-slate-200 dark:bg-slate-800 dark:hover:bg-slate-700 border border-slate-300 dark:border-slate-700 rounded-lg cursor-pointer transition"
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
