import React, { useEffect, useState } from 'react';
import { useContactStore } from '../store/contactStore';
import { useCompanyStore } from '../store/companyStore';
import { ContactTable } from '../components/crm/ContactTable';
import { ContactModal } from '../components/crm/ContactModal';
import { Filters } from '../components/crm/Filters';
import { Pagination } from '../components/crm/Pagination';
import { ActivityTimeline } from '../components/crm/ActivityTimeline';
import { NotesPanel } from '../components/crm/NotesPanel';
import { ContactAttachments } from '../components/crm/ContactAttachments';
import { ContactCommunications } from '../components/crm/ContactCommunications';
import { ContactRelationships } from '../components/crm/ContactRelationships';
import { CustomFieldsManager } from '../components/crm/CustomFieldsManager';
import { ContactResponse, contactApi } from '../services/contactApi';
import { Plus, X, User, Mail, Building, Download, Upload, Settings2, Tag } from 'lucide-react';
import { useUserStore } from '../store/userStore';

export const ContactsPage: React.FC = () => {
  const {
    contacts,
    fetchContacts,
    filters,
    setFilters,
    resetFilters,
    pagination,
    setPagination,
    exportContacts,
    bulkUpdate,
    bulkDelete,
  } = useContactStore();

  const { companies, fetchCompanies } = useCompanyStore();
  const { users, fetchUsers } = useUserStore();
  const activeUsers = users.filter((u) => u.is_active);

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedContact, setSelectedContact] = useState<ContactResponse | null>(null);

  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailContact, setDetailContact] = useState<ContactResponse | null>(null);

  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [isFieldsOpen, setIsFieldsOpen] = useState(false);
  const fileInputRef = React.useRef<HTMLInputElement>(null);

  useEffect(() => {
    fetchContacts();
    if (companies.length === 0) fetchCompanies();
    if (users.length === 0) fetchUsers();
  }, []);

  const handleExport = async (format: 'csv' | 'xlsx') => {
    try {
      await exportContacts(format);
    } catch (e: any) {
      alert(e.message || 'Export failed');
    }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const res = await contactApi.importContacts(file);
      alert(`Imported ${res.created} contact(s); ${res.failed} failed.`);
      fetchContacts();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Import failed');
    } finally {
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleBulkAssign = async (userId: string) => {
    try {
      await bulkUpdate({ contact_ids: selectedIds, fields: { assigned_user_id: userId } });
      setSelectedIds([]);
    } catch (e: any) {
      alert(e.message || 'Bulk assign failed');
    }
  };

  const handleBulkTag = async () => {
    const tag = window.prompt('Tag to add to selected contacts:');
    if (!tag) return;
    try {
      await bulkUpdate({ contact_ids: selectedIds, fields: { add_tags: [tag.trim()] } });
      setSelectedIds([]);
    } catch (e: any) {
      alert(e.message || 'Bulk tag failed');
    }
  };

  const handleBulkDelete = async () => {
    if (!window.confirm(`Delete ${selectedIds.length} contact(s)?`)) return;
    try {
      await bulkDelete(selectedIds);
      setSelectedIds([]);
    } catch (e: any) {
      alert(e.message || 'Bulk delete failed');
    }
  };

  const handleEditClick = (contact: ContactResponse) => {
    setSelectedContact(contact);
    setIsEditOpen(true);
  };

  const handleRowClick = (contact: ContactResponse) => {
    setDetailContact(contact);
    setIsDetailOpen(true);
  };

  const activeOwner = detailContact && users.find(u => u.id === detailContact.assigned_user_id);
  const activeOwnerName = activeOwner ? `${activeOwner.first_name || ''} ${activeOwner.last_name || ''}`.trim() : 'Unassigned';
  
  const linkedCompany = detailContact && companies.find(c => c.id === detailContact.company_id);
  const companyName = linkedCompany ? linkedCompany.name : '—';

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
            Contacts
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Manage customers, log operations, track company linkages, and view recent activities.
          </p>
        </div>

        <div className="flex flex-wrap items-center gap-3">
          <div className="flex items-center rounded-xl overflow-hidden border border-slate-800 shrink-0">
            <button onClick={() => handleExport('csv')} className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 hover:bg-slate-900/80 text-sm font-semibold text-slate-300 transition-all cursor-pointer">
              <Download className="w-4 h-4" /> Export
            </button>
            <button onClick={() => handleExport('xlsx')} className="px-3 py-2.5 bg-slate-900 border-l border-slate-800 hover:bg-slate-900/80 text-sm font-semibold text-slate-400 hover:text-slate-200 transition-all cursor-pointer" title="Export as Excel">
              XLSX
            </button>
          </div>

          <button onClick={() => fileInputRef.current?.click()} className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-sm font-semibold text-slate-300 transition-all cursor-pointer shrink-0">
            <Upload className="w-4 h-4" /> Import
          </button>
          <input ref={fileInputRef} type="file" accept=".csv,.xlsx,.xls" className="hidden" onChange={handleImport} />

          <button onClick={() => setIsFieldsOpen(true)} className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-sm font-semibold text-slate-300 transition-all cursor-pointer shrink-0" title="Manage custom fields">
            <Settings2 className="w-4 h-4" /> Fields
          </button>

          <button
            onClick={() => setIsCreateOpen(true)}
            className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 active:from-brand-700 active:to-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer shrink-0"
          >
            <Plus className="w-4 h-4" />
            Add Contact
          </button>
        </div>
      </div>

      {/* Filters, Table, Pagination */}
      <div className="space-y-4">
        <Filters
          search={filters.search}
          onSearchChange={(search) => setFilters({ search })}
          placeholder="Search contacts by name or email..."
          onReset={resetFilters}
        >
          {/* Company filter inside slot */}
          <div className="w-full sm:w-56">
            <select
              value={filters.company_id}
              onChange={(e) => setFilters({ company_id: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 focus:ring-2 focus:ring-brand-500/10 transition-all"
            >
              <option value="All">All Companies</option>
              {companies.map(c => (
                <option key={c.id} value={c.id}>{c.name}</option>
              ))}
            </select>
          </div>

          {/* Owner filter */}
          <div className="w-full sm:w-48">
            <select
              value={filters.assigned_user_id}
              onChange={(e) => setFilters({ assigned_user_id: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 transition-all"
            >
              <option value="All">All Owners</option>
              {activeUsers.map((u) => (
                <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>
              ))}
            </select>
          </div>

          {/* Tag filter */}
          <div className="w-full sm:w-40">
            <input
              type="text"
              value={filters.tag}
              onChange={(e) => setFilters({ tag: e.target.value })}
              placeholder="Tag"
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50 transition-all"
            />
          </div>

          {/* Has email filter */}
          <div className="w-full sm:w-40">
            <select
              value={filters.has_email}
              onChange={(e) => setFilters({ has_email: e.target.value })}
              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 transition-all"
            >
              <option value="All">Email: any</option>
              <option value="yes">Has email</option>
              <option value="no">No email</option>
            </select>
          </div>
        </Filters>

        <ContactTable onEditClick={handleEditClick} onRowClick={handleRowClick} selectedIds={selectedIds} onSelect={setSelectedIds} />
        
        <Pagination
          skip={pagination.skip}
          limit={pagination.limit}
          itemsCount={contacts.length}
          onPageChange={(skip) => setPagination({ skip })}
        />
      </div>

      {/* Custom Fields Manager */}
      <CustomFieldsManager isOpen={isFieldsOpen} onClose={() => setIsFieldsOpen(false)} />

      {/* Floating Bulk Action Bar */}
      {selectedIds.length > 0 && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-30 flex items-center gap-4 px-6 py-4 bg-slate-900/90 border border-slate-800 rounded-2xl shadow-2xl backdrop-blur-md">
          <div className="flex items-center gap-2">
            <span className="w-5 h-5 rounded-full bg-brand-500 flex items-center justify-center text-[10px] font-black text-white">{selectedIds.length}</span>
            <span className="text-xs text-slate-300 font-semibold">Selected</span>
          </div>
          <div className="w-[1px] h-6 bg-slate-800"></div>
          <div className="flex items-center gap-2">
            <select
              value=""
              onChange={(e) => { if (e.target.value) handleBulkAssign(e.target.value); }}
              className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-xl text-xs font-semibold text-slate-200 cursor-pointer focus:outline-none"
              title="Assign selected"
            >
              <option value="">Assign to…</option>
              {activeUsers.map((u) => (
                <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>
              ))}
            </select>
            <button onClick={handleBulkTag} className="flex items-center gap-1.5 px-4 py-2 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-xl text-xs font-semibold text-slate-200 cursor-pointer">
              <Tag className="w-3.5 h-3.5" /> Add Tag
            </button>
            <button onClick={handleBulkDelete} className="px-4 py-2 bg-red-500/10 border border-red-500/30 hover:bg-red-500/20 rounded-xl text-xs font-semibold text-red-300 cursor-pointer">
              Delete
            </button>
            <button onClick={() => setSelectedIds([])} className="p-2 border border-slate-800 hover:border-slate-700 rounded-xl text-slate-400 hover:text-slate-200 cursor-pointer">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {/* Creation Modal */}
      <ContactModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />

      {/* Edit Modal */}
      <ContactModal
        isOpen={isEditOpen}
        contact={selectedContact}
        onClose={() => {
          setIsEditOpen(false);
          setSelectedContact(null);
          if (selectedContact && detailContact && selectedContact.id === detailContact.id) {
            const updated = contacts.find(c => c.id === detailContact.id);
            if (updated) setDetailContact(updated);
          }
        }}
      />

      {/* Slide-Over Drawer Details */}
      {isDetailOpen && detailContact && (
        <div className="fixed inset-0 z-40 overflow-hidden flex justify-end">
          <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-xs transition-opacity" onClick={() => setIsDetailOpen(false)}></div>
          
          <div className="relative w-full max-w-2xl bg-slate-900 border-l border-slate-800/80 shadow-2xl flex flex-col h-full z-10 animate-slide-in">
            {/* Header */}
            <div className="p-6 border-b border-slate-800 flex items-start justify-between gap-4">
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/30 flex items-center justify-center font-bold text-brand-300 text-lg shrink-0">
                  {`${detailContact.first_name?.[0] || ''}${detailContact.last_name?.[0] || ''}`.toUpperCase()}
                </div>
                <div className="overflow-hidden">
                  <h2 className="text-xl font-bold text-slate-100 truncate">
                    {detailContact.first_name} {detailContact.last_name}
                  </h2>
                  <p className="text-xs text-slate-400 mt-0.5 font-medium">
                    {detailContact.job_title || 'Contact Profile'}
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
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Company</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5 flex items-center gap-1.5">
                    <Building className="w-3.5 h-3.5 text-indigo-400" />
                    <span className="truncate">{companyName}</span>
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Phone</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5">{detailContact.phone || '—'}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Email</p>
                  {detailContact.email ? (
                    <a
                      href={`mailto:${detailContact.email}`}
                      className="text-sm font-medium text-brand-400 hover:text-brand-300 mt-0.5 flex items-center gap-1.5 truncate"
                    >
                      <Mail className="w-3.5 h-3.5" />
                      {detailContact.email}
                    </a>
                  ) : (
                    <p className="text-sm font-medium text-slate-200 mt-0.5">—</p>
                  )}
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Owner</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-brand-400" />
                    {activeOwnerName}
                  </p>
                </div>
              </div>

              {/* Tags */}
              {detailContact.tags && detailContact.tags.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {detailContact.tags.map((t) => (
                    <span key={t} className="inline-flex items-center gap-1 px-2.5 py-1 bg-brand-500/10 border border-brand-500/25 rounded-lg text-xs font-medium text-brand-300">
                      {t}
                    </span>
                  ))}
                </div>
              )}

              {/* Custom fields */}
              {detailContact.custom_fields && Object.keys(detailContact.custom_fields).length > 0 && (
                <div className="p-4 bg-slate-950/40 border border-slate-800/80 rounded-2xl grid grid-cols-2 gap-4">
                  {Object.entries(detailContact.custom_fields).map(([k, v]) => (
                    <div key={k}>
                      <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{k}</p>
                      <p className="text-sm font-medium text-slate-200 mt-0.5">{String(v)}</p>
                    </div>
                  ))}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-800/60">
                {/* Notes logs */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <NotesPanel contactId={detailContact.id} />
                </div>

                {/* Activities timeline */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <ActivityTimeline contactId={detailContact.id} />
                </div>

                {/* Communication history */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <ContactCommunications contactId={detailContact.id} />
                </div>

                {/* Attachments */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <ContactAttachments contactId={detailContact.id} />
                </div>

                {/* Relationships */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl md:col-span-2">
                  <ContactRelationships contactId={detailContact.id} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
