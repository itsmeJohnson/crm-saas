import React, { useEffect, useState, useMemo } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { useUserStore } from '../../store/userStore';
import { LeadResponse } from '../../services/leadApi';
import { Edit3, Trash2, Loader2, AlertCircle, Inbox, Building2, MessageCircle, Phone, ArrowUpDown, ChevronUp, ChevronDown } from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { useAuthStore } from '../../store/authStore';

interface LeadTableProps {
  onEditClick: (lead: LeadResponse) => void;
  onRowClick: (lead: LeadResponse) => void;
  selectedLeadIds: string[];
  onSelectLeads: (ids: string[]) => void;
  hideCheckboxes?: boolean;
  onChatClick?: (lead: LeadResponse, channel?: 'whatsapp' | 'sms') => void;
  onCallClick?: (leadId: string) => void;
}

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

const PRIORITY_ORDER: Record<string, number> = {
  Urgent: 4,
  High: 3,
  Medium: 2,
  Low: 1,
};

type SortKey = 'title' | 'stage' | 'value' | 'priority' | 'owner' | 'created_at';

export const LeadTable: React.FC<LeadTableProps> = ({
  onEditClick,
  onRowClick,
  selectedLeadIds,
  onSelectLeads,
  hideCheckboxes = false,
  onChatClick,
  onCallClick,
}) => {
  const { leads, isLoading, error, deleteLead } = useLeadStore();
  const { users, fetchUsers } = useUserStore();
  const { user } = useAuthStore();
  const isEmployee = user?.role === 'Employee';
  // Delete lead option only given to designations above Team Leader (Manager, OrgAdmin, SuperAdmin)
  const canDeleteLead = user?.role === 'SuperAdmin' || user?.role === 'OrgAdmin' || user?.role === 'Manager';

  const [sortKey, setSortKey] = useState<SortKey>('created_at');
  const [sortOrder, setSortOrder] = useState<'asc' | 'desc'>('desc');

  useEffect(() => {
    if (users.length === 0) fetchUsers();
  }, []);

  const handleSort = (key: SortKey) => {
    if (sortKey === key) {
      setSortOrder((prev) => (prev === 'asc' ? 'desc' : 'asc'));
    } else {
      setSortKey(key);
      setSortOrder('asc');
    }
  };

  const ownerFor = (lead: LeadResponse) => users.find((u) => u.id === lead.assigned_user_id);
  const ownerName = (lead: LeadResponse) => {
    const o = ownerFor(lead);
    return o ? `${o.first_name || ''} ${o.last_name || ''}`.trim() || o.email : 'Unassigned';
  };

  const sortedLeads = useMemo(() => {
    const list = [...leads];
    list.sort((a, b) => {
      let cmp = 0;
      if (sortKey === 'title') {
        cmp = (a.title || '').localeCompare(b.title || '');
      } else if (sortKey === 'stage') {
        const stageA = a.stage?.name || a.status || '';
        const stageB = b.stage?.name || b.status || '';
        cmp = stageA.localeCompare(stageB);
      } else if (sortKey === 'value') {
        cmp = (a.value || 0) - (b.value || 0);
      } else if (sortKey === 'priority') {
        cmp = (PRIORITY_ORDER[a.priority] || 0) - (PRIORITY_ORDER[b.priority] || 0);
      } else if (sortKey === 'owner') {
        cmp = ownerName(a).localeCompare(ownerName(b));
      } else if (sortKey === 'created_at') {
        cmp = new Date(a.created_at).getTime() - new Date(b.created_at).getTime();
      }
      return sortOrder === 'asc' ? cmp : -cmp;
    });
    return list;
  }, [leads, sortKey, sortOrder, users]);

  const handleDelete = async (e: React.MouseEvent, lead: LeadResponse) => {
    e.stopPropagation();
    if (window.confirm(`Delete lead "${lead.title}"? Related activities and notes will be archived.`)) {
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

  const stagePill = (lead: LeadResponse) => {
    const name = lead.stage?.name || lead.status;
    const color = lead.stage?.color || (name === 'Converted' ? '#10B981' : name === 'Lost' ? '#EF4444' : '#6366F1');
    return (
      <span
        className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800/80 text-slate-200 border border-slate-700/80 shadow-2xs"
        title={name}
      >
        <span className="w-1.5 h-1.5 rounded-full shrink-0" style={{ backgroundColor: color }} />
        {name}
      </span>
    );
  };

  const priorityPill = (priority: string) => {
    const isUrgent = priority === 'Urgent';
    const isHigh = priority === 'High';
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium">
        <span
          className={`w-1.5 h-1.5 rounded-full ${
            isUrgent ? 'bg-rose-500' : isHigh ? 'bg-amber-500' : priority === 'Low' ? 'bg-slate-500' : 'bg-blue-500'
          }`}
        />
        <span className="text-slate-300">{priority || 'Medium'}</span>
      </span>
    );
  };

  const ownerBadge = (lead: LeadResponse) => {
    const o = ownerFor(lead);
    return (
      <div className="flex items-center gap-2 min-w-0">
        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-[10px] font-bold shrink-0 ${o ? 'bg-brand-500/15 text-brand-300 border border-brand-500/25' : 'bg-slate-800 text-slate-500 border border-slate-700'}`}>
          {o ? initialsOf(o.first_name, o.last_name, 'U') : '—'}
        </div>
        <span className="text-xs text-slate-300 truncate">{ownerName(lead)}</span>
      </div>
    );
  };

  const renderSortIcon = (key: SortKey) => {
    if (sortKey !== key) return <ArrowUpDown className="w-3 h-3 text-slate-500 opacity-60" />;
    return sortOrder === 'asc' ? (
      <ChevronUp className="w-3 h-3 text-brand-400" />
    ) : (
      <ChevronDown className="w-3 h-3 text-brand-400" />
    );
  };

  if (isLoading && leads.length === 0) {
    return (
      <div className="p-16 rounded-2xl border border-slate-800/80 bg-slate-900/60 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
        <p className="text-sm font-medium">Loading leads…</p>
      </div>
    );
  }

  if (error && leads.length === 0) {
    return (
      <div className="p-12 rounded-2xl border border-red-900/30 bg-red-950/10 flex flex-col items-center justify-center text-red-400">
        <AlertCircle className="w-8 h-8 mb-2" />
        <p className="font-semibold mb-1">Error Loading Leads</p>
        <p className="text-xs text-red-400/80">{error}</p>
      </div>
    );
  }

  if (leads.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-800/80 bg-slate-900/60 py-16 px-6 flex flex-col items-center justify-center text-center">
        <div className="w-12 h-12 rounded-xl bg-brand-500/10 border border-brand-500/20 flex items-center justify-center mb-3">
          <Inbox className="w-6 h-6 text-brand-400" />
        </div>
        <p className="text-sm font-bold text-slate-200">No leads found</p>
        <p className="text-xs text-slate-400 mt-1 max-w-sm">
          Try clearing your filters or create a new lead opportunity to start your pipeline.
        </p>
      </div>
    );
  }

  const allSelected = sortedLeads.length > 0 && selectedLeadIds.length === sortedLeads.length;
  const toggleAll = (checked: boolean) => onSelectLeads(checked ? sortedLeads.map((l) => l.id) : []);
  const toggleOne = (id: string, checked: boolean) =>
    onSelectLeads(checked ? [...selectedLeadIds, id] : selectedLeadIds.filter((x) => x !== id));

  return (
    <div className="bg-slate-900/60 rounded-xl border border-slate-800/80 overflow-hidden shadow-2xs">
      {/* Desktop / Tablet Table */}
      <div className="hidden md:block overflow-x-auto">
        <table className="w-full text-left border-collapse min-w-[850px]">
          <thead>
            <tr className="border-b border-slate-800/90 bg-slate-950/60">
              {!hideCheckboxes && (
                <th className="w-10 px-4 py-3">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={(e) => toggleAll(e.target.checked)}
                    className="w-3.5 h-3.5 rounded border-slate-700 text-brand-500 bg-slate-950 focus:ring-brand-500/25 cursor-pointer"
                  />
                </th>
              )}
              <th
                onClick={() => handleSort('title')}
                className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 cursor-pointer hover:text-slate-200 select-none"
              >
                <div className="flex items-center gap-1.5">
                  <span>Lead</span>
                  {renderSortIcon('title')}
                </div>
              </th>
              <th
                onClick={() => handleSort('stage')}
                className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 cursor-pointer hover:text-slate-200 select-none"
              >
                <div className="flex items-center gap-1.5">
                  <span>Stage</span>
                  {renderSortIcon('stage')}
                </div>
              </th>
              <th
                onClick={() => handleSort('value')}
                className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 text-right cursor-pointer hover:text-slate-200 select-none"
              >
                <div className="flex items-center justify-end gap-1.5">
                  <span>Value</span>
                  {renderSortIcon('value')}
                </div>
              </th>
              <th
                onClick={() => handleSort('priority')}
                className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 cursor-pointer hover:text-slate-200 select-none"
              >
                <div className="flex items-center gap-1.5">
                  <span>Priority</span>
                  {renderSortIcon('priority')}
                </div>
              </th>
              <th
                onClick={() => handleSort('owner')}
                className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 cursor-pointer hover:text-slate-200 select-none"
              >
                <div className="flex items-center gap-1.5">
                  <span>Owner</span>
                  {renderSortIcon('owner')}
                </div>
              </th>
              <th
                onClick={() => handleSort('created_at')}
                className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 cursor-pointer hover:text-slate-200 select-none"
              >
                <div className="flex items-center gap-1.5">
                  <span>Created</span>
                  {renderSortIcon('created_at')}
                </div>
              </th>
              <th className="px-4 py-3 text-xs font-bold uppercase tracking-wider text-slate-400 text-right">
                Actions
              </th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/70">
            {sortedLeads.map((lead) => {
              const contactFullName = `${lead.first_name || ''} ${lead.last_name}`.trim();
              return (
                <tr
                  key={lead.id}
                  onClick={() => onRowClick(lead)}
                  className="hover:bg-slate-900/80 transition-colors cursor-pointer group"
                >
                  {!hideCheckboxes && (
                    <td className="w-10 px-4 py-3" onClick={(e) => e.stopPropagation()}>
                      <input
                        type="checkbox"
                        checked={selectedLeadIds.includes(lead.id)}
                        onChange={(e) => toggleOne(lead.id, e.target.checked)}
                        className="w-3.5 h-3.5 rounded border-slate-700 text-brand-500 bg-slate-950 focus:ring-brand-500/25 cursor-pointer"
                      />
                    </td>
                  )}

                  <td className="px-4 py-3">
                    <div className="flex items-center gap-2.5">
                      <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-600 to-indigo-600 text-white flex items-center justify-center font-bold text-xs shrink-0 shadow-xs">
                        {initialsOf(lead.title?.[0], lead.title?.[1], 'LD')}
                      </div>
                      <div className="min-w-0">
                        <p className="text-xs font-bold text-slate-100 group-hover:text-brand-400 transition-colors truncate">
                          {lead.title}
                        </p>
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px] text-slate-400 mt-0.5">
                          {contactFullName && <span className="text-slate-300 truncate">{contactFullName}</span>}
                          {contactFullName && lead.company_name && <span className="text-slate-600">•</span>}
                          {lead.company_name && (
                            <span className="inline-flex items-center gap-1 truncate text-slate-400">
                              <Building2 className="w-3 h-3 text-slate-500 shrink-0" />
                              {lead.company_name}
                            </span>
                          )}
                          {lead.phone && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                onCallClick?.(lead.id);
                              }}
                              title={`Click to call ${lead.phone}`}
                              className="inline-flex items-center gap-1 font-mono text-[11px] text-emerald-400 bg-emerald-500/10 hover:bg-emerald-500/20 border border-emerald-500/30 px-1.5 py-0.5 rounded transition-all cursor-pointer shadow-xs active:scale-95"
                            >
                              <Phone className="w-2.5 h-2.5 text-emerald-400" />
                              <span>{lead.phone}</span>
                            </button>
                          )}
                        </div>
                      </div>
                    </div>
                  </td>

                  <td className="px-4 py-3 align-middle">{stagePill(lead)}</td>

                  <td className="px-4 py-3 align-middle text-right font-mono">
                    <span className="text-xs font-bold text-slate-200">
                      {lead.value !== null ? formatMoney(lead.value) : '—'}
                    </span>
                  </td>

                  <td className="px-4 py-3 align-middle">{priorityPill(lead.priority)}</td>

                  <td className="px-4 py-3 align-middle">{ownerBadge(lead)}</td>

                  <td className="px-4 py-3 align-middle">
                    <span className="text-xs text-slate-400 whitespace-nowrap">{relativeTime(lead.created_at)}</span>
                  </td>

                  <td className="px-4 py-3 text-right align-middle" onClick={(e) => e.stopPropagation()}>
                    <div className="flex items-center justify-end gap-1.5 opacity-80 group-hover:opacity-100 transition-opacity">
                      {lead.phone && (
                        <>
                          <button
                            type="button"
                            onClick={() => onCallClick?.(lead.id)}
                            title={`Call ${lead.phone}`}
                            className="p-1.5 border border-slate-800 hover:border-emerald-500/30 hover:bg-emerald-500/10 text-emerald-400 rounded-lg transition-all cursor-pointer"
                          >
                            <Phone className="w-3.5 h-3.5" />
                          </button>
                          <button
                            type="button"
                            onClick={() => onChatClick?.(lead, 'whatsapp')}
                            title="WhatsApp / SMS chat"
                            className="p-1.5 border border-slate-800 hover:border-emerald-500/30 hover:bg-emerald-500/10 text-emerald-400 rounded-lg transition-all cursor-pointer"
                          >
                            <MessageCircle className="w-3.5 h-3.5" />
                          </button>
                        </>
                      )}
                      {(!isEmployee || canDeleteLead) && (
                        <button
                          onClick={(e) => handleEdit(e, lead)}
                          title="Edit lead"
                          className="p-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-lg text-slate-300 transition-all cursor-pointer"
                        >
                          <Edit3 className="w-3.5 h-3.5" />
                        </button>
                      )}
                      {canDeleteLead && (
                        <button
                          onClick={(e) => handleDelete(e, lead)}
                          title="Delete lead"
                          className="p-1.5 border border-slate-800 hover:border-red-500/25 hover:bg-red-500/10 text-red-400 rounded-lg transition-all cursor-pointer"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>

      {/* Mobile: card list */}
      <div className="md:hidden">
        {!hideCheckboxes && sortedLeads.length > 0 && (
          <div className="flex items-center justify-between px-3.5 py-2.5 bg-slate-950/80 border-b border-slate-800 text-xs">
            <label className="flex items-center gap-2 cursor-pointer select-none">
              <input
                type="checkbox"
                checked={allSelected}
                onChange={(e) => toggleAll(e.target.checked)}
                className="w-4 h-4 rounded border-slate-700 text-brand-500 bg-slate-950 cursor-pointer"
              />
              <span className="font-semibold text-slate-200">Select All ({sortedLeads.length})</span>
            </label>
            {selectedLeadIds.length > 0 && (
              <span className="text-brand-400 font-semibold">{selectedLeadIds.length} selected</span>
            )}
          </div>
        )}

        <div className="divide-y divide-slate-800/70">
          {sortedLeads.map((lead) => {
            const contactFullName = `${lead.first_name || ''} ${lead.last_name}`.trim();
            return (
              <div
                key={lead.id}
                onClick={() => onRowClick(lead)}
                className="p-3.5 active:bg-slate-900/60 transition-colors cursor-pointer space-y-2.5"
              >
                <div className="flex items-start justify-between gap-2">
                  <div className="flex items-center gap-2.5">
                    {!hideCheckboxes && (
                      <input
                        type="checkbox"
                        checked={selectedLeadIds.includes(lead.id)}
                        onChange={(e) => { e.stopPropagation(); toggleOne(lead.id, e.target.checked); }}
                        className="w-4 h-4 rounded border-slate-700 text-brand-500 bg-slate-950 cursor-pointer shrink-0"
                      />
                    )}
                    <div>
                      <p className="text-xs font-bold text-slate-100">{lead.title}</p>
                      <p className="text-[11px] text-slate-400">{lead.company_name || contactFullName}</p>
                    </div>
                  </div>
                  <div className="text-right font-mono">
                    <span className="text-xs font-bold text-emerald-400">
                      {lead.value !== null ? formatMoney(lead.value) : '—'}
                    </span>
                  </div>
                </div>

                <div className="flex items-center justify-between text-xs pt-1.5 border-t border-slate-800/60">
                  <div className="flex items-center gap-2">
                    {stagePill(lead)}
                    {priorityPill(lead.priority)}
                  </div>
                  <span className="text-[11px] text-slate-400">{relativeTime(lead.created_at)}</span>
                </div>

                {/* Mobile Quick Action Buttons */}
                <div className="flex items-center justify-between pt-1 border-t border-slate-800/40 text-xs">
                  <div className="text-[11px] text-slate-400 truncate max-w-[140px]">
                    {ownerName(lead)}
                  </div>
                  <div className="flex items-center gap-2" onClick={(e) => e.stopPropagation()}>
                    {lead.phone && (
                      <>
                        <button
                          type="button"
                          onClick={() => onCallClick?.(lead.id)}
                          className="p-1.5 text-emerald-400 border border-slate-800 hover:bg-emerald-500/10 rounded-lg"
                          title="Call Lead"
                        >
                          <Phone className="w-3.5 h-3.5" />
                        </button>
                        <button
                          type="button"
                          onClick={() => onChatClick?.(lead, 'whatsapp')}
                          className="p-1.5 text-emerald-400 border border-slate-800 hover:bg-emerald-500/10 rounded-lg"
                          title="WhatsApp Chat"
                        >
                          <MessageCircle className="w-3.5 h-3.5" />
                        </button>
                      </>
                    )}
                    <button
                      onClick={(e) => handleEdit(e, lead)}
                      className="p-1.5 text-slate-300 border border-slate-800 hover:bg-slate-800 rounded-lg"
                      title="Edit Lead"
                    >
                      <Edit3 className="w-3.5 h-3.5" />
                    </button>
                    {canDeleteLead && (
                      <button
                        onClick={(e) => handleDelete(e, lead)}
                        className="p-1.5 text-red-400 border border-slate-800 hover:bg-red-500/10 rounded-lg"
                        title="Delete Lead"
                      >
                        <Trash2 className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
