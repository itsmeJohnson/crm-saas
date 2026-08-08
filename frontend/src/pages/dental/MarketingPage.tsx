import React from 'react';
import {
  Megaphone, Target
} from 'lucide-react';
import { formatMoney } from '../../utils/currency';

export const MarketingPage: React.FC = () => {
  const sources = [
    { source: 'Google Ads', leads: 22, appts: 16, patients: 12, rev: 285000, spend: 32000 },
    { source: 'Instagram Ads', leads: 18, appts: 12, patients: 8, rev: 195000, spend: 24000 },
    { source: 'Website Organic', leads: 14, appts: 10, patients: 7, rev: 145000, spend: 0 },
    { source: 'WhatsApp Enquiries', leads: 12, appts: 9, patients: 8, rev: 120000, spend: 5000 },
    { source: 'Patient Referrals', leads: 8, appts: 8, patients: 7, rev: 160000, spend: 2000 },
    { source: 'Clinic Walk-ins', leads: 6, appts: 6, patients: 5, rev: 75000, spend: 0 }
  ];

  const totalLeads = sources.reduce((a, s) => a + s.leads, 0);
  const totalPatients = sources.reduce((a, s) => a + s.patients, 0);
  const totalRevenue = sources.reduce((a, s) => a + s.rev, 0);
  const totalSpend = sources.reduce((a, s) => a + s.spend, 0);
  const overallRoi = totalSpend > 0 ? ((totalRevenue - totalSpend) / totalSpend).toFixed(1) : '12.4';

  return (
    <div className="space-y-6 pb-12">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-800/80 pb-5">
        <div>
          <h1 className="text-2xl font-black text-slate-100 flex items-center gap-2">
            <Megaphone className="w-6 h-6 text-brand-400" />
            Dental Marketing & Lead Acquisition Analytics
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Track lead sources (Google, Instagram, Referrals, Walk-ins), appointment conversion rates & return on ad spend (ROAS).
          </p>
        </div>
      </div>

      {/* Top Marketing KPI Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
          <span className="text-xs text-slate-400 font-semibold">Total Marketing Inquiries</span>
          <p className="text-2xl font-black text-slate-100">{totalLeads}</p>
          <span className="text-[11px] text-brand-400">Multi-channel patient acquisition</span>
        </div>
        <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
          <span className="text-xs text-slate-400 font-semibold">Converted Patients</span>
          <p className="text-2xl font-black text-emerald-400">{totalPatients}</p>
          <span className="text-[11px] text-emerald-400">{Math.round((totalPatients / totalLeads) * 100)}% Conversion Rate</span>
        </div>
        <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
          <span className="text-xs text-slate-400 font-semibold">Acquired Treatment Value</span>
          <p className="text-2xl font-black text-brand-400">{formatMoney(totalRevenue)}</p>
          <span className="text-[11px] text-slate-400">Total revenue from campaigns</span>
        </div>
        <div className="p-5 bg-slate-900/80 rounded-2xl border border-slate-800/80 space-y-1">
          <span className="text-xs text-slate-400 font-semibold">Campaign ROAS / Multiplier</span>
          <p className="text-2xl font-black text-purple-400">{overallRoi}x</p>
          <span className="text-[11px] text-purple-300">Revenue to ad spend ratio</span>
        </div>
      </div>

      {/* Channel Breakdown Table */}
      <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden shadow-xl">
        <div className="p-5 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Target className="w-4 h-4 text-brand-400" />
            Lead Channel Conversion Performance
          </h3>
          <span className="text-xs text-slate-400">Ranked by revenue contribution</span>
        </div>

        <div className="overflow-x-auto">
          <table className="w-full text-left text-xs">
            <thead>
              <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                <th className="px-6 py-4">Source Channel</th>
                <th className="px-4 py-4">Inquiries</th>
                <th className="px-4 py-4">Appointments Booked</th>
                <th className="px-4 py-4">Converted Patients</th>
                <th className="px-4 py-4">Conversion Rate</th>
                <th className="px-4 py-4">Ad Spend</th>
                <th className="px-6 py-4 text-right">Generated Treatment Revenue</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {sources.map((s, idx) => {
                const conv = Math.round((s.patients / s.leads) * 100);
                return (
                  <tr key={idx} className="hover:bg-slate-800/30 transition">
                    <td className="px-6 py-4 font-bold text-slate-100">
                      {s.source}
                    </td>
                    <td className="px-4 py-4 font-semibold text-slate-300">{s.leads}</td>
                    <td className="px-4 py-4 text-slate-300">{s.appts}</td>
                    <td className="px-4 py-4 font-bold text-emerald-400">{s.patients}</td>
                    <td className="px-4 py-4">
                      <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-brand-500/15 text-brand-300 border border-brand-500/30">
                        {conv}%
                      </span>
                    </td>
                    <td className="px-4 py-4 text-slate-400">{s.spend > 0 ? formatMoney(s.spend) : 'Organic / Free'}</td>
                    <td className="px-6 py-4 text-right font-black text-emerald-400 text-sm">
                      {formatMoney(s.rev)}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
