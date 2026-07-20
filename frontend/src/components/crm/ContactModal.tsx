import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { ContactResponse, contactApi, CustomFieldDefinition } from '../../services/contactApi';
import { useContactStore } from '../../store/contactStore';
import { useCompanyStore } from '../../store/companyStore';
import { useUserStore } from '../../store/userStore';
import { X, Loader2 } from 'lucide-react';

const contactSchema = z.object({
  first_name: z.string().min(1, 'First name is required').max(100),
  last_name: z.string().min(1, 'Last name is required').max(100),
  email: z.string().email('Invalid email address').optional().or(z.literal('')),
  phone: z.string().max(50).optional().or(z.literal('')),
  job_title: z.string().max(100).optional().or(z.literal('')),
  company_id: z.string().optional().or(z.literal('')),
  assigned_user_id: z.string().optional().or(z.literal('')),
});

type ContactFormValues = z.infer<typeof contactSchema>;

interface ContactModalProps {
  isOpen: boolean;
  onClose: () => void;
  contact?: ContactResponse | null;
}

export const ContactModal: React.FC<ContactModalProps> = ({
  isOpen,
  onClose,
  contact
}) => {
  const { createContact, updateContact } = useContactStore();
  const { companies, fetchCompanies } = useCompanyStore();
  const { users, fetchUsers } = useUserStore();
  const activeUsers = users.filter(u => u.is_active);

  const [tagsInput, setTagsInput] = useState('');
  const [definitions, setDefinitions] = useState<CustomFieldDefinition[]>([]);
  const [customValues, setCustomValues] = useState<Record<string, any>>({});

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting }
  } = useForm<ContactFormValues>({
    resolver: zodResolver(contactSchema),
    defaultValues: {
      first_name: '',
      last_name: '',
      email: '',
      phone: '',
      job_title: '',
      company_id: '',
      assigned_user_id: '',
    }
  });

  useEffect(() => {
    if (isOpen) {
      if (companies.length === 0) fetchCompanies();
      if (users.length === 0) fetchUsers();
      contactApi.listCustomFields().then((d) => setDefinitions(d.filter((f) => f.is_active))).catch(() => {});
    }
  }, [isOpen]);

  useEffect(() => {
    if (contact) {
      setTagsInput((contact.tags || []).join(', '));
      setCustomValues(contact.custom_fields || {});
      reset({
        first_name: contact.first_name,
        last_name: contact.last_name,
        email: contact.email || '',
        phone: contact.phone || '',
        job_title: contact.job_title || '',
        company_id: contact.company_id || '',
        assigned_user_id: contact.assigned_user_id || '',
      });
    } else {
      setTagsInput('');
      setCustomValues({});
      reset({
        first_name: '',
        last_name: '',
        email: '',
        phone: '',
        job_title: '',
        company_id: '',
        assigned_user_id: '',
      });
    }
  }, [contact, reset, isOpen]);

  if (!isOpen) return null;

  const onSubmit = async (values: ContactFormValues) => {
    try {
      const tags = tagsInput.split(',').map((t) => t.trim()).filter(Boolean);
      const cleanedCustom: Record<string, any> = {};
      for (const def of definitions) {
        const v = customValues[def.key];
        if (v !== undefined && v !== '') cleanedCustom[def.key] = v;
      }
      const payload = {
        first_name: values.first_name,
        last_name: values.last_name,
        email: values.email || null,
        phone: values.phone || null,
        job_title: values.job_title || null,
        company_id: values.company_id || null,
        assigned_user_id: values.assigned_user_id || null,
        tags: tags.length ? tags : null,
        custom_fields: Object.keys(cleanedCustom).length ? cleanedCustom : null,
      };

      if (contact) {
        await updateContact(contact.id, payload);
      } else {
        await createContact(payload);
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
            {contact ? 'Edit Contact Details' : 'Add New Contact'}
          </h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200 transition-colors">
            <X className="w-5 h-5" />
          </button>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">First Name *</label>
              <input
                type="text"
                {...register('first_name')}
                placeholder="e.g. John"
                className={`w-full px-4 py-3 rounded-xl glass-input ${errors.first_name ? 'border-red-500/50' : ''}`}
              />
              {errors.first_name && <p className="mt-1.5 text-xs text-red-400">{errors.first_name.message}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Last Name *</label>
              <input
                type="text"
                {...register('last_name')}
                placeholder="e.g. Doe"
                className={`w-full px-4 py-3 rounded-xl glass-input ${errors.last_name ? 'border-red-500/50' : ''}`}
              />
              {errors.last_name && <p className="mt-1.5 text-xs text-red-400">{errors.last_name.message}</p>}
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Email Address</label>
              <input
                type="text"
                {...register('email')}
                placeholder="e.g. john.doe@company.com"
                className={`w-full px-4 py-3 rounded-xl glass-input ${errors.email ? 'border-red-500/50' : ''}`}
              />
              {errors.email && <p className="mt-1.5 text-xs text-red-400">{errors.email.message}</p>}
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Phone</label>
              <input
                type="text"
                inputMode="tel"
                maxLength={20}
                {...register('phone')}
                placeholder="e.g. +1 555-0100"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Job Title</label>
              <input
                type="text"
                {...register('job_title')}
                placeholder="e.g. Operations Manager"
                className="w-full px-4 py-3 rounded-xl glass-input"
              />
            </div>
            <div>
              <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Associated Company</label>
              <select
                {...register('company_id')}
                className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
              >
                <option value="">No Company</option>
                {companies.map(c => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
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

          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Tags</label>
            <input
              type="text"
              value={tagsInput}
              onChange={(e) => setTagsInput(e.target.value)}
              placeholder="Comma-separated, e.g. vip, newsletter"
              className="w-full px-4 py-3 rounded-xl glass-input"
            />
          </div>

          {definitions.length > 0 && (
            <div className="space-y-4 pt-2 border-t border-slate-800/60">
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Custom Fields</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {definitions.map((def) => (
                  <div key={def.id}>
                    <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">{def.label}</label>
                    {def.field_type === 'select' && def.options ? (
                      <select
                        value={customValues[def.key] ?? ''}
                        onChange={(e) => setCustomValues((p) => ({ ...p, [def.key]: e.target.value }))}
                        className="w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                      >
                        <option value="">—</option>
                        {def.options.map((o) => <option key={o} value={o}>{o}</option>)}
                      </select>
                    ) : def.field_type === 'checkbox' ? (
                      <input
                        type="checkbox"
                        checked={!!customValues[def.key]}
                        onChange={(e) => setCustomValues((p) => ({ ...p, [def.key]: e.target.checked }))}
                        className="accent-brand-500 w-5 h-5"
                      />
                    ) : (
                      <input
                        type={def.field_type === 'number' ? 'number' : def.field_type === 'date' ? 'date' : 'text'}
                        value={customValues[def.key] ?? ''}
                        onChange={(e) => setCustomValues((p) => ({ ...p, [def.key]: e.target.value }))}
                        className="w-full px-4 py-3 rounded-xl glass-input"
                      />
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

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
                'Save Contact'
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
