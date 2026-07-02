import React, { useState } from 'react';
import { customerApi, LineItem } from '../../services/customerApi';
import { X, Plus, Trash2 } from 'lucide-react';

const inputCls = 'w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-brand-500/50';

const Shell: React.FC<{ title: string; onClose: () => void; onSubmit: () => void; submitting: boolean; children: React.ReactNode }> = ({ title, onClose, onSubmit, submitting, children }) => (
  <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
    <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>
    <div className="relative w-full max-w-xl bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-5 max-h-[90vh] overflow-y-auto">
      <div className="flex items-center justify-between border-b border-slate-800 pb-4">
        <h2 className="text-lg font-bold text-slate-100">{title}</h2>
        <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
      </div>
      {children}
      <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
        <button onClick={onClose} className="px-4 py-2 border border-slate-800 hover:border-slate-700 rounded-xl text-sm font-semibold text-slate-300 cursor-pointer">Cancel</button>
        <button onClick={onSubmit} disabled={submitting} className="px-5 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-xl text-sm font-semibold cursor-pointer">Save</button>
      </div>
    </div>
  </div>
);

const LineItemsEditor: React.FC<{ items: LineItem[]; setItems: (i: LineItem[]) => void }> = ({ items, setItems }) => {
  const update = (idx: number, patch: Partial<LineItem>) => setItems(items.map((it, i) => (i === idx ? { ...it, ...patch } : it)));
  const subtotal = items.reduce((s, it) => s + Number(it.quantity || 0) * Number(it.unit_price || 0), 0);
  return (
    <div className="space-y-2">
      <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Line Items</p>
      {items.map((it, idx) => (
        <div key={idx} className="flex gap-2 items-center">
          <input value={it.description} onChange={(e) => update(idx, { description: e.target.value })} placeholder="Description" className={inputCls + ' flex-1'} />
          <input type="number" min={0} value={it.quantity} onChange={(e) => update(idx, { quantity: Number(e.target.value) })} placeholder="Qty" className={inputCls + ' w-16'} />
          <input type="number" min={0} value={it.unit_price} onChange={(e) => update(idx, { unit_price: Number(e.target.value) })} placeholder="Price" className={inputCls + ' w-24'} />
          <button onClick={() => setItems(items.filter((_, i) => i !== idx))} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
        </div>
      ))}
      <button onClick={() => setItems([...items, { description: '', quantity: 1, unit_price: 0 }])} className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 cursor-pointer">
        <Plus className="w-3.5 h-3.5" /> Add line
      </button>
      <p className="text-right text-sm text-slate-300">Subtotal: <span className="font-semibold">{subtotal.toFixed(2)}</span></p>
    </div>
  );
};

export const OrderModal: React.FC<{ companyId: string; onClose: () => void; onSaved: () => void }> = ({ companyId, onClose, onSaved }) => {
  const [items, setItems] = useState<LineItem[]>([{ description: '', quantity: 1, unit_price: 0 }]);
  const [tax, setTax] = useState('0');
  const [discount, setDiscount] = useState('0');
  const [submitting, setSubmitting] = useState(false);
  const submit = async () => {
    setSubmitting(true);
    try {
      await customerApi.createOrder({ company_id: companyId, items: items.filter((i) => i.description), tax_amount: Number(tax), discount_amount: Number(discount) });
      onSaved(); onClose();
    } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } finally { setSubmitting(false); }
  };
  return (
    <Shell title="New Order" onClose={onClose} onSubmit={submit} submitting={submitting}>
      <LineItemsEditor items={items} setItems={setItems} />
      <div className="grid grid-cols-2 gap-3">
        <div><label className="text-xs text-slate-400">Tax</label><input type="number" value={tax} onChange={(e) => setTax(e.target.value)} className={inputCls} /></div>
        <div><label className="text-xs text-slate-400">Discount</label><input type="number" value={discount} onChange={(e) => setDiscount(e.target.value)} className={inputCls} /></div>
      </div>
    </Shell>
  );
};

