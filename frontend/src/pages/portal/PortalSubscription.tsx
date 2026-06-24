import React, { useState, useEffect } from 'react';
import { portalApi } from '../../services/portalApi';
import {
  Shield, Check, Calendar, Settings, AlertTriangle,
  RotateCcw, Sparkles, Loader2, CheckCircle2, ShieldAlert
} from 'lucide-react';

export const PortalSubscription: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [renewing, setRenewing] = useState(false);

  useEffect(() => {
    fetchSubscription();
  }, []);

  const fetchSubscription = async () => {
    try {
      setLoading(true);
      const res = await portalApi.getSubscription();
      setData(res);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load subscription details.");
    } finally {
      setLoading(false);
    }
  };

  const handleCancelAutoRenew = async () => {
    try {
      setError(null);
      setSuccess(null);
      const res = await portalApi.cancelAutoRenew();
      setSuccess(res.message || "Auto-renewal successfully cancelled.");
      fetchSubscription();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to cancel auto-renewal.");
    }
  };

  const handleRenewSubscription = async () => {
    try {
      setRenewing(true);
      setError(null);
      setSuccess(null);
      
      // 1. Trigger subscription renewal (simulated immediate extension)
      const res = await portalApi.payInvoice(data.subscription.id, {
        gateway: 'UPI',
        transaction_id: `TXN-RENEW-${Math.random().toString(36).substring(2, 12).toUpperCase()}`
      });
      
      setSuccess("Subscription extended successfully!");
      fetchSubscription();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to renew subscription.");
    } finally {
      setRenewing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  const sub = data?.subscription;
  const plan = sub?.plan;

  return (
    <div className="space-y-8 text-left max-w-4xl">
      {/* Header */}
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
          Active Plan & Subscription
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Inspect plan capacities, verify billing timelines, check trial periods, and modify automated renewals.
        </p>
      </div>

      {success && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {success}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {sub ? (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {/* Main Info Columns */}
          <div className="md:col-span-2 space-y-6">
            {/* Status card */}
            <div className="glass-panel border border-slate-900 rounded-2xl p-6 space-y-4">
              <div className="flex justify-between items-center">
                <div>
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Plan Level</span>
                  <h3 className="text-lg font-bold text-slate-100">{plan?.display_name || plan?.name}</h3>
                </div>
                <span className="px-2.5 py-1 text-xs font-bold uppercase bg-brand-500/10 text-brand-400 border border-brand-500/20 rounded-lg">
                  {sub.status}
                </span>
              </div>

              <div className="grid grid-cols-2 gap-4 text-xs pt-4 border-t border-slate-900">
                <div className="space-y-1">
                  <p className="text-slate-500 font-medium">Cycle Term:</p>
                  <p className="text-slate-200 capitalize font-semibold">{sub.billing_cycle || 'monthly'}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-slate-500 font-medium">Auto-Renew:</p>
                  <p className={`font-semibold ${sub.auto_renew ? 'text-emerald-400' : 'text-slate-400'}`}>
                    {sub.auto_renew ? 'Enabled' : 'Disabled'}
                  </p>
                </div>
                <div className="space-y-1">
                  <p className="text-slate-500 font-medium">Plan Start Date:</p>
                  <p className="text-slate-200 font-semibold">{new Date(sub.start_date).toLocaleDateString()}</p>
                </div>
                <div className="space-y-1">
                  <p className="text-slate-500 font-medium">Renewal Date:</p>
                  <p className="text-slate-200 font-semibold">{new Date(sub.end_date).toLocaleDateString()}</p>
                </div>
              </div>
            </div>

            {/* Limits Card */}
            <div className="glass-panel border border-slate-900 rounded-2xl p-6 text-left space-y-4">
              <h3 className="text-xs font-bold uppercase tracking-wider text-slate-400">Capacity Allocations</h3>
              <div className="space-y-3.5 pt-2">
                <div className="flex justify-between items-baseline text-xs">
                  <span className="text-slate-400">Total User Seats limit</span>
                  <strong className="text-slate-200 font-mono">{plan?.max_users} Seats</strong>
                </div>
                <div className="flex justify-between items-baseline text-xs border-t border-slate-900 pt-3">
                  <span className="text-slate-400">Maximum Managers limit</span>
                  <strong className="text-slate-200 font-mono">{plan?.max_managers} Seats</strong>
                </div>
                <div className="flex justify-between items-baseline text-xs border-t border-slate-900 pt-3">
                  <span className="text-slate-400">Maximum Team Leaders limit</span>
                  <strong className="text-slate-200 font-mono">{plan?.max_team_leads} Seats</strong>
                </div>
                <div className="flex justify-between items-baseline text-xs border-t border-slate-900 pt-3">
                  <span className="text-slate-400">Maximum Storage boundary</span>
                  <strong className="text-slate-200 font-mono">{plan?.storage_limit_gb} GB</strong>
                </div>
                <div className="flex justify-between items-baseline text-xs border-t border-slate-900 pt-3">
                  <span className="text-slate-400">Call Recordings Retention</span>
                  <strong className="text-slate-200 font-mono">{plan?.recording_retention_days} Days</strong>
                </div>
              </div>
            </div>
          </div>

          {/* Action sidebar column */}
          <div className="md:col-span-1 space-y-6">
            <div className="glass-panel border border-slate-900 rounded-2xl p-6 space-y-6 bg-slate-950/60">
              <div>
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Quick Operations</h4>
                <p className="text-[10px] text-slate-500 mt-1">Manage active cycles directly</p>
              </div>

              <div className="space-y-2.5">
                {sub.auto_renew ? (
                  <button
                    type="button"
                    onClick={handleCancelAutoRenew}
                    className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-red-500/20 text-slate-300 hover:text-red-400 rounded-xl text-xs font-bold transition-all"
                  >
                    <ShieldAlert className="w-3.5 h-3.5" />
                    Disable Auto-Renew
                  </button>
                ) : (
                  <div className="p-3 bg-rose-500/5 border border-rose-500/10 rounded-xl text-[10px] text-rose-400 flex items-start gap-2">
                    <AlertTriangle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
                    Auto-renew is inactive. Your plan will expire on renewal date.
                  </div>
                )}

                <button
                  type="button"
                  onClick={handleRenewSubscription}
                  disabled={renewing}
                  className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10"
                >
                  {renewing ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <>
                      <RotateCcw className="w-3.5 h-3.5" />
                      Renew Manually Now
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-slate-500 text-sm">No active subscription records found for this organization.</p>
      )}
    </div>
  );
};
