import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { useForm } from 'react-hook-form';
import { zodResolver } from '@hookform/resolvers/zod';
import * as z from 'zod';
import { api } from '../../services/api';
import { useAuthStore } from '../../store/authStore';
import { Building, ShieldAlert, Check, Loader2 } from 'lucide-react';

const orgSchema = z.object({
  name: z.string().min(2, 'Organization name must be at least 2 characters'),
});

type OrgForm = z.infer<typeof orgSchema>;

export const Profile: React.FC = () => {
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const setAuth = useAuthStore((state) => state.setAuth);
  const authStore = useAuthStore();
  const [success, setSuccess] = useState(false);

  const isAdmin = user?.role === 'OrgAdmin' || user?.role === 'SuperAdmin';

  const { data: org, isLoading } = useQuery({
    queryKey: ['my-organization'],
    queryFn: async () => {
      const res = await api.get('/organizations/my');
      return res.data;
    },
  });

  const { register, handleSubmit, formState: { errors } } = useForm<OrgForm>({
    resolver: zodResolver(orgSchema),
    values: org ? { name: org.name } : undefined,
  });

  const updateMutation = useMutation({
    mutationFn: async (data: OrgForm) => {
      const res = await api.put('/organizations/my', data);
      return res.data;
    },
    onSuccess: (updatedOrg) => {
      queryClient.setQueryData(['my-organization'], updatedOrg);
      if (authStore.user && authStore.accessToken && authStore.refreshToken) {
        setAuth(authStore.user, updatedOrg, authStore.accessToken, authStore.refreshToken);
      }
      setSuccess(true);
      setTimeout(() => setSuccess(false), 3000);
    },
  });

  const onSubmit = (data: OrgForm) => {
    updateMutation.mutate(data);
  };

  if (isLoading) {
    return (
      <div className="flex justify-center items-center h-64">
        <Loader2 className="w-8 h-8 text-brand-500 animate-spin" />
      </div>
    );
  }

  return (
    <div className="space-y-6 max-w-2xl">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-extrabold text-white tracking-tight">Organization Profile</h1>
          <p className="text-slate-400 text-sm">View or modify your tenant details and company settings.</p>
        </div>
      </div>

      <div className="glass-panel p-8 rounded-2xl space-y-6">
        <div className="flex items-center gap-4 p-4 bg-slate-900/40 border border-slate-800 rounded-xl">
          <Building className="w-10 h-10 text-brand-400" />
          <div>
            <h3 className="font-bold text-white text-lg">{org?.name}</h3>
            <p className="text-slate-400 text-sm">Unique identifier slug: <span className="text-brand-300 font-mono">/{org?.slug}</span></p>
          </div>
        </div>

        <form onSubmit={handleSubmit(onSubmit)} className="space-y-5">
          <div>
            <label className="block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2">Company Name</label>
            <input
              type="text"
              disabled={!isAdmin}
              {...register('name')}
              className="w-full px-4 py-3 rounded-xl glass-input disabled:opacity-50 disabled:cursor-not-allowed"
              placeholder="Acme Corporation"
            />
            {errors.name && <p className="mt-1.5 text-xs text-red-400">{errors.name.message}</p>}
          </div>

          {!isAdmin && (
            <div className="p-4 bg-amber-500/10 border border-amber-500/20 text-amber-200 text-sm rounded-xl flex items-center gap-3">
              <ShieldAlert className="w-5 h-5 flex-shrink-0 text-amber-400" />
              <p>You need organization admin rights to update this settings profile.</p>
            </div>
          )}

          {isAdmin && (
            <div className="flex items-center gap-4">
              <button
                type="submit"
                disabled={updateMutation.isPending}
                className="py-3 px-6 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 disabled:opacity-50 text-white font-semibold rounded-xl transition-all duration-150 flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20"
              >
                {updateMutation.isPending ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Saving changes...
                  </>
                ) : (
                  'Save Settings'
                )}
              </button>

              {success && (
                <span className="flex items-center gap-1.5 text-green-400 text-sm font-medium animate-fade-in">
                  <Check className="w-4 h-4" />
                  Settings saved successfully
                </span>
              )}
            </div>
          )}
        </form>
      </div>
    </div>
  );
};