export const InvoiceModal: React.FC<{ companyId: string; onClose: () => void; onSaved: () => void }> = ({ companyId, onClose, onSaved }) => {
  const [items, setItems] = useState<LineItem[]>([{ description: '', quantity: 1, unit_price: 0 }]);
  const [tax, setTax] = useState('0');
  const [discount, setDiscount] = useState('0');
  const [dueDate, setDueDate] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const submit = async () => {
    setSubmitting(true);
    try {
      await customerApi.createInvoice({ company_id: companyId, items: items.filter((i) => i.description), tax_amount: Number(tax), discount_amount: Number(discount), due_date: dueDate ? new Date(dueDate).toISOString() : null });
      onSaved(); onClose();
    } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } finally { setSubmitting(false); }
  };
  return (
    <Shell title="New Invoice" onClose={onClose} onSubmit={submit} submitting={submitting}>
      <LineItemsEditor items={items} setItems={setItems} />
      <div className="grid grid-cols-3 gap-3">
        <div><label className="text-xs text-slate-400">Tax</label><input type="number" value={tax} onChange={(e) => setTax(e.target.value)} className={inputCls} /></div>
        <div><label className="text-xs text-slate-400">Discount</label><input type="number" value={discount} onChange={(e) => setDiscount(e.target.value)} className={inputCls} /></div>
        <div><label className="text-xs text-slate-400">Due date</label><input type="date" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={inputCls} /></div>
      </div>
    </Shell>
  );
};

export const ContractModal: React.FC<{ companyId: string; onClose: () => void; onSaved: () => void }> = ({ companyId, onClose, onSaved }) => {
  const [title, setTitle] = useState('');
  const [status, setStatus] = useState('Active');
  const [value, setValue] = useState('');
  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [renewal, setRenewal] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const submit = async () => {
    if (!title.trim()) return;
    setSubmitting(true);
    try {
      await customerApi.createContract({ company_id: companyId, title, status, value: value ? Number(value) : null, start_date: start || null, end_date: end || null, renewal_terms: renewal || null });
      onSaved(); onClose();
    } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } finally { setSubmitting(false); }
  };
  return (
    <Shell title="New Contract" onClose={onClose} onSubmit={submit} submitting={submitting}>
      <div className="space-y-3">
        <div><label className="text-xs text-slate-400">Title</label><input value={title} onChange={(e) => setTitle(e.target.value)} className={inputCls} /></div>
        <div className="grid grid-cols-2 gap-3">
          <div><label className="text-xs text-slate-400">Status</label>
            <select value={status} onChange={(e) => setStatus(e.target.value)} className={inputCls}>
              {['Draft', 'Active', 'Expired', 'Terminated', 'Renewed'].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div><label className="text-xs text-slate-400">Value</label><input type="number" value={value} onChange={(e) => setValue(e.target.value)} className={inputCls} /></div>
          <div><label className="text-xs text-slate-400">Start</label><input type="date" value={start} onChange={(e) => setStart(e.target.value)} className={inputCls} /></div>
          <div><label className="text-xs text-slate-400">End</label><input type="date" value={end} onChange={(e) => setEnd(e.target.value)} className={inputCls} /></div>
        </div>
        <div><label className="text-xs text-slate-400">Renewal terms</label><input value={renewal} onChange={(e) => setRenewal(e.target.value)} className={inputCls} /></div>
      </div>
    </Shell>
  );
};

export const PaymentModal: React.FC<{ invoiceId: string; balanceDue: number; onClose: () => void; onSaved: () => void }> = ({ invoiceId, balanceDue, onClose, onSaved }) => {
  const [amount, setAmount] = useState(String(balanceDue || ''));
  const [method, setMethod] = useState('BankTransfer');
  const [reference, setReference] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const submit = async () => {
    if (!amount || Number(amount) <= 0) return;
    setSubmitting(true);
    try {
      await customerApi.recordPayment(invoiceId, { amount: Number(amount), method, reference: reference || undefined });
      onSaved(); onClose();
    } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } finally { setSubmitting(false); }
  };
  return (
    <Shell title="Record Payment" onClose={onClose} onSubmit={submit} submitting={submitting}>
      <div className="space-y-3">
        <div><label className="text-xs text-slate-400">Amount (balance due: {balanceDue.toFixed(2)})</label><input type="number" value={amount} onChange={(e) => setAmount(e.target.value)} className={inputCls} /></div>
        <div><label className="text-xs text-slate-400">Method</label>
          <select value={method} onChange={(e) => setMethod(e.target.value)} className={inputCls}>
            {['BankTransfer', 'Cash', 'Card', 'UPI', 'Cheque', 'Other'].map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
        </div>
        <div><label className="text-xs text-slate-400">Reference</label><input value={reference} onChange={(e) => setReference(e.target.value)} className={inputCls} /></div>
      </div>
    </Shell>
  );
};
