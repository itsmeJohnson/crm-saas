import React, { useCallback, useEffect, useState } from 'react';
import {
  DollarSign, Loader2, Download, TrendingUp, Wallet, Receipt, Repeat, Landmark, PiggyBank,
  Plus, Trash2,
} from 'lucide-react';
import {
  financialAnalyticsApi as api, FinOverview, Recurring, Collections, Outstanding, InvoicesReport,
  PaymentsReport, ExpensesReport, Profitability, Taxes, Forecast, FinTrend, ExpenseRecord, EXPENSE_CATEGORIES,
} from '../services/financialAnalyticsApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const cur = (n: any) => (typeof n === 'number' ? `₹${Math.round(n).toLocaleString()}` : '—');

const Tile: React.FC<{ label: string; value: React.ReactNode; tone?: string }> = ({ label, value, tone }) => (
  <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{label}</p><p className={`text-xl font-bold mt-1 ${tone || 'text-slate-100'}`}>{value}</p></div>
);
const Bars: React.FC<{ data: [string, number][]; empty?: string }> = ({ data, empty }) => {
  const max = Math.max(1, ...data.map(([, v]) => v));
  if (!data.length) return <p className="text-xs text-slate-500">{empty || 'No data.'}</p>;
  return (
    <div className="space-y-1.5">{data.map(([k, v]) => (
      <div key={k} className="flex items-center gap-2">
        <span className="text-[11px] text-slate-400 w-32 truncate">{k}</span>
        <div className="flex-1 h-2.5 bg-slate-800/60 rounded"><div className="h-2.5 rounded bg-brand-500/70" style={{ width: `${(v / max) * 100}%` }} /></div>
        <span className="text-[11px] text-slate-300 w-20 text-right">{cur(v)}</span>
      </div>
    ))}</div>
  );
};

type Tab = 'overview' | 'revenue' | 'ar' | 'billing' | 'recurring' | 'tax' | 'expenses';

