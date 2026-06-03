import React, { useEffect } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { useUserStore } from '../../store/userStore';
import { LeadResponse } from '../../services/leadApi';
import { Edit3, Trash2, Loader2, AlertCircle } from 'lucide-react';

interface LeadTableProps {
  onEditClick: (lead: LeadResponse) => void;
  onRowClick: (lead: LeadResponse) => void;
}

export const LeadTable: React.FC<LeadTableProps> = ({
  onEditClick,
  onRowClick
}) => {
  const { leads, isLoading, error, deleteLead } = useLeadStore();
  const { users, fetchUsers } = useUserStore();

  useEffect(() => {
    if (users.length === 0) {
      fetchUsers();
    }
  }, []);

  const handleDelete = async (e: React.MouseEvent, lead: LeadResponse) => {
    e.stopPropagation();
    if (window.confirm(`Are you sure you want to delete lead: ${lead.title}? This will also soft delete any related activities and notes.`)) {
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

  const getStatusBadge = (status: string) => {
    switch (status) {
      case 'New':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-blue-500/10 text-blue-400 border border-blue-500/20">
            New
          </span>
        );
      case 'Contacted':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-amber-500/10 text-amber-400 border border-amber-500/20">
            Contacted
          </span>
        );
      case 'Qualified':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
            Qualified
          </span>
        );
      case 'Nurturing':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-purple-500/10 text-purple-400 border border-purple-500/20">
            Nurturing
          </span>
        );
      case 'Lost':
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-400 border border-slate-700">
            Lost
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-semibold bg-slate-800 text-slate-300 border border-slate-700">
            {status}
          </span>
        );
    }
  };

  if (isLoading && leads.length === 0) {
    return (
      <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
        <p className="text-sm">Loading leads...</p>
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

  return (
    <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800/80 bg-slate-900/40">
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Lead</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Value</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Owner</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/65 bg-slate-950/20">
            {leads.length === 0 ? (
              <tr>
                <td colSpan={5} className="px-6 py-12 text-center text-sm text-slate-500">
                  No leads found. Add a lead opportunity to get started.
                </td>
              </tr>
            ) : (
              leads.map((lead) => {
                const initials = lead.title.substring(0, 2).toUpperCase() || 'LD';
                const contactFullName = `${lead.first_name || ''} ${lead.last_name}`.trim();
                
                const ownerUser = users.find(u => u.id === lead.assigned_user_id);
                const ownerName = ownerUser ? `${ownerUser.first_name || ''} ${ownerUser.last_name || ''}`.trim() : 'Unassigned';

                const formattedValue = lead.value !== null 
                  ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(lead.value)
                  : '—';

                return (
                  <tr
                    key={lead.id}
                    onClick={() => onRowClick(lead)}
                    className="hover:bg-slate-900/30 transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/25 flex items-center justify-center font-bold text-brand-300 text-sm">
                          {initials}
                        </div>
                        <div className="overflow-hidden">
                          <p className="text-sm font-semibold text-slate-200 truncate">{lead.title}</p>
                          <div className="flex flex-wrap items-center gap-x-2 text-xs text-slate-400 mt-0.5">
                            {contactFullName && <span className="text-slate-300">{contactFullName}</span>}
                            {contactFullName && lead.company_name && <span className="text-slate-600">•</span>}
                            {lead.company_name && <span className="truncate">{lead.company_name}</span>}
                          </div>
                        </div>
                      </div>
                    </td>

                    <td className="px-6 py-4 align-middle">
                      <span className="text-sm font-medium text-slate-200">
                        {formattedValue}
                      </span>
                    </td>

                    <td className="px-6 py-4 align-middle">
                      {getStatusBadge(lead.status)}
                    </td>

                    <td className="px-6 py-4 align-middle">
                      <span className="text-sm text-slate-300">
                        {ownerName}
                      </span>
                    </td>

                    <td className="px-6 py-4 text-right align-middle">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => handleEdit(e, lead)}
                          title="Edit Lead"
                          className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-lg text-slate-300 transition-all cursor-pointer"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, lead)}
                          title="Delete Lead"
                          className="p-2 border border-slate-800 hover:border-red-500/25 hover:bg-red-500/10 text-red-400 rounded-lg transition-all cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                );
              })
            )}
          </tbody>
        </table>
      </div>
    </div>
  );
};
