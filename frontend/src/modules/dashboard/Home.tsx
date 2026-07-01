import React, { useEffect } from 'react';
import { useAuthStore } from '../../store/authStore';
import { useDashboardStore } from '../../store/dashboardStore';
import { SummaryCards } from '../../components/dashboard/SummaryCards';
import { LeadStatusChart } from '../../components/dashboard/LeadStatusChart';
import { RecentActivitiesWidget } from '../../components/dashboard/RecentActivitiesWidget';
import { AnalyticsDashboard } from '../../components/dashboard/AnalyticsDashboard';
import { useAnalyticsStore } from '../../store/analyticsStore';
import { DialerConsole } from '../../components/dialer/DialerConsole';
import { Sparkles, Building, RefreshCw } from 'lucide-react';

export const Home: React.FC = () => {
  const { user, organization, features } = useAuthStore();
  const {
    summary,
    recentActivities,
    totalRecent,
    page,
    limit,
    isLoadingSummary,
    isLoadingActivities,
    fetchSummary,
    fetchRecentActivities,
    setPage
  } = useDashboardStore();

  const { dashboardData, fetchDashboardMetrics } = useAnalyticsStore();

  const handleRefresh = async () => {
    await Promise.all([fetchSummary(), fetchRecentActivities(), fetchDashboardMetrics()]);
  };

  useEffect(() => {
    fetchSummary();
    fetchRecentActivities();
    fetchDashboardMetrics();
  }, []);

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="glass-panel p-8 rounded-2xl relative overflow-hidden flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-indigo-500/10 rounded-full blur-[80px] pointer-events-none"></div>
        
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-brand-500/10 text-brand-600 dark:text-brand-300 text-xs font-semibold rounded-full border border-brand-500/20">
            <Sparkles className="w-3.5 h-3.5" />
            Operations Overview
          </div>
          <h1 className="text-4xl font-extrabold text-slate-100 tracking-tight">
            Welcome back, <span className="gradient-text">{user?.first_name || 'Admin'}</span>
          </h1>
          <p className="text-slate-500 dark:text-slate-400 text-sm md:text-base max-w-xl">
            Real-time analytics and activity summary for your organization workspace.
          </p>
        </div>

        <div className="flex items-center gap-6">
          <button
            onClick={handleRefresh}
            title="Refresh dashboard data"
            className="p-3 border border-slate-200 dark:border-slate-800 hover:bg-slate-100 dark:hover:bg-slate-900 rounded-xl text-slate-600 dark:text-slate-400 hover:text-slate-800 dark:hover:text-slate-200 transition-all cursor-pointer bg-slate-50 dark:bg-slate-950/20"
          >
            <RefreshCw className={`w-4 h-4 ${(isLoadingSummary || isLoadingActivities) ? 'animate-spin' : ''}`} />
          </button>

          <div className="flex items-center gap-3 px-5 py-4 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-xl">
            <Building className="w-10 h-10 text-brand-400" />
            <div>
              <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Active Tenant</p>
              <p className="text-md font-bold text-slate-100">{organization?.name}</p>
              <p className="text-xs text-slate-500 dark:text-slate-400">/{organization?.slug}</p>
            </div>
          </div>
        </div>
      </div>

      {/* Telecaller cockpit — available on all plans. Plans with OUTBOUND_CALLING get
          integrated click-to-call; entry plans (e.g. Core CRM) get the manual workflow. */}
      {dashboardData?.role === 'Telecaller' && (
        <div className="space-y-4">
          <div>
            <h3 className="text-lg font-bold text-slate-100">Agent Dialer cockpit</h3>
            <p className="text-xs text-slate-500 dark:text-slate-400 mt-1">
              {features.includes('OUTBOUND_CALLING')
                ? 'Start your dialing session to contact leads assigned to your queue.'
                : 'Work your assigned queue — call on your own phone, then log the outcome and update the pipeline.'}
            </p>
          </div>
          <DialerConsole />
        </div>
      )}

      {/* Analytics Performance Dashboard */}
      <AnalyticsDashboard />

      {/* KPI Cards Widget */}
      <SummaryCards summary={summary} isLoading={isLoadingSummary} />

      {/* Analytics Charts & Timelines Grid */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Left column - Lead Status Chart */}
        <div className="lg:col-span-1">
          <LeadStatusChart summary={summary} isLoading={isLoadingSummary} />
        </div>

        {/* Right column - Recent Activities Widget */}
        <div className="lg:col-span-2">
          <RecentActivitiesWidget
            activities={recentActivities}
            total={totalRecent}
            page={page}
            limit={limit}
            isLoading={isLoadingActivities}
            onPageChange={setPage}
          />
        </div>
      </div>
    </div>
  );
};
