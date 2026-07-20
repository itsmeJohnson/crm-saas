import React, { useEffect, useState } from 'react';
import { Plus, CreditCard, Loader2, X, CheckCircle2 } from 'lucide-react';
import { portalApi } from '../../services/portalApi';
import { payInvoiceViaCashfree } from '../../services/cashfree';
import { extractErrorMessage } from '../../utils/errors';

interface Props {
  /** Called after seats are successfully purchased so the parent can refresh. */
  onPurchased?: () => void;
  className?: string;
  label?: string;
}

/**
 * Self-contained "buy more seats" control: renders a trigger button and the
 * purchase modal. Fetches its own pricing/eligibility and hides itself entirely
 * when the tenant isn't allowed to buy extra seats (inactive plan, additional
 * seats disallowed, or minimum not yet met). Drop it anywhere in the portal.
 */
export const BuySeatsButton: React.FC<Props> = ({ onPurchased, className, label = 'Buy More Seats' }) => {
  const [open, setOpen] = useState(false);
  const [seatCount, setSeatCount] = useState(1);
  const [billingCycle, setBillingCycle] = useState<'monthly' | 'quarterly' | 'annual'>('monthly');
  const [gateway, setGateway] = useState('Cashfree');
  const [buying, setBuying] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  const [canAddExtra, setCanAddExtra] = useState(false);
  const [planName, setPlanName] = useState<string | null>(null);
  const [gstPercent, setGstPercent] = useState(0);
  const [gstInclusive, setGstInclusive] = useState(false);
  const [cyclePrices, setCyclePrices] = useState<{ monthly: number; quarterly: number; annual: number }>({
    monthly: 0, quarterly: 0, annual: 0,
  });

  useEffect(() => {
    let active = true;
    portalApi.getExtraSeatPricing()
      .then((p) => {
        if (!active) return;
        setCanAddExtra(Boolean(p.can_add_extra));
        setCyclePrices(p.cycle_prices || { monthly: 0, quarterly: 0, annual: 0 });
        setGstPercent(p.gst_percentage || 0);
        setGstInclusive(Boolean(p.gst_inclusive));
        setPlanName(p.plan_name);
      })
      .catch(() => { /* pricing unavailable → button stays hidden */ });
    return () => { active = false; };
  }, []);

  const total = () => {
    const base = seatCount * (cyclePrices[billingCycle] || 0);
    return gstInclusive ? base : base * (1 + gstPercent / 100);
  };

  const handleBuy = async () => {
    try {
      setBuying(true);
      setError(null);
      const invoice = await portalApi.buyExtraSeats({
        user_count: seatCount,
        gateway,
        billing_cycle: billingCycle,
      });
      if (gateway === 'Cashfree') {
        await payInvoiceViaCashfree(invoice.id);
      } else {
        await portalApi.payInvoice(invoice.id, {
          gateway,
          transaction_id: `TXN-SEAT-${Math.random().toString(36).substring(2, 14).toUpperCase()}`,
        });
      }
      setSuccess(`Added ${seatCount} seat${seatCount > 1 ? 's' : ''}. You can now create ${seatCount > 1 ? 'those users' : 'that user'}.`);
      onPurchased?.();
      setTimeout(() => { setOpen(false); setSuccess(null); }, 1600);
    } catch (err: any) {
      setError(extractErrorMessage(err, err?.message || 'Failed to purchase additional seats.'));
    } finally {
      setBuying(false);
    }
  };

  // Not eligible → render nothing (keeps callers simple).
  if (!canAddExtra) return null;

  return (
    <>
      <button
        type="button"
        onClick={() => { setError(null); setSuccess(null); setOpen(true); }}
        className={className || 'flex items-center gap-1.5 px-4 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10'}
      >
        <Plus className="w-3.5 h-3.5" />
        {label}
      </button>

      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <div className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-6 bg-slate-950">
            <div className="flex items-start justify-between">
              <div>
                <h3 className="text-lg font-bold text-slate-100">Buy Additional Seats</h3>
                <p className="text-xs text-slate-500 mt-1">
                  Pick how many seats and a billing cycle. Limits update on payment, then you can create the users.
                </p>
              </div>
              <button onClick={() => setOpen(false)} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
            </div>

            {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-300 text-xs rounded-xl">{error}</div>}
            {success && (
              <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-300 text-xs rounded-xl flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4" />{success}
              </div>
            )}

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
                  value={gateway}
                  onChange={(e) => setGateway(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                >
                  <option value="Cashfree">Cashfree (Cards / UPI / Netbanking)</option>
                  <option value="UPI">UPI / Instant (test only)</option>
                </select>
              </div>

              <div className="p-4 bg-slate-900/50 rounded-xl space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Unit Price ({planName || 'current plan'}):</span>
                  <span className="font-mono text-slate-300">
                    ₹{(cyclePrices[billingCycle] || 0).toFixed(2)} / seat / {billingCycle === 'monthly' ? 'month' : billingCycle === 'quarterly' ? 'quarter' : 'year'}
                  </span>
                </div>
                <div className="flex justify-between border-t border-slate-800/80 pt-2 font-bold text-sm">
                  <span className="text-slate-400">Total + Tax ({gstPercent}% GST{gstInclusive ? ', inclusive' : ''}):</span>
                  <span className="text-slate-100">₹{total().toFixed(2)}</span>
                </div>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleBuy}
                disabled={buying}
                className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold disabled:opacity-60"
              >
                {buying ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <><CreditCard className="w-3.5 h-3.5" />Pay & Process</>}
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
};
