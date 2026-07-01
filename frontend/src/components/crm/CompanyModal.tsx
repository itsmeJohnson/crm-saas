import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { CompanyResponse } from '../../services/companyApi';
import { useCompanyStore } from '../../store/companyStore';
import { useUserStore } from '../../store/userStore';
import { X, Loader2 } from 'lucide-react';

const companySchema = z.object({
  name: z.string().min(1, 'Company name is required').max(255),
  domain: z.string().max(255).optional().or(z.literal('')),
  industry: z.string().max(100).optional().or(z.literal('')),
  website: z.string().max(255).optional().or(z.literal('')),
  phone: z.string().max(50).optional().or(z.literal('')),
  assigned_user_id: z.string().optional().or(z.literal('')),
});

type CompanyFormValues = z.infer<typeof companySchema>;

interface CompanyModalProps {
  isOpen: boolean;
  onClose: () => void;
  company?: CompanyResponse | null;
}

export const CompanyModal: React.FC<CompanyModalProps> = ({
  isOpen,
  onClose,
  company
}) => {
  const { createCompany, updateCompany } = useCompanyStore();
  const { users, fetchUsers } = useUserStore();
  const activeUsers = users.filter(u => u.is_active);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting }
  } = useForm<CompanyFormValues>({
    resolver: zodResolver(companySchema),
    defaultValues: {
      name: '',
      domain: '',
      industry: '',
      website: '',
      phone: '',
      assigned_user_id: '',
    }
  });

  useEffect(() => {
    if (users.length === 0 && isOpen) {
      fetchUsers();
    }
  }, [isOpen]);

  useEffect(() => {
    if (company) {
      reset({
        name: company.name,
        domain: company.domain || '',
        industry: company.industry || '',
        website: company.website || '',
        phone: company.phone || '',
        assigned_user_id: company.assigned_user_id || '',
      });
    } else {
      reset({
        name: '',
        domain: '',
        industry: '',
        website: '',
        phone: '',
        assigned_user_id: '',
      });
    }
  }, [company, reset, isOpen]);

  if (!isOpen) return null;

  const onSubmit = async (values: CompanyFormValues) => {
    try {
      const payload = {
        name: values.name,
        domain: values.domain || undefined,
        industry: values.industry || undefined,
        website: values.website || undefined,
        phone: values.phone || undefined,
        assigned_user_id: values.assigned_user_id || null,
      };

      if (company) {
        await updateCompany(company.id, payload);
      } else {
        await createCompany(payload);
      }
      onClose();
    } catch (err: any) {
      alert(err.message || 'Operation failed');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      {/* Overlay backdrop */}
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>

      {/* Modal Card */}
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            {company ? 'Edit Company Details' : 'Add New Company'}
          </h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Company Name *</label>
            <input
              type="text"
              {...register('name')}
              placeholder="e.g. Acme Corp"
              className={`w-full px-4 py-3 rounded-xl glass-input ${errors.name ? 'border-red-500/50' : ''}`}
            />
            {errors.name && <p className="mt-1.5 text-xs text-red-400">{errors.name.message}</p>}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Domain</label>
              <input
                type="text"
                {...register('domain')}
                placeholder="e.g. acme.com"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Industry</label>
              <input
                type="text"
                {...register('industry')}
                placeholder="e.g. Technology"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Website</label>
              <input
                type="text"
                {...register('website')}
                placeholder="e.g. https://acme.com"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Phone</label>
              <input
                type="text"
                inputMode="tel"
                maxLength={20}
                {...register('phone')}
                placeholder="e.g. +1 555-0199"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Assign Owner</label>
            <select
              {...register('assigned_user_id')}
              className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
            >
              <option value="">Unassigned</option>
              {activeUsers.map(u => (
                <option key={u.id} value={u.id}>
                  {`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}
                </option>
              ))}
            </select>
          </div>

          <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
            <button
              type="button"
              onClick={onClose}
              className="px-5 py-2.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-900/50 active:bg-slate-900 rounded-xl text-sm font-semibold text-slate-300 transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="flex items-center justify-center gap-2 px-5 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Saving...
                </>
              ) : (
                'Save Company'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
