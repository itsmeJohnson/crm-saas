import React, { useEffect, useState } from 'react';
import { customerApi, CustomerReport } from '../services/customerApi';
import { Users, ShoppingCart, DollarSign, AlertTriangle, Loader2 } from 'lucide-react';

const currency = (n: number) => new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n || 0);

export const CustomerReportsPage: React.FC = () => {
  const [report, setReport] = useState<CustomerReport | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');

  const load = async () => {
    setIsLoading(true); setError(null);
    try {
      const params: { date_from?: string; date_to?: string } = {};
      if (dateFrom) params.date_from = new Date(dateFrom).toISOString();
      if (dateTo) params.date_to = new Date(dateTo + 'T23:59:59').toISOString();
      setReport(await customerApi.getReport(params));
    } catch (e: any) { setError(e.response?.data?.detail || 'Failed to load report'); }
    finally { setIsLoading(false); }
  };

  useEffect(() => { load(); /* eslint-disable-next-line */ }, []);

  const stats = report ? [
    { label: 'Customers', value: String(report.total_customers), icon: Users, color: 'text-brand-400' },
    { label: 'Orders', value: `${report.total_orders} · ${currency(report.total_order_value)}`, icon: ShoppingCart, color: 'text-indigo-400' },
    { label: 'Collected', value: currency(report.total_collected), icon: DollarSign, color: 'text-emerald-400' },
    { label: 'Outstanding AR', value: currency(report.outstanding_ar), icon: AlertTriangle, color: 'text-amber-400' },
  ] : [];

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">Customer Reports</h1>
          <p className="text-sm text-slate-400 mt-1">Order-to-cash: orders, invoicing, collections &amp; receivables.</p>
        </div>
        <div className="flex flex-wrap items-end gap-3">
          <div><label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">From</label><input type="date" value={dateFrom} onChange={(e) => setDateFrom(e.target.value)} className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50" /></div>
          <div><label className="block text-[10px] font-semibold text-slate-500 uppercase tracking-wider mb-1">To</label><input type="date" value={dateTo} onChange={(e) => setDateTo(e.target.value)} className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50" /></div>
          <button onClick={load} className="px-5 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-xl text-sm font-semibold cursor-pointer">Apply</button>
        </div>
      </div>

      {isLoading ? (
        <div className="flex items-center justify-center py-24 text-slate-400"><Loader2 className="w-6 h-6 animate-spin" /></div>
      ) : error ? (
        <div className="py-24 text-center text-red-400">{error}</div>
      ) : report ? (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
            {stats.map((s) => (
              <div key={s.label} className="glass-panel border border-slate-800/85 rounded-2xl p-5">
                <div className="flex items-center gap-2 mb-2"><s.icon className={`w-4 h-4 ${s.color}`} /><span className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{s.label}</span></div>
                <p className="text-xl font-bold text-slate-100">{s.value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4">Invoices by Status</h3>
              {report.invoices_by_status.length === 0 ? <p className="text-xs text-slate-500">No invoices.</p> : (
                <ul className="space-y-2">{report.invoices_by_status.map((b) => (
                  <li key={b.label} className="flex justify-between text-sm"><span className="text-slate-300">{b.label}</span><span className="text-slate-400">{b.count}</span></li>
                ))}</ul>
              )}
              <div className="mt-4 pt-3 border-t border-slate-800/60 flex justify-between text-sm">
                <span className="text-amber-300">Overdue AR</span><span className="text-amber-300 font-semibold">{currency(report.overdue_ar)}</span>
              </div>
            </div>
            <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
              <h3 className="text-sm font-semibold text-slate-200 mb-4">Top Customers by Invoiced</h3>
              {report.top_customers.length === 0 ? <p className="text-xs text-slate-500">No data.</p> : (
                <ul className="space-y-2">{report.top_customers.map((t) => (
                  <li key={t.name} className="flex justify-between text-sm"><span className="text-slate-300 truncate">{t.name}</span><span className="text-emerald-300 font-semibold shrink-0 ml-2">{currency(t.invoiced)}</span></li>
                ))}</ul>
              )}
              <div className="mt-4 pt-3 border-t border-slate-800/60 flex justify-between text-sm">
                <span className="text-slate-400">Active contracts</span><span className="text-slate-200 font-semibold">{report.active_contracts}</span>
              </div>
            </div>
          </div>
        </>
      ) : null}
    </div>
  );
};
