import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { 
  Building, Users, FileText, Edit, Plus, X, ShieldAlert, 
  Loader2, Calendar, DollarSign, CheckCircle2, AlertCircle, Clock, Trash2
} from 'lucide-react';
import { 
  superAdminApi, TenantResponse, TenantUserResponse, TenantInvoiceResponse,
  SubscriptionUpdateRequest, InvoiceCreateRequest, CreateTenantRequest
} from '../services/superAdminApi';

export const TenantsPage: React.FC = () => {
  const [tenants, setTenants] = useState<TenantResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);

  // Modals / Drawer state
  const [selectedTenant, setSelectedTenant] = useState<TenantResponse | null>(null);
  const [activeModal, setActiveModal] = useState<'create' | 'editSubscription' | 'users' | 'invoices' | 'deleteConfirm' | null>(null);
  const [deleteConfirmSlug, setDeleteConfirmSlug] = useState('');
  
  // Modal specific state
  const [tenantUsers, setTenantUsers] = useState<TenantUserResponse[]>([]);
  const [invoices, setInvoices] = useState<TenantInvoiceResponse[]>([]);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  const fetchTenants = async () => {
    setIsLoading(true);
    setGlobalError(null);
    try {
      const data = await superAdminApi.getTenants();
      setTenants(data);
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || 'Failed to fetch tenants');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchTenants();
  }, []);

  const openUsersModal = async (tenant: TenantResponse) => {
    setSelectedTenant(tenant);
    setTenantUsers([]);
    setActiveModal('users');
    setIsModalLoading(true);
    setModalError(null);
    try {
      const data = await superAdminApi.getTenantUsers(tenant.id);
      setTenantUsers(data);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to load tenant users');
    } finally {
      setIsModalLoading(false);
    }
  };

  const openInvoicesModal = async (tenant: TenantResponse) => {
    setSelectedTenant(tenant);
    setInvoices([]);
    setActiveModal('invoices');
    setIsModalLoading(true);
    setModalError(null);
    try {
      const data = await superAdminApi.getTenantInvoices(tenant.id);
      setInvoices(data);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to load tenant invoices');
    } finally {
      setIsModalLoading(false);
    }
  };

  const openEditSubModal = (tenant: TenantResponse) => {
    setSelectedTenant(tenant);
    setModalError(null);
    setActiveModal('editSubscription');
  };

  // Form hooks
  const { 
    register: regTenant, 
    handleSubmit: handleTenantSubmit, 
    reset: resetTenant,
    formState: { errors: tenantErrors } 
  } = useForm<CreateTenantRequest>();

  const { 
    register: regSub, 
    handleSubmit: handleSubSubmit, 
    setValue: setSubValue,
    formState: { errors: subErrors } 
  } = useForm<SubscriptionUpdateRequest>();

  const { 
    register: regInv, 
    handleSubmit: handleInvSubmit, 
    reset: resetInv,
    formState: { errors: invErrors } 
  } = useForm<InvoiceCreateRequest>();

  useEffect(() => {
    if (selectedTenant && activeModal === 'editSubscription') {
      setSubValue('subscription_plan', selectedTenant.subscription_plan);
      setSubValue('subscription_status', selectedTenant.subscription_status);
      setSubValue('max_users', selectedTenant.max_users);
      setSubValue('subscription_expires_at', selectedTenant.subscription_expires_at ? selectedTenant.subscription_expires_at.substring(0, 10) : '');
    }
  }, [selectedTenant, activeModal, setSubValue]);

  // Actions
  const onCreateTenant = async (data: CreateTenantRequest) => {
    setIsModalLoading(true);
    setModalError(null);
    try {
      await superAdminApi.createTenant(data);
      await fetchTenants();
      resetTenant();
      setActiveModal(null);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to create tenant');
    } finally {
      setIsModalLoading(false);
    }
  };

  const onUpdateSubscription = async (data: SubscriptionUpdateRequest) => {
    if (!selectedTenant) return;
    setIsModalLoading(true);
    setModalError(null);
    try {
      const payload: SubscriptionUpdateRequest = {
        subscription_plan: data.subscription_plan,
        subscription_status: data.subscription_status,
        max_users: Number(data.max_users),
        subscription_expires_at: data.subscription_expires_at ? new Date(data.subscription_expires_at).toISOString() : null
      };
      await superAdminApi.updateSubscription(selectedTenant.id, payload);
      await fetchTenants();
      setActiveModal(null);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to update subscription');
    } finally {
      setIsModalLoading(false);
    }
  };

  const onCreateInvoice = async (data: InvoiceCreateRequest) => {
    if (!selectedTenant) return;
    setIsModalLoading(true);
    setModalError(null);
    try {
      const payload: InvoiceCreateRequest = {
        amount: Number(data.amount),
        due_date: new Date(data.due_date).toISOString(),
        status: data.status || 'Pending'
      };
      await superAdminApi.createInvoice(selectedTenant.id, payload);
      const updatedInvoices = await superAdminApi.getTenantInvoices(selectedTenant.id);
      setInvoices(updatedInvoices);
      resetInv();
      await fetchTenants(); // update counts
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to create invoice');
    } finally {
      setIsModalLoading(false);
    }
  };

  const onToggleInvoiceStatus = async (invoiceId: string, currentStatus: string) => {
    if (!selectedTenant) return;
    const nextStatus = currentStatus === 'Paid' ? 'Pending' : currentStatus === 'Pending' ? 'Overdue' : 'Paid';
    setIsModalLoading(true);
    setModalError(null);
    try {
      await superAdminApi.updateInvoiceStatus(invoiceId, nextStatus);
      const updatedInvoices = await superAdminApi.getTenantInvoices(selectedTenant.id);
      setInvoices(updatedInvoices);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to update invoice status');
    } finally {
      setIsModalLoading(false);
    }
  };

  const handleDeleteTenant = (tenant: TenantResponse) => {
    setSelectedTenant(tenant);
    setDeleteConfirmSlug('');
    setActiveModal('deleteConfirm');
  };

  const onConfirmDeleteTenant = async () => {
    if (!selectedTenant) return;
    setIsLoading(true);
    setGlobalError(null);
    try {
      await superAdminApi.deleteTenant(selectedTenant.id);
      setActiveModal(null);
      await fetchTenants();
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || 'Failed to delete tenant');
    } finally {
      setIsLoading(false);
    }
  };

  const getInvoiceStatusIcon = (status: string) => {
    switch (status) {
      case 'Paid':
        return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />;
      case 'Pending':
        return <Clock className="w-4 h-4 text-amber-400 shrink-0" />;
      case 'Overdue':
        return <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />;
      default:
        return null;
    }
  };

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/60 pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
            Tenant Subscription Management
          </h1>
          <p className="text-sm text-slate-400 mt-1">
            Create tenant instances, configure limits, monitor user counts, and manage billing invoices globally.
          </p>
        </div>

        <button
          onClick={() => {
            resetTenant();
            setModalError(null);
            setActiveModal('create');
          }}
          className="flex items-center justify-center gap-2 px-5 py-3 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 active:from-brand-700 active:to-indigo-700 text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-brand-500/20 cursor-pointer self-start sm:self-auto shrink-0"
        >
          <Plus className="w-4 h-4" />
          Create Tenant
        </button>
      </div>

      {globalError && (
        <div className="p-4 bg-red-950/20 border border-red-900/30 rounded-2xl flex items-start gap-2.5 text-sm text-red-400">
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{globalError}</span>
        </div>
      )}

      {/* Tenants Table */}
      {isLoading ? (
        <div className="glass-panel p-20 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-400">
          <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
          <p className="text-sm font-medium">Fetching tenant databases...</p>
        </div>
      ) : tenants.length === 0 ? (
        <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-500 text-center">
          <Building className="w-12 h-12 text-slate-600 mb-3" />
          <p className="text-base font-semibold text-slate-400">No Tenants Created</p>
          <p className="text-sm text-slate-500 mt-1">Click the 'Create Tenant' button to spin up a new organization instance.</p>
        </div>
      ) : (
        <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden shadow-xl">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse">
              <thead>
                <tr className="border-b border-slate-800/80 bg-slate-900/40">
                  <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Tenant / Slug</th>
                  <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
                  <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Plan & Limits</th>
                  <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Expires At</th>
                  <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400 text-center">Resources</th>
                  <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/65 bg-slate-950/20">
                {tenants.map((tenant) => (
                  <tr key={tenant.id} className="hover:bg-slate-900/30 transition-colors">
                    {/* Tenant detail */}
                    <td className="px-6 py-4">
                      <div>
                        <p className="text-sm font-semibold text-slate-200">{tenant.name}</p>
                        <p className="text-xs text-slate-500">/{tenant.slug}</p>
                      </div>
                    </td>

                    {/* Subscription status */}
                    <td className="px-6 py-4">
                      <span className={`inline-flex items-center gap-1.5 text-xs font-medium ${
                        tenant.subscription_status === 'Active' && tenant.is_active ? 'text-emerald-400' : 'text-rose-400'
                      }`}>
                        <span className={`w-1.5 h-1.5 rounded-full ${
                          tenant.subscription_status === 'Active' && tenant.is_active ? 'bg-emerald-400' : 'bg-rose-400'
                        }`} />
                        {tenant.subscription_status} {tenant.is_active ? '' : '(Suspended)'}
                      </span>
                    </td>

                    {/* Plan and user limit */}
                    <td className="px-6 py-4">
                      <div>
                        <span className="inline-block px-2.5 py-0.5 text-xs font-semibold rounded bg-brand-500/10 text-brand-400 border border-brand-500/20 uppercase tracking-wider">
                          {tenant.subscription_plan}
                        </span>
                        <p className="text-xs text-slate-400 mt-1">Max Users: {tenant.max_users}</p>
                      </div>
                    </td>

                    {/* Expiration date */}
                    <td className="px-6 py-4 text-sm text-slate-300">
                      {tenant.subscription_expires_at 
                        ? new Date(tenant.subscription_expires_at).toLocaleDateString()
                        : 'Never'
                      }
                    </td>

                    {/* Stats counts */}
                    <td className="px-6 py-4 text-center">
                      <div className="flex justify-center items-center gap-4">
                        <button 
                          onClick={() => openUsersModal(tenant)}
                          title="View Users"
                          className="flex items-center gap-1 text-xs text-slate-400 hover:text-brand-400 transition-colors cursor-pointer"
                        >
                          <Users className="w-4 h-4 text-slate-500" />
                          <span>{tenant.user_count}</span>
                        </button>
                        <button 
                          onClick={() => openInvoicesModal(tenant)}
                          title="View Invoices"
                          className="flex items-center gap-1 text-xs text-slate-400 hover:text-indigo-400 transition-colors cursor-pointer"
                        >
                          <FileText className="w-4 h-4 text-slate-500" />
                          <span>{tenant.invoice_count}</span>
                        </button>
                      </div>
                    </td>

                    {/* Actions */}
                    <td className="px-6 py-4 text-right">
                      <div className="flex items-center justify-end gap-2">
                        <button
                          onClick={() => openEditSubModal(tenant)}
                          title="Configure Subscription"
                          className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-lg text-slate-300 transition-all cursor-pointer inline-flex items-center gap-1"
                        >
                          <Edit className="w-4 h-4" />
                          <span className="text-xs font-semibold pr-1">Config</span>
                        </button>
                        <button
                          onClick={() => handleDeleteTenant(tenant)}
                          title="Delete Tenant"
                          className="p-2 border border-slate-800 hover:border-red-500/25 hover:bg-red-500/10 text-red-400 rounded-lg transition-all cursor-pointer inline-flex items-center"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* CREATE TENANT MODAL */}
      {activeModal === 'create' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-lg glass-panel border border-slate-800/90 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                  <Building className="w-5 h-5 text-brand-400" />
                  Spin Up Tenant Instance
                </h3>
                <p className="text-xs text-slate-400">Creates database entries for a new tenant and assigns its primary admin account.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleTenantSubmit(onCreateTenant)} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
              {modalError && (
                <div className="p-3 bg-red-950/20 border border-red-900/30 rounded-xl text-sm text-red-400 flex items-start gap-2">
                  <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{modalError}</span>
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Company Name</label>
                  <input
                    type="text"
                    placeholder="Acme Corp"
                    {...regTenant('company_name', { required: 'Company name is required', maxLength: 255 })}
                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                  />
                  {tenantErrors.company_name && <p className="text-xs text-red-400 mt-1">{tenantErrors.company_name.message}</p>}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Subdomain Slug</label>
                  <input
                    type="text"
                    placeholder="acme"
                    {...regTenant('slug', { 
                      required: 'Subdomain slug is required', 
                      pattern: { value: /^[a-z0-9-]+$/i, message: 'Only alphanumeric characters and hyphens allowed' } 
                    })}
                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                  />
                  {tenantErrors.slug && <p className="text-xs text-red-400 mt-1">{tenantErrors.slug.message}</p>}
                </div>
              </div>

              <div className="border-t border-slate-800/80 my-4 pt-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 mb-3">Primary Administrator Credentials</h4>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">First Name</label>
                      <input
                        type="text"
                        placeholder="John"
                        {...regTenant('first_name')}
                        className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Last Name</label>
                      <input
                        type="text"
                        placeholder="Doe"
                        {...regTenant('last_name')}
                        className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Admin Email</label>
                    <input
                      type="email"
                      placeholder="admin@acme.com"
                      {...regTenant('admin_email', { 
                        required: 'Admin email is required',
                        pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Invalid email address' }
                      })}
                      className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                    />
                    {tenantErrors.admin_email && <p className="text-xs text-red-400 mt-1">{tenantErrors.admin_email.message}</p>}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Admin Password</label>
                    <input
                      type="password"
                      placeholder="Min 8 characters"
                      {...regTenant('admin_password', { 
                        required: 'Password is required',
                        minLength: { value: 8, message: 'Password must be at least 8 characters' }
                      })}
                      className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                    />
                    {tenantErrors.admin_password && <p className="text-xs text-red-400 mt-1">{tenantErrors.admin_password.message}</p>}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800/80">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  disabled={isModalLoading}
                  className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-sm font-medium text-slate-300 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isModalLoading}
                  className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-sm font-semibold transition-all cursor-pointer shadow-lg shadow-brand-500/20"
                >
                  {isModalLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Provisioning...
                    </>
                  ) : (
                    'Provision Tenant'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* EDIT SUBSCRIPTION CONFIG MODAL */}
      {activeModal === 'editSubscription' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel border border-slate-800/90 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                  <Edit className="w-5 h-5 text-brand-400" />
                  Subscription Settings
                </h3>
                <p className="text-xs text-slate-400">Configure parameters for <strong>{selectedTenant.name}</strong>.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubSubmit(onUpdateSubscription)} className="p-6 space-y-4">
              {modalError && (
                <div className="p-3 bg-red-950/20 border border-red-900/30 rounded-xl text-sm text-red-400 flex items-start gap-2">
                  <ShieldAlert className="w-4 h-4 shrink-0 mt-0.5" />
                  <span>{modalError}</span>
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Subscription Plan</label>
                <select
                  {...regSub('subscription_plan', { required: 'Plan is required' })}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                >
                  <option value="Starter">Starter</option>
                  <option value="Growth">Growth</option>
                  <option value="Enterprise">Enterprise</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Subscription Status</label>
                <select
                  {...regSub('subscription_status', { required: 'Status is required' })}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                >
                  <option value="Active">Active</option>
                  <option value="Suspended">Suspended</option>
                  <option value="Trial">Trial</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Max User Seat Limits</label>
                <input
                  type="number"
                  {...regSub('max_users', { required: 'User limit is required', min: { value: 1, message: 'Must allow at least 1 user' } })}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                />
                {subErrors.max_users && <p className="text-xs text-red-400 mt-1">{subErrors.max_users.message}</p>}
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-slate-500" />
                  Subscription Expiration Date (Optional)
                </label>
                <input
                  type="date"
                  {...regSub('subscription_expires_at')}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-slate-800/80">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  disabled={isModalLoading}
                  className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-sm font-medium text-slate-300 transition-all cursor-pointer"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={isModalLoading}
                  className="flex items-center justify-center gap-2 px-5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-sm font-semibold transition-all cursor-pointer shadow-lg shadow-brand-500/20"
                >
                  {isModalLoading ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Saving...
                    </>
                  ) : (
                    'Save Settings'
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* VIEW USERS SIDE DRAWER / MODAL */}
      {activeModal === 'users' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md h-screen bg-slate-950 border-l border-slate-800 flex flex-col justify-between shadow-2xl animate-slide-in">
            {/* Header */}
            <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                  <Users className="w-5 h-5 text-brand-400" />
                  Users List
                </h3>
                <p className="text-xs text-slate-400">Active personnel registered inside <strong>{selectedTenant.name}</strong>.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* List Body */}
            <div className="flex-1 overflow-y-auto p-6 space-y-4">
              {modalError && (
                <div className="p-3 bg-red-950/20 border border-red-900/30 rounded-xl text-sm text-red-400">
                  {modalError}
                </div>
              )}

              {isModalLoading ? (
                <div className="h-full flex flex-col items-center justify-center text-slate-400 py-20">
                  <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-3" />
                  <p className="text-xs">Querying database users...</p>
                </div>
              ) : tenantUsers.length === 0 ? (
                <div className="text-center py-20 text-slate-500">
                  <Users className="w-8 h-8 mx-auto mb-2 text-slate-700" />
                  <p className="text-sm font-semibold">No Registered Users</p>
                  <p className="text-xs text-slate-600 mt-1">This tenant has not created any staff database profiles yet.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {tenantUsers.map((user) => {
                    const initials = `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase() || 'U';
                    return (
                      <div key={user.id} className="p-3 bg-slate-900/30 border border-slate-800 rounded-xl flex items-center justify-between hover:border-slate-800/80 transition-colors">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/20 flex items-center justify-center font-bold text-xs text-brand-300">
                            {initials}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-slate-200">
                              {user.first_name} {user.last_name}
                            </p>
                            <p className="text-xs text-slate-400">{user.email}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className={`inline-block text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${
                            user.role === 'OrgAdmin'
                              ? 'bg-red-500/10 text-red-400 border-red-500/20'
                              : user.role === 'Manager'
                              ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                              : 'bg-slate-800 text-slate-300 border-slate-700'
                          }`}>
                            {user.role}
                          </span>
                          <p className={`text-[10px] mt-1 ${user.is_active ? 'text-emerald-400' : 'text-slate-500'}`}>
                            {user.is_active ? 'Active' : 'Inactive'}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-slate-800/80 bg-slate-950">
              <button
                onClick={() => setActiveModal(null)}
                className="w-full px-4 py-2.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-300 text-sm font-semibold rounded-xl transition-all cursor-pointer"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* MANAGE INVOICES MODAL */}
      {activeModal === 'invoices' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-3xl glass-panel border border-slate-800/90 rounded-2xl shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between shrink-0">
              <div>
                <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                  <FileText className="w-5 h-5 text-indigo-400" />
                  Tenant Invoices & Billing
                </h3>
                <p className="text-xs text-slate-400">Generate or check payment invoices for <strong>{selectedTenant.name}</strong>.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="p-6 overflow-y-auto space-y-6 flex-1">
              {modalError && (
                <div className="p-3 bg-red-950/20 border border-red-900/30 rounded-xl text-sm text-red-400">
                  {modalError}
                </div>
              )}

              <div className="grid grid-cols-1 md:grid-cols-3 gap-6 items-start">
                {/* Invoice Generation Form */}
                <div className="glass-panel p-5 border border-slate-800/70 rounded-xl space-y-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Generate Invoice</h4>
                  
                  <form onSubmit={handleInvSubmit(onCreateInvoice)} className="space-y-4">
                    <div>
                      <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Billing Amount ($)</label>
                      <div className="relative">
                        <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
                        <input
                          type="number"
                          placeholder="299.00"
                          step="0.01"
                          {...regInv('amount', { required: 'Amount is required', min: { value: 0.01, message: 'Must be positive' } })}
                          className="w-full pl-9 pr-4 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
                        />
                      </div>
                      {invErrors.amount && <p className="text-xs text-red-400 mt-1">{invErrors.amount.message}</p>}
                    </div>

                    <div>
                      <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Due Date</label>
                      <input
                        type="date"
                        {...regInv('due_date', { required: 'Due date is required' })}
                        className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                      />
                      {invErrors.due_date && <p className="text-xs text-red-400 mt-1">{invErrors.due_date.message}</p>}
                    </div>

                    <div>
                      <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-2">Status</label>
                      <select
                        {...regInv('status', { required: 'Status is required' })}
                        className="w-full px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                      >
                        <option value="Pending">Pending</option>
                        <option value="Paid">Paid</option>
                        <option value="Overdue">Overdue</option>
                      </select>
                    </div>

                    <button
                      type="submit"
                      disabled={isModalLoading}
                      className="w-full flex items-center justify-center gap-1.5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
                    >
                      {isModalLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                      Generate Invoice
                    </button>
                  </form>
                </div>

                {/* Invoices List */}
                <div className="md:col-span-2 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-400">Invoice Registry</h4>

                  {isModalLoading && invoices.length === 0 ? (
                    <div className="text-center py-10 text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-brand-500" />
                      <p className="text-xs">Loading billing events...</p>
                    </div>
                  ) : invoices.length === 0 ? (
                    <div className="p-8 border border-dashed border-slate-800 rounded-xl text-center text-slate-500">
                      <FileText className="w-6 h-6 mx-auto mb-2 text-slate-600" />
                      <p className="text-xs font-semibold">No invoices generated</p>
                      <p className="text-[10px] text-slate-600 mt-0.5">Generate a billing invoice on the left form to begin record history.</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
                      {invoices.map((invoice) => (
                        <div key={invoice.id} className="p-3 bg-slate-900/40 border border-slate-800/80 rounded-xl flex items-center justify-between hover:border-slate-800 transition-colors">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-slate-200">{invoice.invoice_number}</span>
                              <span className="text-xs text-brand-300 font-semibold">${invoice.amount.toFixed(2)}</span>
                            </div>
                            <p className="text-[10px] text-slate-500 mt-1">
                              Due: {new Date(invoice.due_date).toLocaleDateString()} | Created: {new Date(invoice.created_at).toLocaleDateString()}
                            </p>
                          </div>

                          <button 
                            onClick={() => onToggleInvoiceStatus(invoice.id, invoice.status)}
                            disabled={isModalLoading}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 bg-slate-950/20 text-xs text-slate-300 transition-colors cursor-pointer disabled:cursor-not-allowed"
                            title="Click to toggle status cycle: Paid -> Pending -> Overdue -> Paid"
                          >
                            {getInvoiceStatusIcon(invoice.status)}
                            <span className="font-semibold text-[10px]">{invoice.status}</span>
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Footer */}
            <div className="p-6 border-t border-slate-800/80 bg-slate-950 shrink-0">
              <button
                onClick={() => setActiveModal(null)}
                className="w-full px-4 py-2.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 text-slate-300 text-sm font-semibold rounded-xl transition-all cursor-pointer"
              >
                Close Panel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE CONFIRMATION MODAL */}
      {activeModal === 'deleteConfirm' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel border border-red-500/30 rounded-2xl shadow-2xl relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            {/* Header */}
            <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-red-500/10 rounded-lg text-red-400">
                  <ShieldAlert className="w-5 h-5 animate-pulse" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-slate-100">
                    Delete Tenant Instance
                  </h3>
                  <p className="text-xs text-slate-400">This action is permanent and irreversible.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Content */}
            <div className="p-6 space-y-4">
              <div className="p-4 bg-red-950/20 border border-red-900/30 rounded-xl text-sm text-red-400">
                <p className="font-semibold text-xs">WARNING:</p>
                <p className="mt-1 text-xs leading-relaxed text-red-300">
                  You are about to permanently delete the tenant <strong>{selectedTenant.name}</strong>.
                  This will completely erase all associated data, including users, leads, contacts, invoices, notes, activities, and subscription history from the database.
                </p>
              </div>
              <p className="text-sm text-slate-300">
                Please type the tenant slug <code className="px-1.5 py-0.5 bg-slate-900 rounded border border-slate-800 font-mono text-xs text-brand-400">{selectedTenant.slug}</code> to confirm deletion:
              </p>
              <input
                type="text"
                placeholder={selectedTenant.slug}
                value={deleteConfirmSlug}
                onChange={(e) => setDeleteConfirmSlug(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-red-500/40 animate-pulse"
              />
            </div>

            {/* Footer */}
            <div className="flex items-center justify-end gap-3 p-6 border-t border-slate-800/80 bg-slate-950/20">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-4 py-2.5 bg-slate-900 hover:bg-slate-800 border border-slate-800 rounded-xl text-sm font-medium text-slate-300 transition-all cursor-pointer"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={onConfirmDeleteTenant}
                disabled={deleteConfirmSlug !== selectedTenant.slug || isLoading}
                className="flex items-center justify-center gap-2 px-5 py-2.5 bg-red-600 hover:bg-red-700 active:bg-red-800 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl text-sm font-semibold transition-all shadow-lg shadow-red-600/20 cursor-pointer"
              >
                {isLoading ? (
                  <>
                    <Loader2 className="w-4 h-4 animate-spin" />
                    Deleting...
                  </>
                ) : (
                  'Permanently Delete'
                )}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
