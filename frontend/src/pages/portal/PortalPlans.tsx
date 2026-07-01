import React, { useState, useEffect } from 'react';
import { portalApi } from '../../services/portalApi';
import { payInvoiceViaCashfree } from '../../services/cashfree';
import {
  CheckCircle2, AlertTriangle, Loader2, CreditCard, Check,
} from 'lucide-react';

export const PortalPlans: React.FC = () => {
  const [plans, setPlans] = useState<any[]>([]);
  const [subscription, setSubscription] = useState<any | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'quarterly' | 'annual'>('monthly');

  // Checkout states
  const [selectedPlan, setSelectedPlan] = useState<any | null>(null);
  const [selectedGateway, setSelectedGateway] = useState('Cashfree');
  const [processing, setProcessing] = useState(false);

  useEffect(() => {
    fetchPlans();
  }, []);

  const fetchPlans = async () => {
    try {
      setLoading(true);
      const [plansData, subData] = await Promise.all([
        portalApi.getPlans(),
        portalApi.getSubscription()
      ]);
      setPlans(plansData);
      setSubscription(subData?.subscription || null);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to retrieve subscription plans.");
    } finally {
      setLoading(false);
    }
  };

  // Returns the per-seat per-MONTH rate for the chosen billing cycle (discounted rate).
  const getCycleMonthlyRate = (plan: any): number => {
    if (billingCycle === 'annual') return plan.annual_price > 0 ? plan.annual_price : plan.monthly_price;
    if (billingCycle === 'quarterly') return plan.quarterly_price > 0 ? plan.quarterly_price : plan.monthly_price;
    return plan.monthly_price > 0 ? plan.monthly_price : plan.price_inr;
  };

  // Number of months covered by one invoice for the current cycle.
  const cycleMonths = billingCycle === 'annual' ? 12 : billingCycle === 'quarterly' ? 3 : 1;

  const handleCheckout = async () => {
    if (!selectedPlan) return;
    try {
      setProcessing(true);
      setError(null);
      setSuccess(null);

      // 1. Generate upgrade invoice
      const invoice = await portalApi.upgradePlan({
        plan_id: selectedPlan.id,
        billing_cycle: billingCycle,
        gateway: selectedGateway
      });

      // 2. Pay. Cashfree = real hosted checkout + server-side verification;
      //    other options are dev-only simulated payments (rejected in production).
      if (selectedGateway === 'Cashfree') {
        await payInvoiceViaCashfree(invoice.id);
      } else {
        await portalApi.payInvoice(invoice.id, {
          gateway: selectedGateway,
          transaction_id: `TXN-UPGRADE-${Math.random().toString(36).substring(2, 14).toUpperCase()}`
        });
      }

      setSuccess(`Successfully upgraded to the "${selectedPlan.display_name || selectedPlan.name}" plan! Your subscription has been updated.`);
      setSelectedPlan(null);
      window.scrollTo({ top: 0, behavior: 'smooth' });
      fetchPlans();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to process plan upgrade.");
    } finally {
      setProcessing(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 text-left max-w-6xl mx-auto">
      {/* Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
            Subscription Tier Upgrades
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Compare subscription tier capabilities, explore dynamic discount rates, and upgrade workspace structures.
          </p>
        </div>

        {/* Cycle Toggle */}
        <div className="bg-slate-900/60 border border-slate-800 p-1 rounded-xl flex gap-1">
          {(['monthly', 'quarterly', 'annual'] as const).map((cycle) => (
            <button
              key={cycle}
              onClick={() => setBillingCycle(cycle)}
              className={`px-3.5 py-1.5 rounded-lg text-xs font-bold capitalize transition-all cursor-pointer ${
                billingCycle === cycle
                  ? 'bg-brand-500 text-white shadow'
                  : 'text-slate-400 hover:text-slate-200'
              }`}
            >
              {cycle}
            </button>
          ))}
        </div>
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

      {/* Plans Comparison Grid */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-stretch">
        {plans.map((plan) => {
          const monthlyRate = getCycleMonthlyRate(plan);
          const isPopular = plan.popular_plan;
          const isRecommended = plan.recommended_plan;

          return (
            <div
              key={plan.id}
              className={`glass-panel border rounded-2xl p-6 flex flex-col justify-between relative transition-all duration-200 ${
                isRecommended
                  ? 'border-brand-500/40 shadow-lg shadow-brand-500/5 bg-slate-950/40'
                  : 'border-slate-900 hover:border-slate-800'
              }`}
            >
              {/* Badge */}
              {(isPopular || isRecommended || plan.plan_badge) && (
                <span className="absolute top-4 right-4 px-2 py-0.5 text-[9px] font-bold tracking-wider uppercase rounded bg-brand-500/20 text-brand-400 border border-brand-500/20">
                  {plan.plan_badge || (isRecommended ? 'Recommended' : 'Popular')}
                </span>
              )}

              {/* Title & Description */}
              <div className="space-y-4">
                <div>
                  <h3 className="text-lg font-bold text-slate-100">{plan.display_name || plan.name}</h3>
                  <p className="text-xs text-slate-400 mt-1 min-h-[32px]">{plan.description || 'Enterprise tools to accelerate calling operations.'}</p>
                </div>

                {/* Price Display */}
                <div className="py-2 space-y-1">
                  <div className="flex items-baseline gap-1">
                    <span className="text-2xl font-bold text-slate-100">₹{monthlyRate.toLocaleString('en-IN', { minimumFractionDigits: 2 })}</span>
                    <span className="text-[10px] text-slate-500 font-medium">/ seat / mo</span>
                  </div>
                  {billingCycle !== 'monthly' && (
                    <p className="text-[9px] text-amber-400 font-semibold">
                      Billed {billingCycle === 'quarterly' ? 'every 3 months' : 'annually'} — one invoice covers {cycleMonths} months
                    </p>
                  )}
                  <p className="text-[10px] text-brand-400 font-semibold">
                    Starts from: ₹{(monthlyRate * plan.minimum_users * cycleMonths).toLocaleString('en-IN')}/{billingCycle === 'monthly' ? 'mo' : billingCycle === 'quarterly' ? 'quarter' : 'yr'} (Min {plan.minimum_users} seats)
                  </p>
                  {subscription && (
                    <p className="text-[10px] text-indigo-400 font-semibold">
                      Your cost ({Math.max(subscription.users_purchased, plan.minimum_users)} seats): ₹{(monthlyRate * Math.max(subscription.users_purchased, plan.minimum_users) * cycleMonths).toLocaleString('en-IN', { maximumFractionDigits: 0 })}/{billingCycle === 'monthly' ? 'mo' : billingCycle === 'quarterly' ? 'quarter' : 'yr'}
                    </p>
                  )}
                  {plan.setup_charges > 0 && (
                    <p className="text-[9px] text-slate-500 mt-1">One-time setup charges: ₹{parseFloat(plan.setup_charges).toFixed(2)}</p>
                  )}
                </div>

                {/* Divider */}
                <div className="border-t border-slate-900 my-4"></div>

                {/* Key Features */}
                <div className="space-y-3 pt-2 text-xs">
                  <div className="flex items-center gap-2 text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>Minimum <strong>{plan.minimum_users} Licensed Seats</strong></span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>{plan.allow_additional_seats ? `Add seats dynamically at ₹${parseFloat(plan.extra_user_price || plan.monthly_price).toFixed(0)}/seat/mo` : 'Fixed seats count (no add-on seats)'}</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span><strong>{plan.storage_limit_gb} GB</strong> Cloud Storage</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span><strong>{plan.recording_retention_days} Days</strong> Call Recording retention</span>
                  </div>
                  <div className="flex items-center gap-2 text-slate-300">
                    <Check className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>{plan.priority_support ? '24/7 Priority Support' : 'Standard email support'}</span>
                  </div>
                </div>
              </div>

              {/* Action Button */}
              <div className="mt-8">
                <button
                  type="button"
                  onClick={() => setSelectedPlan(plan)}
                  disabled={!plan.allow_upgrade}
                  className={`w-full py-2.5 rounded-xl text-xs font-bold transition-all cursor-pointer ${
                    plan.allow_upgrade
                      ? isRecommended
                        ? 'bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white shadow-md shadow-brand-500/10'
                        : 'bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 hover:text-slate-100'
                      : 'bg-slate-950 border border-slate-900/50 text-slate-600 cursor-not-allowed'
                  }`}
                >
                  {plan.allow_upgrade ? 'Select Tier Plan' : 'Plan Locked'}
                </button>
              </div>
            </div>
          );
        })}
      </div>

      {/* Checkout Modal */}
      {selectedPlan && (() => {
        const currentSeatCount = subscription ? Math.max(subscription.users_purchased, selectedPlan.minimum_users) : selectedPlan.minimum_users;
        const ratePerSeatPerMonth = getCycleMonthlyRate(selectedPlan);
        const tierPrice = ratePerSeatPerMonth * currentSeatCount * cycleMonths;
        const setupCharges = parseFloat(selectedPlan.setup_charges || 0.0);
        const gstAmount = tierPrice * 0.18;
        const totalPrice = tierPrice + gstAmount + setupCharges;

        return (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
            <div className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-6 bg-slate-950">
              <div>
                <h3 className="text-lg font-bold text-slate-100">Upgrade Plan Checkout</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Verify upgrade specifications. Billing updates automatically after processed transaction.
                </p>
              </div>

              <div className="space-y-4">
                <div className="p-3 bg-slate-900/40 border border-slate-900 rounded-xl space-y-1">
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">New Tier Plan</span>
                  <div className="flex justify-between items-center">
                    <span className="text-sm font-bold text-slate-200">{selectedPlan.display_name || selectedPlan.name}</span>
                    <span className="text-xs font-semibold text-slate-400 capitalize">{billingCycle} Cycle</span>
                  </div>
                </div>

                <div>
                  <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Payment Gateway</label>
                  <select
                    value={selectedGateway}
                    onChange={(e) => setSelectedGateway(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  >
                    <option value="Cashfree">Cashfree (Cards / UPI / Netbanking)</option>
                    <option value="UPI">UPI / Instant (test only)</option>
                  </select>
                </div>

                {/* Total calculations */}
                <div className="p-4 bg-slate-900/50 rounded-xl space-y-2 text-xs">
                  <div className="flex justify-between">
                    <span className="text-slate-500">Rate per seat / mo:</span>
                    <span className="font-mono text-slate-300">₹{ratePerSeatPerMonth.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Licensed seats:</span>
                    <span className="font-semibold text-slate-300">
                      {currentSeatCount} seats
                      {subscription && subscription.users_purchased < selectedPlan.minimum_users && (
                        <span className="text-[9px] text-brand-400 block font-normal">
                          (adjusted to plan minimum of {selectedPlan.minimum_users})
                        </span>
                      )}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-500">Billing period:</span>
                    <span className="font-semibold text-slate-300">{cycleMonths} month{cycleMonths > 1 ? 's' : ''}</span>
                  </div>
                  <div className="flex justify-between border-t border-slate-800/80 pt-1">
                    <span className="text-slate-500">Subtotal ({currentSeatCount} × ₹{ratePerSeatPerMonth.toFixed(0)} × {cycleMonths}mo):</span>
                    <span className="font-mono text-slate-300">₹{tierPrice.toFixed(2)}</span>
                  </div>
                  {setupCharges > 0 && (
                    <div className="flex justify-between">
                      <span className="text-slate-500">Setup charges (one-time):</span>
                      <span className="font-mono text-slate-300">₹{setupCharges.toFixed(2)}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-slate-500">GST @18%:</span>
                    <span className="font-mono text-slate-300">₹{gstAmount.toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-t border-slate-800/80 pt-2 font-bold text-sm">
                    <span className="text-slate-400">Total due now:</span>
                    <span className="text-slate-100">₹{totalPrice.toFixed(2)}</span>
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setSelectedPlan(null)}
                  className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleCheckout}
                  disabled={processing}
                  className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold"
                >
                  {processing ? (
                    <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  ) : (
                    <>
                      <CreditCard className="w-3.5 h-3.5" />
                      Pay & Process
                    </>
                  )}
                </button>
              </div>
            </div>
          </div>
        );
      })()}
    </div>
  );
};