export const FinancialAnalyticsPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('overview');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [granularity, setGranularity] = useState('monthly');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const [ov, setOv] = useState<FinOverview | null>(null);
  const [rev, setRev] = useState<any | null>(null);
  const [prof, setProf] = useState<Profitability | null>(null);
  const [trend, setTrend] = useState<FinTrend | null>(null);
  const [col, setCol] = useState<Collections | null>(null);
  const [out, setOut] = useState<Outstanding | null>(null);
  const [inv, setInv] = useState<InvoicesReport | null>(null);
  const [pay, setPay] = useState<PaymentsReport | null>(null);
  const [rec, setRec] = useState<Recurring | null>(null);
  const [tax, setTax] = useState<Taxes | null>(null);
  const [fc, setFc] = useState<Forecast | null>(null);
  const [exp, setExp] = useState<ExpensesReport | null>(null);
  const [expRecords, setExpRecords] = useState<ExpenseRecord[]>([]);

  const range = () => ({ date_from: from || undefined, date_to: to || undefined });
  const load = useCallback(async () => {
    setLoading(true); setErr('');
    const p = { date_from: from || undefined, date_to: to || undefined };
    try {
      if (tab === 'overview') { setOv(await api.overview(p)); setTrend(await api.trend({ ...p, granularity })); }
      else if (tab === 'revenue') { setRev(await api.revenue(p)); setProf(await api.profitability(p)); }
      else if (tab === 'ar') { setCol(await api.collections(p)); setOut(await api.outstanding()); }
      else if (tab === 'billing') { setInv(await api.invoices(p)); setPay(await api.payments(p)); }
      else if (tab === 'recurring') setRec(await api.recurring(p));
      else if (tab === 'tax') { setTax(await api.taxes(p)); setFc(await api.forecast(p)); }
      else if (tab === 'expenses') { setExp(await api.expenses(p)); setExpRecords(await api.listExpenses(p)); }
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load financial analytics.')); } finally { setLoading(false); }
  }, [tab, from, to, granularity]);
  useEffect(() => { load(); }, [load]);

  const exportCsv = async () => {
    try { const b = await api.exportCsv(range()); const u = URL.createObjectURL(b); const a = document.createElement('a'); a.href = u; a.download = 'financial-analytics.csv'; a.click(); URL.revokeObjectURL(u); }
    catch (e) { setErr(extractErrorMessage(e, 'Export failed.')); }
  };

  const TABS: [Tab, string, any][] = [
    ['overview', 'Overview', DollarSign], ['revenue', 'Revenue & Profit', TrendingUp], ['ar', 'Collections & AR', Wallet],
    ['billing', 'Invoices & Payments', Receipt], ['recurring', 'Recurring (MRR/LTV)', Repeat],
    ['tax', 'Taxes & Forecast', Landmark], ['expenses', 'Expenses', PiggyBank],
  ];

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><DollarSign className="w-6 h-6 text-brand-400" /> Financial Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">Revenue, expenses, profitability, collections, recurring revenue, taxes and forecast.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={F} />
          <span className="text-slate-600 text-xs">→</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={F} />
          <button onClick={exportCsv} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Export</button>
        </div>
      </div>

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {TABS.map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {label}</button>
        ))}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'overview' && ov ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tile label="Revenue (billed)" value={cur(ov.revenue_billed)} tone="text-emerald-400" />
            <Tile label="Collected" value={cur(ov.revenue_collected)} />
            <Tile label="Expenses" value={cur(ov.expenses)} tone={ov.expenses ? 'text-red-400' : undefined} />
            <Tile label="Gross profit" value={cur(ov.gross_profit)} tone={ov.gross_profit >= 0 ? 'text-emerald-400' : 'text-red-400'} />
            <Tile label="Margin" value={`${ov.profit_margin}%`} />
            <Tile label="Outstanding" value={cur(ov.outstanding)} tone={ov.overdue ? 'text-amber-400' : undefined} />
            <Tile label="MRR / ARR" value={`${cur(ov.mrr)} / ${cur(ov.arr)}`} tone="text-brand-300" />
            <Tile label="Tax collected" value={cur(ov.tax_collected)} />
          </div>
          {trend && (
            <div className={`${card} overflow-x-auto`}>
              <div className="flex items-center justify-between mb-2"><p className="text-xs font-semibold text-slate-400">Trend</p>
                <select value={granularity} onChange={(e) => setGranularity(e.target.value)} className={F}>{['daily', 'weekly', 'monthly'].map((g) => <option key={g} value={g}>{g}</option>)}</select></div>
              <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Period</th><th className="text-right px-2">Revenue</th><th className="text-right px-2">Collected</th><th className="text-right px-2">Expenses</th><th className="text-right px-2">Profit</th></tr></thead>
                <tbody>
                  {trend.series.length === 0 && <tr><td colSpan={5} className="py-4 text-center text-slate-500">No activity.</td></tr>}
                  {trend.series.map((b) => <tr key={b.bucket} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{b.bucket}</td><td className="text-right px-2">{cur(b.revenue)}</td><td className="text-right px-2">{cur(b.collected)}</td><td className="text-right px-2 text-red-400">{cur(b.expenses)}</td><td className={`text-right px-2 ${b.profit >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>{cur(b.profit)}</td></tr>)}
                </tbody>
              </table>
            </div>
          )}
        </div>
      ) : tab === 'revenue' && rev && prof ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tile label="Revenue" value={cur(prof.revenue)} tone="text-emerald-400" />
            <Tile label="Expenses" value={cur(prof.expenses)} />
            <Tile label="Gross profit" value={cur(prof.gross_profit)} tone={prof.gross_profit >= 0 ? 'text-emerald-400' : 'text-red-400'} />
            <Tile label="Margin" value={`${prof.profit_margin}%`} />
            <Tile label="Cash profit" value={cur(prof.cash_profit)} />
            <Tile label="Invoices" value={rev.invoice_count} />
            <Tile label="Avg invoice" value={cur(rev.avg_invoice)} />
          </div>
          <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">Top customers by revenue</p>
            <Bars data={(rev.top_customers || []).map((c: any) => [c.company, c.revenue])} empty="No customer revenue." /></div>
        </div>
      ) : tab === 'ar' && col && out ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tile label="Collected" value={cur(col.collected)} tone="text-emerald-400" />
            <Tile label="Collection rate" value={`${col.collection_rate}%`} />
            <Tile label="Outstanding" value={cur(out.outstanding)} />
            <Tile label="Overdue" value={cur(out.overdue)} tone={out.overdue ? 'text-red-400' : undefined} />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">Collections by method</p><Bars data={col.by_method.map((m) => [m.method, m.amount])} /></div>
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">AR aging</p><Bars data={out.aging.map((a) => [a.bucket, a.amount])} /></div>
          </div>
        </div>
      ) : tab === 'billing' && inv && pay ? (
        <div className="grid md:grid-cols-2 gap-4">
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-2">Invoices · {inv.count} · {cur(inv.total)}</p>
            <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Status</th><th className="text-right">Count</th><th className="text-right">Amount</th></tr></thead>
              <tbody>{inv.by_status.map((s) => <tr key={s.status} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{s.status}</td><td className="text-right">{s.count}</td><td className="text-right">{cur(s.amount)}</td></tr>)}</tbody></table>
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-2">Payments · {pay.count} · {cur(pay.total)}</p>
            <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Method</th><th className="text-right">Count</th><th className="text-right">Amount</th></tr></thead>
              <tbody>{pay.by_method.map((s) => <tr key={s.method} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{s.method}</td><td className="text-right">{s.count}</td><td className="text-right">{cur(s.amount)}</td></tr>)}</tbody></table>
          </div>
        </div>
      ) : tab === 'recurring' && rec ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile label="Subscription rev (MRR)" value={cur(rec.mrr)} tone="text-brand-300" />
          <Tile label="ARR" value={cur(rec.arr)} tone="text-brand-300" />
          <Tile label="Active contracts" value={rec.active_contracts} />
          <Tile label="ARPA" value={cur(rec.arpa)} />
          <Tile label="Churn rate" value={`${rec.churn_rate}%`} tone={rec.churn_rate > 0 ? 'text-red-400' : 'text-emerald-400'} />
          <Tile label="LTV" value={cur(rec.ltv)} tone="text-emerald-400" />
          <Tile label="CAC" value={cur(rec.cac)} />
          <Tile label="LTV : CAC" value={rec.ltv_cac_ratio ? `${rec.ltv_cac_ratio}×` : '—'} tone={rec.ltv_cac_ratio >= 3 ? 'text-emerald-400' : undefined} />
        </div>
      ) : tab === 'tax' && tax && fc ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile label="Tax collected" value={cur(tax.tax_collected)} />
          <Tile label="Taxable base" value={cur(tax.taxable_base)} />
          <Tile label="Effective rate" value={`${tax.effective_rate}%`} />
          <Tile label="Invoices" value={tax.invoice_count} />
          <Tile label="Monthly run-rate" value={cur(fc.monthly_run_rate)} />
          <Tile label="MRR" value={cur(fc.mrr)} tone="text-brand-300" />
          <Tile label="Expected AR" value={cur(fc.expected_ar_collection)} />
          <Tile label="Projected next month" value={cur(fc.projected_next_month)} tone="text-emerald-400" />
        </div>
      ) : tab === 'expenses' && exp ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Tile label="Total expenses" value={cur(exp.total)} tone="text-red-400" />
            <Tile label="Records" value={exp.count} />
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            <div className={card}><p className="text-xs font-semibold text-slate-400 mb-2">By category</p><Bars data={exp.by_category.map((c) => [c.category, c.amount])} empty="No expenses recorded." /></div>
            <ExpenseManager records={expRecords} onChanged={load} setErr={setErr} />
          </div>
        </div>
      ) : null}
    </div>
  );
};

const ExpenseManager: React.FC<{ records: ExpenseRecord[]; onChanged: () => void; setErr: (s: string) => void }> = ({ records, onChanged, setErr }) => {
  const [category, setCategory] = useState('General');
  const [amount, setAmount] = useState('');
  const [vendor, setVendor] = useState('');
  const [busy, setBusy] = useState(false);
  const add = async () => {
    if (!amount || Number(amount) <= 0) { setErr('Enter a positive amount'); return; }
    setBusy(true);
    try { await api.createExpense({ category, amount: Number(amount), vendor: vendor || undefined }); setAmount(''); setVendor(''); onChanged(); }
    catch (e) { setErr(extractErrorMessage(e, 'Failed to add expense')); } finally { setBusy(false); }
  };
  return (
    <div className={card}>
      <p className="text-xs font-semibold text-slate-400 mb-2">Record expense</p>
      <div className="flex items-center gap-1.5 mb-3">
        <select value={category} onChange={(e) => setCategory(e.target.value)} className={F}>{EXPENSE_CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}</select>
        <input value={amount} onChange={(e) => setAmount(e.target.value)} type="number" placeholder="amount" className={`${F} w-24`} />
        <input value={vendor} onChange={(e) => setVendor(e.target.value)} placeholder="vendor" className={`${F} flex-1`} />
        <button onClick={add} disabled={busy} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1"><Plus className="w-3.5 h-3.5" /> Add</button>
      </div>
      <div className="space-y-1 max-h-64 overflow-y-auto">
        {records.length === 0 && <p className="text-[11px] text-slate-600">No expense records.</p>}
        {records.map((r) => (
          <div key={r.id} className="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-slate-950/40 border border-slate-800/60">
            <span className="text-slate-300">{cur(r.amount)} <span className="text-slate-600">· {r.category}{r.vendor ? ` · ${r.vendor}` : ''} · {r.incurred_at}</span></span>
            <button onClick={async () => { await api.deleteExpense(r.id); onChanged(); }} className="text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
          </div>
        ))}
      </div>
    </div>
  );
};
