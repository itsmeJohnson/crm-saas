import React, { useState, useEffect } from 'react';
import {
  Receipt, Search, RefreshCw, Plus, Download, MessageCircle
} from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { api } from '../../services/api';
import { RecordPaymentModal } from '../../components/dental/RecordPaymentModal';
import { CreateInvoiceModal } from '../../components/dental/CreateInvoiceModal';


export const BillingPage: React.FC = () => {
  const [invoices, setInvoices] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [statusFilter, setStatusFilter] = useState('All');
  const [isLoading, setIsLoading] = useState(true);

  // Modals
  const [selectedInvoice, setSelectedInvoice] = useState<any | null>(null);
  const [isPaymentOpen, setIsPaymentOpen] = useState(false);
  const [isCreateOpen, setIsCreateOpen] = useState(false);

  const sendWhatsApp = async (inv: any) => {
    try {
      const res = await api.get(`/customers/invoices/${inv.id}/whatsapp-share`);
      const { phone, pdf_url, invoice_number } = res.data || {};
      const msg = `Hello, here is your invoice ${invoice_number || ''} from our clinic.\nView / download it here: ${pdf_url}`;
      const wa = phone
        ? `https://wa.me/${phone}?text=${encodeURIComponent(msg)}`
        : `https://wa.me/?text=${encodeURIComponent(msg)}`;
      window.open(wa, '_blank');
    } catch (e) {
      alert('Could not prepare the WhatsApp message for this invoice.');
    }
  };

  const downloadPdf = async (inv: any) => {
    try {
      const res = await api.get(`/customers/invoices/${inv.id}/pdf`, { responseType: 'blob' });
      const url = window.URL.createObjectURL(new Blob([res.data], { type: 'application/pdf' }));
      const a = document.createElement('a');
      a.href = url;
      a.download = `${inv.invoice_number || 'invoice'}.pdf`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      window.URL.revokeObjectURL(url);
    } catch (e) {
      alert('Could not download the invoice PDF.');
    }
  };


  useEffect(() => {
    fetchInvoices();
  }, []);

  const fetchInvoices = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/customers/invoices');
      setInvoices(res.data || []);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredInvoices = invoices.filter((inv) => {
    const invNum = (inv.invoice_number || '').toLowerCase();
    const desc = (inv.items?.[0]?.description || '').toLowerCase();
    const matchesSearch = invNum.includes(search.toLowerCase()) || desc.includes(search.toLowerCase());
    const matchesStatus = statusFilter === 'All' || inv.status === statusFilter;
    return matchesSearch && matchesStatus;
  });

  const totalInvoiced = invoices.reduce((acc, i) => acc + Number(i.total_amount || 0), 0);
  const totalCollected = invoices.reduce((acc, i) => acc + Number(i.amount_paid || 0), 0);
  const totalOutstanding = Math.max(0, totalInvoiced - totalCollected);
  const realizationRate = totalInvoiced ? Math.round((totalCollected / totalInvoiced) * 100) : 0;

  const statuses = ['All', 'Paid', 'PartiallyPaid', 'Sent', 'Overdue'];

  return (
    <div className="space-y-6 select-none">
      {/* Header Bento */}
      <div className="bento-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-emerald-400 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-emerald-500/25 flex-shrink-0">
            <Receipt className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-100">
              Patient Invoicing, Billing &amp; Receipts
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Procedure invoices, point-of-sale collections &amp; accounts receivable tracking.
            </p>
          </div>
        </div>

        <div className="flex items-center gap-2.5">
          <button
            onClick={() => setIsCreateOpen(true)}
            className="neo-btn-primary px-4 py-2.5 text-xs flex items-center gap-2"
          >
            <Plus className="w-4 h-4" />
            Create Invoice
          </button>
        </div>
      </div>

      {/* Financial Summary Bento Tiles */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <div className="bento-card p-5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Total Billed</span>
          <div className="text-2xl font-black text-slate-100 mt-1">{formatMoney(totalInvoiced)}</div>
          <span className="text-[10px] text-cyan-400 font-semibold mt-1 inline-block">{invoices.length} Clinical Invoices</span>
        </div>

        <div className="bento-card p-5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Collections Cleared</span>
          <div className="text-2xl font-black text-emerald-400 mt-1">{formatMoney(totalCollected)}</div>
          <span className="text-[10px] text-emerald-400 font-semibold mt-1 inline-block">{realizationRate}% Realization Rate</span>
        </div>

        <div className="bento-card p-5">
          <span className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Accounts Receivable</span>
          <div className="text-2xl font-black text-rose-400 mt-1">{formatMoney(totalOutstanding)}</div>
          <span className="text-[10px] text-rose-400 font-semibold mt-1 inline-block">Pending Follow-up</span>
        </div>
      </div>

      {/* Filters Bar Bento */}
      <div className="bento-card p-5 space-y-4">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search by invoice number, procedure description..."
            className="neo-input w-full pr-4 py-2.5 text-xs"
            style={{ paddingLeft: '2.4rem' }}
          />
        </div>

        <div className="flex items-center gap-2 overflow-x-auto pt-1">
          {statuses.map((st) => (
            <button
              key={st}
              onClick={() => setStatusFilter(st)}
              className={`px-3.5 py-1.5 rounded-xl text-xs font-bold whitespace-nowrap transition cursor-pointer ${
                statusFilter === st
                  ? 'neo-btn-primary'
                  : 'neo-btn text-slate-400 hover:text-slate-200'
              }`}
            >
              {st}
            </button>
          ))}
        </div>
      </div>

      {/* Invoices Table Bento */}
      <div className="bento-card p-0 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-[var(--bg-inset)] border-b border-slate-800/40 text-slate-400 uppercase tracking-wider font-bold text-[10px]">
                <th className="px-6 py-4">Invoice #</th>
                <th className="px-4 py-4">Procedure Description</th>
                <th className="px-4 py-4">Date Issued</th>
                <th className="px-4 py-4">Total Amount</th>
                <th className="px-4 py-4">Paid</th>
                <th className="px-4 py-4">Balance Due</th>
                <th className="px-4 py-4">Status</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/30">
              {isLoading ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    <RefreshCw className="w-5 h-5 animate-spin mx-auto text-cyan-400 mb-2" />
                    Loading clinical invoices...
                  </td>
                </tr>
              ) : filteredInvoices.length === 0 ? (
                <tr>
                  <td colSpan={8} className="p-8 text-center text-slate-400">
                    No matching invoices found.
                  </td>
                </tr>
              ) : (
                filteredInvoices.map((inv) => {
                  const item = inv.items?.[0] || {};
                  const total = Number(inv.total_amount || 0);
                  const paid = Number(inv.amount_paid || 0);
                  const balance = Math.max(0, total - paid);

                  return (
                    <tr
                      key={inv.id}
                      className="hover:bg-[var(--bg-card-hover)] transition-colors group"
                    >
                      <td className="px-6 py-4 font-mono font-bold text-slate-200">
                        {inv.invoice_number}
                      </td>
                      <td className="px-4 py-4 font-bold text-slate-100">
                        {item.description || 'Clinical Procedure Fee'}
                      </td>
                      <td className="px-4 py-4 text-slate-400">
                        {inv.issue_date ? new Date(inv.issue_date).toLocaleDateString('en-IN') : '08 Aug 2026'}
                      </td>
                      <td className="px-4 py-4 font-extrabold text-slate-100">
                        {formatMoney(total)}
                      </td>
                      <td className="px-4 py-4 font-bold text-emerald-400">
                        {formatMoney(paid)}
                      </td>
                      <td className="px-4 py-4 font-bold text-rose-400">
                        {balance > 0 ? formatMoney(balance) : '₹0'}
                      </td>
                      <td className="px-4 py-4">
                        <span className={`neo-pill text-[10px] ${
                          inv.status === 'Paid'
                            ? 'text-emerald-400 bg-emerald-500/10 border-emerald-500/20'
                            : inv.status === 'PartiallyPaid'
                            ? 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                            : 'text-rose-400 bg-rose-500/10 border-rose-500/20'
                        }`}>
                          {inv.status}
                        </span>
                      </td>
                      <td className="px-6 py-4 text-right">
                        <div className="flex items-center justify-end gap-1.5">
                          <button
                            onClick={() => downloadPdf(inv)}
                            title="Download PDF"
                            className="neo-btn px-2.5 py-1 text-xs text-slate-300 hover:text-slate-100 flex items-center gap-1"
                          >
                            <Download className="w-3.5 h-3.5" /> PDF
                          </button>
                          <button
                            onClick={() => sendWhatsApp(inv)}
                            title="Send on WhatsApp"
                            className="neo-btn px-2.5 py-1 text-xs text-emerald-400 hover:text-emerald-300 flex items-center gap-1"
                          >
                            <MessageCircle className="w-3.5 h-3.5" /> WhatsApp
                          </button>
                          <button
                            onClick={() => {
                              setSelectedInvoice(inv);
                              setIsPaymentOpen(true);
                            }}
                            className="neo-btn px-2.5 py-1 text-xs text-cyan-400 hover:text-cyan-300 font-bold"
                          >
                            Record Payment
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Invoice Modal */}
      <CreateInvoiceModal
        isOpen={isCreateOpen}
        onClose={() => setIsCreateOpen(false)}
        onSuccess={() => {
          setIsCreateOpen(false);
          fetchInvoices();
        }}
      />

      {/* Record Payment Modal */}
      <RecordPaymentModal
        invoice={selectedInvoice}
        isOpen={isPaymentOpen}
        onClose={() => {
          setIsPaymentOpen(false);
          setSelectedInvoice(null);
        }}
        onSuccess={() => {
          setIsPaymentOpen(false);
          fetchInvoices();
        }}
      />
    </div>
  );
};

export default BillingPage;
