import React, { useCallback, useEffect, useState } from 'react';
import { useAuthStore } from '../../store/authStore';
import { dashboardApi, EmployeeSummary } from '../../services/dashboardApi';
import { attendanceApi, MyToday } from '../../services/attendanceApi';
import { DialerConsole } from '../../components/dialer/DialerConsole';
import { Sparkles, RefreshCw, PhoneCall, LogIn, Clock, RotateCcw } from 'lucide-react';
import { MyTasksWidget } from '../../components/dashboard/MyTasksWidget';
import { WorkQueueWidget } from '../../components/dashboard/WorkQueueWidget';
import { MyLeadsWidget } from '../../components/dashboard/MyLeadsWidget';
import { TodayScheduleWidget } from '../../components/dashboard/TodayScheduleWidget';
import { AttendanceWidget } from '../../components/dashboard/AttendanceWidget';
import { LeaveWidget } from '../../components/dashboard/LeaveWidget';
import { TargetsWidget } from '../../components/dashboard/TargetsWidget';
import { PerformanceWidget } from '../../components/dashboard/PerformanceWidget';
import { ApprovalsWidget } from '../../components/dashboard/ApprovalsWidget';
import { DashboardNotificationsWidget } from '../../components/dashboard/DashboardNotificationsWidget';
import { AnnouncementsWidget } from '../../components/dashboard/AnnouncementsWidget';
import { QuickActionsWidget } from '../../components/dashboard/QuickActionsWidget';
import { MyReportsWidget } from '../../components/dashboard/MyReportsWidget';
import { EmployeeHeroCard } from '../../components/dashboard/EmployeeHeroCard';

/**
 * Focused, role-based dashboard for individual contributors (Employee / Telecaller).
 * Shows the person's own work — calling cockpit, leads, tasks, schedule, attendance, leave,
 * targets, performance — rather than the org-wide operations overview that
 * managers/OrgAdmins see. Fully responsive (Tailwind grids).
 */
