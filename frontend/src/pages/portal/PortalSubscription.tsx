import React, { useState, useEffect } from 'react';
import { portalApi } from '../../services/portalApi';
import { payInvoiceViaCashfree } from '../../services/cashfree';
import {
  Shield, Check, AlertTriangle,
  RotateCcw, Loader2, CheckCircle2, ShieldAlert, Users, X
} from 'lucide-react';

export const PortalSubscription: React.FC = () => {
  const [data, setData] = useState<any>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [renewing, setRenewing] = useState(false);

  // Seat reduction states
  const [isReduceSeatsOpen, setIsReduceSeatsOpen] = useState(false);
  const [newSeatCount, setNewSeatCount] = useState(10);
  const [reducing, setReducing] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

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

      const sub = data?.subscription;
      if (!sub?.plan_id) {
        setError("No active subscription found to renew.");
        return;
      }

      // Renewal = a fresh invoice for the CURRENT plan + billing cycle. Paying it
      // extends the subscription for another period (handled by the upgrade_plan
      // action on the backend). Verified & charged through Cashfree.
      const invoice = await portalApi.upgradePlan({
        plan_id: sub.plan_id,
        billing_cycle: sub.billing_cycle || 'monthly',
        gateway: 'Cashfree'
      });

      await payInvoiceViaCashfree(invoice.id);

      setSuccess("Subscription renewed successfully! Your billing period has been extended.");
      fetchSubscription();
    } catch (err: any) {
      setError(err.response?.data?.detail || err?.message || "Failed to renew subscription.");
    } finally {
      setRenewing(false);
    }
  };

  const handleReduceSeats = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!sub) return;

    if (newSeatCount < 10) {
      setModalError("Seat count must be at least 10 Licensed Seats.");
      return;
    }
    if (newSeatCount >= sub.users_purchased) {
      setModalError("New seat count must be lower than your current purchased seats.");
      return;
    }
    if (newSeatCount < sub.users_active) {
      setModalError(`Cannot reduce seats below active user count of ${sub.users_active}. Please deactivate employees first.`);
      return;
    }

    try {
      setReducing(true);
      setModalError(null);
      setError(null);
      setSuccess(null);
      
      await portalApi.reduceSeats({ new_seat_count: newSeatCount });
      
      setSuccess(`Successfully scheduled seat count reduction to ${newSeatCount} seats. This will take effect on next billing cycle renewal.`);
      setIsReduceSeatsOpen(false);
      fetchSubscription();
    } catch (err: any) {
      setModalError(err.response?.data?.detail || "Failed to schedule seat count reduction.");
    } finally {
      setReducing(false);
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
                  <span className="text-slate-400">Licensed Seats</span>
                  <div className="text-right">
                    <strong className="text-slate-200 font-mono">{sub?.users_purchased || plan?.max_users || 10} Seats</strong>
                    {sub?.users_purchased_next && (
                      <span className="text-[10px] text-brand-400 block mt-0.5">
                        (Reducing to {sub.users_purchased_next} seats next cycle)
                      </span>
                    )}
                  </div>
                </div>
                <div className="flex justify-between items-baseline text-xs border-t border-slate-900 pt-3">
                  <span className="text-slate-400">Occupied Seats</span>
                  <strong className="text-slate-200 font-mono">{sub?.users_active || 0} Seats</strong>
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
                    className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-red-500/20 text-slate-300 hover:text-red-400 rounded-xl text-xs font-bold transition-all cursor-pointer"
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
                  className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
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

                <button
                  type="button"
                  onClick={() => {
                    setNewSeatCount(sub?.users_purchased || 10);
                    setModalError(null);
                    setIsReduceSeatsOpen(true);
                  }}
                  className="w-full flex items-center justify-center gap-1.5 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-brand-500/20 text-slate-300 hover:text-brand-400 rounded-xl text-xs font-bold transition-all cursor-pointer"
                >
                  <Users className="w-3.5 h-3.5" />
                  Reduce Licensed Seats
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : (
        <p className="text-slate-500 text-sm">No active subscription records found for this organization.</p>
      )}

      {/* Commercial Terms & Conditions */}
      <div className="glass-panel border border-slate-900 rounded-2xl p-6 text-left space-y-4">
        <div className="flex items-center gap-2 pb-2 border-b border-slate-900">
          <Shield className="w-5 h-5 text-indigo-400" />
          <div>
            <h3 className="text-sm font-bold text-slate-100 uppercase tracking-wider">Commercial Terms & Conditions</h3>
            <p className="text-[10px] text-slate-500">Johnson Softwares Enterprise CRM SaaS Platform v1.0</p>
          </div>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
          <div className="space-y-3">
            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-brand-400 uppercase tracking-widest">1. License Model</span>
              <p className="text-[11px] text-slate-300">The CRM platform is licensed on a Licensed Seat basis. Each active or allocated seat represents one user license. User roles do not affect pricing.</p>
            </div>
            
            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-brand-400 uppercase tracking-widest">2. Initial Subscription</span>
              <p className="text-[11px] text-slate-300">Every new organization must subscribe to a minimum of 10 Licensed Seats and a minimum 3 Months Contract. GST extra as applicable.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-brand-400 uppercase tracking-widest">3. Additional Licenses</span>
              <p className="text-[11px] text-slate-300">After onboarding, additional licenses may be purchased in increments of one (1) seat. Pricing is based on the subscribed plan.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-brand-400 uppercase tracking-widest">4. Billing Cycle</span>
              <p className="text-[11px] text-slate-300">Billing follows the Calendar Month (1st Day to Last Day of the Month). No daily or prorated calculations are applicable.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-brand-400 uppercase tracking-widest">5. New User Activation</span>
              <p className="text-[11px] text-slate-300">Any new licensed seat activated during a billing month will be billed for the entire billing month.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-brand-400 uppercase tracking-widest">6. User Deactivation</span>
              <p className="text-[11px] text-slate-300">If an employee resigns or is deactivated, the seat remains billable until the end of the current billing cycle. Reductions take effect next cycle.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-brand-400 uppercase tracking-widest">7. Replace Employee Policy</span>
              <p className="text-[11px] text-slate-300">Organizations may replace an inactive employee with a new employee using the existing seat. No additional charges are applied.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-brand-400 uppercase tracking-widest">8. License Reduction</span>
              <p className="text-[11px] text-slate-300">Unused licensed seats may be reduced before the next billing cycle. Seat reductions will not affect invoices already generated.</p>
            </div>
          </div>

          <div className="space-y-3">
            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest">9. Role Flexibility</span>
              <p className="text-[11px] text-slate-300">Complete flexibility in assigning roles. Billing depends only on Licensed Seats and not on user roles (Admins/Managers/Telecallers).</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest">10. Storage & Call Recordings</span>
              <p className="text-[11px] text-slate-300">Storage allocation and call recording retention are based on the subscribed plan. Additional storage may be purchased separately.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest">11. Plan Upgrade</span>
              <p className="text-[11px] text-slate-300">Plan upgrades become effective immediately. Additional features are activated without data loss.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest">12. Plan Downgrade</span>
              <p className="text-[11px] text-slate-300">Plan downgrades become effective from the next billing cycle and are subject to plan compatibility.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest">13. Payment Terms</span>
              <p className="text-[11px] text-slate-300">Invoices are generated according to the subscribed licensed seats. Late payments may result in suspension of services.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest">14. Taxes & Support SLA</span>
              <p className="text-[11px] text-slate-300">GST is charged extra as per government regulations. Support SLA depends on plan: Starter (Business Hours), Growth (Priority), Enterprise (Dedicated).</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1">
              <span className="text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest">15. Data Security</span>
              <p className="text-[11px] text-slate-300">Each organization operates in a completely isolated multi-tenant environment. Role Based Access Control (RBAC) and Audit Logs are active.</p>
            </div>

            <div className="p-3 bg-slate-905/30 rounded-xl space-y-1 border border-brand-500/10">
              <span className="text-[9px] font-extrabold text-indigo-400 uppercase tracking-widest font-mono">16. License Definition</span>
              <p className="text-[11px] text-slate-300">Seats are the commercial billing entity. Users and roles are operational entities. Reassign seats using the Replace Employee feature.</p>
            </div>
          </div>
        </div>
      </div>

      {/* Reduce Seats Modal */}
      {isReduceSeatsOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <div className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-6 bg-slate-950 animate-in fade-in zoom-in-95 duration-200">
            <div className="flex justify-between items-center border-b border-slate-900 pb-3">
              <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                <Users className="w-5 h-5 text-brand-400" />
                Schedule Seat Reduction
              </h3>
              <button
                onClick={() => setIsReduceSeatsOpen(false)}
                className="p-1 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            {modalError && (
              <div className="p-3 bg-red-950/20 border border-red-900/30 rounded-xl text-xs text-red-400 flex items-start gap-2">
                <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                <span>{modalError}</span>
              </div>
            )}

            <div className="space-y-4">
              <div className="p-3 bg-slate-900/40 border border-slate-900 rounded-xl space-y-1 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Current Purchased Seats:</span>
                  <span className="font-semibold text-slate-200">{sub.users_purchased} Seats</span>
                </div>
                <div className="flex justify-between border-t border-slate-900 pt-1 mt-1">
                  <span className="text-slate-500">Active (Occupied) Seats:</span>
                  <span className="font-semibold text-slate-200">{sub.users_active} Seats</span>
                </div>
              </div>

              <div className="space-y-1.5">
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400">Target Seat Count</label>
                <input
                  type="number"
                  value={newSeatCount}
                  onChange={(e) => setNewSeatCount(parseInt(e.target.value) || 0)}
                  min={10}
                  max={sub.users_purchased - 1}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                />
                <p className="text-[10px] text-slate-500">
                  Must be at least 10, cannot drop below active users ({sub.users_active}), and must be less than current count ({sub.users_purchased}).
                </p>
              </div>

              <div className="p-3.5 bg-amber-500/5 border border-amber-500/10 rounded-xl text-[10px] text-amber-400/90 leading-relaxed space-y-1">
                <p className="font-bold flex items-center gap-1">
                  <AlertTriangle className="w-3.5 h-3.5" />
                  Important Notice:
                </p>
                <p>
                  Seat count reductions are scheduled and take effect only on your next renewal date (<strong>{new Date(sub.end_date).toLocaleDateString()}</strong>).
                </p>
                <p>
                  You will remain billed for your current seat count ({sub.users_purchased} seats) until the end of the current billing cycle.
                </p>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setIsReduceSeatsOpen(false)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleReduceSeats}
                disabled={reducing}
                className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
              >
                {reducing ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <>
                    <Check className="w-3.5 h-3.5" />
                    Schedule Reduction
                  </>
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
