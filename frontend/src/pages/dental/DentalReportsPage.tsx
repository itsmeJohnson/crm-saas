import React from 'react';
import {
  BarChart3, Activity, Stethoscope
} from 'lucide-react';
import { formatMoney } from '../../utils/currency';

export const DentalReportsPage: React.FC = () => {
  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <BarChart3 className="w-6 h-6 text-brand-400" />
            Dental Practice Performance & Clinical Reports
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Comprehensive analytics: lead conversion velocity, patient retention, procedure revenue & recall effectiveness.
          </p>
        </div>
      </div>

      {/* Top Metric Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
          <span className="text-xs text-slate-400 font-semibold">Overall Lead-to-Patient Conversion</span>
          <p className="text-2xl font-black text-emerald-400">38.4%</p>
          <span className="text-[11px] text-emerald-400">+5.2% vs previous quarter</span>
        </div>
        <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
          <span className="text-xs text-slate-400 font-semibold">Average Revenue Per Patient</span>
          <p className="text-2xl font-black text-slate-100">{formatMoney(18400)}</p>
          <span className="text-[11px] text-brand-400">Multi-sitting treatment plans</span>
        </div>
        <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
          <span className="text-xs text-slate-400 font-semibold">Appointment Show-up Rate</span>
          <p className="text-2xl font-black text-brand-400">92.6%</p>
          <span className="text-[11px] text-slate-400">WhatsApp reminders enabled</span>
        </div>
        <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
          <span className="text-xs text-slate-400 font-semibold">6-Month Recall Compliance</span>
          <p className="text-2xl font-black text-amber-400">74.1%</p>
          <span className="text-[11px] text-amber-400">89 Patients re-visited</span>
        </div>
      </div>

      {/* Procedure Revenue Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Procedure-wise Revenue */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-4">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Activity className="w-4 h-4 text-brand-400" />
            Revenue by Dental Treatment Category
          </h3>
          <div className="space-y-3 text-xs">
            {[
              { name: 'Implantology (Dental Implants)', rev: 285000, share: 42, count: 8 },
              { name: 'Orthodontics (Invisalign & Braces)', rev: 190000, share: 28, count: 6 },
              { name: 'Endodontics (Root Canal Therapy)', rev: 96000, share: 14, count: 12 },
              { name: 'Prosthodontics (Zirconia Crowns)', rev: 60000, share: 9, count: 7 },
              { name: 'Cosmetic (Teeth Whitening)', rev: 38000, share: 5, count: 5 },
              { name: 'Preventive (Deep Cleaning & Scaling)', rev: 13000, share: 2, count: 18 },
            ].map((p, idx) => (
              <div key={idx} className="p-3 bg-slate-950/40 rounded-xl border border-slate-800/60 space-y-1.5">
                <div className="flex justify-between font-semibold">
                  <span className="text-slate-200">{p.name}</span>
                  <span className="text-emerald-400">{formatMoney(p.rev)}</span>
                </div>
                <div className="flex justify-between text-[11px] text-slate-400">
                  <span>{p.count} Patients treated</span>
                  <span>{p.share}% of practice revenue</span>
                </div>
                <div className="w-full h-1.5 bg-slate-900 rounded-full overflow-hidden">
                  <div className="h-full bg-brand-500 rounded-full" style={{ width: `${p.share}%` }} />
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Doctor-wise Patient Load & Revenue */}
        <div className="glass-panel p-6 rounded-2xl border border-slate-800/80 space-y-4">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Stethoscope className="w-4 h-4 text-emerald-400" />
            Doctor Case Load & Revenue Contribution
          </h3>
          <div className="space-y-3.5 text-xs">
            {[
              { doc: 'Dr. Arvind Mehta', spec: 'Orthodontics', rev: 275000, cases: 28 },
              { doc: 'Dr. Priya Sharma', spec: 'Endodontics & Cosmetic', rev: 215000, cases: 42 },
              { doc: 'Dr. Vikram Rao', spec: 'Implantology & Surgery', rev: 185000, cases: 16 },
              { doc: 'Dr. Johnson Dev', spec: 'General & Diagnostics', rev: 95000, cases: 34 }
            ].map((d, idx) => (
              <div key={idx} className="p-4 bg-slate-950/40 rounded-xl border border-slate-800/60 flex items-center justify-between">
                <div className="space-y-0.5">
                  <span className="font-bold text-slate-100 text-sm">{d.doc}</span>
                  <p className="text-xs text-brand-400">{d.spec}</p>
                  <p className="text-[11px] text-slate-400">{d.cases} Completed Patient Cases</p>
                </div>
                <div className="text-right">
                  <span className="text-sm font-black text-emerald-400">{formatMoney(d.rev)}</span>
                  <p className="text-[11px] text-slate-400">Total Billed</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
