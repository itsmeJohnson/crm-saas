import React, { useEffect } from 'react';
import { useCompanyStore } from '../../store/companyStore';
import { useUserStore } from '../../store/userStore';
import { CompanyResponse } from '../../services/companyApi';
import { Edit3, Trash2, Globe, Loader2, AlertCircle } from 'lucide-react';

interface CompanyTableProps {
  onEditClick: (company: CompanyResponse) => void;
  onRowClick: (company: CompanyResponse) => void;
}

export const CompanyTable: React.FC<CompanyTableProps> = ({
  onEditClick,
  onRowClick
}) => {
  const { companies, isLoading, error, deleteCompany } = useCompanyStore();
  const { users, fetchUsers } = useUserStore();

  useEffect(() => {
    if (users.length === 0) {
      fetchUsers();
    }
  }, []);

  const handleDelete = async (e: React.MouseEvent, company: CompanyResponse) => {
    e.stopPropagation(); // Avoid triggering row click details panel
    if (window.confirm(`Are you sure you want to delete ${company.name}? This will also soft delete any related activities and notes.`)) {
      try {
        await deleteCompany(company.id);
      } catch (err: any) {
        alert(err.message || 'Deletion failed');
      }
    }
  };

  const handleEdit = (e: React.MouseEvent, company: CompanyResponse) => {
    e.stopPropagation();
    onEditClick(company);
  };

  if (isLoading && companies.length === 0) {
    return (
      <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
        <p className="text-sm">Loading companies...</p>
      </div>
    );
  }

  if (error && companies.length === 0) {
    return (
      <div className="glass-panel p-12 rounded-2xl border border-red-900/30 bg-red-950/10 flex flex-col items-center justify-center text-red-400">
        <AlertCircle className="w-8 h-8 mb-2" />
        <p className="font-semibold mb-2">Error Loading Companies</p>
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
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Company</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Industry</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Owner</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/65 bg-slate-950/20">
            {companies.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-12 text-center text-sm text-slate-500">
                  No companies found. Add a company to get started.
                </td>
              </tr>
            ) : (
              companies.map((company) => {
                const initials = company.name.substring(0, 2).toUpperCase() || 'CO';
                const ownerUser = users.find(u => u.id === company.assigned_user_id);
                const ownerName = ownerUser ? `${ownerUser.first_name || ''} ${ownerUser.last_name || ''}`.trim() : 'Unassigned';

                return (
                  <tr
                    key={company.id}
                    onClick={() => onRowClick(company)}
                    className="hover:bg-slate-900/30 transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-indigo-500/20 to-brand-500/20 border border-brand-500/25 flex items-center justify-center font-bold text-indigo-300 text-sm">
                          {initials}
                        </div>
                        <div className="overflow-hidden">
                          <p className="text-sm font-semibold text-slate-200 truncate">{company.name}</p>
                          {company.domain && (
                            <p className="text-xs text-slate-400 flex items-center gap-1.5 truncate mt-0.5">
                              <Globe className="w-3.5 h-3.5 text-slate-500" />
                              {company.domain}
                            </p>
                          )}
                        </div>
                      </div>
                    </td>

                    <td className="px-6 py-4 align-middle">
                      <span className="text-sm text-slate-300">
                        {company.industry || '—'}
                      </span>
                    </td>

                    <td className="px-6 py-4 align-middle">
                      <span className="text-sm text-slate-300">
                        {ownerName}
                      </span>
                    </td>

                    <td className="px-6 py-4 text-right align-middle">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => handleEdit(e, company)}
                          title="Edit Company"
                          className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-lg text-slate-300 transition-all cursor-pointer"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, company)}
                          title="Delete Company"
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
