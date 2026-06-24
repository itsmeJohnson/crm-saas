import React, { useEffect } from 'react';
import { useContactStore } from '../../store/contactStore';
import { useCompanyStore } from '../../store/companyStore';
import { useUserStore } from '../../store/userStore';
import { ContactResponse } from '../../services/contactApi';
import { Edit3, Trash2, Mail, Building2, Loader2, AlertCircle } from 'lucide-react';

interface ContactTableProps {
  onEditClick: (contact: ContactResponse) => void;
  onRowClick: (contact: ContactResponse) => void;
}

export const ContactTable: React.FC<ContactTableProps> = ({
  onEditClick,
  onRowClick
}) => {
  const { contacts, isLoading, error, deleteContact } = useContactStore();
  const { companies, fetchCompanies } = useCompanyStore();
  const { users, fetchUsers } = useUserStore();

  useEffect(() => {
    if (companies.length === 0) fetchCompanies();
    if (users.length === 0) fetchUsers();
  }, []);

  const handleDelete = async (e: React.MouseEvent, contact: ContactResponse) => {
    e.stopPropagation();
    const fullName = `${contact.first_name} ${contact.last_name}`;
    if (window.confirm(`Are you sure you want to delete ${fullName}? This will also soft delete any related activities and notes.`)) {
      try {
        await deleteContact(contact.id);
      } catch (err: any) {
        alert(err.message || 'Deletion failed');
      }
    }
  };

  const handleEdit = (e: React.MouseEvent, contact: ContactResponse) => {
    e.stopPropagation();
    onEditClick(contact);
  };

  if (isLoading && contacts.length === 0) {
    return (
      <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-400">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
        <p className="text-sm">Loading contacts...</p>
      </div>
    );
  }

  if (error && contacts.length === 0) {
    return (
      <div className="glass-panel p-12 rounded-2xl border border-red-900/30 bg-red-950/10 flex flex-col items-center justify-center text-red-400">
        <AlertCircle className="w-8 h-8 mb-2" />
        <p className="font-semibold mb-2">Error Loading Contacts</p>
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
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Contact</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Company</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Owner</th>
              <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/65 bg-slate-950/20">
            {contacts.length === 0 ? (
              <tr>
                <td colSpan={4} className="px-6 py-12 text-center text-sm text-slate-500">
                  No contacts found. Add a contact to get started.
                </td>
              </tr>
            ) : (
              contacts.map((contact) => {
                const fullName = `${contact.first_name} ${contact.last_name}`;
                const initials = `${contact.first_name?.[0] || ''}${contact.last_name?.[0] || ''}`.toUpperCase() || 'CO';
                
                const linkedCompany = companies.find(c => c.id === contact.company_id);
                const companyName = linkedCompany ? linkedCompany.name : '—';

                const ownerUser = users.find(u => u.id === contact.assigned_user_id);
                const ownerName = ownerUser ? `${ownerUser.first_name || ''} ${ownerUser.last_name || ''}`.trim() : 'Unassigned';

                return (
                  <tr
                    key={contact.id}
                    onClick={() => onRowClick(contact)}
                    className="hover:bg-slate-900/30 transition-colors cursor-pointer"
                  >
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-xl bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/25 flex items-center justify-center font-bold text-brand-300 text-sm">
                          {initials}
                        </div>
                        <div className="overflow-hidden">
                          <p className="text-sm font-semibold text-slate-200 truncate">{fullName}</p>
                          <div className="flex flex-wrap items-center gap-x-2 gap-y-0.5 text-xs text-slate-400 mt-0.5">
                            {contact.job_title && (
                              <span className="text-slate-300 font-medium">{contact.job_title}</span>
                            )}
                            {contact.job_title && contact.email && (
                              <span className="text-slate-600">•</span>
                            )}
                            {contact.email && (
                              <span className="flex items-center gap-1 text-slate-400 truncate">
                                <Mail className="w-3.5 h-3.5 text-slate-500" />
                                {contact.email}
                              </span>
                            )}
                          </div>
                        </div>
                      </div>
                    </td>

                    <td className="px-6 py-4 align-middle">
                      <div className="flex items-center gap-1.5 text-sm text-slate-300">
                        {linkedCompany ? (
                          <>
                            <Building2 className="w-4 h-4 text-indigo-400 shrink-0" />
                            <span className="truncate">{companyName}</span>
                          </>
                        ) : (
                          <span className="text-slate-500">—</span>
                        )}
                      </div>
                    </td>

                    <td className="px-6 py-4 align-middle">
                      <span className="text-sm text-slate-300">
                        {ownerName}
                      </span>
                    </td>

                    <td className="px-6 py-4 text-right align-middle">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={(e) => handleEdit(e, contact)}
                          title="Edit Contact"
                          className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-lg text-slate-300 transition-all cursor-pointer"
                        >
                          <Edit3 className="w-4 h-4" />
                        </button>
                        <button
                          onClick={(e) => handleDelete(e, contact)}
                          title="Delete Contact"
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
