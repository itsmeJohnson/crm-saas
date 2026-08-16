import React, { useEffect } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { useUserStore } from '../../store/userStore';
import { LeadResponse } from '../../services/leadApi';
import { Edit3, Trash2, Loader2, AlertCircle, Inbox, Building2, Flame } from 'lucide-react';
import { MaskedField } from '../common/MaskedField';
import { formatMoney } from '../../utils/currency';
import { useAuthStore } from '../../store/authStore';

interface LeadTableProps {
  onEditClick: (lead: LeadResponse) => void;
  onRowClick: (lead: LeadResponse) => void;
  selectedLeadIds: string[];
  onSelectLeads: (ids: string[]) => void;
  hideCheckboxes?: boolean;
}

/** Compact relative time, e.g. "Today", "3d ago", "2mo ago". */
const relativeTime = (iso?: string): string => {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diff = Date.now() - then;
  const day = 86400000;
  if (diff < day && new Date(iso).getDate() === new Date().getDate()) return 'Today';
  const days = Math.floor(diff / day);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  if (days < 365) return `${Math.floor(days / 30)}mo ago`;
  return `${Math.floor(days / 365)}y ago`;
};

const initialsOf = (a?: string | null, b?: string | null, fallback = '?'): string =>
  ([a?.[0], b?.[0]].filter(Boolean).join('') || fallback).toUpperCase();

const PRIORITY_STYLES: Record<string, string> = {
  Urgent: 'text-red-400',
  High: 'text-amber-400',
  Medium: 'text-slate-400',
  Low: 'text-slate-500',
};

const STATUS_STYLES: Record<string, string> = {
  New: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
  Contacted: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  Qualified: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  Nurturing: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
  Picked: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  Lost: 'bg-slate-800 text-slate-400 border-slate-700',
};

