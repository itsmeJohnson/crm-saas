import React, { useState, useEffect, useMemo } from 'react';
import { X, FileText, Plus, Trash2, Loader2 } from 'lucide-react';
import { api } from '../../services/api';

interface Props {
  isOpen: boolean;
  onClose: () => void;
  onSuccess?: () => void;
}
interface LineItem { description: string; quantity: number; unit_price: number; }

export const CreateInvoiceModal: React.FC<Props> = ({ isOpen, onClose, onSuccess }) => {
  const [patients, setPatients] = useState<any[]>([]);
  const [contactId, setContactId] = useState('');
  const [items, setItems] = useState<LineItem[]>([{ description: '', quantity: 1, unit_price: 0 }]);
  const [discount, setDiscount] = useState(0);
  const [taxPercent, setTaxPercent] = useState(0);
  const [notes, setNotes] = useState('');
  const [sym, setSym] = useState('₹');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!isOpen) return;
    (async () => {
      try {
        const [p, s] = await Promise.all([
          api.get('/contacts/', { params: { limit: 100 } }),
          api.get('/customers/invoice-settings'),
        ]);
        setPatients(p.data || []);
        setTaxPercent(Number(s.data?.default_tax_percent || 0));
        setSym(s.data?.currency_symbol || '₹');
      } catch { /* settings/patients optional */ }
    })();
  }, [isOpen]);

  const subtotal = useMemo(
    () => items.reduce((sum, it) => sum + (Number(it.quantity) || 0) * (Number(it.unit_price) || 0), 0),
    [items]);
  const taxable = Math.max(0, subtotal - (Number(discount) || 0));
  const taxAmount = +(taxable * (Number(taxPercent) || 0) / 100).toFixed(2);
  const total = +(taxable + taxAmount).toFixed(2);

  if (!isOpen) return null;

  const setItem = (i: number, patch: Partial<LineItem>) =>
    setItems((prev) => prev.map((it, idx) => (idx === i ? { ...it, ...patch } : it)));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!contactId) { setError('Select a patient.'); return; }
    const clean = items.filter((it) => it.description.trim() && Number(it.unit_price) >= 0);
    if (clean.length === 0) { setError('Add at least one line item.'); return; }
    setSubmitting(true); setError('');
    try {
      await api.post('/customers/invoices', {
        contact_id: contactId,
        items: clean.map((it) => ({ description: it.description.trim(), quantity: Number(it.quantity) || 1, unit_price: Number(it.unit_price) || 0 })),
        discount_amount: Number(discount) || 0,
        tax_amount: taxAmount,
        notes: notes.trim() || null,
      });
      onSuccess?.();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not create the invoice.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        <div className="p-5 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-cyan-500/15 border border-cyan-500/25 flex items-center justify-center text-cyan-400">
              <FileText className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-100">Create Invoice</h3>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300"><X className="w-5 h-5" /></button>
        </div>

        <form onSubmit={submit} className="p-5 space-y-4 overflow-y-auto">
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Patient</label>
            <select value={contactId} onChange={(e) => setContactId(e.target.value)} className="neo-input w-full px-3.5 py-2.5 text-xs">
              <option value="">Select a patient…</option>
              {patients.map((p) => (
                <option key={p.id} value={p.id}>{p.first_name} {p.last_name}{p.phone ? ` · ${p.phone}` : ''}</option>
              ))}
            </select>
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label className="text-[11px] font-bold uppercase tracking-wider text-slate-400">Treatments / line items</label>
              <button type="button" onClick={() => setItems((p) => [...p, { description: '', quantity: 1, unit_price: 0 }])}
                      className="neo-btn px-2 py-1 text-[11px] text-cyan-400 flex items-center gap-1"><Plus className="w-3.5 h-3.5" /> Add</button>
            </div>
            <div className="space-y-2">
              {items.map((it, i) => (
                <div key={i} className="flex items-center gap-2">
                  <input value={it.description} onChange={(e) => setItem(i, { description: e.target.value })}
                         placeholder="e.g. Root Canal Therapy" className="neo-input flex-1 px-3 py-2 text-xs" />
                  <input type="number" min={0} value={it.quantity} onChange={(e) => setItem(i, { quantity: Number(e.target.value) })}
                         className="neo-input w-14 px-2 py-2 text-xs text-center" title="Qty" />
                  <input type="number" min={0} value={it.unit_price} onChange={(e) => setItem(i, { unit_price: Number(e.target.value) })}
                         placeholder="Price" className="neo-input w-24 px-2 py-2 text-xs text-right" />
                  <button type="button" onClick={() => setItems((p) => p.filter((_, idx) => idx !== i))}
                          className="text-slate-500 hover:text-rose-400 flex-shrink-0" disabled={items.length === 1}>
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>
              ))}
            </div>
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Discount ({sym})</label>
              <input type="number" min={0} value={discount} onChange={(e) => setDiscount(Number(e.target.value))} className="neo-input w-full px-3 py-2 text-xs" />
            </div>
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Tax (%)</label>
              <input type="number" min={0} max={100} value={taxPercent} onChange={(e) => setTaxPercent(Number(e.target.value))} className="neo-input w-full px-3 py-2 text-xs" />
            </div>
          </div>

          {/* live totals */}
          <div className="bento-card p-3 text-xs space-y-1">
            <div className="flex justify-between text-slate-400"><span>Subtotal</span><span>{sym}{subtotal.toFixed(2)}</span></div>
            <div className="flex justify-between text-slate-400"><span>Discount</span><span>-{sym}{(Number(discount) || 0).toFixed(2)}</span></div>
            <div className="flex justify-between text-slate-400"><span>Tax</span><span>{sym}{taxAmount.toFixed(2)}</span></div>
            <div className="flex justify-between text-slate-100 font-bold pt-1 border-t border-slate-800"><span>Total</span><span>{sym}{total.toFixed(2)}</span></div>
          </div>

          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Notes <span className="text-slate-600 normal-case font-normal">(optional)</span></label>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Shown on the invoice" className="neo-input w-full px-3 py-2 text-xs" />
          </div>

          {error && <p className="text-xs text-rose-400">{error}</p>}

          <div className="flex items-center gap-2 pt-1">
            <button type="button" onClick={onClose} className="neo-btn px-4 py-2.5 text-xs text-slate-300 flex-1">Cancel</button>
            <button type="submit" disabled={submitting} className="neo-btn-primary px-4 py-2.5 text-xs flex-1 flex items-center justify-center gap-2">
              {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating…</> : 'Create Invoice'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
