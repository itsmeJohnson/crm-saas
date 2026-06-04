import React, { useEffect, useState } from 'react';
import { useLeadStore } from '../store/leadStore';
import { LeadTable } from '../components/crm/LeadTable';
import { LeadModal } from '../components/crm/LeadModal';
import { Filters } from '../components/crm/Filters';
import { Pagination } from '../components/crm/Pagination';
import { ActivityTimeline } from '../components/crm/ActivityTimeline';
import { NotesPanel } from '../components/crm/NotesPanel';
import { LeadResponse } from '../services/leadApi';
import { Plus, X, User, Mail, DollarSign, Compass, Upload } from 'lucide-react';
import { useUserStore } from '../store/userStore';
import { ImportModal } from '../components/crm/ImportModal';
import { AssignmentToggle } from '../components/crm/AssignmentToggle';

export const LeadsPage: React.FC = () => {
  const {
    leads,
    fetchLeads,
    filters,
    setFilters,
    resetFilters,
    pagination,
    setPagination
  } = useLeadStore();

  const { users, fetchUsers } = useUserStore();
  const activeUsers = users.filter(u => u.is_active);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<LeadResponse | null>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);

  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailLead, setDetailLead] = useState<LeadResponse | null>(null);

  useEffect(() => {
    fetchLeads();
    if (users.length === 0) fetchUsers();
  }, []);

  const handleEditClick = (lead: LeadResponse) => {
    setSelectedLead(lead);
    setIsEditOpen(true);
  };

  const handleRowClick = (lead: LeadResponse) => {
    setDetailLead(lead);
    setIsDetailOpen(true);
  };

  const activeOwner = detailLead && users.find(u => u.id === detailLead.assigned_user_id);
  const activeOwnerName = activeOwner ? `${activeOwner.first_name || ''} ${activeOwner.last_name || ''}`.trim() : 'Unassigned';

  const formattedValue = detailLead && detailLead.value !== null 
    ? new Intl.NumberFormat('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 }).format(detailLead.value)
    : '—';

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
            Leads
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Monitor sales opportunities, deal values, and log interactions to drive conversions.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <AssignmentToggle />

          <button
            onClick={() => setIsImportOpen(true)}
            className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50 rounded-xl text-sm font-semibold text-slate-300 transition-all cursor-pointer shrink-0"
          >
            <Upload className="w-4 h-4" />
            Import Leads
          </button>

          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 active:from-brand-700 active:to-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer shrink-0"
          >
            <Plus className="w-4 h-4" />
            Add Lead
          </button>
        </div>
      </div>

      {/* Filters, Table, Pagination */}
      <div className="space-y-4">
        <Filters
          search={filters.search}
          onSearchChange={(search) => setFilters({ search })}
          placeholder="Search leads by title, name, or company..."
          onReset={resetFilters}
        >
          {/* Status filter dropdown */}
          <div className="w-full sm:w-48">
            <select
              value={filters.status}
              onChange={(e) => setFilters({ status: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
            >
              <option value="All">All Statuses</option>
              <option value="New">New</option>
              <option value="Contacted">Contacted</option>
              <option value="Qualified">Qualified</option>
              <option value="Nurturing">Nurturing</option>
              <option value="Lost">Lost</option>
            </select>
          </div>

          {/* Owner filter dropdown */}
          <div className="w-full sm:w-48">
            <select
              value={filters.assigned_user_id}
              onChange={(e) => setFilters({ assigned_user_id: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
            >
              <option value="All">All Owners</option>
              {activeUsers.map(u => (
                <option key={u.id} value={u.id}>
                  {`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}
                </option>
              ))}
            </select>
          </div>
        </Filters>

        <LeadTable onEditClick={handleEditClick} onRowClick={handleRowClick} />
        
        <Pagination
          skip={pagination.skip}
          limit={pagination.limit}
          itemsCount={leads.length}
          onPageChange={(skip) => setPagination({ skip })}
        />
      </div>

      {/* Creation Modal */}
      <LeadModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />

      {/* Import Modal */}
      <ImportModal isOpen={isImportOpen} onClose={() => setIsImportOpen(false)} onSuccess={fetchLeads} />

      {/* Edit Modal */}
      <LeadModal
        isOpen={isEditOpen}
        lead={selectedLead}
        onClose={() => {
          setIsEditOpen(false);
          setSelectedLead(null);
          if (selectedLead && detailLead && selectedLead.id === detailLead.id) {
            const updated = leads.find(l => l.id === detailLead.id);
            if (updated) setDetailLead(updated);
          }
        }}
      />

      {/* Slide-Over Drawer Details */}
      {isDetailOpen && detailLead && (
        <div className="fixed inset-0 z-40 overflow-hidden flex justify-end">
          <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-xs transition-opacity" onClick={() => setIsDetailOpen(false)}></div>
          
          <div className="relative w-full max-w-2xl bg-slate-900 border-l border-slate-800/80 shadow-2xl flex flex-col h-full z-10 animate-slide-in">
            {/* Header */}
            <div className="p-6 border-b border-slate-800 flex items-start justify-between gap-4">
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/30 flex items-center justify-center font-bold text-brand-300 text-lg shrink-0">
                  {detailLead.title.substring(0, 2).toUpperCase()}
                </div>
                <div className="overflow-hidden">
                  <h2 className="text-xl font-bold text-slate-100 truncate">
                    {detailLead.title}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5 font-medium flex items-center gap-1">
                    <span>
                      {`${detailLead.first_name || ''} ${detailLead.last_name}`.trim()}
                    </span>
                    {detailLead.company_name && (
                      <>
                        <span className="text-slate-600">•</span>
                        <span className="truncate">{detailLead.company_name}</span>
                      </>
                    )}
                  </p>
                </div>
              </div>

              <button
                onClick={() => setIsDetailOpen(false)}
                className="p-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-950/50 text-slate-400 hover:text-slate-200 rounded-xl transition-all cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable details view */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {/* Quick Details Card */}
              <div className="p-4 bg-slate-950/40 border border-slate-800/80 rounded-2xl grid grid-cols-2 gap-4">
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Opportunity Value</p>
                  <p className="text-sm font-semibold text-slate-200 mt-0.5 flex items-center gap-1.5">
                    <DollarSign className="w-4 h-4 text-emerald-400 shrink-0" />
                    <span>{formattedValue}</span>
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Lead Status</p>
                  <span className="inline-flex mt-1.5 text-xs font-semibold text-brand-300">
                    {detailLead.status}
                  </span>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Lead Source</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5 flex items-center gap-1.5">
                    <Compass className="w-3.5 h-3.5 text-indigo-400" />
                    <span>{detailLead.source || '—'}</span>
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Owner</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-brand-400" />
                    {activeOwnerName}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Email</p>
                  {detailLead.email ? (
                    <a
                      href={`mailto:${detailLead.email}`}
                      className="text-sm font-medium text-brand-400 hover:text-brand-300 mt-0.5 flex items-center gap-1.5 truncate"
                    >
                      <Mail className="w-3.5 h-3.5" />
                      {detailLead.email}
                    </a>
                  ) : (
                    <p className="text-sm font-medium text-slate-200 mt-0.5">—</p>
                  )}
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Phone</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5">{detailLead.phone || '—'}</p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-800/60">
                {/* Notes logs */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <NotesPanel leadId={detailLead.id} />
                </div>

                {/* Activities timeline */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <ActivityTimeline leadId={detailLead.id} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
