import React, { useEffect } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { LeadResponse } from '../../services/leadApi';
import { useLeadStore } from '../../store/leadStore';
import { useUserStore } from '../../store/userStore';
import { X, Loader2 } from 'lucide-react';

const leadSchema = z.object({
  title: z.string().min(1, 'Lead Title is required').max(255),
  last_name: z.string().min(1, 'Last name is required').max(100),
  first_name: z.string().max(100).optional().or(z.literal('')),
  email: z.string().email('Invalid email address').optional().or(z.literal('')),
  phone: z.string().max(50).optional().or(z.literal('')),
  company_name: z.string().max(255).optional().or(z.literal('')),
  status: z.string().min(1, 'Status is required'),
  source: z.string().max(100).optional().or(z.literal('')),
  value: z.coerce.number().min(0, 'Value must be positive').optional().or(z.literal('')),
  assigned_user_id: z.string().optional().or(z.literal('')),
});

type LeadFormValues = z.infer<typeof leadSchema>;

interface LeadModalProps {
  isOpen: boolean;
  onClose: () => void;
  lead?: LeadResponse | null;
}

export const LeadModal: React.FC<LeadModalProps> = ({
  isOpen,
  onClose,
  lead
}) => {
  const { createLead, updateLead } = useLeadStore();
  const { users, fetchUsers } = useUserStore();
  const activeUsers = users.filter(u => u.is_active);

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting }
  } = useForm<LeadFormValues>({
    resolver: zodResolver(leadSchema),
    defaultValues: {
      title: '',
      last_name: '',
      first_name: '',
      email: '',
      phone: '',
      company_name: '',
      status: 'New',
      source: '',
      value: '',
      assigned_user_id: '',
    }
  });

  useEffect(() => {
    if (isOpen && users.length === 0) {
      fetchUsers();
    }
  }, [isOpen]);

  useEffect(() => {
    if (lead) {
      reset({
        title: lead.title,
        last_name: lead.last_name,
        first_name: lead.first_name || '',
        email: lead.email || '',
        phone: lead.phone || '',
        company_name: lead.company_name || '',
        status: lead.status,
        source: lead.source || '',
        value: lead.value || '',
        assigned_user_id: lead.assigned_user_id || '',
      });
    } else {
      reset({
        title: '',
        last_name: '',
        first_name: '',
        email: '',
        phone: '',
        company_name: '',
        status: 'New',
        source: '',
        value: '',
        assigned_user_id: '',
      });
    }
  }, [lead, reset, isOpen]);

  if (!isOpen) return null;

  const onSubmit = async (values: LeadFormValues) => {
    try {
      const payload = {
        title: values.title,
        last_name: values.last_name,
        first_name: values.first_name || null,
        email: values.email || null,
        phone: values.phone || null,
        company_name: values.company_name || null,
        status: values.status,
        source: values.source || null,
        value: values.value !== '' ? Number(values.value) : null,
        assigned_user_id: values.assigned_user_id || null,
      };

      if (lead) {
        await updateLead(lead.id, payload);
      } else {
        await createLead(payload);
      }
      onClose();
    } catch (err: any) {
      alert(err.message || 'Operation failed');
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>

      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-6">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-xl font-bold tracking-tight text-slate-100">
            {lead ? 'Edit Lead Opportunity' : 'Add New Lead'}
          </h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Lead Title *</label>
            <input
              type="text"
              {...register('title')}
              placeholder="e.g. Acme Licensing Deal"
              className={`w-full px-4 py-3 rounded-xl glass-input ${errors.title ? 'border-red-500/50' : ''}`}
            />
            {errors.title && <p className="mt-1.5 text-xs text-red-400">{errors.title.message}</p>}
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Contact First Name</label>
              <input
                type="text"
                {...register('first_name')}
                placeholder="e.g. Robert"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Contact Last Name *</label>
              <input
                type="text"
                {...register('last_name')}
                placeholder="e.g. Downey"
                className={`w-full px-4 py-3 rounded-xl glass-input ${errors.last_name ? 'border-red-500/50' : ''}`}
              />
              {errors.last_name && <p className="mt-1.5 text-xs text-red-400">{errors.last_name.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Email</label>
              <input
                type="text"
                {...register('email')}
                placeholder="e.g. rob@acme.com"
                className={`w-full px-4 py-3 rounded-xl glass-input ${errors.email ? 'border-red-500/50' : ''}`}
              />
              {errors.email && <p className="mt-1.5 text-xs text-red-400">{errors.email.message}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Phone</label>
              <input
                type="text"
                {...register('phone')}
                placeholder="e.g. +1 555-0900"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Company Name</label>
              <input
                type="text"
                {...register('company_name')}
                placeholder="e.g. Acme Industries"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Lead Value ($)</label>
              <input
                type="number"
                step="any"
                {...register('value')}
                placeholder="e.g. 15000"
                className={`w-full px-4 py-3 rounded-xl glass-input ${errors.value ? 'border-red-500/50' : ''}`}
              />
              {errors.value && <p className="mt-1.5 text-xs text-red-400">{errors.value.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Status</label>
              <select
                {...register('status')}
                className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
              >
                <option value="New">New</option>
                <option value="Contacted">Contacted</option>
                <option value="Qualified">Qualified</option>
                <option value="Nurturing">Nurturing</option>
                <option value="Lost">Lost</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Source</label>
              <input
                type="text"
                {...register('source')}
                placeholder="e.g. Website, Referral"
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
                'Save Lead'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
