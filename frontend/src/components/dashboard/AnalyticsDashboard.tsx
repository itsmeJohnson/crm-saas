import React, { useEffect, useState } from 'react';
import { DialerConsole } from '../dialer/DialerConsole';
import { useAnalyticsStore } from '../../store/analyticsStore';
import { useAuthStore } from '../../store/authStore';
import {
  Phone,
  CheckCircle,
  Calendar,
  TrendingUp,
  Award,
  Users,
  Target,
  RefreshCw,
  AlertCircle,
  TrendingDown
} from 'lucide-react';
import {
  TelecallerMetrics,
  TeamLeaderMetrics,
  ManagerMetrics,
  SuperAdminMetrics
} from '../../services/analyticsApi';

export const AnalyticsDashboard: React.FC = () => {
  const { dashboardData, isLoading, error, fetchDashboardMetrics } = useAnalyticsStore();
  const { features } = useAuthStore();
  const [enableDialer, setEnableDialer] = useState(false);

  useEffect(() => {
    fetchDashboardMetrics();
  }, []);

  if (isLoading && !dashboardData) {
    return (
      <div className="grid grid-cols-1 md:grid-cols-4 gap-6 animate-pulse">
        {[...Array(4)].map((_, i) => (
          <div key={i} className="h-32 bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
            <div className="h-4 bg-slate-800 rounded w-1/2"></div>
            <div className="h-8 bg-slate-800 rounded w-3/4"></div>
          </div>
        ))}
      </div>
    );
  }

  if (error) {
    return (
      <div className="glass-panel p-8 rounded-2xl border border-red-500/20 bg-red-500/5 flex flex-col items-center text-center space-y-4">
        <AlertCircle className="w-12 h-12 text-red-400" />
        <h3 className="text-lg font-bold text-slate-100">Failed to Load Performance Analytics</h3>
        <p className="text-slate-400 text-sm max-w-md">{error}</p>
        <button
          onClick={() => fetchDashboardMetrics()}
          className="flex items-center gap-2 px-4 py-2 bg-slate-900 border border-slate-850 hover:border-slate-700 hover:bg-slate-900/80 rounded-xl text-sm text-slate-200 transition-all cursor-pointer"
        >
          <RefreshCw className="w-4 h-4" />
          Retry Connection
        </button>
      </div>
    );
  }

  if (!dashboardData) {
    return (
      <div className="glass-panel p-8 rounded-2xl text-center text-slate-400 text-sm">
        No performance analytics data available for today.
      </div>
    );
  }

  const { role, metrics } = dashboardData;

  // --- 1. Agent Canvas (Telecaller) ---
  if (role === 'Telecaller') {
    const teleMetrics = metrics as TelecallerMetrics;
    const callsMade = teleMetrics.calls_made || 0;
    const conversions = teleMetrics.conversions || 0;
    const uniqueLeads = teleMetrics.unique_leads_contacted || 0;
    const followUps = Math.max(0, uniqueLeads - conversions);
    const conversionRate = callsMade > 0 ? ((conversions / callsMade) * 100).toFixed(1) : '0.0';

    const cards = [
      { title: "Today's Calls", value: callsMade, icon: Phone, color: 'text-indigo-400 bg-indigo-500/5 border-indigo-500/10' },
      { title: 'Converted', value: conversions, icon: CheckCircle, color: 'text-emerald-400 bg-emerald-500/5 border-emerald-500/10' },
      { title: 'Follow-up Counter', value: followUps, icon: Calendar, color: 'text-amber-400 bg-amber-500/5 border-amber-500/10' },
      { title: 'Conversion Ratio', value: `${conversionRate}%`, icon: TrendingUp, color: 'text-brand-400 bg-brand-500/5 border-brand-500/10' }
    ];

    return (
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {cards.map((card, idx) => (
          <div key={idx} className="glass-panel p-6 rounded-2xl flex items-center justify-between border border-slate-800/80 hover:border-slate-700/60 transition-all group">
            <div className="space-y-1">
              <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">{card.title}</p>
              <p className="text-3xl font-extrabold text-slate-100 group-hover:scale-[1.02] transition-transform origin-left">{card.value}</p>
            </div>
            <div className={`p-3 rounded-xl border ${card.color}`}>
              <card.icon className="w-6 h-6" />
            </div>
          </div>
        ))}
      </div>
    );
  }

  // --- 2. Team Leader Canvas ---
  if (role === 'TeamLeader') {
    const tlMetrics = metrics as TeamLeaderMetrics;
    const totalCalls = tlMetrics.total_calls_made || 0;
    const totalConversions = tlMetrics.total_conversions || 0;
    const tlConvRate = totalCalls > 0 ? ((totalConversions / totalCalls) * 100).toFixed(1) : '0.0';

    return (
      <div className="space-y-8">
        {/* Cumulative Stats Grid */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
          <div className="glass-panel p-6 rounded-2xl flex items-center justify-between border border-slate-800/80">
            <div className="space-y-1">
              <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Team Calls Made</p>
              <p className="text-3xl font-extrabold text-slate-100">{totalCalls}</p>
            </div>
            <div className="p-3 rounded-xl bg-indigo-500/5 border border-indigo-500/10 text-indigo-400">
              <Phone className="w-6 h-6" />
            </div>
          </div>
          <div className="glass-panel p-6 rounded-2xl flex items-center justify-between border border-slate-800/80">
            <div className="space-y-1">
              <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Team Conversions</p>
              <p className="text-3xl font-extrabold text-slate-100">{totalConversions}</p>
            </div>
            <div className="p-3 rounded-xl bg-emerald-500/5 border border-emerald-500/10 text-emerald-400">
              <CheckCircle className="w-6 h-6" />
            </div>
          </div>
          <div className="glass-panel p-6 rounded-2xl flex items-center justify-between border border-slate-800/80">
            <div className="space-y-1">
              <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Team Conversion Rate</p>
              <p className="text-3xl font-extrabold text-brand-400">{tlConvRate}%</p>
            </div>
            <div className="p-3 rounded-xl bg-brand-500/5 border border-brand-500/10 text-brand-400">
              <TrendingUp className="w-6 h-6" />
            </div>
          </div>
          <div className="glass-panel p-6 rounded-2xl flex items-center justify-between border border-slate-800/80">
            <div className="space-y-1">
              <p className="text-xs text-slate-400 uppercase tracking-wider font-semibold">Active Downlines</p>
              <p className="text-3xl font-extrabold text-slate-100">{tlMetrics.downlines?.length || 0}</p>
            </div>
            <div className="p-3 rounded-xl bg-slate-500/5 border border-slate-500/10 text-slate-400">
              <Users className="w-6 h-6" />
            </div>
          </div>
        </div>

        {/* Team Performers Ranks & Matrix */}
        <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden">
          <div className="px-6 py-5 border-b border-slate-800/60 bg-slate-900/20 flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
            <div>
              <h3 className="text-lg font-bold text-slate-100">Telecaller Performance Matrix</h3>
              <p className="text-xs text-slate-400 mt-1">Real-time team leaderboard based on conversion metrics.</p>
            </div>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800/50 bg-slate-950/20 text-xs text-slate-400 uppercase font-semibold">
                  <th className="px-6 py-4">Agent Name</th>
                  <th className="px-6 py-4">Email</th>
                  <th className="px-6 py-4">Calls Made</th>
                  <th className="px-6 py-4">Unique Contacted</th>
                  <th className="px-6 py-4">Conversions</th>
                  <th className="px-6 py-4">Conversion Rate</th>
                  <th className="px-6 py-4 text-right">Performance Designation</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/40 text-sm text-slate-300">
                {tlMetrics.downlines?.map((agent) => {
                  const isTop = tlMetrics.top_performer?.user_id === agent.user_id;
                  const isLow = tlMetrics.low_performer?.user_id === agent.user_id;

                  return (
                    <tr key={agent.user_id} className="hover:bg-slate-900/10 transition-colors">
                      <td className="px-6 py-4 font-semibold text-slate-100">
                        {`${agent.first_name || ''} ${agent.last_name || ''}`.trim() || '—'}
                      </td>
                      <td className="px-6 py-4 text-slate-400">{agent.email}</td>
                      <td className="px-6 py-4">{agent.calls_made}</td>
                      <td className="px-6 py-4">{agent.unique_leads_contacted}</td>
                      <td className="px-6 py-4">{agent.conversions}</td>
                      <td className="px-6 py-4 font-medium text-slate-100">{agent.conversion_rate}%</td>
                      <td className="px-6 py-4 text-right">
                        {isTop && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-emerald-500/10 text-emerald-400 text-xs font-semibold rounded-full border border-emerald-500/20">
                            <Award className="w-3.5 h-3.5" />
                            Top Performer
                          </span>
                        )}
                        {isLow && (
                          <span className="inline-flex items-center gap-1 px-2.5 py-1 bg-amber-500/10 text-amber-400 text-xs font-semibold rounded-full border border-amber-500/20">
                            <TrendingDown className="w-3.5 h-3.5" />
                            Low Performer
                          </span>
                        )}
                        {!isTop && !isLow && <span className="text-slate-500 text-xs">—</span>}
                      </td>
                    </tr>
                  );
                })}
                {(!tlMetrics.downlines || tlMetrics.downlines.length === 0) && (
                  <tr>
                    <td colSpan={7} className="px-6 py-8 text-center text-slate-500 text-sm">
                      No active telecalling agents report to your workspace.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* Optional Team Leader Dialer Workspace */}
        {features.includes('OUTBOUND_CALLING') && (
          <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-4 bg-gradient-to-tr from-slate-950/20 via-slate-900/5 to-brand-950/5">
            <div className="flex items-center justify-between">
              <div>
                <h3 className="text-base font-bold text-slate-100">TL Dialer Workspace</h3>
                <p className="text-xs text-slate-400 mt-0.5">Enable dialer mode to make calls directly from your own lead queue.</p>
              </div>
              <button
                onClick={() => setEnableDialer(!enableDialer)}
                className={`px-4 py-2 rounded-xl text-xs font-semibold border transition-all cursor-pointer ${
                  enableDialer
                    ? 'bg-brand-500/10 text-brand-300 border-brand-500/30 shadow-lg shadow-brand-500/5'
                    : 'bg-slate-900 text-slate-400 border-slate-800 hover:border-slate-700 hover:text-slate-200'
                }`}
              >
                {enableDialer ? 'Disable Dialer Mode' : 'Enable Dialer Mode'}
              </button>
            </div>

            {enableDialer && (
              <div className="pt-4 border-t border-slate-800/60 animate-in fade-in slide-in-from-top-2 duration-200">
                <DialerConsole />
              </div>
            )}
          </div>
        )}
      </div>
    );
  }

  // --- 3. Manager Canvas ---
  if (role === 'Manager') {
    const mgrMetrics = metrics as ManagerMetrics;
    const sortedTeams = [...(mgrMetrics.teams || [])].sort((a, b) => b.total_conversions - a.total_conversions);

    return (
      <div className="space-y-8">
        {/* Manager Summary totals card */}
        <div className="glass-panel p-8 rounded-2xl border border-slate-800 flex flex-col md:flex-row md:items-center justify-between gap-6 bg-gradient-to-tr from-slate-950/40 via-slate-900/10 to-indigo-950/10">
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-slate-100">Manager Operational Cluster overview</h3>
            <p className="text-sm text-slate-550 dark:text-slate-400">Comparing performance metrics across active Team Leader teams.</p>
          </div>
          <div className="flex flex-wrap items-center gap-8">
            <div className="space-y-1">
              <p className="text-xs text-slate-500 uppercase font-semibold">Total Cluster Calls</p>
              <p className="text-2xl font-black text-slate-100">{mgrMetrics.total_calls_made}</p>
            </div>
            <div className="w-[1px] h-10 bg-slate-800 hidden md:block"></div>
            <div className="space-y-1">
              <p className="text-xs text-slate-500 uppercase font-semibold">Total Cluster Conversions</p>
              <p className="text-2xl font-black text-brand-400">{mgrMetrics.total_conversions}</p>
            </div>
            <div className="w-[1px] h-10 bg-slate-800 hidden md:block"></div>
            <div className="space-y-1">
              <p className="text-xs text-slate-500 uppercase font-semibold">Overall Conversion Rate</p>
              <p className="text-2xl font-black text-emerald-400">
                {mgrMetrics.total_calls_made > 0 ? ((mgrMetrics.total_conversions / mgrMetrics.total_calls_made) * 100).toFixed(1) : '0.0'}%
              </p>
            </div>
          </div>
        </div>

        {/* Side-by-Side Comparative Team Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {sortedTeams.map((team, idx) => {
            const isHighest = idx === 0 && team.total_conversions > 0;
            const isLowest = idx === sortedTeams.length - 1 && sortedTeams.length > 1;
            const convRate = team.total_calls_made > 0 ? ((team.total_conversions / team.total_calls_made) * 100).toFixed(1) : '0.0';

            return (
              <div
                key={team.tl_id}
                className={`glass-panel p-6 rounded-2xl border transition-all flex flex-col justify-between ${
                  isHighest ? 'border-emerald-500/20 bg-emerald-500/5' : isLowest ? 'border-amber-500/20 bg-amber-500/5' : 'border-slate-800'
                }`}
              >
                <div className="space-y-4">
                  <div className="flex items-start justify-between">
                    <div>
                      <p className="text-sm font-bold text-slate-100">
                        {`${team.tl_first_name || ''} ${team.tl_last_name || ''}`.trim() || 'TL Team'}
                      </p>
                      <p className="text-xs text-slate-500 mt-0.5">{team.tl_email}</p>
                    </div>
                    {isHighest && (
                      <span className="px-2 py-0.5 bg-emerald-500/10 text-emerald-400 text-[10px] font-bold uppercase rounded-full border border-emerald-500/25">
                        High Production
                      </span>
                    )}
                    {isLowest && (
                      <span className="px-2 py-0.5 bg-amber-500/10 text-amber-400 text-[10px] font-bold uppercase rounded-full border border-amber-500/25">
                        Low Production
                      </span>
                    )}
                  </div>

                  <div className="grid grid-cols-3 gap-4 pt-4 border-t border-slate-800/40">
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-slate-550 dark:text-slate-500 uppercase tracking-wider">Calls</p>
                      <p className="text-md font-bold text-slate-100">{team.total_calls_made}</p>
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-slate-550 dark:text-slate-500 uppercase tracking-wider">Conversions</p>
                      <p className="text-md font-bold text-slate-100">{team.total_conversions}</p>
                    </div>
                    <div className="space-y-0.5">
                      <p className="text-[10px] text-slate-500 uppercase tracking-wider">Ratio</p>
                      <p className="text-md font-bold text-brand-400">{convRate}%</p>
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
          {sortedTeams.length === 0 && (
            <div className="col-span-full py-8 text-center text-slate-500 text-sm">
              No active Team Leader clusters report to your workspace.
            </div>
          )}
        </div>
      </div>
    );
  }

  // --- 4. Super Admin Canvas ---
  if (role === 'SuperAdmin') {
    const adminMetrics = metrics as SuperAdminMetrics;

    return (
      <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-6">
        <div className="flex items-center justify-between">
          <div className="space-y-1">
            <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
              <Target className="w-5 h-5 text-brand-400" />
              Organizational Performance Milestones
            </h3>
            <p className="text-xs text-slate-400">Tracking progress gauges against current active goals.</p>
          </div>
        </div>

        <div className="space-y-6">
          {adminMetrics.targets_progress?.map((gauge) => {
            // Formatting text label
            const typeLabel = gauge.target_type.charAt(0) + gauge.target_type.slice(1).toLowerCase();
            const metricLabel = gauge.metric_type === 'CALLS_MADE' ? 'Calls Quota' : 'Conversions Quota';

            return (
              <div key={gauge.target_id} className="space-y-2">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between text-sm gap-1">
                  <div className="flex items-center gap-2">
                    <span className="px-2 py-0.5 bg-slate-900 border border-slate-800 rounded-md text-[10px] font-bold text-slate-400 uppercase">
                      {typeLabel}
                    </span>
                    <span className="text-slate-200 font-semibold">{metricLabel}</span>
                  </div>
                  <span className="text-xs text-slate-550 dark:text-slate-400">
                    <span className="text-slate-100 font-extrabold">{gauge.progress_percentage.toFixed(0)}%</span> of {typeLabel} {gauge.metric_type === 'CALLS_MADE' ? 'Call' : 'Conversion'} Goal Achieved
                  </span>
                </div>

                {/* Progress Line */}
                <div className="relative w-full h-2 bg-slate-950/80 rounded-full border border-slate-850 overflow-hidden">
                  <div
                    className="absolute top-0 left-0 h-full rounded-full bg-gradient-to-r from-brand-500 to-indigo-500 shadow-md shadow-brand-500/25"
                    style={{ width: `${Math.min(100, gauge.progress_percentage)}%` }}
                  ></div>
                </div>
              </div>
            );
          })}
          {(!adminMetrics.targets_progress || adminMetrics.targets_progress.length === 0) && (
            <div className="py-8 text-center text-slate-500 text-sm">
              No active performance targets set for this period.
            </div>
          )}
        </div>
      </div>
    );
  }

  return null;
};