export const EmployeeDashboard: React.FC = () => {
  const { user } = useAuthStore();
  const [summary, setSummary] = useState<EmployeeSummary | null>(null);
  const [loading, setLoading] = useState(true);
  const [todayAttendance, setTodayAttendance] = useState<MyToday | null>(null);
  const [clockingIn, setClockingIn] = useState(false);

  const checkAttendance = useCallback(async () => {
    try {
      const att = await attendanceApi.myToday();
      setTodayAttendance(att);
      return att;
    } catch {
      return null;
    }
  }, []);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      await Promise.allSettled([
        checkAttendance(),
        dashboardApi.getEmployeeSummary().then(setSummary)
      ]);
    } finally {
      setLoading(false);
    }
  }, [checkAttendance]);

  useEffect(() => { load(); }, [load]);

  // Reactive listener for cross-widget attendance events
  useEffect(() => {
    const handleSync = () => {
      checkAttendance();
      dashboardApi.getEmployeeSummary().then(setSummary).catch(() => {});
    };
    window.addEventListener('attendance-updated', handleSync);
    return () => window.removeEventListener('attendance-updated', handleSync);
  }, [checkAttendance]);

  const isClockedIn = Boolean(
    (todayAttendance?.record?.clock_in_at && !todayAttendance?.record?.clock_out_at) ||
    summary?.is_online
  );
  const isPunchedOutToday = Boolean(
    todayAttendance?.record?.clock_in_at && todayAttendance?.record?.clock_out_at
  );

  const handleQuickClockIn = async () => {
    setClockingIn(true);
    try {
      let res: any;
      if (isPunchedOutToday) {
        try {
          res = await attendanceApi.resumeShift();
        } catch {
          res = await attendanceApi.clockIn({ resume: true });
        }
      } else {
        res = await attendanceApi.clockIn();
      }
      setTodayAttendance((prev) => ({
        work_date: res.work_date || new Date().toISOString().split('T')[0],
        record: res,
        shift: prev?.shift || null,
        on_break: false,
      }));
      window.dispatchEvent(new CustomEvent('attendance-updated'));
      await Promise.allSettled([
        checkAttendance(),
        dashboardApi.getEmployeeSummary().then(setSummary)
      ]);
    } catch (e: any) {
      console.error(e);
      // Self-heal: If error message mentions already completed, resume shift
      if (e?.response?.data?.detail?.includes('already completed') || e?.response?.status === 409) {
        try {
          const res = await attendanceApi.resumeShift();
          setTodayAttendance((prev) => ({
            work_date: res.work_date || new Date().toISOString().split('T')[0],
            record: res,
            shift: prev?.shift || null,
            on_break: false,
          }));
          window.dispatchEvent(new CustomEvent('attendance-updated'));
          await Promise.allSettled([
            checkAttendance(),
            dashboardApi.getEmployeeSummary().then(setSummary)
          ]);
          return;
        } catch {}
      }
      alert(e?.response?.data?.detail || e?.message || 'Attendance action failed');
    } finally {
      setClockingIn(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Personal welcome banner */}
      <div className="glass-panel p-6 sm:p-8 rounded-2xl relative overflow-hidden flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-indigo-500/10 rounded-full blur-[80px] pointer-events-none" />
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-brand-500/10 text-brand-600 dark:text-brand-300 text-xs font-semibold rounded-full border border-brand-500/20">
            <Sparkles className="w-3.5 h-3.5" /> My Workspace
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-900 dark:text-slate-100 tracking-tight">
            Hi, <span className="gradient-text">{user?.first_name || 'there'}</span>
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm max-w-xl">Here's your day at a glance — your calling queue, leads, tasks and schedule.</p>
        </div>
        <button onClick={load} title="Refresh" className="p-3 border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-900 rounded-xl text-slate-600 dark:text-slate-400 cursor-pointer bg-slate-50 dark:bg-slate-950/20">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* Employee hero card — large, prominent, immediately after login */}
      <EmployeeHeroCard
        summary={summary}
        name={user?.first_name || ''}
        loading={loading}
        attendanceRecord={todayAttendance?.record}
        onClockIn={handleQuickClockIn}
        clockingIn={clockingIn}
      />

      {/* Agent Cockpit: Calling Option & Progressive Dialer */}
      <div className="glass-panel border border-slate-200 dark:border-slate-800/90 rounded-2xl p-6 shadow-card relative overflow-hidden space-y-4">
        <div className="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 border-b border-slate-200 dark:border-slate-800/80 pb-4">
          <div className="flex items-center gap-3">
            <div className={`w-11 h-11 rounded-xl flex items-center justify-center border shadow-lg ${
              isClockedIn 
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                : isPunchedOutToday
                  ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                  : 'bg-slate-700/30 border-slate-600/40 text-slate-400'
            }`}>
              <PhoneCall className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100">Telecaller Agent Cockpit</h2>
                <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border ${
                  isClockedIn 
                    ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-400' 
                    : isPunchedOutToday
                      ? 'bg-amber-500/10 border-amber-500/30 text-amber-400'
                      : 'bg-slate-700/30 border-slate-600/40 text-slate-400'
                }`}>
                  {isClockedIn 
                    ? 'Active • Attendance Verified' 
                    : isPunchedOutToday
                      ? 'Shift Ended • Calling Paused'
                      : 'Punch-In Required to Call'}
                </span>
              </div>
              <p className="text-xs text-slate-400 mt-0.5">
                {isClockedIn
                  ? 'Your calling queue is active. Auto-dial ready, consecutive call progression, and break management.'
                  : isPunchedOutToday
                    ? 'Shift was punched out today. Accidentally clicked punch out? Resume your shift to continue calling.'
                    : 'Punch in attendance to unlock your assigned leads queue and progressive telecalling.'}
              </p>
            </div>
          </div>

          {!isClockedIn && (
            <button
              onClick={handleQuickClockIn}
              disabled={clockingIn}
              className="inline-flex items-center gap-2 px-4 py-2.5 bg-gradient-to-r from-emerald-500 to-teal-600 hover:from-emerald-400 hover:to-teal-500 text-white font-semibold text-xs rounded-xl shadow-lg shadow-emerald-500/20 transition-all cursor-pointer disabled:opacity-50"
            >
              {isPunchedOutToday ? <RotateCcw className={`w-4 h-4 ${clockingIn ? 'animate-spin' : ''}`} /> : <LogIn className="w-4 h-4" />}
              {clockingIn 
                ? (isPunchedOutToday ? 'Resuming Shift...' : 'Punching In...') 
                : (isPunchedOutToday ? 'Resume Shift & Start Calling' : 'Punch In & Start Calling')}
            </button>
          )}
        </div>

        {/* Cockpit Dialer Console when attendance marked, or prompt banner */}
        {isClockedIn ? (
          <div className="mt-2">
            <DialerConsole />
          </div>
        ) : (
          <div className="py-8 px-6 bg-slate-950/40 border border-dashed border-slate-800 rounded-xl text-center space-y-3">
            <Clock className="w-8 h-8 text-amber-400/80 mx-auto animate-pulse" />
            <h3 className="text-sm font-semibold text-slate-200">
              {isPunchedOutToday ? 'Shift Punched Out (Cockpit Paused)' : 'Calling Cockpit is Paused'}
            </h3>
            <p className="text-xs text-slate-400 max-w-md mx-auto">
              {isPunchedOutToday
                ? 'Your shift is currently marked as punched out. If you ended it by mistake or want to continue outreach, resume your shift below.'
                : 'Company policy requires an active attendance punch before starting customer outreach. Punch in above to start your dialing session.'}
            </p>
            {isPunchedOutToday && (
              <button
                onClick={handleQuickClockIn}
                disabled={clockingIn}
                className="mt-2 inline-flex items-center gap-2 px-4 py-2 bg-gradient-to-r from-amber-500 to-emerald-600 hover:from-amber-400 hover:to-emerald-500 text-white text-xs font-semibold rounded-xl shadow-lg shadow-amber-500/20 cursor-pointer"
              >
                <RotateCcw className={`w-3.5 h-3.5 ${clockingIn ? 'animate-spin' : ''}`} />
                Resume Shift Now
              </button>
            )}
          </div>
        )}
      </div>

      {/* Quick actions + Announcements */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2"><QuickActionsWidget /></div>
        <div className="lg:col-span-1"><AnnouncementsWidget /></div>
      </div>

      {/* Personal work widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <WorkQueueWidget />
        <MyTasksWidget />
        <MyLeadsWidget data={summary} loading={loading} />
        <TodayScheduleWidget data={summary} loading={loading} />
        <AttendanceWidget />
        <LeaveWidget />
        <TargetsWidget />
        <PerformanceWidget />
        <ApprovalsWidget />
        <DashboardNotificationsWidget />
        <MyReportsWidget />
      </div>
    </div>
  );
};
