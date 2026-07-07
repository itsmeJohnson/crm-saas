import React, { useCallback, useEffect, useState } from 'react';
import { useAuthStore } from '../../store/authStore';
import { dashboardApi, EmployeeSummary } from '../../services/dashboardApi';
import { Sparkles, RefreshCw, FolderKanban, Phone, Users, ListTodo } from 'lucide-react';
import { MyTasksWidget } from '../../components/dashboard/MyTasksWidget';
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

/**
 * Focused, role-based dashboard for individual contributors (Employee).
 * Shows the person's own work — leads, tasks, schedule, attendance, leave,
 * targets, performance — rather than the org-wide operations overview that
 * managers/OrgAdmins see. Fully responsive (Tailwind grids).
 */
export const EmployeeDashboard: React.FC = () => {
  const { user } = useAuthStore();
  const [summary, setSummary] = useState<EmployeeSummary | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(() => {
    setLoading(true);
    dashboardApi.getEmployeeSummary().then(setSummary).catch(() => {}).finally(() => setLoading(false));
  }, []);
  useEffect(() => { load(); }, [load]);

  const kpis = [
    { label: 'My leads', value: summary?.my_leads_total ?? 0, icon: FolderKanban },
    { label: 'Calls today', value: summary?.today_calls ?? 0, icon: Phone },
    { label: 'Meetings today', value: summary?.today_meetings_count ?? 0, icon: Users },
    { label: 'Open tasks', value: summary?.open_tasks ?? 0, icon: ListTodo, alert: (summary?.overdue_tasks ?? 0) > 0 ? `${summary?.overdue_tasks} overdue` : undefined },
  ];

  return (
    <div className="space-y-6">
      {/* Personal welcome banner */}
      <div className="glass-panel p-6 sm:p-8 rounded-2xl relative overflow-hidden flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
        <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-indigo-500/10 rounded-full blur-[80px] pointer-events-none" />
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-brand-500/10 text-brand-600 dark:text-brand-300 text-xs font-semibold rounded-full border border-brand-500/20">
            <Sparkles className="w-3.5 h-3.5" /> My Workspace
          </div>
          <h1 className="text-3xl sm:text-4xl font-extrabold text-slate-100 tracking-tight">
            Hi, <span className="gradient-text">{user?.first_name || 'there'}</span>
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm max-w-xl">Here's your day at a glance — your leads, tasks and schedule.</p>
        </div>
        <button onClick={load} title="Refresh" className="p-3 border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-900 rounded-xl text-slate-600 dark:text-slate-400 cursor-pointer bg-slate-50 dark:bg-slate-950/20">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
        </button>
      </div>

      {/* KPI row */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {kpis.map((k) => (
          <div key={k.label} className="glass-panel border border-slate-800/85 rounded-xl p-4">
            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><k.icon className="w-3 h-3 text-brand-400" /> {k.label}</p>
            <p className="text-2xl font-bold text-slate-100 mt-1">{k.value}</p>
            {k.alert && <p className="text-[10px] text-amber-400 mt-0.5">{k.alert}</p>}
          </div>
        ))}
      </div>

      {/* Quick actions + Announcements */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2"><QuickActionsWidget /></div>
        <div className="lg:col-span-1"><AnnouncementsWidget /></div>
      </div>

      {/* Personal work widgets */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
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
