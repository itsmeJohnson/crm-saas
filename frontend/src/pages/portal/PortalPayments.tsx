import React, { useState, useEffect } from 'react';
import { portalApi, PortalPaymentResponse } from '../../services/portalApi';
import {
  Search,
  AlertTriangle, Loader2, 
} from 'lucide-react';

export const PortalPayments: React.FC = () => {
  const [payments, setPayments] = useState<PortalPaymentResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    fetchPayments();
  }, []);

  const fetchPayments = async () => {
    try {
      setLoading(true);
      const data = await portalApi.getPayments();
      setPayments(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load payment history.");
    } finally {
      setLoading(false);
    }
  };

  const filteredPayments = payments.filter((payment) => {
    const query = searchQuery.toLowerCase();
    return (
      payment.invoice_number.toLowerCase().includes(query) ||
      payment.gateway.toLowerCase().includes(query) ||
      (payment.transaction_id && payment.transaction_id.toLowerCase().includes(query))
    );
  });

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
      <div>
        <h2 className="text-xl md:text-2xl font-bold text-slate-100 flex items-center gap-2">
          Payment History Ledger
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Monitor transactional details, audit financial references, trace payment statuses, and review processing logs.
        </p>
      </div>

      {error && (
        <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs font-medium flex items-center gap-2">
          <AlertTriangle className="w-4 h-4 shrink-0" />
          {error}
        </div>
      )}

      {/* Search Bar */}
      <div className="relative">
        <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
        <input
          type="text"
          placeholder="Search by invoice number, transaction ID, or gateway..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
        />
      </div>

      {/* Payment Ledger Grid */}
      <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden">
        {filteredPayments.length === 0 ? (
          <p className="p-8 text-slate-500 text-xs text-center">No payment transactions recorded.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                  <th className="p-4">Transaction ID / Reference</th>
                  <th className="p-4">Invoice No</th>
                  <th className="p-4">Paid Date</th>
                  <th className="p-4">Gateway</th>
                  <th className="p-4">Amount</th>
                  <th className="p-4">Remarks</th>
                  <th className="p-4">Status</th>
                </tr>
              </thead>
              <tbody>
                {filteredPayments.map((p) => (
                  <tr key={p.id} className="border-b border-slate-900 hover:bg-slate-900/10 text-slate-300">
                    <td className="p-4 font-mono">
                      <span className="font-semibold text-slate-200 block">{p.transaction_id || 'N/A'}</span>
                      <span className="text-[9px] text-slate-500 uppercase tracking-widest">{p.id.substring(0, 8)}...</span>
                    </td>
                    <td className="p-4 font-mono font-medium text-slate-400">
                      {p.invoice_number}
                    </td>
                    <td className="p-4 text-slate-500">
                      {p.paid_date ? new Date(p.paid_date).toLocaleString() : 'N/A'}
                    </td>
                    <td className="p-4 font-semibold text-brand-400">
                      {p.gateway}
                    </td>
                    <td className="p-4 font-mono font-bold text-slate-200">
                      ₹{p.amount.toFixed(2)}
                    </td>
                    <td className="p-4 max-w-xs truncate text-slate-500" title={p.remarks || ''}>
                      {p.remarks || 'Processed successfully'}
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 text-[9px] font-bold rounded uppercase border ${
                        p.status.toLowerCase() === 'paid' || p.status.toLowerCase() === 'success' || p.status.toLowerCase() === 'approved'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : p.status.toLowerCase() === 'failed'
                          ? 'bg-red-500/10 text-red-400 border-red-500/20'
                          : 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                      }`}>
                        {p.status}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
