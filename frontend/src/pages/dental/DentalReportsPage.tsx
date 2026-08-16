import React, { useEffect, useState } from 'react';
import { BarChart3, Activity, Stethoscope, RefreshCw } from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { api } from '../../services/api';

const ATTENDED = new Set(['completed', 'attended', 'done', 'checked_in', 'checked-in', 'checkedin']);
const CONVERTED = new Set(['converted', 'won', 'closed_won', 'treatment started', 'treatment completed / converted']);

export const DentalReportsPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [leads, setLeads] = useState<any[]>([]);
  const [contacts, setContacts] = useState<any[]>([]);
  const [invoices, setInvoices] = useState<any[]>([]);
  const [appts, setAppts] = useState<any[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const [l, c, inv, cal] = await Promise.all([
        api.get('/leads/?limit=500').catch(() => ({ data: [] })),
        api.get('/contacts/?limit=500').catch(() => ({ data: [] })),
        api.get('/customers/invoices').catch(() => ({ data: [] })),
        api.get('/calendar/?types=Appointment&limit=500').catch(() => ({ data: [] })),
      ]);
      setLeads(l.data || []); setContacts(c.data || []); setInvoices(inv.data || []); setAppts(cal.data || []);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  // ---- KPIs ----
  const totalLeads = leads.length;
  const convertedLeads = leads.filter(l => CONVERTED.has(String(l.status || '').toLowerCase())).length;
  const conversion = totalLeads ? (convertedLeads / totalLeads) * 100 : 0;

  const totalInvoiced = invoices.reduce((a, i) => a + Number(i.total_amount || 0), 0);
  const payingPatients = new Set(invoices.map(i => i.contact_id || i.company_id).filter(Boolean)).size;
  const avgRevenuePerPatient = payingPatients ? totalInvoiced / payingPatients : 0;

  const apptTotal = appts.length;
  const apptAttended = appts.filter(a => ATTENDED.has(String(a.status || '').toLowerCase())).length;
  const showUpRate = apptTotal ? (apptAttended / apptTotal) * 100 : 0;

  // Recall: contacts due/returning for a recall visit (best-effort from category)
  const recallDue = contacts.filter(c => /recall|return/i.test(String(c.custom_fields?.patient_category || ''))).length;
  const recallCompliance = contacts.length ? (recallDue / contacts.length) * 100 : 0;

  // ---- Revenue by treatment (from invoice line items) ----
  const byTreatment: Record<string, { rev: number; count: number }> = {};
  for (const inv of invoices) {
    for (const it of (inv.items || [])) {
      const key = String(it.category || it.description || 'Other').trim() || 'Other';
      const amt = Number(it.amount ?? (Number(it.unit_price || 0) * Number(it.quantity || 0)));
      const d = (byTreatment[key] ||= { rev: 0, count: 0 });
      d.rev += amt; d.count += 1;
    }
  }
  const treatmentTotal = Object.values(byTreatment).reduce((a, d) => a + d.rev, 0);
  const treatments = Object.entries(byTreatment)
    .map(([name, d]) => ({ name, rev: d.rev, count: d.count, share: treatmentTotal ? Math.round((d.rev / treatmentTotal) * 100) : 0 }))
    .sort((a, b) => b.rev - a.rev);

  // ---- Doctor case load (invoice -> patient contact -> consultant) ----
  const contactById = new Map(contacts.map(c => [c.id, c]));
  const byDoctor: Record<string, { rev: number; cases: number }> = {};
  for (const inv of invoices) {
    const c = inv.contact_id ? contactById.get(inv.contact_id) : null;
    const doc = (c?.custom_fields?.consultant_name || c?.custom_fields?.primary_doctor || 'Unassigned').trim() || 'Unassigned';
    const d = (byDoctor[doc] ||= { rev: 0, cases: 0 });
    d.rev += Number(inv.total_amount || 0); d.cases += 1;
  }
  const doctors = Object.entries(byDoctor).map(([doc, d]) => ({ doc, ...d })).sort((a, b) => b.rev - a.rev);

  const Kpi = ({ label, value, sub, color }: { label: string; value: string; sub: string; color: string }) => (
    <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
      <span className="text-xs text-slate-400 font-semibold">{label}</span>
      <p className={`text-2xl font-black ${color}`}>{value}</p>
      <span className="text-[11px] text-slate-400">{sub}</span>
    </div>
  );

  return (
    <div className="space-y-6 pb-12">
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-brand-400" />
            Dental Practice Performance &amp; Clinical Reports
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Comprehensive analytics: lead conversion velocity, patient retention, procedure revenue &amp; recall effectiveness.
          </p>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-100 disabled:opacity-50">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Overall Lead-to-Patient Conversion" value={`${conversion.toFixed(1)}%`} sub={`${convertedLeads} of ${totalLeads} leads converted`} color="text-emerald-400" />
        <Kpi label="Average Revenue Per Patient" value={formatMoney(Math.round(avgRevenuePerPatient))} sub={`${payingPatients} billed patients`} color="text-slate-100" />
        <Kpi label="Appointment Show-up Rate" value={apptTotal ? `${showUpRate.toFixed(1)}%` : '—'} sub={apptTotal ? `${apptAttended} of ${apptTotal} attended` : 'No appointments yet'} color="text-brand-400" />
        <Kpi label="Recall / Returning Patients" value={contacts.length ? `${recallCompliance.toFixed(1)}%` : '—'} sub={`${recallDue} patients flagged`} color="text-amber-400" />
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-4">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Activity className="w-4 h-4 text-brand-400" /> Revenue by Dental Treatment Category
          </h3>
          {treatments.length === 0 ? (
            <p className="text-xs text-slate-500 py-8 text-center">No billed treatments yet. Create invoices to see revenue by category.</p>
          ) : (
            <div className="space-y-3 text-xs">
              {treatments.map((p, idx) => (
                <div key={idx} className="p-3 bg-slate-950/40 rounded-xl border border-slate-800/60 space-y-1.5">
                  <div className="flex justify-between font-semibold">
                    <span className="text-slate-200">{p.name}</span>
                    <span className="text-emerald-400">{formatMoney(p.rev)}</span>
                  </div>
                  <div className="flex justify-between text-[11px] text-slate-400">
                    <span>{p.count} procedure{p.count === 1 ? '' : 's'} billed</span>
                    <span>{p.share}% of billed revenue</span>
                  </div>
                  <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden">
                    <div className="h-full bg-brand-500 rounded-full" style={{ width: `${p.share}%` }} />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-4">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Stethoscope className="w-4 h-4 text-emerald-400" /> Doctor Case Load &amp; Revenue Contribution
          </h3>
          {doctors.length === 0 ? (
            <p className="text-xs text-slate-500 py-8 text-center">No billed cases yet. Assign a consultant when registering patients.</p>
          ) : (
            <div className="space-y-3.5 text-xs">
              {doctors.map((d, idx) => (
                <div key={idx} className="p-4 bg-slate-950/40 rounded-xl border border-slate-800/60 flex items-center justify-between">
                  <div className="space-y-0.5">
                    <span className="font-bold text-slate-100 text-sm">{d.doc}</span>
                    <p className="text-[11px] text-slate-400">{d.cases} Billed Patient Case{d.cases === 1 ? '' : 's'}</p>
                  </div>
                  <div className="text-right">
                    <span className="text-sm font-black text-emerald-400">{formatMoney(d.rev)}</span>
                    <p className="text-[11px] text-slate-400">Total Billed</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
