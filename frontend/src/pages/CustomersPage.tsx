import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  customerApi, CustomerListItem, CustomerSummary, Order, Invoice, Payment, Contract,
} from '../services/customerApi';
import { OrderModal, InvoiceModal, ContractModal, PaymentModal } from '../components/customers/CustomerModals';
import { CustomerTimeline } from '../components/customers/CustomerTimeline';
import { Search, X, Loader2, FileText, Send, Download, DollarSign, Plus } from 'lucide-react';
import { formatMoney } from '../utils/currency';

const currency = (n: number) => formatMoney(n);

const statusColor = (s: string) =>
  s === 'Paid' ? 'text-emerald-300' : s === 'Overdue' ? 'text-red-300' : s === 'PartiallyPaid' ? 'text-amber-300' : 'text-slate-300';

export const CustomersPage: React.FC = () => {
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);
  const [detailId, setDetailId] = useState<string | null>(null);
  const [searchParams, setSearchParams] = useSearchParams();

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      setCustomers(await customerApi.listCustomers(search || undefined));
    } catch { /* silent */ } finally { setIsLoading(false); }
  }, [search]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const cid = searchParams.get('companyId');
    if (cid) {
      setDetailId(cid);
      searchParams.delete('companyId');
      setSearchParams(searchParams);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">Customers</h1>
          <p className="text-sm text-slate-400 mt-1">Accounts flagged as customers, with orders, invoices, payments &amp; contracts.</p>
        </div>
      </div>

      <div className="relative w-full sm:w-96">
        <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
        <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search customers…" className="w-full pl-9 pr-3 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50" />
      </div>

      <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden">
        <table className="w-full text-left">
          <thead>
            <tr className="border-b border-slate-800/80 bg-slate-900/40 text-xs font-semibold uppercase tracking-wider text-slate-400">
              <th className="px-6 py-4">Customer</th>
              <th className="px-6 py-4">Orders</th>
              <th className="px-6 py-4">Invoiced</th>
              <th className="px-6 py-4">Outstanding</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/65">
            {isLoading ? (
              <tr><td colSpan={4} className="px-6 py-12 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></td></tr>
            ) : customers.length === 0 ? (
              <tr><td colSpan={4} className="px-6 py-12 text-center text-sm text-slate-500">No customers yet. Set a company's Type to "Customer".</td></tr>
            ) : customers.map((c) => (
              <tr key={c.company_id} onClick={() => setDetailId(c.company_id)} className="hover:bg-slate-900/30 cursor-pointer">
                <td className="px-6 py-4">
                  <p className="text-sm font-semibold text-slate-200">{c.name}</p>
                  <p className="text-xs text-slate-500">{c.industry || '—'}</p>
                </td>
                <td className="px-6 py-4 text-sm text-slate-300">{c.order_count}</td>
                <td className="px-6 py-4 text-sm text-slate-300">{currency(c.total_invoiced)}</td>
                <td className="px-6 py-4 text-sm font-semibold text-amber-300">{currency(c.outstanding_balance)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {detailId && <CustomerDetail companyId={detailId} onClose={() => { setDetailId(null); load(); }} />}
    </div>
  );
};

const CustomerDetail: React.FC<{ companyId: string; onClose: () => void }> = ({ companyId, onClose }) => {
  const [summary, setSummary] = useState<CustomerSummary | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [invoices, setInvoices] = useState<Invoice[]>([]);
  const [payments, setPayments] = useState<Payment[]>([]);
  const [contracts, setContracts] = useState<Contract[]>([]);
  const [modal, setModal] = useState<null | 'order' | 'invoice' | 'contract'>(null);
  const [payFor, setPayFor] = useState<Invoice | null>(null);

  const load = useCallback(async () => {
    const [s, o, i, p, c] = await Promise.all([
      customerApi.getSummary(companyId), customerApi.listOrders(companyId), customerApi.listInvoices(companyId),
      customerApi.listPayments(companyId), customerApi.listContracts(companyId),
    ]);
    setSummary(s); setOrders(o); setInvoices(i); setPayments(p); setContracts(c);
  }, [companyId]);

  useEffect(() => { load(); }, [load]);

  const invoiceFromOrder = async (orderId: string) => {
    try { await customerApi.createInvoiceFromOrder(orderId); await load(); }
    catch (e: any) { alert(e.response?.data?.detail || 'Failed'); }
  };
  const send = async (id: string) => { await customerApi.sendInvoice(id); await load(); };
  const downloadPdf = async (inv: Invoice) => {
    const blob = await customerApi.downloadInvoicePdf(inv.id);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = `${inv.invoice_number}.pdf`; document.body.appendChild(a); a.click(); a.remove();
    window.URL.revokeObjectURL(url);
  };

  const Stat = ({ label, value, color }: { label: string; value: string; color?: string }) => (
    <div className="p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{label}</p>
      <p className={`text-lg font-bold ${color || 'text-slate-100'}`}>{value}</p>
    </div>
  );

  return (
    <div className="fixed inset-0 z-40 overflow-hidden flex justify-end">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-xs" onClick={onClose}></div>
      <div className="relative w-full max-w-3xl bg-slate-900 border-l border-slate-800/80 shadow-2xl flex flex-col h-full z-10 animate-slide-in">
        <div className="p-6 border-b border-slate-800 flex items-center justify-between">
          <h2 className="text-xl font-bold text-slate-100">{summary?.name || 'Customer'}</h2>
          <button onClick={onClose} className="p-1.5 border border-slate-800 hover:border-slate-700 rounded-xl text-slate-400 hover:text-slate-200 cursor-pointer"><X className="w-5 h-5" /></button>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {summary && (
            <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
              <Stat label="Orders" value={String(summary.orders.count)} />
              <Stat label="Invoiced" value={currency(summary.invoices.total_invoiced)} />
              <Stat label="Collected" value={currency(summary.payments.total_collected)} color="text-emerald-300" />
              <Stat label="Outstanding" value={currency(summary.invoices.outstanding)} color="text-amber-300" />
            </div>
          )}

          {/* Unified timeline — the ONE customer timeline */}
          <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
            <CustomerTimeline companyId={companyId} />
          </div>

          {/* Orders */}
          <Section title="Orders" onAdd={() => setModal('order')}>
            {orders.length === 0 ? <Empty /> : orders.map((o) => (
              <Row key={o.id}>
                <div className="min-w-0">
                  <p className="text-sm text-slate-200">{o.order_number} <span className="text-xs text-slate-500">· {o.status}</span></p>
                  <p className="text-xs text-slate-500">{o.items.length} item(s)</p>
                </div>
                <div className="flex items-center gap-3 shrink-0">
                  <span className="text-sm text-slate-300">{currency(Number(o.total_amount))}</span>
                  <button onClick={() => invoiceFromOrder(o.id)} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">Invoice</button>
                </div>
              </Row>
            ))}
          </Section>

          {/* Invoices */}
          <Section title="Invoices" onAdd={() => setModal('invoice')}>
            {invoices.length === 0 ? <Empty /> : invoices.map((inv) => (
              <Row key={inv.id}>
                <div className="min-w-0">
                  <p className="text-sm text-slate-200 flex items-center gap-2">
                    <FileText className="w-3.5 h-3.5 text-slate-500" /> {inv.invoice_number}
                    <span className={`text-xs ${statusColor(inv.status)}`}>· {inv.status}</span>
                  </p>
                  <p className="text-xs text-slate-500">Total {currency(Number(inv.total_amount))} · Due {currency(Number(inv.balance_due))}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  {inv.status === 'Draft' && <button onClick={() => send(inv.id)} title="Send" className="p-1.5 text-slate-400 hover:text-brand-300 cursor-pointer"><Send className="w-4 h-4" /></button>}
                  <button onClick={() => downloadPdf(inv)} title="PDF" className="p-1.5 text-slate-400 hover:text-slate-200 cursor-pointer"><Download className="w-4 h-4" /></button>
                  {Number(inv.balance_due) > 0 && inv.status !== 'Void' && (
                    <button onClick={() => setPayFor(inv)} title="Record payment" className="p-1.5 text-emerald-400 hover:text-emerald-300 cursor-pointer"><DollarSign className="w-4 h-4" /></button>
                  )}
                </div>
              </Row>
            ))}
          </Section>

          {/* Payments */}
          <Section title="Payments">
            {payments.length === 0 ? <Empty /> : payments.map((p) => (
              <Row key={p.id}>
                <p className="text-sm text-slate-200">{currency(Number(p.amount))} <span className="text-xs text-slate-500">· {p.method}</span></p>
                <span className="text-xs text-slate-500">{p.paid_at ? new Date(p.paid_at).toLocaleDateString() : ''}</span>
              </Row>
            ))}
          </Section>

          {/* Contracts */}
          <Section title="Contracts" onAdd={() => setModal('contract')}>
            {contracts.length === 0 ? <Empty /> : contracts.map((c) => (
              <Row key={c.id}>
                <div className="min-w-0">
                  <p className="text-sm text-slate-200">{c.title} <span className="text-xs text-slate-500">· {c.status}</span></p>
                  <p className="text-xs text-slate-500">{c.contract_number}{c.end_date ? ` · ends ${c.end_date}` : ''}</p>
                </div>
                {c.value != null && <span className="text-sm text-slate-300 shrink-0">{currency(Number(c.value))}</span>}
              </Row>
            ))}
          </Section>
        </div>
      </div>

      {modal === 'order' && <OrderModal companyId={companyId} onClose={() => setModal(null)} onSaved={load} />}
      {modal === 'invoice' && <InvoiceModal companyId={companyId} onClose={() => setModal(null)} onSaved={load} />}
      {modal === 'contract' && <ContractModal companyId={companyId} onClose={() => setModal(null)} onSaved={load} />}
      {payFor && <PaymentModal invoiceId={payFor.id} balanceDue={Number(payFor.balance_due)} onClose={() => setPayFor(null)} onSaved={load} />}
    </div>
  );
};

const Section: React.FC<{ title: string; onAdd?: () => void; children: React.ReactNode }> = ({ title, onAdd, children }) => (
  <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
    <div className="flex items-center justify-between mb-3">
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      {onAdd && <button onClick={onAdd} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 cursor-pointer"><Plus className="w-3.5 h-3.5" /> New</button>}
    </div>
    <div className="space-y-2">{children}</div>
  </div>
);

const Row: React.FC<{ children: React.ReactNode }> = ({ children }) => (
  <div className="flex items-center justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">{children}</div>
);

const Empty: React.FC = () => <p className="text-xs text-slate-500">Nothing yet.</p>;