export const LeadTable: React.FC<LeadTableProps> = ({
  onEditClick,
  onRowClick,
  selectedLeadIds,
  onSelectLeads,
  hideCheckboxes = false,
}) => {
  const { leads, isLoading, error, deleteLead } = useLeadStore();
  const { users, fetchUsers } = useUserStore();
  const { user } = useAuthStore();
  const isEmployee = user?.role === 'Employee';

  useEffect(() => {
    if (users.length === 0) fetchUsers();
  }, []);

  const handleDelete = async (e: React.MouseEvent, lead: LeadResponse) => {
    e.stopPropagation();
    if (window.confirm(`Delete lead "${lead.title}"? Related activities and notes are soft-deleted too.`)) {
      try {
        await deleteLead(lead.id);
      } catch (err: any) {
        alert(err.message || 'Deletion failed');
      }
    }
  };

  const handleEdit = (e: React.MouseEvent, lead: LeadResponse) => {
    e.stopPropagation();
    onEditClick(lead);
  };

  const ownerFor = (lead: LeadResponse) => users.find((u) => u.id === lead.assigned_user_id);
  const ownerName = (lead: LeadResponse) => {
    const o = ownerFor(lead);
    return o ? `${o.first_name || ''} ${o.last_name || ''}`.trim() || o.email : 'Unassigned';
  };

  // Progress pill: prefer the tenant's pipeline stage (with its colour); fall back to status.
  const stagePill = (lead: LeadResponse) => {
    if (lead.stage?.name) {
      const color = lead.stage.color || '#6366f1';
      return (
        <span
          className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800/60 text-slate-200 border border-slate-700/60"
          title={lead.stage.name}
        >
          <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
          {lead.stage.name}
        </span>
      );
    }
    const cls = STATUS_STYLES[lead.status] || 'bg-slate-800 text-slate-300 border-slate-700';
    return (
      <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold border ${cls}`}>
        {lead.status}
      </span>
    );
  };

  const priorityPill = (priority: string) => (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium">
      <Flame className={`w-3.5 h-3.5 ${PRIORITY_STYLES[priority] || 'text-slate-400'}`} />
      <span className="text-slate-300">{priority}</span>
    </span>
  );

  const ownerBadge = (lead: LeadResponse) => {
    const o = ownerFor(lead);
    return (
      <div className="flex items-center gap-2 min-w-0">
        <div className={`w-7 h-7 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${o ? 'bg-brand-500/15 text-brand-300 border border-brand-500/25' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}>
          {o ? initialsOf(o.first_name, o.last_name, 'U') : '—'}
        </div>
        <span className="text-sm text-slate-300 truncate">{ownerName(lead)}</span>
      </div>
    );
  };

  if (isLoading && leads.length === 0) {
    return (
      <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
        <p className="text-sm">Loading leads…</p>
      </div>
    );
  }

  if (error && leads.length === 0) {
    return (
      <div className="glass-panel p-12 rounded-2xl border border-red-900/30 bg-red-950/10 flex flex-col items-center justify-center text-red-400">
        <AlertCircle className="w-8 h-8 mb-2" />
        <p className="font-semibold mb-2">Error Loading Leads</p>
        <p className="text-sm text-red-400/80">{error}</p>
      </div>
    );
  }

  if (leads.length === 0) {
    return (
      <div className="glass-panel rounded-2xl border border-slate-800/80 py-16 px-6 flex flex-col items-center justify-center text-center">
        <div className="w-14 h-14 rounded-2xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mb-4">
          <Inbox className="w-7 h-7 text-brand-400" />
        </div>
        <p className="text-base font-semibold text-slate-200">No leads yet</p>
        <p className="text-sm text-slate-400 mt-1 max-w-sm">
          Add your first opportunity or import a list to start tracking deals through your pipeline.
        </p>
      </div>
    );
  }

  const allSelected = leads.length > 0 && selectedLeadIds.length === leads.length;
  const toggleAll = (checked: boolean) => onSelectLeads(checked ? leads.map((l) => l.id) : []);
  const toggleOne = (id: string, checked: boolean) =>
    onSelectLeads(checked ? [...selectedLeadIds, id] : selectedLeadIds.filter((x) => x !== id));

  return (
    <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden">
      {/* ── Desktop / tablet: table ── */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[820px]">
          <thead>
            <tr className="border-b border-slate-800/80 bg-slate-900/40">
              {!hideCheckboxes && (
                <th className="w-12 px-5 py-3.5">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={(e) => toggleAll(e.target.checked)}
                    className="w-4 h-4 rounded border-slate-700 text-brand-500 bg-slate-950 focus:ring-brand-500/25 cursor-pointer"
                  />
                </th>
              )}
              <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Lead</th>
              <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Stage</th>
              <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Value</th>
              <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Priority</th>
              <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Owner</th>
              <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Created</th>
              {!isEmployee && (
                <th className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Actions</th>
              )}
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/65">
            {leads.map((lead) => {
              const contactFullName = `${lead.first_name || ''} ${lead.last_name}`.trim();
              return (
                <tr
                  key={lead.id}
                  onClick={() => onRowClick(lead)}
                  className="hover:bg-slate-900/30 transition-colors cursor-pointer"
                >
                  {!hideCheckboxes && (
                    <td className="w-12 px-5 py-3.5" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedLeadIds.includes(lead.id)}
                        onChange={(e) => toggleOne(lead.id, e.target.checked)}
                        className="w-4 h-4 rounded border-slate-700 text-brand-500 bg-slate-950 focus:ring-brand-500/25 cursor-pointer"
                      />
                    </td>
                  )}

                  <td className="px-5 py-3.5">
                    <div className="flex items-center gap-3">
                      <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/25 flex items-center justify-center font-bold text-brand-300 text-sm shrink-0">
                        {initialsOf(lead.title?.[0], lead.title?.[1], 'LD')}
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-semibold text-slate-200 truncate">{lead.title}</p>
                        <div className="flex flex-wrap items-center gap-x-1.5 text-xs text-slate-400 mt-0.5">
                          {contactFullName && <span className="text-slate-300 truncate">{contactFullName}</span>}
                          {contactFullName && lead.company_name && <span className="text-slate-600">•</span>}
                          {lead.company_name && (
                            <span className="inline-flex items-center gap-1 truncate">
                              <Building2 className="w-3 h-3 text-slate-500 shrink-0" />
                              {lead.company_name}
                            </span>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>

                  <td className="px-5 py-3.5 align-middle">{stagePill(lead)}</td>

                  <td className="px-5 py-3.5 align-middle text-right">
                    <span className="text-sm font-semibold text-slate-200">
                      {lead.value !== null ? formatMoney(lead.value) : '—'}
                    </span>
                  </td>

                  <td className="px-5 py-3.5 align-middle">{priorityPill(lead.priority)}</td>

                  <td className="px-5 py-3.5 align-middle">{ownerBadge(lead)}</td>

                  <td className="px-5 py-3.5 align-middle">
                    <span className="text-xs text-slate-400 whitespace-nowrap">{relativeTime(lead.created_at)}</span>
                  </td>

                  {!isEmployee && (
                    <td className="px-5 py-3.5 text-right align-middle">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => handleEdit(e, lead)}
                          title="Edit lead"
                          className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-lg text-slate-300 transition-all cursor-pointer"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, lead)}
                          title="Delete lead"
                          className="p-2 border border-slate-800 hover:border-red-500/25 hover:bg-red-500/10 text-red-400 rounded-lg transition-all cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* ── Mobile: card list ── */}
      <div className="md:hidden divide-y divide-slate-800/65">
        {leads.map((lead) => {
          const contactFullName = `${lead.first_name || ''} ${lead.last_name}`.trim();
          return (
            <div
              key={lead.id}
              onClick={() => onRowClick(lead)}
              className="p-4 active:bg-slate-900/40 transition-colors cursor-pointer"
            >
              <div className="flex items-start gap-3">
                {!hideCheckboxes && (
                  <input
                    type="checkbox"
                    checked={selectedLeadIds.includes(lead.id)}
                    onClick={(e) => e.stopPropagation()}
                    onChange={(e) => toggleOne(lead.id, e.target.checked)}
                    className="mt-1 w-4 h-4 rounded border-slate-700 text-brand-500 bg-slate-950 focus:ring-brand-500/25 cursor-pointer shrink-0"
                  />
                )}
                <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/25 flex items-center justify-center font-bold text-brand-300 text-sm shrink-0">
                  {initialsOf(lead.title?.[0], lead.title?.[1], 'LD')}
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-semibold text-slate-200 truncate">{lead.title}</p>
                    <span className="text-sm font-semibold text-slate-200 shrink-0">
                      {lead.value !== null ? formatMoney(lead.value) : ''}
                    </span>
                  </div>
                  <p className="text-xs text-slate-400 truncate mt-0.5">
                    {contactFullName}
                    {contactFullName && lead.company_name ? ' • ' : ''}
                    {lead.company_name}
                  </p>
                  <div className="flex items-center flex-wrap gap-2 mt-2">
                    {stagePill(lead)}
                    {priorityPill(lead.priority)}
                    <span className="text-[11px] text-slate-500 ml-auto">{relativeTime(lead.created_at)}</span>
                  </div>
                  <div className="flex items-center justify-between mt-2.5">
                    {ownerBadge(lead)}
                    {!isEmployee && (
                      <div className="flex items-center gap-2 shrink-0">
                        <button
                          onClick={(e) => handleEdit(e, lead)}
                          className="p-1.5 border border-slate-800 hover:bg-slate-900 rounded-lg text-slate-300 cursor-pointer"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, lead)}
                          className="p-1.5 border border-slate-800 hover:bg-red-500/10 text-red-400 rounded-lg cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    )}
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    <MaskedField value={lead.phone} />
                  </div>
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
