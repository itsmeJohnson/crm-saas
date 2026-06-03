import React, { useEffect, useState } from 'react';
import { useContactStore } from '../store/contactStore';
import { useCompanyStore } from '../store/companyStore';
import { ContactTable } from '../components/crm/ContactTable';
import { ContactModal } from '../components/crm/ContactModal';
import { Filters } from '../components/crm/Filters';
import { Pagination } from '../components/crm/Pagination';
import { ActivityTimeline } from '../components/crm/ActivityTimeline';
import { NotesPanel } from '../components/crm/NotesPanel';
import { ContactResponse } from '../services/contactApi';
import { Plus, X, User, Mail, Building } from 'lucide-react';
import { useUserStore } from '../store/userStore';

export const ContactsPage: React.FC = () => {
  const {
    contacts,
    fetchContacts,
    filters,
    setFilters,
    resetFilters,
    pagination,
    setPagination
  } = useContactStore();

  const { companies, fetchCompanies } = useCompanyStore();
  const { users, fetchUsers } = useUserStore();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedContact, setSelectedContact] = useState<ContactResponse | null>(null);

  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailContact, setDetailContact] = useState<ContactResponse | null>(null);

  useEffect(() => {
    fetchContacts();
    if (companies.length === 0) fetchCompanies();
    if (users.length === 0) fetchUsers();
  }, []);

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

        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 active:from-brand-700 active:to-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer shrink-0"
        >
          <Plus className="w-4 h-4" />
          Add Contact
        </button>
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
        </Filters>

        <ContactTable onEditClick={handleEditClick} onRowClick={handleRowClick} />
        
        <Pagination
          skip={pagination.skip}
          limit={pagination.limit}
          itemsCount={contacts.length}
          onPageChange={(skip) => setPagination({ skip })}
        />
      </div>

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

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-800/60">
                {/* Notes logs */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <NotesPanel contactId={detailContact.id} />
                </div>

                {/* Activities timeline */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <ActivityTimeline contactId={detailContact.id} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
