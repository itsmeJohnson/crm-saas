import React, { useState, useEffect } from 'react';
import { Settings2, Save, Loader2, CheckCircle2 } from 'lucide-react';
import { api } from '../../services/api';

type S = Record<string, any>;

const Field: React.FC<{ label: string; children: React.ReactNode; hint?: string }> = ({ label, children, hint }) => (
  <div>
    <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">{label}</label>
    {children}
    {hint && <p className="text-[11px] text-slate-500 mt-1">{hint}</p>}
  </div>
);

export const InvoiceSettingsPage: React.FC = () => {
  const [s, setS] = useState<S>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => { (async () => {
    try { const r = await api.get('/customers/invoice-settings'); setS(r.data || {}); }
    catch { setError('Could not load invoice settings.'); }
    finally { setLoading(false); }
  })(); }, []);

  const set = (k: string, v: any) => { setS((p) => ({ ...p, [k]: v })); setSaved(false); };
  const inp = (k: string, extra = '') => (
    <input value={s[k] ?? ''} onChange={(e) => set(k, e.target.value)} className={`neo-input w-full px-3.5 py-2.5 text-xs ${extra}`} />
  );

  const save = async () => {
    setSaving(true); setError('');
    try {
      const payload = {
        legal_name: s.legal_name, address: s.address, phone: s.phone, email: s.email, website: s.website, logo_url: s.logo_url,
        gst_number: s.gst_number, pan: s.pan, tax_label: s.tax_label, default_tax_percent: Number(s.default_tax_percent) || 0,
        currency: s.currency, currency_symbol: s.currency_symbol,
        invoice_prefix: s.invoice_prefix, next_invoice_number: Number(s.next_invoice_number) || 1, number_padding: Number(s.number_padding) || 0,
        bank_name: s.bank_name, account_holder: s.account_holder, account_number: s.account_number, ifsc: s.ifsc, upi_id: s.upi_id,
        payment_terms: s.payment_terms, footer_text: s.footer_text, default_notes: s.default_notes,
      };
      const r = await api.put('/customers/invoice-settings', payload);
      setS(r.data); setSaved(true);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not save settings.');
    } finally { setSaving(false); }
  };

  if (loading) return (
    <div className="bento-card p-10 flex items-center justify-center text-slate-400 text-sm">
      <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading invoice settings…
    </div>
  );

  return (
    <div className="space-y-6 select-none max-w-3xl">
      <div className="bento-card p-6 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-cyan-400 to-blue-500 flex items-center justify-center text-white shadow-lg shadow-cyan-500/25 flex-shrink-0">
            <Settings2 className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-100">Invoice Settings</h1>
            <p className="text-xs text-slate-400 mt-0.5">Branding, tax, currency &amp; numbering applied to every invoice you issue.</p>
          </div>
        </div>
        <button onClick={save} disabled={saving} className="neo-btn-primary px-4 py-2.5 text-xs flex items-center gap-2">
          {saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving…</> : saved ? <><CheckCircle2 className="w-4 h-4" /> Saved</> : <><Save className="w-4 h-4" /> Save</>}
        </button>
      </div>

      {error && <div className="bento-card p-4 text-xs text-rose-400">{error}</div>}

      <div className="bento-card p-6 space-y-4">
        <h2 className="text-sm font-bold text-slate-100">Clinic identity</h2>
        <Field label="Legal / clinic name">{inp('legal_name')}</Field>
        <Field label="Address">
          <textarea value={s.address ?? ''} onChange={(e) => set('address', e.target.value)} rows={2} className="neo-input w-full px-3.5 py-2.5 text-xs" />
        </Field>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
          <Field label="Phone">{inp('phone')}</Field>
          <Field label="Email">{inp('email')}</Field>
          <Field label="Website">{inp('website')}</Field>
        </div>
        <Field label="Logo URL" hint="Paste an image URL (or a data: URI) to print on invoices.">{inp('logo_url')}</Field>
      </div>

      <div className="bento-card p-6 space-y-4">
        <h2 className="text-sm font-bold text-slate-100">Tax &amp; currency</h2>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          <Field label="GST number">{inp('gst_number')}</Field>
          <Field label="PAN">{inp('pan')}</Field>
          <Field label="Tax label" hint="e.g. GST, VAT">{inp('tax_label')}</Field>
          <Field label="Default tax %">
            <input type="number" min={0} max={100} value={s.default_tax_percent ?? 0} onChange={(e) => set('default_tax_percent', e.target.value)} className="neo-input w-full px-3.5 py-2.5 text-xs" />
          </Field>
        </div>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Currency code" hint="e.g. INR, USD">{inp('currency')}</Field>
          <Field label="Currency symbol">{inp('currency_symbol')}</Field>
        </div>
      </div>

      <div className="bento-card p-6 space-y-4">
        <h2 className="text-sm font-bold text-slate-100">Invoice numbering</h2>
        <div className="grid grid-cols-3 gap-3">
          <Field label="Prefix" hint="e.g. SC-">{inp('invoice_prefix')}</Field>
          <Field label="Next number">
            <input type="number" min={1} value={s.next_invoice_number ?? 1} onChange={(e) => set('next_invoice_number', e.target.value)} className="neo-input w-full px-3.5 py-2.5 text-xs" />
          </Field>
          <Field label="Zero-padding" hint="e.g. 4 → 0001">
            <input type="number" min={0} max={10} value={s.number_padding ?? 4} onChange={(e) => set('number_padding', e.target.value)} className="neo-input w-full px-3.5 py-2.5 text-xs" />
          </Field>
        </div>
        <p className="text-[11px] text-slate-500">
          Next invoice will be <span className="font-mono text-cyan-400">{(s.invoice_prefix ?? '') + String(s.next_invoice_number ?? 1).padStart(Number(s.number_padding) || 0, '0')}</span>
        </p>
      </div>

      <div className="bento-card p-6 space-y-4">
        <h2 className="text-sm font-bold text-slate-100">Payment details</h2>
        <div className="grid grid-cols-2 gap-3">
          <Field label="Bank name">{inp('bank_name')}</Field>
          <Field label="Account holder">{inp('account_holder')}</Field>
          <Field label="Account number">{inp('account_number')}</Field>
          <Field label="IFSC">{inp('ifsc')}</Field>
        </div>
        <Field label="UPI ID">{inp('upi_id')}</Field>
        <Field label="Payment terms" hint="Printed on the invoice, e.g. “Payable within 7 days.”">{inp('payment_terms')}</Field>
        <Field label="Footer text">{inp('footer_text')}</Field>
      </div>
    </div>
  );
};
