import React, { useEffect, useState } from 'react';
import { Megaphone, Target, RefreshCw } from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { api } from '../../services/api';

const CONVERTED = new Set(['converted', 'won', 'closed_won', 'treatment started', 'treatment completed / converted']);
const LOST = new Set(['lost', 'lost / not interested', 'closed_lost']);
const NEW = new Set(['new', 'new enquiry', 'new lead']);

export const MarketingPage: React.FC = () => {
  const [loading, setLoading] = useState(true);
  const [leads, setLeads] = useState<any[]>([]);

  const load = async () => {
    setLoading(true);
    try {
      const res = await api.get('/leads/?limit=1000').catch(() => ({ data: [] }));
      setLeads(res.data || []);
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => { load(); }, []);

  const leadValue = (l: any) => Number(l.value ?? l.estimated_value ?? l.deal_value ?? 0);

  // Group by source
  const map: Record<string, { leads: number; booked: number; patients: number; rev: number }> = {};
  for (const l of leads) {
    const src = (l.source || 'Direct / Unknown').toString().trim() || 'Direct / Unknown';
    const status = String(l.status || '').toLowerCase();
    const d = (map[src] ||= { leads: 0, booked: 0, patients: 0, rev: 0 });
    d.leads += 1;
    if (!NEW.has(status) && !LOST.has(status)) d.booked += 1;
    if (CONVERTED.has(status)) { d.patients += 1; d.rev += leadValue(l); }
  }
  const sources = Object.entries(map)
    .map(([source, d]) => ({ source, ...d }))
    .sort((a, b) => b.rev - a.rev || b.leads - a.leads);

  const totalLeads = leads.length;
  const totalPatients = sources.reduce((a, s) => a + s.patients, 0);
  const totalRevenue = sources.reduce((a, s) => a + s.rev, 0);
  const convRate = totalLeads ? Math.round((totalPatients / totalLeads) * 100) : 0;

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
            <Megaphone className="w-6 h-6 text-brand-400" />
            Dental Marketing &amp; Lead Acquisition Analytics
          </h1>
          <p className="text-xs text-slate-400 mt-1">
            Lead sources (Google, Instagram, Referrals, Walk-ins), conversion rates &amp; acquired treatment value — from your live leads.
          </p>
        </div>
        <button onClick={load} disabled={loading} className="flex items-center gap-2 px-3 py-2 rounded-xl text-xs font-semibold bg-slate-900 border border-slate-800 text-slate-300 hover:text-slate-100 disabled:opacity-50">
          <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <Kpi label="Total Marketing Inquiries" value={String(totalLeads)} sub="Multi-channel patient acquisition" color="text-slate-100" />
        <Kpi label="Converted Patients" value={String(totalPatients)} sub={`${convRate}% Conversion Rate`} color="text-emerald-400" />
        <Kpi label="Acquired Treatment Value" value={formatMoney(totalRevenue)} sub="Value of converted leads" color="text-brand-400" />
        <Kpi label="Campaign ROAS / Multiplier" value="—" sub="Add ad spend per channel to compute" color="text-purple-400" />
      </div>

      <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden shadow-xl">
        <div className="p-5 border-b border-slate-800 bg-slate-950/40 flex items-center justify-between">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2">
            <Target className="w-4 h-4 text-brand-400" /> Lead Channel Conversion Performance
          </h3>
          <span className="text-xs text-slate-400">Ranked by revenue contribution</span>
        </div>

        {sources.length === 0 ? (
          <p className="text-xs text-slate-500 py-12 text-center">No leads yet. Captured leads (Google/Instagram/Facebook/webhooks, walk-ins, referrals) will appear here grouped by source.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-left text-xs">
              <thead>
                <tr className="bg-slate-950/80 border-b border-slate-800 text-slate-400 uppercase tracking-wider font-semibold">
                  <th className="px-6 py-4">Source Channel</th>
                  <th className="px-4 py-4">Inquiries</th>
                  <th className="px-4 py-4">Engaged / Booked</th>
                  <th className="px-4 py-4">Converted Patients</th>
                  <th className="px-4 py-4">Conversion Rate</th>
                  <th className="px-4 py-4">Ad Spend</th>
                  <th className="px-6 py-4 text-right">Generated Treatment Revenue</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60">
                {sources.map((s, idx) => {
                  const conv = s.leads ? Math.round((s.patients / s.leads) * 100) : 0;
                  return (
                    <tr key={idx} className="hover:bg-slate-800/30 transition">
                      <td className="px-6 py-4 font-bold text-slate-100">{s.source}</td>
                      <td className="px-4 py-4 font-semibold text-slate-300">{s.leads}</td>
                      <td className="px-4 py-4 text-slate-300">{s.booked}</td>
                      <td className="px-4 py-4 font-bold text-emerald-400">{s.patients}</td>
                      <td className="px-4 py-4">
                        <span className="px-2.5 py-1 rounded-full text-[11px] font-bold bg-brand-500/15 text-brand-300 border border-brand-500/30">{conv}%</span>
                      </td>
                      <td className="px-4 py-4 text-slate-500">—</td>
                      <td className="px-6 py-4 text-right font-black text-emerald-400 text-sm">{formatMoney(s.rev)}</td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};
