import React, { useState } from 'react';
import { X, Receipt, CheckCircle2, Loader2 } from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { api } from '../../services/api';

interface RecordPaymentModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
  invoice?: any;
}

export const RecordPaymentModal: React.FC<RecordPaymentModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  invoice,
}) => {
  const [amount, setAmount] = useState<number>(invoice ? Number(invoice.total_amount) - Number(invoice.amount_paid || 0) : 5000);
  const [method, setMethod] = useState<string>('UPI');
  const [reference, setReference] = useState<string>('');
  const notes = '';
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);

  if (!isOpen || !invoice) return null;

  const balDue = Number(invoice.total_amount) - Number(invoice.amount_paid || 0);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsSubmitting(true);
    try {
      await api.post(`/customers/invoices/${invoice.id}/payments`, {
        amount: amount,
        method: method,
        reference: reference || `REC-${Date.now().toString().slice(-6)}`,
        notes: notes || `Payment received for ${invoice.invoice_number}`
      });

      alert('Payment recorded successfully!');
      if (onSuccess) onSuccess();
      onClose();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to record payment');
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col">
        <div className="p-5 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/25 flex items-center justify-center text-emerald-400">
              <Receipt className="w-5 h-5" />
            </div>
            <div>
              <h3 className="text-base font-bold text-slate-100">Record Patient Payment</h3>
              <p className="text-xs text-slate-400">Invoice #{invoice.invoice_number}</p>
            </div>
          </div>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-200 rounded-lg hover:bg-slate-800">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit} className="p-5 space-y-4 text-xs">
          <div className="p-3 bg-slate-950/60 rounded-xl border border-slate-800 flex justify-between items-center">
            <span className="text-slate-400">Current Balance Due:</span>
            <strong className="text-sm text-amber-400 font-bold">{formatMoney(balDue)}</strong>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Payment Amount (INR)</label>
            <input
              type="number"
              value={amount}
              max={balDue > 0 ? balDue : undefined}
              onChange={(e) => setAmount(Number(e.target.value))}
              required
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-emerald-500 font-mono text-sm font-bold"
            />
          </div>

          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Payment Method</label>
            <select
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              className="w-full px-3.5 py-2.5 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-emerald-500"
            >
              <option value="UPI">UPI (Google Pay / PhonePe / Paytm)</option>
              <option value="Card">Credit / Debit Card POS</option>
              <option value="Cash">Cash at Reception</option>
              <option value="BankTransfer">Net Banking / NEFT / IMPS</option>
            </select>
          </div>

          <div>
            <label className="block font-semibold text-slate-300 uppercase tracking-wider mb-1.5">Transaction Ref / Receipt #</label>
            <input
              type="text"
              value={reference}
              onChange={(e) => setReference(e.target.value)}
              placeholder="e.g. UPI-987213451 or POS-654"
              className="w-full px-3.5 py-2 bg-slate-950 border border-slate-800 rounded-xl text-slate-200 focus:outline-none focus:border-emerald-500 font-mono"
            />
          </div>

          <div className="flex items-center justify-end gap-3 pt-3 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-semibold rounded-xl"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-5 py-2 bg-emerald-500 hover:bg-emerald-600 active:bg-emerald-700 text-white font-semibold rounded-xl flex items-center gap-2 shadow-lg shadow-emerald-500/20 disabled:opacity-50"
            >
              {isSubmitting ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle2 className="w-4 h-4" />}
              Confirm Receipt
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
