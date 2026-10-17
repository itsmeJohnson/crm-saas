import React, { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Building, ShieldCheck, Database, HardDrive, RefreshCw,
  Users, TrendingUp, AlertTriangle, ArrowRight,
  Server, Shield
} from 'lucide-react';
import { superAdminApi, SuperAdminDashboard } from '../../services/superAdminApi';

export const SuperAdminTelemetryDashboard: React.FC = () => {
  const [data, setData] = useState<SuperAdminDashboard | null>(null);
  const [period, setPeriod] = useState<'day' | 'week' | 'month'>('month');
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchTelemetry = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const res = await superAdminApi.getDashboard(period);
      setData(res);
    } catch (err: any) {
      setError(err?.response?.data?.detail || 'Failed to load platform telemetry metrics.');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTelemetry();
  }, [period]);

  return (
    <div className="space-y-6 animate-fade-in">
      {/* ── Systemic Telemetry Header ── */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 p-6 rounded-2xl bg-gradient-to-r from-slate-900/90 via-slate-900/70 to-slate-800/80 border border-slate-800/80 backdrop-blur-md shadow-xl">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-cyan-500/10 text-cyan-400 border border-cyan-500/30">
              Root Control
            </span>
            <span className="flex items-center gap-1.5 text-xs font-medium text-emerald-400">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
              Infrastructure Operational
            </span>
          </div>
          <h1 className="text-2xl font-bold tracking-tight text-slate-100">
            CRM Enterprise · Secure Multi-Tenant Platform
          </h1>
          <p className="text-xs text-slate-400 max-w-xl">
            System-level multi-tenant telemetry, VPS node allocations, and licensing orchestration across client environments.
          </p>
        </div>

        <div className="flex items-center gap-2.5 flex-wrap">
          <div className="flex rounded-xl overflow-hidden border border-slate-800 bg-slate-900/80 p-0.5">
            {(['day', 'week', 'month'] as const).map((p) => (
              <button
                key={p}
                onClick={() => setPeriod(p)}
                className={`px-3 py-1.5 text-xs font-semibold rounded-lg transition-all capitalize cursor-pointer ${
                  period === p
                    ? 'bg-cyan-600 text-white shadow'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {p === 'day' ? 'Today' : p === 'week' ? 'This Week' : 'This Month'}
              </button>
            ))}
          </div>

          <button
            onClick={fetchTelemetry}
            disabled={isLoading}
            className="flex items-center gap-1.5 px-3.5 py-1.5 rounded-xl text-xs font-medium bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700/60 transition cursor-pointer"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>
      </div>

      {error && (
        <div className="p-4 rounded-xl bg-rose-500/10 border border-rose-500/20 text-rose-400 text-xs flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* ── Systemic Telemetry KPI Row ── */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {/* Total Tenants */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Total Tenants</span>
            <Building className="w-4 h-4 text-cyan-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">
            {isLoading ? '...' : data?.orgs.total ?? 0}
          </div>
          <div className="flex items-center gap-2 text-xs text-slate-400">
            <span className="text-emerald-400 font-medium">{data?.orgs.active ?? 0} Active</span>
            <span>•</span>
            <span className="text-cyan-400 font-medium">{data?.orgs.trial ?? 0} Trial</span>
          </div>
        </div>

        {/* Licensed Seats */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Seat Utilization</span>
            <Users className="w-4 h-4 text-brand-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100">
            {isLoading ? '...' : `${data?.licensing.utilization_percent ?? 0}%`}
          </div>
          <div className="text-xs text-slate-400">
            <span className="text-slate-200 font-medium">{data?.licensing.active_seats ?? 0}</span> of{' '}
            {data?.licensing.total_licensed_seats ?? 0} total licensed seats
          </div>
        </div>

        {/* Platform MRR */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Platform MRR</span>
            <TrendingUp className="w-4 h-4 text-emerald-400" />
          </div>
          <div className="text-2xl font-bold text-emerald-400">
            {isLoading ? '...' : `₹${Number(data?.revenue.mrr ?? 0).toLocaleString('en-IN')}`}
          </div>
          <div className="text-xs text-slate-400">
            ARR: ₹{Number(data?.revenue.arr ?? 0).toLocaleString('en-IN')}
          </div>
        </div>

        {/* System Health */}
        <div className="p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-lg space-y-2">
          <div className="flex items-center justify-between text-slate-400">
            <span className="text-xs font-semibold uppercase tracking-wider">Database & Cache</span>
            <Server className="w-4 h-4 text-purple-400" />
          </div>
          <div className="text-2xl font-bold text-slate-100 flex items-center gap-2">
            <span className="inline-block w-3 h-3 rounded-full bg-emerald-400" />
            <span>Optimal</span>
          </div>
          <div className="text-xs text-slate-400 flex items-center gap-2">
            <span>DB: {data?.infra.db_status || 'healthy'}</span>
            <span>•</span>
            <span>Redis: {data?.infra.redis_status || 'healthy'}</span>
          </div>
        </div>
      </div>

      {/* ── Infrastructure & Actions Grid ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* VPS & Node Infrastructure Telemetry */}
        <div className="lg:col-span-2 p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-lg space-y-5">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2.5">
              <HardDrive className="w-5 h-5 text-cyan-400" />
              <h3 className="text-sm font-bold text-slate-100 tracking-tight">
                Cluster Storage & Node Allocation
              </h3>
            </div>
            <span className="text-[10px] text-slate-400 font-mono">
              telemetry: {data?.generated_at ? new Date(data.generated_at).toLocaleTimeString() : 'live'}
            </span>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <span className="text-xs text-slate-400">Total Cloud Volume Storage</span>
              <div className="text-xl font-bold text-slate-100">
                {data?.infra.total_storage_gb ?? 0} GB
              </div>
              <p className="text-[11px] text-slate-500">PostgreSQL data & tenant upload storage</p>
            </div>

            <div className="p-4 rounded-xl bg-slate-950/60 border border-slate-800 space-y-2">
              <span className="text-xs text-slate-400">Call Recordings Archive</span>
              <div className="text-xl font-bold text-slate-100">
                {data?.infra.call_recording_gb ?? 0} GB
              </div>
              <p className="text-[11px] text-slate-500">Audio playback media across call centers</p>
            </div>
          </div>

          <div className="p-4 rounded-xl bg-slate-950/40 border border-slate-800/60 space-y-3">
            <h4 className="text-xs font-semibold text-slate-300">System Telemetry Highlights</h4>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-3 text-xs">
              <div>
                <span className="text-slate-500 block">New Tenants ({period})</span>
                <span className="text-slate-200 font-bold">{data?.revenue.period_onboarded ?? 0}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Renewals (Next 7 Days)</span>
                <span className="text-slate-200 font-bold">{data?.activity.renewals_due_7days ?? 0}</span>
              </div>
              <div>
                <span className="text-slate-500 block">Trials Expiring (Next 7 Days)</span>
                <span className="text-slate-200 font-bold">{data?.activity.trials_expiring_7days ?? 0}</span>
              </div>
            </div>
          </div>
        </div>

        {/* Root Infrastructure Shortcuts */}
        <div className="p-6 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-lg flex flex-col justify-between space-y-4">
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Shield className="w-5 h-5 text-cyan-400" />
              <h3 className="text-sm font-bold text-slate-100">Root Management Shortcuts</h3>
            </div>
            <p className="text-xs text-slate-400 leading-relaxed">
              Direct access to multi-tenant scaling, database instances, and licensing controls.
            </p>
          </div>

          <div className="space-y-2.5">
            <Link
              to="/tenants"
              className="w-full flex items-center justify-between p-3 rounded-xl bg-cyan-950/30 hover:bg-cyan-900/40 border border-cyan-500/20 text-cyan-300 text-xs font-semibold transition"
            >
              <div className="flex items-center gap-2.5">
                <Building className="w-4 h-4 text-cyan-400" />
                <span>Manage Tenants & VPS Nodes</span>
              </div>
              <ArrowRight className="w-4 h-4" />
            </Link>

            <Link
              to="/trial-requests"
              className="w-full flex items-center justify-between p-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 text-slate-200 text-xs font-semibold transition"
            >
              <div className="flex items-center gap-2.5">
                <ShieldCheck className="w-4 h-4 text-emerald-400" />
                <span>Review Trial Requests</span>
              </div>
              <ArrowRight className="w-4 h-4" />
            </Link>

            <Link
              to="/settings"
              className="w-full flex items-center justify-between p-3 rounded-xl bg-slate-800/60 hover:bg-slate-800 border border-slate-700/60 text-slate-200 text-xs font-semibold transition"
            >
              <div className="flex items-center gap-2.5">
                <Database className="w-4 h-4 text-purple-400" />
                <span>Global System Settings</span>
              </div>
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      </div>
    </div>
  );
};
