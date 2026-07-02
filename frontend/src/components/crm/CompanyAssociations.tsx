import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { companyApi, CompanyContactSummary, CompanyLeadSummary, CompanyDealsSummary } from '../../services/companyApi';
import { Users, Briefcase, TrendingUp, Trophy } from 'lucide-react';

const currency = (n: number) =>
  new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(n);

export const CompanyAssociations: React.FC<{ companyId: string }> = ({ companyId }) => {
  const [contacts, setContacts] = useState<CompanyContactSummary[]>([]);
  const [leads, setLeads] = useState<CompanyLeadSummary[]>([]);
  const [deals, setDeals] = useState<CompanyDealsSummary | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    companyApi.getContacts(companyId).then(setContacts).catch(() => {});
    companyApi.getLeads(companyId).then(setLeads).catch(() => {});
    companyApi.getDeals(companyId).then(setDeals).catch(() => {});
  }, [companyId]);

  return (
    <div className="space-y-6">
      {/* Deals rollup */}
      {deals && (
        <div>
          <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-emerald-400" /> Deals
          </h3>
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
            <div className="p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Total</p>
              <p className="text-lg font-bold text-slate-100">{deals.total_leads}</p>
            </div>
            <div className="p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Open</p>
              <p className="text-lg font-bold text-slate-100">{deals.open_count}</p>
            </div>
            <div className="p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
              <p className="text-[10px] font-semibold text-emerald-400/80 uppercase tracking-wider flex items-center gap-1"><Trophy className="w-3 h-3" /> Customers</p>
              <p className="text-lg font-bold text-emerald-300">{deals.won_count}</p>
            </div>
            <div className="p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Value</p>
              <p className="text-lg font-bold text-slate-100">{currency(deals.total_value)}</p>
            </div>
          </div>
        </div>
      )}

      {/* Associated leads */}
      <div>
        <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
          <Briefcase className="w-4 h-4 text-brand-400" /> Associated Leads
        </h3>
        {leads.length === 0 ? (
          <p className="text-xs text-slate-500">No associated leads.</p>
        ) : (
          <ul className="space-y-2">
            {leads.map((l) => (
              <li
                key={l.id}
                onClick={() => navigate(`/leads?leadId=${l.id}`)}
                className="flex items-center justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg cursor-pointer hover:border-slate-700"
              >
                <div className="min-w-0">
                  <p className="text-xs font-medium text-slate-200 truncate">{l.title}</p>
                  <p className="text-[11px] text-slate-500">{l.stage || l.status}</p>
                </div>
                {l.value != null && <span className="text-xs text-slate-400 shrink-0">{currency(Number(l.value))}</span>}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* People / employees roster */}
      <div>
        <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
          <Users className="w-4 h-4 text-indigo-400" /> People ({contacts.length})
        </h3>
        {contacts.length === 0 ? (
          <p className="text-xs text-slate-500">No contacts linked to this company.</p>
        ) : (
          <ul className="space-y-2">
            {contacts.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">
                <span className="text-xs text-slate-200 truncate">{c.first_name} {c.last_name}</span>
                <span className="text-[11px] text-slate-500 truncate">{c.job_title || c.email || ''}</span>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
