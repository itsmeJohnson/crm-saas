import React, { useState, useEffect } from 'react';
import { portalApi, PortalInvoiceResponse } from '../../services/portalApi';
import {
  FileText, Download, CreditCard, Search, Calendar,
  AlertTriangle, Loader2, CheckCircle2, SlidersHorizontal
} from 'lucide-react';

export const PortalInvoices: React.FC = () => {
  const [invoices, setInvoices] = useState<PortalInvoiceResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);

  // Search & Filter
  const [searchQuery, setSearchQuery] = useState('');
  const [statusFilter, setStatusFilter] = useState<'all' | 'paid' | 'unpaid'>('all');

  // Checkout modal state
  const [selectedInvoice, setSelectedInvoice] = useState<PortalInvoiceResponse | null>(null);
  const [selectedGateway, setSelectedGateway] = useState('UPI');
  const [paying, setPaying] = useState(false);

  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    try {
      setLoading(true);
      const data = await portalApi.getInvoices();
      setInvoices(data);
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to load invoices.");
    } finally {
      setLoading(false);
    }
  };

  const handleDownloadPdf = async (invoiceId: string, invoiceNumber: string) => {
    try {
      const blob = await portalApi.downloadInvoicePdf(invoiceId);
      const url = window.URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `invoice_${invoiceNumber}.pdf`;
      document.body.appendChild(a);
      a.click();
      window.URL.revokeObjectURL(url);
      a.remove();
    } catch (err: any) {
      setError("Failed to download invoice PDF.");
    }
  };

  const handlePayInvoice = async () => {
    if (!selectedInvoice) return;
    try {
      setPaying(true);
      setError(null);
      setSuccess(null);

      const txnId = `TXN-INV-${Math.random().toString(36).substring(2, 14).toUpperCase()}`;
      await portalApi.payInvoice(selectedInvoice.id, {
        gateway: selectedGateway,
        transaction_id: txnId
      });

      setSuccess(`Invoice ${selectedInvoice.invoice_number} paid successfully via ${selectedGateway}! Transaction reference: ${txnId}`);
      setSelectedInvoice(null);
      fetchInvoices();
    } catch (err: any) {
      setError(err.response?.data?.detail || "Failed to process payment checkout.");
    } finally {
      setPaying(false);
    }
  };

  const filteredInvoices = invoices.filter((inv) => {
    const matchesSearch = inv.invoice_number.toLowerCase().includes(searchQuery.toLowerCase()) || 
                          (inv.plan_name && inv.plan_name.toLowerCase().includes(searchQuery.toLowerCase()));
    
    const matchesStatus = statusFilter === 'all' || 
                          (statusFilter === 'paid' && inv.payment_status.toLowerCase() === 'paid') ||
                          (statusFilter === 'unpaid' && inv.payment_status.toLowerCase() === 'unpaid');

    return matchesSearch && matchesStatus;
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
          Billing Invoices Log
        </h2>
        <p className="text-xs text-slate-400 mt-1">
          Review generated invoices, track outstanding dues, process pending payments, and archive official receipts.
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

      {/* Search and Filters */}
      <div className="flex flex-col sm:flex-row gap-4 justify-between items-stretch">
        <div className="relative flex-1">
          <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
          <input
            type="text"
            placeholder="Search by invoice number or plan name..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2.5 bg-slate-900/60 border border-slate-800 focus:border-slate-700 rounded-xl text-xs text-slate-200 focus:outline-none"
          />
        </div>

        <div className="flex gap-2">
          <div className="bg-slate-900/60 border border-slate-800 p-1 rounded-xl flex gap-1 items-center">
            <SlidersHorizontal className="w-3.5 h-3.5 text-slate-500 ml-2" />
            <span className="text-[10px] text-slate-500 font-bold uppercase tracking-wider px-1">Filter</span>
            {(['all', 'paid', 'unpaid'] as const).map((status) => (
              <button
                key={status}
                onClick={() => setStatusFilter(status)}
                className={`px-3 py-1.5 rounded-lg text-[10px] font-bold capitalize transition-all cursor-pointer ${
                  statusFilter === status
                    ? 'bg-brand-500 text-white'
                    : 'text-slate-400 hover:text-slate-200'
                }`}
              >
                {status}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Invoice Data Grid */}
      <div className="glass-panel border border-slate-900 rounded-2xl overflow-hidden">
        {filteredInvoices.length === 0 ? (
          <p className="p-8 text-slate-500 text-xs text-center">No invoices found matching criteria.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs text-left">
              <thead>
                <tr className="bg-slate-950/40 text-slate-500 border-b border-slate-900 uppercase font-bold">
                  <th className="p-4">Invoice ID</th>
                  <th className="p-4">Billing Item</th>
                  <th className="p-4">Issued At</th>
                  <th className="p-4">Due Date</th>
                  <th className="p-4">GST + setup</th>
                  <th className="p-4">Amount</th>
                  <th className="p-4">Status</th>
                  <th className="p-4 text-center">Actions</th>
                </tr>
              </thead>
              <tbody>
                {filteredInvoices.map((inv) => (
                  <tr key={inv.id} className="border-b border-slate-900 hover:bg-slate-900/10 text-slate-300">
                    <td className="p-4 font-mono font-semibold text-slate-200">
                      {inv.invoice_number}
                    </td>
                    <td className="p-4">
                      {inv.plan_name || 'Additional Seats/Storage'}
                    </td>
                    <td className="p-4 text-slate-500">
                      {new Date(inv.issue_date).toLocaleDateString()}
                    </td>
                    <td className="p-4 text-slate-500">
                      {new Date(inv.due_date).toLocaleDateString()}
                    </td>
                    <td className="p-4 font-mono text-slate-400">
                      ₹{(inv.gst_amount || 0).toFixed(2)}
                    </td>
                    <td className="p-4 font-mono font-bold text-slate-200">
                      ₹{(inv.amount || inv.total_amount || 0).toFixed(2)}
                    </td>
                    <td className="p-4">
                      <span className={`px-2 py-0.5 text-[9px] font-bold rounded uppercase border ${
                        inv.payment_status.toLowerCase() === 'paid'
                          ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                          : 'bg-rose-500/10 text-rose-400 border-rose-500/20 animate-pulse'
                      }`}>
                        {inv.payment_status}
                      </span>
                    </td>
                    <td className="p-4 flex justify-center items-center gap-2">
                      <button
                        type="button"
                        onClick={() => handleDownloadPdf(inv.id, inv.invoice_number)}
                        className="p-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 text-slate-400 hover:text-slate-200 rounded-lg transition-all"
                        title="Download PDF Invoice"
                      >
                        <Download className="w-3.5 h-3.5" />
                      </button>
                      
                      {inv.payment_status.toLowerCase() !== 'paid' && (
                        <button
                          type="button"
                          onClick={() => setSelectedInvoice(inv)}
                          className="flex items-center gap-1 px-3 py-1.5 bg-brand-500 hover:bg-brand-600 text-white rounded-lg transition-all font-bold"
                        >
                          <CreditCard className="w-3 h-3" />
                          Pay Now
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* Payment checkout modal */}
      {selectedInvoice && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-950/80 backdrop-blur-sm p-4 text-left">
          <div className="glass-panel border border-slate-800 rounded-2xl max-w-md w-full p-6 space-y-6 bg-slate-950">
            <div>
              <h3 className="text-lg font-bold text-slate-100">Simulate Payment Checkout</h3>
              <p className="text-xs text-slate-500 mt-1">
                Select your payment gateway below to process invoice {selectedInvoice.invoice_number} manually.
              </p>
            </div>

            <div className="space-y-4">
              <div className="p-4 bg-slate-900/50 rounded-xl space-y-2 text-xs">
                <div className="flex justify-between">
                  <span className="text-slate-500">Invoice Number:</span>
                  <span className="font-semibold text-slate-300">{selectedInvoice.invoice_number}</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-slate-500">GST Dues:</span>
                  <span className="font-mono text-slate-300">₹{(selectedInvoice.gst_amount || 0).toFixed(2)}</span>
                </div>
                <div className="flex justify-between border-t border-slate-800/85 pt-2 font-bold text-sm">
                  <span className="text-slate-400">Total Outstanding:</span>
                  <span className="text-slate-100">₹{(selectedInvoice.amount || selectedInvoice.total_amount || 0).toFixed(2)}</span>
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold uppercase tracking-wider text-slate-400 mb-2">Select Gateway</label>
                <select
                  value={selectedGateway}
                  onChange={(e) => setSelectedGateway(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                >
                  <option value="UPI">UPI / Instant QR</option>
                  <option value="Stripe">Stripe Checkout</option>
                  <option value="Razorpay">Razorpay Gateway</option>
                  <option value="PhonePe">PhonePe Portal</option>
                  <option value="Bank">Direct Bank Transfer</option>
                </select>
              </div>
            </div>

            <div className="flex justify-end gap-3 pt-2">
              <button
                type="button"
                onClick={() => setSelectedInvoice(null)}
                className="px-4 py-2 border border-slate-900 hover:border-slate-800 text-slate-400 hover:text-slate-200 text-xs font-bold rounded-xl"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handlePayInvoice}
                disabled={paying}
                className="flex items-center justify-center gap-1.5 px-6 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold"
              >
                {paying ? (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                ) : (
                  <>
                    <CreditCard className="w-3.5 h-3.5" />
                    Complete Payment
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
