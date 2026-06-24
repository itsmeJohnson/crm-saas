import React, { useEffect, useState } from 'react';
import { useCompanyStore } from '../store/companyStore';
import { CompanyTable } from '../components/crm/CompanyTable';
import { CompanyModal } from '../components/crm/CompanyModal';
import { Filters } from '../components/crm/Filters';
import { Pagination } from '../components/crm/Pagination';
import { ActivityTimeline } from '../components/crm/ActivityTimeline';
import { NotesPanel } from '../components/crm/NotesPanel';
import { CompanyResponse } from '../services/companyApi';
import { Plus, X, Globe, User, Calendar, ExternalLink } from 'lucide-react';
import { useUserStore } from '../store/userStore';

export const CompaniesPage: React.FC = () => {
  const {
    companies,
    fetchCompanies,
    filters,
    setFilters,
    resetFilters,
    pagination,
    setPagination
  } = useCompanyStore();

  const { users, fetchUsers } = useUserStore();

  const [isCreateOpen, setIsCreateOpen] = useState(false);
  const [isEditOpen, setIsEditOpen] = useState(false);
  const [selectedCompany, setSelectedCompany] = useState<CompanyResponse | null>(null);

  const [isDetailOpen, setIsDetailOpen] = useState(false);
  const [detailCompany, setDetailCompany] = useState<CompanyResponse | null>(null);

  useEffect(() => {
    fetchCompanies();
    if (users.length === 0) fetchUsers();
  }, []);

  const handleEditClick = (company: CompanyResponse) => {
    setSelectedCompany(company);
    setIsEditOpen(true);
  };

  const handleRowClick = (company: CompanyResponse) => {
    setDetailCompany(company);
    setIsDetailOpen(true);
  };

  const activeOwner = detailCompany && users.find(u => u.id === detailCompany.assigned_user_id);
  const activeOwnerName = activeOwner ? `${activeOwner.first_name || ''} ${activeOwner.last_name || ''}`.trim() : 'Unassigned';

  return (
    <div className="space-y-6">
      {/* Title Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
            Companies
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Maintain and browse accounts, industries, and view associated activities or notes.
          </p>
        </div>

        <button
          onClick={() => setIsCreateOpen(true)}
          className="flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 active:from-brand-700 active:to-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer shrink-0"
        >
          <Plus className="w-4 h-4" />
          Add Company
        </button>
      </div>

      {/* Filters, Table, Pagination */}
      <div className="space-y-4">
        <Filters
          search={filters.search}
          onSearchChange={(search) => setFilters({ search })}
          placeholder="Search by company name or domain..."
          onReset={resetFilters}
        />
        <CompanyTable onEditClick={handleEditClick} onRowClick={handleRowClick} />
        <Pagination
          skip={pagination.skip}
          limit={pagination.limit}
          itemsCount={companies.length}
          onPageChange={(skip) => setPagination({ skip })}
        />
      </div>

      {/* Creation Modal */}
      <CompanyModal isOpen={isCreateOpen} onClose={() => setIsCreateOpen(false)} />

      {/* Edit Modal */}
      <CompanyModal
        isOpen={isEditOpen}
        company={selectedCompany}
        onClose={() => {
          setIsEditOpen(false);
          setSelectedCompany(null);
          // If we edited the company that is currently open in detail slideover, update it
          if (selectedCompany && detailCompany && selectedCompany.id === detailCompany.id) {
            // Refetch current details
            const updated = companies.find(c => c.id === detailCompany.id);
            if (updated) setDetailCompany(updated);
          }
        }}
      />

      {/* Slide-Over Drawer Details */}
      {isDetailOpen && detailCompany && (
        <div className="fixed inset-0 z-40 overflow-hidden flex justify-end">
          {/* Backdrop */}
          <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-xs transition-opacity" onClick={() => setIsDetailOpen(false)}></div>
          
          {/* Flyout Panel */}
          <div className="relative w-full max-w-2xl bg-slate-900 border-l border-slate-800/80 shadow-2xl flex flex-col h-full z-10 animate-slide-in">
            {/* Header */}
            <div className="p-6 border-b border-slate-800 flex items-start justify-between gap-4">
              <div className="flex items-center gap-3 overflow-hidden">
                <div className="w-12 h-12 rounded-2xl bg-gradient-to-tr from-indigo-500/20 to-brand-500/20 border border-brand-500/30 flex items-center justify-center font-bold text-indigo-300 text-lg shrink-0">
                  {detailCompany.name.substring(0, 2).toUpperCase()}
                </div>
                <div className="overflow-hidden">
                  <h2 className="text-xl font-bold text-slate-100 truncate" title={detailCompany.name}>
                    {detailCompany.name}
                  </h2>
                  {detailCompany.website && (
                    <a
                      href={detailCompany.website.startsWith('http') ? detailCompany.website : `https://${detailCompany.website}`}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="text-xs text-brand-400 hover:text-brand-300 flex items-center gap-1.5 mt-0.5"
                    >
                      <Globe className="w-3.5 h-3.5" />
                      {detailCompany.website}
                      <ExternalLink className="w-3 h-3" />
                    </a>
                  )}
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
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Industry</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5">{detailCompany.industry || '—'}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Phone</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5">{detailCompany.phone || '—'}</p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Owner</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5 flex items-center gap-1.5">
                    <User className="w-3.5 h-3.5 text-brand-400" />
                    {activeOwnerName}
                  </p>
                </div>
                <div>
                  <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">Created</p>
                  <p className="text-sm font-medium text-slate-200 mt-0.5 flex items-center gap-1.5">
                    <Calendar className="w-3.5 h-3.5 text-slate-500" />
                    {new Date(detailCompany.created_at).toLocaleDateString()}
                  </p>
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-6 pt-4 border-t border-slate-800/60">
                {/* Notes logs */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <NotesPanel companyId={detailCompany.id} />
                </div>

                {/* Activities timeline */}
                <div className="glass-panel border border-slate-800/85 p-4.5 rounded-2xl">
                  <ActivityTimeline companyId={detailCompany.id} />
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
