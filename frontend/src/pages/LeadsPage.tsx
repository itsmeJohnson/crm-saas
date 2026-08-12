import React, { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { useLeadStore } from '../store/leadStore';
import { LeadTable } from '../components/crm/LeadTable';
import { LeadModal } from '../components/crm/LeadModal';
import { Filters } from '../components/crm/Filters';
import { Pagination } from '../components/crm/Pagination';
import { LeadTimeline } from '../components/crm/LeadTimeline';
import { NotesPanel } from '../components/crm/NotesPanel';
import { LeadAttachments } from '../components/crm/LeadAttachments';
import { LeadReminders } from '../components/crm/LeadReminders';
import { SavedFilters } from '../components/crm/SavedFilters';
import { leadApi } from '../services/leadApi';
import { LeadResponse, LeadReport } from '../services/leadApi';
import { Plus, X, User, Mail, DollarSign, Compass, Upload, ArrowRightLeft, Download, Flame, Phone, LayoutGrid, List, SlidersHorizontal, Users2, TrendingUp, Star } from 'lucide-react';
import { useUserStore } from '../store/userStore';
import { useMetadataStore } from '../store/metadataStore';
import { formatMoney } from '../utils/currency';
import { LeadKanban } from '../components/crm/LeadKanban';
import { LeadCustomFieldsManager } from '../components/crm/LeadCustomFieldsManager';
import { ImportModal } from '../components/leads/ImportModal';
import { AssignmentSettings } from '../components/leads/AssignmentSettings';
import { ImportHistoryTable } from '../components/leads/ImportHistoryTable';
import { useAuthStore } from '../store/authStore';
import { useAnalyticsStore } from '../store/analyticsStore';
import { BulkAssignModal } from '../components/crm/BulkAssignModal';
import { LeadTransferModal } from '../components/crm/LeadTransferModal';
import { useDialerStore } from '../store/dialerStore';
import { ActiveCallDisposition } from '../components/crm/ActiveCallDisposition';

export const LeadsPage: React.FC = () => {
  const { user, features } = useAuthStore();
  // Bulk import (CSV/Excel/Sheets) is a Growth+ plan feature.
  const canBulkImport = (features || []).includes('BULK_IMPORT');
  const { dashboardData, fetchDashboardMetrics } = useAnalyticsStore();
  const { agentState, currentLead, callSpecificLead, error: dialerError } = useDialerStore();
  const [callError, setCallError] = useState<string | null>(null);

  const isTL = dashboardData?.role === 'TeamLeader';
  const isPrivileged = user && (user.role === 'OrgAdmin' || user.role === 'Manager' || isTL);
  // Telecallers (Employees) can place a manual click-to-call to their own leads.
  const canManualCall = user?.role === 'Employee';

  const handleManualCall = async (leadId: string) => {
    setCallError(null);
    // Telephony is configured org-wide by an admin (Settings → Communication →
    // Calling) and applied server-side. Agents send no credentials; if the org
    // hasn't configured it, the backend returns a clear message.
    try {
      await callSpecificLead(leadId);
    } catch (e: any) {
      setCallError(e.response?.data?.detail || 'Failed to place the call.');
    }
  };

  const {
    leads,
    fetchLeads,
    filters,
    setFilters,
    resetFilters,
    pagination,
    setPagination,
    exportLeads,
    bulkUpdate,
    archiveLead,
    restoreLead,
  } = useLeadStore();

  const handleConvert = async (lead: LeadResponse) => {
    if (lead.is_archived && lead.status === 'Converted') return;
    if (!window.confirm(`Convert "${lead.title}" into a contact? The lead will be archived.`)) return;
    try {
      await leadApi.convertLead(lead.id, true);
      setIsDetailOpen(false);
      setDetailLead(null);
      fetchLeads();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Conversion failed');
    }
  };

  const handleArchiveToggle = async (lead: LeadResponse) => {
    try {
      if (lead.is_archived) {
        await restoreLead(lead.id);
      } else {
        await archiveLead(lead.id);
      }
      setIsDetailOpen(false);
      setDetailLead(null);
    } catch (e: any) {
      alert(e.message || 'Operation failed');
    }
  };

  const [isExporting, setIsExporting] = useState(false);

  const handleExport = async (format: 'csv' | 'xlsx') => {
    setIsExporting(true);
    try {
      await exportLeads(format);
    } catch (e: any) {
      alert(e.message || 'Export failed');
    } finally {
      setIsExporting(false);
    }
  };

  const handleBulkPriority = async (priority: string) => {
    try {
      await bulkUpdate({ lead_ids: selectedLeadIds, fields: { priority } });
      setSelectedLeadIds([]);
    } catch (e: any) {
      alert(e.message || 'Bulk update failed');
    }
  };

  const { users, fetchUsers } = useUserStore();
  const activeUsers = users.filter(u => u.is_active);

  const [selectedLeadIds, setSelectedLeadIds] = useState<string[]>([]);
  const [isBulkAssignOpen, setIsBulkAssignOpen] = useState(false);
  const [isLeadTransferOpen, setIsLeadTransferOpen] = useState(false);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedLead, setSelectedLead] = useState<LeadResponse | null>(null);
  const [isImportOpen, setIsImportOpen] = useState(false);

  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailLead, setDetailLead] = useState<LeadResponse | null>(null);

  const [view, setView] = useState<'table' | 'kanban'>('table');
  const [isFieldsOpen, setIsFieldsOpen] = useState(false);
  const [report, setReport] = useState<LeadReport | null>(null);
  const { customFields, fetchBootstrap } = useMetadataStore();
  const leadCustomFields = customFields.filter((f) => f.entity_type === 'lead');

  // Org-wide KPI summary (accurate totals, independent of the paginated table).
  useEffect(() => {
    leadApi.getReport().then(setReport).catch(() => {});
  }, [leads]);

  const [searchParams, setSearchParams] = useSearchParams();
  const queryLeadId = searchParams.get('leadId');

  useEffect(() => {
    fetchLeads();
    if (users.length === 0) fetchUsers();
    fetchDashboardMetrics();
    fetchBootstrap();
  }, []);

  useEffect(() => {
    if (queryLeadId) {
      const loadLead = async () => {
        try {
          const { leadApi } = await import('../services/leadApi');
          const lead = await leadApi.getLead(queryLeadId);
          if (lead) {
            setDetailLead(lead);
            setIsDetailOpen(true);
            searchParams.delete('leadId');
            setSearchParams(searchParams);
          }
        } catch (e) {
          console.error("Failed to auto-load lead details from query param:", e);
        }
      };
      loadLead();
    }
  }, [queryLeadId]);

  const selectedLeadsList = leads.filter(l => selectedLeadIds.includes(l.id));

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
    ? formatMoney(detailLead.value)
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
          {/* View toggle: Table / Kanban */}
          <div className="flex items-center rounded-xl overflow-hidden border border-slate-800 shrink-0">
            <button
              onClick={() => setView('table')}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-sm font-semibold transition-all cursor-pointer ${view === 'table' ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-900 text-slate-400 hover:text-slate-200'}`}
              title="Table view"
            >
              <List className="w-4 h-4" /> Table
            </button>
            <button
              onClick={() => setView('kanban')}
              className={`flex items-center gap-1.5 px-3 py-2.5 text-sm font-semibold border-l border-slate-800 transition-all cursor-pointer ${view === 'kanban' ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-900 text-slate-400 hover:text-slate-200'}`}
              title="Kanban board"
            >
              <LayoutGrid className="w-4 h-4" /> Board
            </button>
          </div>

          {user?.role === 'OrgAdmin' && (
            <button
              onClick={() => setIsFieldsOpen(true)}
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/80 rounded-xl text-sm font-semibold text-slate-300 transition-all cursor-pointer shrink-0"
              title="Manage custom fields"
            >
              <SlidersHorizontal className="w-4 h-4" />
              Custom Fields
            </button>
          )}

          {isPrivileged && <AssignmentSettings />}

          <div className="flex items-center rounded-xl overflow-hidden border border-slate-800 shrink-0">
            <button
              onClick={() => handleExport('csv')}
              disabled={isExporting}
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-900/80 active:bg-slate-900/50 disabled:opacity-50 text-sm font-semibold text-slate-300 transition-all cursor-pointer"
            >
              <Download className="w-4 h-4" />
              Export CSV
            </button>
            <button
              onClick={() => handleExport('xlsx')}
              disabled={isExporting}
              className="px-3 py-2.5 bg-slate-900 border-l border-slate-800 hover:bg-slate-900/80 active:bg-slate-900/50 disabled:opacity-50 text-sm font-semibold text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
              title="Export as Excel"
            >
              XLSX
            </button>
          </div>

          {isPrivileged && canBulkImport && (
            <button
              onClick={() => setIsImportOpen(true)}
              className="flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/80 active:bg-slate-900/50 rounded-xl text-sm font-semibold text-slate-300 transition-all cursor-pointer shrink-0"
            >
              <Upload className="w-4 h-4" />
              Import Leads
            </button>
          )}

          {isPrivileged && (
            <button
              onClick={() => setIsCreateOpen(true)}
              className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 active:from-brand-700 active:to-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer shrink-0"
            >
              <Plus className="w-4 h-4" />
              Add Lead
            </button>
          )}
        </div>
      </div>

      {/* KPI summary strip */}
      {report && (
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-3">
          {[
            { label: 'Total Leads', value: report.total_leads.toLocaleString(), icon: Users2, tint: 'text-brand-400' },
            { label: 'Pipeline Value', value: formatMoney(report.total_value), icon: DollarSign, tint: 'text-emerald-400' },
            { label: 'Conversion Rate', value: `${report.conversion_rate}%`, icon: TrendingUp, tint: 'text-indigo-400' },
            { label: 'Avg. Score', value: Math.round(report.avg_score || 0).toString(), icon: Star, tint: 'text-amber-400' },
          ].map((s) => (
            <div key={s.label} className="glass-panel border border-slate-800/80 rounded-2xl p-4">
              <div className="flex items-center gap-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                <s.icon className={`w-3.5 h-3.5 ${s.tint}`} />
                {s.label}
              </div>
              <p className="text-2xl font-bold text-slate-100 mt-1.5">{s.value}</p>
            </div>
          ))}
        </div>
      )}

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

          {/* Priority filter dropdown */}
          <div className="w-full sm:w-40">
            <select
              value={filters.priority}
              onChange={(e) => setFilters({ priority: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
            >
              <option value="All">All Priorities</option>
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
              <option value="Urgent">Urgent</option>
            </select>
          </div>

          {/* Source filter */}
          <div className="w-full sm:w-40">
            <input
              type="text"
              value={filters.source}
              onChange={(e) => setFilters({ source: e.target.value })}
              placeholder="Source"
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
            />
          </div>

          {/* Dynamic custom-field filters (tenant-defined, filterable) */}
          {leadCustomFields.filter((f) => f.is_active && f.filterable).map((f) => {
            const val = filters.custom_fields[f.key] || '';
            const update = (v: string) => {
              const next = { ...filters.custom_fields };
              if (v === '') delete next[f.key];
              else next[f.key] = v;
              setFilters({ custom_fields: next });
            };
            return (
              <div key={f.id} className="w-full sm:w-44">
                {f.field_type === 'select' ? (
                  <select
                    value={val}
                    onChange={(e) => update(e.target.value)}
                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
                  >
                    <option value="">{f.label}: All</option>
                    {(f.options || []).map((opt) => <option key={opt} value={opt}>{opt}</option>)}
                  </select>
                ) : (
                  <input
                    type={f.field_type === 'number' ? 'number' : f.field_type === 'date' ? 'date' : 'text'}
                    value={val}
                    onChange={(e) => update(e.target.value)}
                    placeholder={f.label}
                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
                  />
                )}
              </div>
            );
          })}

          {/* Include archived toggle */}
          <label className="flex items-center gap-2 px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-300 cursor-pointer select-none shrink-0">
            <input
              type="checkbox"
              checked={filters.include_archived}
              onChange={(e) => setFilters({ include_archived: e.target.checked })}
              className="accent-brand-500"
            />
            Show archived
          </label>

          {/* Saved filters */}
          <SavedFilters currentFilters={filters} onApply={(def) => setFilters(def as any)} />
        </Filters>

        {view === 'table' ? (
          <>
            <LeadTable
              onEditClick={handleEditClick}
              onRowClick={handleRowClick}
              selectedLeadIds={selectedLeadIds}
              onSelectLeads={setSelectedLeadIds}
              hideCheckboxes={!isPrivileged}
            />

            <Pagination
              skip={pagination.skip}
              limit={pagination.limit}
              itemsCount={leads.length}
              onPageChange={(skip) => setPagination({ skip })}
            />
          </>
        ) : (
          <LeadKanban onCardClick={handleRowClick} />
        )}
      </div>

      {isPrivileged && canBulkImport && (
        <div className="pt-6 border-t border-slate-800/60">
          <ImportHistoryTable />
        </div>
      )}

      {/* Creation Modal */}
      <LeadModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />

      {/* Import Modal */}
      <ImportModal isOpen={isImportOpen} onClose={() => setIsImportOpen(false)} onSuccess={fetchLeads} />

      {/* Custom Fields Manager (OrgAdmin) */}
      <LeadCustomFieldsManager isOpen={isFieldsOpen} onClose={() => setIsFieldsOpen(false)} />

      {/* Bulk Assign Modal */}
      <BulkAssignModal 
        isOpen={isBulkAssignOpen} 
        onClose={() => setIsBulkAssignOpen(false)} 
        selectedLeadIds={selectedLeadIds} 
        onSuccess={() => {
          setSelectedLeadIds([]);
          fetchLeads();
        }} 
      />

      {/* Lead Transfer Modal */}
      <LeadTransferModal 
        isOpen={isLeadTransferOpen} 
        onClose={() => setIsLeadTransferOpen(false)} 
        selectedLeads={selectedLeadsList} 
        onSuccess={() => {
          setSelectedLeadIds([]);
          fetchLeads();
        }} 
      />

      {/* Floating Bulk Action Bar */}
      {selectedLeadIds.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 flex items-center gap-4 px-6 py-4 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-bottom-4 duration-300">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-brand-500 flex items-center justify-center text-[10px] font-black text-white">
              {selectedLeadIds.length}
            </span>
            <span className="text-xs text-slate-300 font-semibold">Leads Selected</span>
          </div>
          <div className="w-[1px] h-6 bg-slate-800"></div>
          <div className="flex items-center gap-2">
            <button
              onClick={() => setIsBulkAssignOpen(true)}
              className="px-4 py-2 bg-slate-950 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-xl text-xs font-semibold text-slate-200 transition-all cursor-pointer"
            >
              Assign Selected
            </button>
            <button
              onClick={() => setIsLeadTransferOpen(true)}
              className="px-4 py-2 bg-slate-950 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-xl text-xs font-semibold text-slate-200 transition-all cursor-pointer flex items-center gap-1.5"
            >
              <ArrowRightLeft className="w-3.5 h-3.5" />
              Transfer Selected
            </button>
            <select
              value=""
              onChange={(e) => { if (e.target.value) handleBulkPriority(e.target.value); }}
              className="px-3 py-2 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-xl text-xs font-semibold text-slate-200 transition-all cursor-pointer focus:outline-none"
              title="Set priority for selected leads"
            >
              <option value="">Set Priority…</option>
              <option value="Low">Low</option>
              <option value="Medium">Medium</option>
              <option value="High">High</option>
              <option value="Urgent">Urgent</option>
            </select>
            <button
              onClick={() => setSelectedLeadIds([])}
              className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-xl text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

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

              <div className="flex items-center gap-2 shrink-0">
                {canManualCall && agentState !== 'ACTIVE_CALLING' && detailLead.phone && (
                  <button
                    onClick={() => handleManualCall(detailLead.id)}
                    title="Place a call to this lead"
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-brand-500/10 border border-brand-500/30 hover:bg-brand-500/20 text-xs font-semibold text-brand-300 rounded-xl transition-all cursor-pointer"
                  >
                    <Phone className="w-3.5 h-3.5" /> Call
                  </button>
                )}
                {isPrivileged && !detailLead.converted_contact_id && (
                  <button
                    onClick={() => handleConvert(detailLead)}
                    className="px-3 py-1.5 bg-emerald-500/10 border border-emerald-500/30 hover:bg-emerald-500/20 text-xs font-semibold text-emerald-300 rounded-xl transition-all cursor-pointer"
                  >
                    Convert
                  </button>
                )}
                {isPrivileged && (
                  <button
                    onClick={() => handleArchiveToggle(detailLead)}
                    className="px-3 py-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-950/50 text-xs font-semibold text-slate-300 hover:text-slate-100 rounded-xl transition-all cursor-pointer"
                  >
                    {detailLead.is_archived ? 'Restore' : 'Archive'}
                  </button>
                )}
                <button
                  onClick={() => setIsDetailOpen(false)}
                  className="p-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-950/50 text-slate-400 hover:text-slate-200 rounded-xl transition-all cursor-pointer"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
            </div>

            {/* Scrollable details view */}
            <div className="flex-1 overflow-y-auto p-6 space-y-6">
              {(callError || dialerError) && agentState !== 'ACTIVE_CALLING' && (
                <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs">
                  {callError || dialerError}
                </div>
              )}

              {/* Active Call Control/Disposition */}
              {agentState === 'ACTIVE_CALLING' && currentLead?.id === detailLead.id && (
                <ActiveCallDisposition />
              )}

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
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Priority</p>
                  <p className="text-sm font-semibold mt-0.5 flex items-center gap-1.5">
                    <Flame className={`w-3.5 h-3.5 ${
                      detailLead.priority === 'Urgent' ? 'text-red-400'
                      : detailLead.priority === 'High' ? 'text-amber-400'
                      : detailLead.priority === 'Low' ? 'text-slate-500' : 'text-slate-400'
                    }`} />
                    <span className="text-slate-200">{detailLead.priority}</span>
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Lead Score</p>
                  <p className="text-sm font-semibold text-slate-200 mt-0.5">{detailLead.score}</p>
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
                {detailLead.stage?.name && (
                  <div>
                    <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Pipeline Stage</p>
                    <p className="text-sm font-semibold text-indigo-400 mt-0.5">
                      {detailLead.stage.name}
                    </p>
                  </div>
                )}
              </div>

              {/* Custom fields (tenant-defined) — always shown so the org's schema is
                  visible on every lead, with "—" for values not filled in yet. */}
              {(() => {
                const activeCf = leadCustomFields.filter((f) => f.is_active && f.visible);
                if (activeCf.length === 0) return null;
                const cf = detailLead.custom_fields || {};
                const fmt = (f: typeof activeCf[number]) => {
                  const v = cf[f.key];
                  if (v === undefined || v === null || v === '') return '—';
                  if (f.field_type === 'checkbox') return v ? 'Yes' : 'No';
                  return String(v);
                };
                return (
                  <div>
                    <p className="text-[11px] font-bold text-slate-400 uppercase tracking-wider mb-2">Additional Details</p>
                    <div className="p-4 bg-slate-950/40 border border-slate-800/80 rounded-2xl grid grid-cols-2 gap-4">
                      {activeCf.map((f) => {
                        const v = cf[f.key];
                        const empty = v === undefined || v === null || v === '';
                        return (
                          <div key={f.id}>
                            <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{f.label}</p>
                            <p className={`text-sm font-medium mt-0.5 break-words ${empty ? 'text-slate-500' : 'text-slate-200'}`}>
                              {fmt(f)}
                            </p>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })()}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-800/60">
                {/* Notes logs */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <NotesPanel leadId={detailLead.id} />
                </div>

                {/* Unified activity timeline (notes + activities + audit + tasks + reminders) */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <LeadTimeline leadId={detailLead.id} />
                </div>
              </div>

              {/* Reminders + Attachments */}
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <LeadReminders leadId={detailLead.id} />
                </div>
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <LeadAttachments leadId={detailLead.id} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
