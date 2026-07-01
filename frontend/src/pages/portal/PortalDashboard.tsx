import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { portalApi, DashboardStatsResponse } from '../../services/portalApi';
import { extractErrorMessage } from '../../utils/errors';
import {
  Sparkles, CreditCard, Users, HardDrive, PhoneCall,
  ArrowRight, Plus, AlertTriangle, Loader2, CheckCircle2, ChevronRight
} from 'lucide-react';

export const PortalDashboard: React.FC = () => {
  const [stats, setStats] = useState<DashboardStatsResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  // Seat purchase state
  const [showSeatModal, setShowSeatModal] = useState(false);
  const [seatCount, setSeatCount] = useState(1);
  const [selectedGateway, setSelectedGateway] = useState('UPI');
  const [buyingSeats, setBuyingSeats] = useState(false);
  const [purchaseSuccess, setPurchaseSuccess] = useState<string | null>(null);
  const [extraSeatUnitPrice, setExtraSeatUnitPrice] = useState(0);
  const [extraSeatGstPercent, setExtraSeatGstPercent] = useState(0);
  const [extraSeatGstInclusive, setExtraSeatGstInclusive] = useState(false);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'quarterly' | 'annual'>('monthly');
  const [cyclePrices, setCyclePrices] = useState<{ monthly: number; quarterly: number; annual: number }>({ monthly: 0, quarterly: 0, annual: 0 });
  const [canAddExtra, setCanAddExtra] = useState(false);

  useEffect(() => {
    fetchStats();
    fetchSeatPricing();
  }, []);

  const fetchStats = async () => {
    try {
      setLoading(true);
      const data = await portalApi.getStats();
      setStats(data);
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to load dashboard statistics."));
    } finally {
      setLoading(false);
    }
  };

  const fetchSeatPricing = async () => {
    try {
      const pricing = await portalApi.getExtraSeatPricing();
      setExtraSeatUnitPrice(pricing.unit_price || 0);
      setExtraSeatGstPercent(pricing.gst_percentage || 0);
      setExtraSeatGstInclusive(pricing.gst_inclusive || false);
      setCyclePrices(pricing.cycle_prices || { monthly: 0, quarterly: 0, annual: 0 });
      setCanAddExtra(Boolean(pricing.can_add_extra));
    } catch {
      // Pricing display falls back to 0 if pricing details aren't available yet
    }
  };

  // Mirrors the backend's exact billing math (PortalService.buy_extra_seats)
  // so the preview total always matches what gets invoiced.
  const calculateSeatTotal = () => {
    const baseAmount = seatCount * (cyclePrices[billingCycle] || extraSeatUnitPrice);
    if (extraSeatGstInclusive) {
      return baseAmount;
    }
    return baseAmount * (1 + extraSeatGstPercent / 100);
  };

  const handleBuySeats = async () => {
    try {
      setBuyingSeats(true);
      setError(null);
      // 1. Generate Invoice
      const invoice = await portalApi.buyExtraSeats({
        user_count: seatCount,
        gateway: selectedGateway,
        billing_cycle: billingCycle
      });
      // 2. Pay Invoice (Simulated immediately on checkout)
      await portalApi.payInvoice(invoice.id, {
        gateway: selectedGateway,
        transaction_id: `TXN-SEAT-${uuidFast()}`
      });
      setPurchaseSuccess(`Successfully added ${seatCount} user seats! Your limits have been updated.`);
      setShowSeatModal(false);
      fetchStats();
    } catch (err: any) {
      setError(extractErrorMessage(err, "Failed to purchase additional seats."));
    } finally {
      setBuyingSeats(false);
    }
  };

  const uuidFast = () => {
    return Math.random().toString(36).substring(2, 15).toUpperCase();
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader2 className="w-8 h-8 animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="space-y-8 text-left">
      {/* Page Header */}
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center gap-4">
        <div>
          <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
            Subscription Command Center
          </h2>
          <p className="text-xs text-slate-400 mt-1">
            Manage subscription metrics, extra seat volumes, dynamic billing configs, and local support tickets.
          </p>
        </div>
        <div className="flex gap-2">
          <Link
            to="/portal/plans"
            className="flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10"
          >
            <Sparkles className="w-3.5 h-3.5" />
            Upgrade Plan
          </Link>
          {canAddExtra && (
            <button
              onClick={() => {
                setPurchaseSuccess(null);
                setShowSeatModal(true);
              }}
              className="flex items-center gap-1.5 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 rounded-xl text-xs font-bold transition-all"
            >
              <Plus className="w-3.5 h-3.5" />
              Add User Seats
            </button>
          )}
        </div>
      </div>

      {purchaseSuccess && (
        <div className="p-4 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 shrink-0" />
          {purchaseSuccess}
        </div>
      )}

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {stats && (
        <>
          {/* Top KPI row */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Plan Info */}
            <div className="glass-panel p-5 border border-slate-900 rounded-2xl relative overflow-hidden">
              <div className="absolute top-0 right-0 w-24 h-24 bg-brand-500/5 rounded-full blur-2xl"></div>
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Active Plan</span>
                  <h3 className="text-lg font-bold text-slate-100 mt-1">{stats.plan_name}</h3>
                </div>
                <div className="p-2 bg-brand-500/10 rounded-lg text-brand-400">
                  <Sparkles className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4 flex items-center gap-2">
                <span className="px-2 py-0.5 text-[9px] font-bold bg-emerald-500/10 text-emerald-400 rounded uppercase border border-emerald-500/20">
                  {stats.subscription_status}
                </span>
                <span className="text-[10px] text-slate-500 font-medium">
                  {stats.days_remaining} days left
                </span>
              </div>
            </div>

            {/* Days Left */}
            <div className="glass-panel p-5 border border-slate-900 rounded-2xl relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Days Remaining</span>
                  <h3 className="text-xl font-bold text-slate-100 mt-1">{stats.days_remaining} Days</h3>
                </div>
                <div className="p-2 bg-indigo-500/10 rounded-lg text-indigo-400">
                  <CreditCard className="w-4 h-4" />
                </div>
              </div>
              <p className="text-[10px] text-slate-500 mt-4">
                Upcoming renewal: {stats.upcoming_renewal_date ? new Date(stats.upcoming_renewal_date).toLocaleDateString() : 'N/A'}
              </p>
            </div>

            {/* Pending Invoices */}
            <div className="glass-panel p-5 border border-slate-900 rounded-2xl relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Unpaid Balance</span>
                  <h3 className="text-xl font-bold text-slate-100 mt-1">
                    {stats.pending_invoice_amount > 0 ? `₹${stats.pending_invoice_amount.toFixed(2)}` : 'No Dues'}
                  </h3>
                </div>
                <div className="p-2 bg-rose-500/10 rounded-lg text-rose-400">
                  <AlertTriangle className="w-4 h-4" />
                </div>
              </div>
              <div className="mt-4">
                {stats.pending_invoice_amount > 0 ? (
                  <Link to="/portal/invoices" className="text-[10px] text-brand-400 hover:text-brand-300 font-bold flex items-center gap-1">
                    Pay Now <ArrowRight className="w-3 h-3" />
                  </Link>
                ) : (
                  <span className="text-[10px] text-slate-500 font-medium">All invoices cleared</span>
                )}
              </div>
            </div>

            {/* Last Payment */}
            <div className="glass-panel p-5 border border-slate-900 rounded-2xl relative overflow-hidden">
              <div className="flex justify-between items-start">
                <div>
                  <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider">Last Transaction</span>
                  <h3 className="text-xl font-bold text-slate-100 mt-1">₹{stats.last_payment_amount.toFixed(2)}</h3>
                </div>
                <div className="p-2 bg-emerald-500/10 rounded-lg text-emerald-400">
                  <CheckCircle2 className="w-4 h-4" />
                </div>
              </div>
              <p className="text-[10px] text-slate-500 mt-4">
                Verified successfully processed
              </p>
            </div>
          </div>

          {/* Usage Meters */}
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
            {/* User Seats Meter */}
            <div className="glass-panel p-6 border border-slate-900 rounded-2xl text-left space-y-4">
              <div className="flex justify-between items-center">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <Users className="w-4 h-4 text-brand-400" />
                  User Seats Usage
                </h4>
                <span className="text-xs font-semibold text-slate-300">
                  {stats.users.current} / {stats.users.limit} Limit
                </span>
              </div>
              <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-brand-500 to-indigo-500 h-full rounded-full transition-all"
                  style={{ width: `${Math.min(stats.users.percent, 100)}%` }}
                ></div>
              </div>
              <div className="flex justify-between items-center text-[10px] text-slate-500">
                <span>{stats.users.percent}% Consumed</span>
                {canAddExtra && (
                  <button
                    onClick={() => setShowSeatModal(true)}
                    className="text-brand-400 hover:text-brand-300 font-bold"
                  >
                    Buy Seats
                  </button>
                )}
              </div>
            </div>

            {/* Storage Meter */}
            <div className="glass-panel p-6 border border-slate-900 rounded-2xl text-left space-y-4">
              <div className="flex justify-between items-center">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <HardDrive className="w-4 h-4 text-indigo-400" />
                  Storage Allocation
                </h4>
                <span className="text-xs font-semibold text-slate-300">
                  {stats.storage.used_gb.toFixed(2)} GB / {stats.storage.limit_gb} GB
                </span>
              </div>
              <div className="w-full bg-slate-900 h-2.5 rounded-full overflow-hidden">
                <div
                  className="bg-gradient-to-r from-indigo-500 to-purple-500 h-full rounded-full transition-all"
                  style={{ width: `${Math.min(stats.storage.percent, 100)}%` }}
                ></div>
              </div>
              <div className="flex justify-between items-center text-[10px] text-slate-500">
                <span>{stats.storage.percent}% Used</span>
                <Link to="/portal/storage" className="text-brand-400 hover:text-brand-300 font-bold">
                  Purchase Storage
                </Link>
              </div>
            </div>

            {/* Recordings Stats */}
            <div className="glass-panel p-6 border border-slate-900 rounded-2xl text-left space-y-4">
              <div className="flex justify-between items-center">
                <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400 flex items-center gap-1.5">
                  <PhoneCall className="w-4 h-4 text-emerald-400" />
                  Voice Recordings
                </h4>
                <span className="text-xs font-semibold text-slate-300">
                  {stats.recording_count} Logs
                </span>
              </div>
              <div className="p-3.5 bg-slate-900/50 rounded-xl flex items-center justify-between text-xs mt-1">
                <span className="text-slate-500">Recordings stored:</span>
                <strong className="text-slate-300">{stats.recording_count} files</strong>
              </div>
              <div className="text-right">
                <Link to="/portal/recordings" className="text-[10px] text-brand-400 hover:text-brand-300 font-bold flex items-center justify-end gap-0.5">
                  View Recordings <ChevronRight className="w-3.5 h-3.5" />
                </Link>
              </div>
            </div>
          </div>

          {/* Recent Activity Section */}
          <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden text-left">
            <div className="p-5 border-b border-slate-900 flex justify-between items-center">
              <h3 className="text-sm font-bold text-slate-200 uppercase tracking-wider">
                Recent Operations History
              </h3>
              <Link to="/portal/activity" className="text-xs font-bold text-slate-500 hover:text-slate-300">
                View All Audit Logs
              </Link>
            </div>
            {stats.recent_activities.length === 0 ? (
              <p className="p-6 text-slate-500 text-xs text-center">No recent operations logged.</p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-xs text-left">
                  <thead>
                    <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                      <th className="p-4">Action Event</th>
                      <th className="p-4">Modified Layer</th>
                      <th className="p-4 text-right">Performed At</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stats.recent_activities.map((log) => (
                      <tr key={log.id} className="border-b border-slate-900 hover:bg-slate-900/20 text-slate-300">
                        <td className="p-4 font-mono font-semibold text-brand-400">{log.action}</td>
                        <td className="p-4">{log.resource_type}</td>
                        <td className="p-4 text-right text-slate-500">
                          {new Date(log.created_at).toLocaleString()}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </div>
        </>
      )}

      {/* Seat Purchase Modal */}
      {showSeatModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <div className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-6 bg-slate-950">
            <div>
              <h3 className="text-lg font-bold text-slate-100">Add Extra User Seats</h3>
              <p className="text-xs text-slate-500 mt-1">
                Purchase seat volume instantly. Limits automatically update upon transaction completion.
              </p>
            </div>

            <div className="space-y-4">
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Billing Cycle</label>
                <div className="grid grid-cols-3 gap-2">
                  {(['monthly', 'quarterly', 'annual'] as const).map((cycle) => (
                    <button
                      key={cycle}
                      type="button"
                      onClick={() => setBillingCycle(cycle)}
                      className={`px-2 py-2 rounded-xl text-xs font-bold capitalize border transition-all ${
                        billingCycle === cycle
                          ? 'bg-brand-500/15 border-brand-500/50 text-brand-300'
                          : 'bg-slate-900 border-slate-800 text-slate-400 hover:border-slate-700'
                      }`}
                    >
                      {cycle}
                      <span className="block text-[10px] font-mono font-normal text-slate-500 mt-0.5">
                        ₹{(cyclePrices[cycle] || 0).toFixed(0)}/seat
                      </span>
                    </button>
                  ))}
                </div>
              </div>
              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Number of Seats</label>
                <input
                  type="number"
                  min="1"
                  max="500"
                  value={seatCount}
                  onChange={(e) => setSeatCount(Math.min(500, Math.max(1, Math.floor(Number(e.target.value)) || 1)))}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Payment Gateway</label>
                <select
                  value={selectedGateway}
                  onChange={(e) => setSelectedGateway(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                >
                  <option value="UPI">UPI / Instant QR</option>
                  <option value="Stripe">Stripe Gateway</option>
                  <option value="Razorpay">Razorpay Checkout</option>
                  <option value="PhonePe">PhonePe Transfer</option>
                  <option value="Bank">Direct Bank Transfer</option>
                </select>
              </div>

              <div className="p-4 bg-slate-900/50 rounded-xl space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Unit Price ({stats?.plan_name || 'current plan'}):</span>
                  <span className="font-mono text-slate-300">₹{(cyclePrices[billingCycle] || extraSeatUnitPrice).toFixed(2)} / seat / {billingCycle === 'monthly' ? 'month' : billingCycle === 'quarterly' ? 'quarter' : 'year'}</span>
                </div>
                <div className="flex justify-between border-t border-slate-800/80 pt-2 font-bold text-sm">
                  <span className="text-slate-400">Total + Tax ({extraSeatGstPercent}% GST{extraSeatGstInclusive ? ', inclusive' : ''}):</span>
                  <span className="text-slate-100">₹{calculateSeatTotal().toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setShowSeatModal(false)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleBuySeats}
                disabled={buyingSeats}
                className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold"
              >
                {buyingSeats ? (
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
      )}
    </div>
  );
};
