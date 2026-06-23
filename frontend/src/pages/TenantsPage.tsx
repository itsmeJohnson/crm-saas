import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { 
  Building, Users, FileText, Edit, Plus, X, ShieldAlert, 
  Loader2, Calendar, DollarSign, CheckCircle2, AlertCircle, Clock, Trash2,
  Workflow, CheckSquare, Settings, Lock, Check, Key, ArrowUpDown, FolderKanban
} from 'lucide-react';
import { 
  superAdminApi, TenantResponse, TenantUserResponse, TenantInvoiceResponse,
  SubscriptionUpdateRequest, InvoiceCreateRequest, CreateTenantRequest,
  PlanResponse, FeatureResponse, PlanFeatureResponse, PlanCreatePayload
} from '../services/superAdminApi';

export const TenantsPage: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'tenants' | 'plans' | 'features' | 'invoice-settings' | 'system-settings'>('tenants');
  const [tenants, setTenants] = useState<TenantResponse[]>([]);
  const [plans, setPlans] = useState<PlanResponse[]>([]);
  const [features, setFeatures] = useState<FeatureResponse[]>([]);
  const [mappings, setMappings] = useState<PlanFeatureResponse[]>([]);
  const [settingsData, setSettingsData] = useState<Record<string, any>>({});
  
  const [isLoading, setIsLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Modals / Drawer state
  const [selectedTenant, setSelectedTenant] = useState<TenantResponse | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PlanResponse | null>(null);
  const [activeModal, setActiveModal] = useState<'createTenant' | 'editSubscription' | 'users' | 'invoices' | 'deleteTenantConfirm' | 'resetPassword' | 'createPlan' | 'editPlan' | null>(null);
  
  // Specific inputs
  const [deleteConfirmSlug, setDeleteConfirmSlug] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [tenantUsers, setTenantUsers] = useState<TenantUserResponse[]>([]);
  const [invoices, setInvoices] = useState<TenantInvoiceResponse[]>([]);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);

  // Loaders
  const fetchAllData = async () => {
    setIsLoading(true);
    setGlobalError(null);
    try {
      if (activeTab === 'tenants') {
        const data = await superAdminApi.getTenants();
        setTenants(data);
      } else if (activeTab === 'plans') {
        const data = await superAdminApi.getPlans();
        setPlans(data);
      } else if (activeTab === 'features') {
        const pData = await superAdminApi.getPlans();
        const fData = await superAdminApi.getFeatures();
        const mData = await superAdminApi.getPlanFeatures();
        setPlans(pData);
        setFeatures(fData);
        setMappings(mData);
      } else if (activeTab === 'invoice-settings' || activeTab === 'system-settings') {
        const data = await superAdminApi.getSystemSettings();
        const configMap: Record<string, any> = {};
        data.forEach(item => {
          configMap[item.key] = item.value;
        });
        setSettingsData(configMap);
      }
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || 'Failed to fetch settings from backend');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchAllData();
  }, [activeTab]);

  const showSuccess = (msg: string) => {
    setSuccessMessage(msg);
    setTimeout(() => setSuccessMessage(null), 4000);
  };

  // ==========================================
  // TENANT ACTIONS
  // ==========================================
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
      setModalError(err.response?.data?.detail || 'Failed to load users');
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
      setModalError(err.response?.data?.detail || 'Failed to load invoices');
    } finally {
      setIsModalLoading(false);
    }
  };

  const handleSuspendTenant = async (tenant: TenantResponse) => {
    setIsLoading(true);
    try {
      await superAdminApi.suspendTenant(tenant.id);
      showSuccess(`Subscription status for ${tenant.name} updated.`);
      await fetchAllData();
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || 'Failed to toggle status');
    } finally {
      setIsLoading(false);
    }
  };

  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedTenant || !newPassword) return;
    setIsModalLoading(true);
    setModalError(null);
    try {
      await superAdminApi.resetTenantOwnerPassword(selectedTenant.id, newPassword);
      showSuccess(`Owner password reset successfully.`);
      setNewPassword('');
      setActiveModal(null);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to reset password');
    } finally {
      setIsModalLoading(false);
    }
  };

  // Forms Hooks
  const { register: regTenant, handleSubmit: handleTenantSubmit, reset: resetTenant, formState: { errors: tenantErrors } } = useForm<CreateTenantRequest>();
  const { register: regSub, handleSubmit: handleSubSubmit, setValue: setSubValue, formState: { errors: subErrors } } = useForm<SubscriptionUpdateRequest>();
  const { register: regInv, handleSubmit: handleInvSubmit, reset: resetInv, formState: { errors: invErrors } } = useForm<InvoiceCreateRequest>();
  const { register: regPlan, handleSubmit: handlePlanSubmit, reset: resetPlan, setValue: setPlanValue, formState: { errors: planErrors } } = useForm<PlanCreatePayload>();

  const openEditSubModal = (tenant: TenantResponse) => {
    setSelectedTenant(tenant);
    setModalError(null);
    setActiveModal('editSubscription');
  };

  useEffect(() => {
    if (selectedTenant && activeModal === 'editSubscription') {
      setSubValue('subscription_plan', selectedTenant.subscription_plan);
      setSubValue('subscription_status', selectedTenant.subscription_status);
      setSubValue('max_users', selectedTenant.max_users);
      setSubValue('subscription_expires_at', selectedTenant.subscription_expires_at ? selectedTenant.subscription_expires_at.substring(0, 10) : '');
    }
  }, [selectedTenant, activeModal, setSubValue]);

  const onCreateTenant = async (data: CreateTenantRequest) => {
    setIsModalLoading(true);
    setModalError(null);
    try {
      await superAdminApi.createTenant(data);
      showSuccess(`Tenant ${data.company_name} created successfully.`);
      await fetchAllData();
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
      showSuccess(`Subscription bounds saved.`);
      await fetchAllData();
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
      await superAdminApi.createManualInvoice(selectedTenant.id, payload);
      showSuccess('Manual invoice generated successfully.');
      const updatedInvoices = await superAdminApi.getTenantInvoices(selectedTenant.id);
      setInvoices(updatedInvoices);
      resetInv();
      await fetchAllData(); // update count
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to create manual invoice');
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
      setModalError(err.response?.data?.detail || 'Failed to update status');
    } finally {
      setIsModalLoading(false);
    }
  };

  const onConfirmDeleteTenant = async () => {
    if (!selectedTenant) return;
    setIsLoading(true);
    try {
      await superAdminApi.deleteTenant(selectedTenant.id);
      showSuccess('Tenant instance and all associated databases purged.');
      setActiveModal(null);
      await fetchAllData();
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || 'Failed to purge tenant');
    } finally {
      setIsLoading(false);
    }
  };

  // ==========================================
  // PLANS CRUD ACTIONS
  // ==========================================
  const handleCreatePlan = async (data: PlanCreatePayload) => {
    setIsModalLoading(true);
    setModalError(null);
    try {
      await superAdminApi.createPlan({
        ...data,
        monthly_price: Number(data.monthly_price),
        quarterly_price: Number(data.quarterly_price),
        annual_price: Number(data.annual_price),
        max_users: Number(data.max_users),
        max_admins: Number(data.max_admins),
        max_managers: Number(data.max_managers),
        max_team_leads: Number(data.max_team_leads),
        max_employees: Number(data.max_employees),
        storage_limit_gb: Number(data.storage_limit_gb),
        recording_retention_days: Number(data.recording_retention_days),
        display_order: Number(data.display_order),
        setup_charges: Number(data.setup_charges),
        minimum_users: Number(data.minimum_users),
        maximum_users: Number(data.maximum_users),
        minimum_contract_months: Number(data.minimum_contract_months)
      });
      showSuccess(`Pricing plan template added.`);
      await fetchAllData();
      setActiveModal(null);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to create plan template');
    } finally {
      setIsModalLoading(false);
    }
  };

  const handleEditPlan = async (data: PlanCreatePayload) => {
    if (!selectedPlan) return;
    setIsModalLoading(true);
    setModalError(null);
    try {
      await superAdminApi.updatePlan(selectedPlan.id, {
        ...data,
        monthly_price: Number(data.monthly_price),
        quarterly_price: Number(data.quarterly_price),
        annual_price: Number(data.annual_price),
        max_users: Number(data.max_users),
        max_admins: Number(data.max_admins),
        max_managers: Number(data.max_managers),
        max_team_leads: Number(data.max_team_leads),
        max_employees: Number(data.max_employees),
        storage_limit_gb: Number(data.storage_limit_gb),
        recording_retention_days: Number(data.recording_retention_days),
        display_order: Number(data.display_order),
        setup_charges: Number(data.setup_charges),
        minimum_users: Number(data.minimum_users),
        maximum_users: Number(data.maximum_users),
        minimum_contract_months: Number(data.minimum_contract_months)
      });
      showSuccess(`Pricing plan updated.`);
      await fetchAllData();
      setActiveModal(null);
    } catch (err: any) {
      setModalError(err.response?.data?.detail || 'Failed to update plan template');
    } finally {
      setIsModalLoading(false);
    }
  };

  const handleDeletePlan = async (planId: string) => {
    if (!confirm('Are you sure you want to delete this pricing plan?')) return;
    setIsLoading(true);
    try {
      await superAdminApi.deletePlan(planId);
      showSuccess('Plan deleted successfully.');
      await fetchAllData();
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || 'Failed to delete plan');
    } finally {
      setIsLoading(false);
    }
  };

  const handleReorderPlans = async (planId: string, dir: 'up' | 'down') => {
    const idx = plans.findIndex(p => p.id === planId);
    if (idx === -1) return;
    const newPlans = [...plans];
    if (dir === 'up' && idx > 0) {
      const temp = newPlans[idx];
      newPlans[idx] = newPlans[idx - 1];
      newPlans[idx - 1] = temp;
    } else if (dir === 'down' && idx < newPlans.length - 1) {
      const temp = newPlans[idx];
      newPlans[idx] = newPlans[idx + 1];
      newPlans[idx + 1] = temp;
    } else {
      return;
    }
    setIsLoading(true);
    try {
      await superAdminApi.reorderPlans(newPlans.map(p => p.id));
      await fetchAllData();
    } catch (err: any) {
      setGlobalError('Failed to save plans display sequence');
    } finally {
      setIsLoading(false);
    }
  };

  // ==========================================
  // FEATURE MATRIX ACTIONS
  // ==========================================
  const isFeatureMapped = (planId: string, featureId: string) => {
    return mappings.some(m => m.plan_id === planId && m.feature_id === featureId && m.enabled);
  };

  const handleToggleFeature = async (planId: string, featureId: string) => {
    const currentEnabled = isFeatureMapped(planId, featureId);
    try {
      await superAdminApi.togglePlanFeature({
        plan_id: planId,
        feature_id: featureId,
        enabled: !currentEnabled
      });
      // Optimistic update local state
      const updatedMappings = [...mappings];
      const idx = updatedMappings.findIndex(m => m.plan_id === planId && m.feature_id === featureId);
      if (idx !== -1) {
        updatedMappings[idx].enabled = !currentEnabled;
      } else {
        updatedMappings.push({
          id: '',
          plan_id: planId,
          feature_id: featureId,
          enabled: !currentEnabled
        });
      }
      setMappings(updatedMappings);
      showSuccess('Plan feature mapping updated successfully.');
    } catch (err: any) {
      setGlobalError('Failed to toggle feature mapping');
    }
  };

  // ==========================================
  // SYSTEM SETTINGS ACTIONS
  // ==========================================
  const handleSaveInvoiceSettings = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const value = {
      company_name: formData.get('company_name'),
      gst_number: formData.get('gst_number'),
      billing_address: formData.get('billing_address'),
      invoice_prefix: formData.get('invoice_prefix') || 'INV'
    };
    setIsLoading(true);
    try {
      await superAdminApi.upsertSystemSetting({ key: 'invoice_settings', value });
      showSuccess('Invoicing configuration saved.');
    } catch (err: any) {
      setGlobalError('Failed to save invoice settings');
    } finally {
      setIsLoading(false);
    }
  };

  const handleSaveSystemSettings = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const formData = new FormData(e.currentTarget);
    const smtp = {
      host: formData.get('smtp_host'),
      port: Number(formData.get('smtp_port')),
      user: formData.get('smtp_user'),
      from_name: formData.get('smtp_from_name')
    };
    const knowlarity = {
      api_key: formData.get('k_key'),
      agent_number: formData.get('k_agent')
    };
    setIsLoading(true);
    try {
      await superAdminApi.upsertSystemSetting({ key: 'smtp_settings', value: smtp });
      await superAdminApi.upsertSystemSetting({ key: 'telephony_settings', value: knowlarity });
      showSuccess('Core SMTP & Telephony settings updated.');
    } catch (err: any) {
      setGlobalError('Failed to save system settings');
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
      {/* Tab Navigation header */}
      <div className="flex flex-col border-b border-slate-800 pb-2">
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">
              Super Admin Command Center
            </h1>
            <p className="text-sm text-slate-400 mt-1">
              Configure dynamic plans, map permissions, toggle features, manage billing ledgers, and verify setups.
            </p>
          </div>
        </div>

        {/* Tab Links */}
        <div className="flex items-center gap-1.5 mt-6 overflow-x-auto pb-1 scrollbar-thin">
          <button 
            onClick={() => setActiveTab('tenants')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer shrink-0 ${
              activeTab === 'tenants' ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/10' : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
            }`}
          >
            <Building className="w-4 h-4" />
            Tenants Registry
          </button>
          <button 
            onClick={() => setActiveTab('plans')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer shrink-0 ${
              activeTab === 'plans' ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/10' : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
            }`}
          >
            <FolderKanban className="w-4 h-4" />
            Plan Templates
          </button>
          <button 
            onClick={() => setActiveTab('features')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer shrink-0 ${
              activeTab === 'features' ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/10' : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
            }`}
          >
            <Workflow className="w-4 h-4" />
            Feature Matrix
          </button>
          <button 
            onClick={() => setActiveTab('invoice-settings')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer shrink-0 ${
              activeTab === 'invoice-settings' ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/10' : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
            }`}
          >
            <FileText className="w-4 h-4" />
            Invoice Config
          </button>
          <button 
            onClick={() => setActiveTab('system-settings')}
            className={`flex items-center gap-2 px-4 py-2.5 rounded-xl text-xs font-semibold uppercase tracking-wider transition-all cursor-pointer shrink-0 ${
              activeTab === 'system-settings' ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/10' : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200'
            }`}
          >
            <Settings className="w-4 h-4" />
            System Settings
          </button>
        </div>
      </div>

      {globalError && (
        <div className="p-4 bg-red-950/20 border border-red-900/30 rounded-2xl flex items-start gap-2.5 text-sm text-red-400">
          <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{globalError}</span>
        </div>
      )}

      {successMessage && (
        <div className="p-4 bg-emerald-950/20 border border-emerald-900/30 rounded-2xl flex items-start gap-2.5 text-sm text-emerald-400">
          <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" />
          <span>{successMessage}</span>
        </div>
      )}

      {isLoading ? (
        <div className="glass-panel p-20 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-400">
          <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
          <p className="text-sm font-medium">Fetching details from configuration ledger...</p>
        </div>
      ) : (
        <>
          {/* ==========================================
              TAB 1: TENANTS REGISTRY
             ========================================== */}
          {activeTab === 'tenants' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Tenants List</h3>
                <button
                  onClick={() => {
                    resetTenant();
                    setModalError(null);
                    setActiveModal('createTenant');
                  }}
                  className="flex items-center justify-center gap-1.5 px-4 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Create Tenant
                </button>
              </div>

              {tenants.length === 0 ? (
                <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-500 text-center">
                  <Building className="w-12 h-12 text-slate-600 mb-3" />
                  <p className="text-base font-semibold text-slate-400">No Tenants Found</p>
                  <p className="text-xs text-slate-500 mt-1">Spin up a new tenant to initiate database instances.</p>
                </div>
              ) : (
                <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 bg-slate-900/20">
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Company / Subdomain</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Status</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Tier / Max Seats</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400">Expires At</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400 text-center">Resources</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-slate-400 text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 bg-slate-950/10">
                        {tenants.map((tenant) => (
                          <tr key={tenant.id} className="hover:bg-slate-900/10 transition-colors">
                            <td className="px-6 py-4.5">
                              <div>
                                <p className="text-sm font-semibold text-slate-200">{tenant.name}</p>
                                <p className="text-xs text-slate-500">/{tenant.slug}</p>
                              </div>
                            </td>
                            <td className="px-6 py-4.5">
                              <span className={`inline-flex items-center gap-1 text-xs font-medium ${
                                tenant.subscription_status.toLowerCase() === 'active' && tenant.is_active ? 'text-emerald-400' : 'text-rose-400'
                              }`}>
                                <span className={`w-1.5 h-1.5 rounded-full ${
                                  tenant.subscription_status.toLowerCase() === 'active' && tenant.is_active ? 'bg-emerald-400' : 'bg-rose-400'
                                }`} />
                                {tenant.subscription_status} {tenant.is_active ? '' : '(Suspended)'}
                              </span>
                            </td>
                            <td className="px-6 py-4.5">
                              <div>
                                <span className="inline-block px-2 py-0.5 text-[10px] font-bold rounded bg-brand-500/10 text-brand-400 border border-brand-500/20 uppercase tracking-wider">
                                  {tenant.subscription_plan}
                                </span>
                                <p className="text-[10px] text-slate-400 mt-1">Users Limit: {tenant.max_users}</p>
                              </div>
                            </td>
                            <td className="px-6 py-4.5 text-xs text-slate-300">
                              {tenant.subscription_expires_at 
                                ? new Date(tenant.subscription_expires_at).toLocaleDateString()
                                : 'Lifetime'
                              }
                            </td>
                            <td className="px-6 py-4.5 text-center">
                              <div className="flex justify-center items-center gap-4">
                                <button 
                                  onClick={() => openUsersModal(tenant)}
                                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-brand-400 transition-colors cursor-pointer"
                                >
                                  <Users className="w-4 h-4 text-slate-500" />
                                  <span>{tenant.user_count}</span>
                                </button>
                                <button 
                                  onClick={() => openInvoicesModal(tenant)}
                                  className="flex items-center gap-1 text-xs text-slate-400 hover:text-indigo-400 transition-colors cursor-pointer"
                                >
                                  <FileText className="w-4 h-4 text-slate-500" />
                                  <span>{tenant.invoice_count}</span>
                                </button>
                              </div>
                            </td>
                            <td className="px-6 py-4.5 text-right">
                              <div className="flex items-center justify-end gap-2.5">
                                <button
                                  onClick={() => openEditSubModal(tenant)}
                                  className="px-2 py-1.5 border border-slate-800 hover:bg-slate-900 rounded-lg text-slate-300 transition-all text-xs font-semibold flex items-center gap-1 cursor-pointer"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                  Tier
                                </button>
                                <button
                                  onClick={() => {
                                    setSelectedTenant(tenant);
                                    setActiveModal('resetPassword');
                                  }}
                                  className="p-1.5 border border-slate-800 hover:bg-slate-900 rounded-lg text-slate-300 transition-all cursor-pointer"
                                  title="Reset Owner Password"
                                >
                                  <Key className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => handleSuspendTenant(tenant)}
                                  className={`p-1.5 border border-slate-800 hover:bg-slate-900 rounded-lg transition-all cursor-pointer ${
                                    tenant.is_active ? 'text-amber-400 hover:text-amber-300' : 'text-emerald-400 hover:text-emerald-300'
                                  }`}
                                  title={tenant.is_active ? 'Suspend Account' : 'Reactivate Account'}
                                >
                                  <Lock className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => {
                                    setSelectedTenant(tenant);
                                    setDeleteConfirmSlug('');
                                    setActiveModal('deleteTenantConfirm');
                                  }}
                                  className="p-1.5 border border-slate-800 hover:bg-red-500/10 hover:border-red-500/20 text-red-400 rounded-lg transition-all cursor-pointer"
                                  title="Delete Tenant Database"
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
            </div>
          )}

          {/* ==========================================
              TAB 2: PLANS CRUD
             ========================================== */}
          {activeTab === 'plans' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Subscription Plans</h3>
                <button
                  onClick={() => {
                    resetPlan();
                    setSelectedPlan(null);
                    setModalError(null);
                    setActiveModal('createPlan');
                  }}
                  className="flex items-center justify-center gap-1.5 px-4 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
                >
                  <Plus className="w-3.5 h-3.5" />
                  Add Plan
                </button>
              </div>

              {plans.length === 0 ? (
                <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-500 text-center">
                  <FolderKanban className="w-12 h-12 text-slate-600 mb-3" />
                  <p className="text-base font-semibold text-slate-400">No Custom Plans Registered</p>
                  <p className="text-xs text-slate-500 mt-1">Add your first commercial pricing plan to begin assigning tenant limits.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {plans.map((plan) => (
                    <div key={plan.id} className="glass-panel p-6 border border-slate-800/80 rounded-2xl space-y-4 relative flex flex-col justify-between hover:border-slate-800 transition-all">
                      <div className="space-y-2">
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className="text-lg font-bold text-slate-100">{plan.display_name}</h4>
                            <p className="text-xs text-slate-500 font-mono">slug: {plan.name}</p>
                          </div>
                          <div className="flex items-center gap-1 bg-slate-900 border border-slate-800 rounded-lg p-0.5">
                            <button 
                              onClick={() => handleReorderPlans(plan.id, 'up')}
                              className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
                            >
                              <ArrowUpDown className="w-3 h-3 rotate-180" />
                            </button>
                            <button 
                              onClick={() => handleReorderPlans(plan.id, 'down')}
                              className="p-1 hover:bg-slate-800 rounded text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
                            >
                              <ArrowUpDown className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                        <p className="text-xs text-slate-400 line-clamp-2">{plan.description || 'No description provided.'}</p>
                        
                        <div className="py-2 border-y border-slate-800/80 flex justify-between items-baseline gap-2">
                          <span className="text-2xl font-black text-brand-400">
                            {plan.currency} {plan.monthly_price}
                          </span>
                          <span className="text-xs text-slate-500">/ month</span>
                        </div>

                        <div className="space-y-1.5 pt-2">
                          <p className="text-xs text-slate-300 flex items-center gap-2">
                            <Users className="w-3.5 h-3.5 text-slate-500" />
                            <span>Max Seats: <strong>{plan.max_users}</strong></span>
                          </p>
                          <p className="text-xs text-slate-300 flex items-center gap-2">
                            <Building className="w-3.5 h-3.5 text-slate-500" />
                            <span>Storage limit: <strong>{plan.storage_limit_gb} GB</strong></span>
                          </p>
                          <p className="text-xs text-slate-300 flex items-center gap-2">
                            <FileText className="w-3.5 h-3.5 text-slate-500" />
                            <span>Retention: <strong>{plan.recording_retention_days} days</strong></span>
                          </p>
                          <p className="text-xs text-slate-300 flex items-center gap-2">
                            <Check className="w-3.5 h-3.5 text-emerald-500" />
                            <span>Contract: <strong>{plan.minimum_contract_months} months</strong></span>
                          </p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 pt-4 border-t border-slate-800/50">
                        <button
                          onClick={() => {
                            setSelectedPlan(plan);
                            setModalError(null);
                            // Populate values
                            Object.keys(plan).forEach((key) => {
                              setPlanValue(key as any, plan[key as keyof PlanResponse]);
                            });
                            setActiveModal('editPlan');
                          }}
                          className="flex-1 py-2 bg-slate-900 border border-slate-800 hover:border-slate-700 text-slate-300 rounded-xl text-xs font-semibold transition-all cursor-pointer text-center"
                        >
                          Configure
                        </button>
                        <button
                          onClick={() => handleDeletePlan(plan.id)}
                          className="p-2 border border-slate-800 hover:border-red-500/30 hover:bg-red-500/10 text-red-400 rounded-xl transition-all cursor-pointer"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ==========================================
              TAB 3: FEATURE MATRIX
             ========================================== */}
          {activeTab === 'features' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-slate-400">Plan Permissions Matrix</h3>
                <p className="text-xs text-slate-500 mt-1">Cross-check plans mapping checkbox cells to dynamically authorize API scopes.</p>
              </div>

              {plans.length === 0 || features.length === 0 ? (
                <div className="glass-panel p-16 rounded-2xl border border-slate-800/80 flex flex-col items-center justify-center text-slate-500 text-center">
                  <Workflow className="w-12 h-12 text-slate-600 mb-3" />
                  <p className="text-base font-semibold text-slate-400">Setup Required</p>
                  <p className="text-xs text-slate-500 mt-1">You must create at least one Plan Template and seed features to build matrix mappings.</p>
                </div>
              ) : (
                <div className="glass-panel rounded-2xl border border-slate-800/80 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-slate-800 bg-slate-900/20">
                          <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Feature Description</th>
                          <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-slate-400">Category</th>
                          {plans.map((p) => (
                            <th key={p.id} className="px-6 py-4.5 text-xs font-bold uppercase tracking-wider text-brand-400 text-center">
                              {p.display_name}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-800 bg-slate-950/10">
                        {features.map((feature) => (
                          <tr key={feature.id} className="hover:bg-slate-900/10 transition-colors">
                            <td className="px-6 py-4">
                              <div>
                                <p className="text-sm font-semibold text-slate-200">{feature.display_name}</p>
                                <p className="text-[10px] text-slate-500 font-mono">code: {feature.code}</p>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <span className="inline-block px-1.5 py-0.5 text-[9px] font-semibold bg-slate-800 text-slate-400 rounded uppercase tracking-wider">
                                {feature.category}
                              </span>
                            </td>
                            {plans.map((plan) => {
                              const enabled = isFeatureMapped(plan.id, feature.id);
                              return (
                                <td key={plan.id} className="px-6 py-4 text-center">
                                  <button
                                    onClick={() => handleToggleFeature(plan.id, feature.id)}
                                    className={`w-6 h-6 rounded-lg border flex items-center justify-center transition-all cursor-pointer mx-auto ${
                                      enabled 
                                        ? 'bg-brand-500/20 border-brand-500/40 text-brand-400 shadow-md shadow-brand-500/5' 
                                        : 'border-slate-800 hover:border-slate-700 bg-slate-900/40 text-transparent'
                                    }`}
                                  >
                                    <CheckSquare className="w-4 h-4" />
                                  </button>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ==========================================
              TAB 4: INVOICE CONFIGURATION
             ========================================== */}
          {activeTab === 'invoice-settings' && (
            <div className="max-w-2xl">
              <div className="glass-panel p-6 border border-slate-800/80 rounded-2xl space-y-6">
                <div>
                  <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                    <FileText className="w-5 h-5 text-indigo-400" />
                    Invoicing Settings
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">Configure company billing address, prefix logs, and tax/GST rules for invoice generations.</p>
                </div>

                <form onSubmit={handleSaveInvoiceSettings} className="space-y-4">
                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Company Name (Billing Issuer)</label>
                    <input
                      type="text"
                      name="company_name"
                      defaultValue={settingsData['invoice_settings']?.company_name || 'Johnson Softwares Ltd.'}
                      className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                    />
                  </div>

                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Tax / GST Number</label>
                      <input
                        type="text"
                        name="gst_number"
                        defaultValue={settingsData['invoice_settings']?.gst_number || '27AAAAA1111A1Z1'}
                        className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Invoice Number Prefix</label>
                      <input
                        type="text"
                        name="invoice_prefix"
                        defaultValue={settingsData['invoice_settings']?.invoice_prefix || 'INV'}
                        className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Billing Address & Support Contact</label>
                    <textarea
                      name="billing_address"
                      rows={4}
                      defaultValue={settingsData['invoice_settings']?.billing_address || '101, Antigravity Heights, Google DeepMind St, BKC, Mumbai - 400051.\nSupport: billing@johnsonsoftwares.com'}
                      className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                    />
                  </div>

                  <button
                    type="submit"
                    className="flex items-center justify-center gap-1.5 px-5 py-3 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
                  >
                    Save Invoice Config
                  </button>
                </form>
              </div>
            </div>
          )}

          {/* ==========================================
              TAB 5: SYSTEM CONFIGURATIONS
             ========================================== */}
          {activeTab === 'system-settings' && (
            <div className="max-w-2xl">
              <div className="glass-panel p-6 border border-slate-800/80 rounded-2xl space-y-6">
                <div>
                  <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                    <Settings className="w-5 h-5 text-indigo-400" />
                    SMTP & Telephony Settings
                  </h3>
                  <p className="text-xs text-slate-500 mt-1">Register default system mailer connections and external calling gateway keys securely.</p>
                </div>

                <form onSubmit={handleSaveSystemSettings} className="space-y-6">
                  {/* SMTP CONFIG */}
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 border-b border-slate-800/80 pb-2">SMTP Mailer Settings</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">SMTP Host</label>
                        <input
                          type="text"
                          name="smtp_host"
                          defaultValue={settingsData['smtp_settings']?.host || 'smtp.mailgun.org'}
                          className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">SMTP Port</label>
                        <input
                          type="number"
                          name="smtp_port"
                          defaultValue={settingsData['smtp_settings']?.port || 587}
                          className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Sender Username</label>
                        <input
                          type="text"
                          name="smtp_user"
                          defaultValue={settingsData['smtp_settings']?.user || 'postmaster@mg.johnsonsoftwares.com'}
                          className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Sender Display Name</label>
                        <input
                          type="text"
                          name="smtp_from_name"
                          defaultValue={settingsData['smtp_settings']?.from_name || 'TeleCRM Invoices'}
                          className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>

                  {/* TELEPHONY CONFIG */}
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 border-b border-slate-800/80 pb-2">Telephony Gateway (Knowlarity)</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Knowlarity API Key</label>
                        <input
                          type="password"
                          name="k_key"
                          defaultValue={settingsData['telephony_settings']?.api_key || '••••••••••••••••'}
                          className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Primary Agent ID Number</label>
                        <input
                          type="text"
                          name="k_agent"
                          defaultValue={settingsData['telephony_settings']?.agent_number || '+912250972233'}
                          className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>

                  <button
                    type="submit"
                    className="flex items-center justify-center gap-1.5 px-5 py-3 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer"
                  >
                    Save System Configs
                  </button>
                </form>
              </div>
            </div>
          )}
        </>
      )}

      {/* ==========================================
          MODALS & DRAWERS
         ========================================== */}

      {/* RESET OWNER PASSWORD MODAL */}
      {activeModal === 'resetPassword' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel border border-slate-800/90 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                  <Key className="w-5 h-5 text-amber-400" />
                  Reset Admin Password
                </h3>
                <p className="text-xs text-slate-400">Force password reset for the primary OrgAdmin of <strong>{selectedTenant.name}</strong>.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleResetPassword} className="p-6 space-y-4">
              {modalError && (
                <div className="p-3 bg-red-950/20 border border-red-900/30 rounded-xl text-sm text-red-400">
                  {modalError}
                </div>
              )}

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">New Password</label>
                <input
                  type="password"
                  placeholder="Minimum 8 characters"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
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
                  {isModalLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Reset Password'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE PLAN MODAL */}
      {(activeModal === 'createPlan' || activeModal === 'editPlan') && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-2xl glass-panel border border-slate-800/90 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="px-6 py-5 border-b border-slate-800/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                  <FolderKanban className="w-5 h-5 text-brand-400" />
                  {activeModal === 'createPlan' ? 'Create Plan Template' : 'Configure Plan Limits'}
                </h3>
                <p className="text-xs text-slate-400">Define specifications, pricing bounds, setup costs, and storage limits.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-colors cursor-pointer"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handlePlanSubmit(activeModal === 'createPlan' ? handleCreatePlan : handleEditPlan)} className="p-6 space-y-4 max-h-[75vh] overflow-y-auto">
              {modalError && (
                <div className="p-3 bg-red-950/20 border border-red-900/30 rounded-xl text-sm text-red-400">
                  {modalError}
                </div>
              )}

              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Plan Code Name (Slug)</label>
                  <input
                    type="text"
                    placeholder="starter"
                    disabled={activeModal === 'editPlan'}
                    {...regPlan('name', { required: 'Slug name is required', pattern: { value: /^[a-z0-9-]+$/i, message: 'Alphanumeric & hyphens only' } })}
                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none disabled:opacity-50"
                  />
                  {planErrors.name && <p className="text-xs text-red-400 mt-1">{planErrors.name.message}</p>}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Display Name</label>
                  <input
                    type="text"
                    placeholder="Starter Plan"
                    {...regPlan('display_name', { required: 'Display name is required' })}
                    className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                  {planErrors.display_name && <p className="text-xs text-red-400 mt-1">{planErrors.display_name.message}</p>}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Description</label>
                <textarea
                  placeholder="Describe target market or features highlight"
                  rows={2}
                  {...regPlan('description')}
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-4 gap-4">
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-2">Monthly ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('monthly_price', { required: true, min: 0 })}
                    className="w-full px-3 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-2">Quarterly ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('quarterly_price', { required: true, min: 0 })}
                    className="w-full px-3 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-2">Annual ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('annual_price', { required: true, min: 0 })}
                    className="w-full px-3 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-slate-400 uppercase mb-2">Currency</label>
                  <input
                    type="text"
                    {...regPlan('currency', { required: true })}
                    className="w-full px-3 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
              </div>

              <div className="border-t border-slate-800/80 pt-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 mb-3">Seat Limits & Allocation Counts</h4>
                <div className="grid grid-cols-5 gap-3">
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1.5">Max Users</label>
                    <input
                      type="number"
                      {...regPlan('max_users', { required: true, min: 1 })}
                      className="w-full px-2 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 text-center focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1.5">Max Admins</label>
                    <input
                      type="number"
                      {...regPlan('max_admins', { required: true, min: 1 })}
                      className="w-full px-2 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 text-center focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1.5">Max Mgrs</label>
                    <input
                      type="number"
                      {...regPlan('max_managers', { required: true, min: 0 })}
                      className="w-full px-2 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 text-center focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1.5">Max TLs</label>
                    <input
                      type="number"
                      {...regPlan('max_team_leads', { required: true, min: 0 })}
                      className="w-full px-2 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 text-center focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1.5">Max Agents</label>
                    <input
                      type="number"
                      {...regPlan('max_employees', { required: true, min: 0 })}
                      className="w-full px-2 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 text-center focus:outline-none"
                    />
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 border-t border-slate-800/80 pt-4">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Storage Limit (GB)</label>
                  <input
                    type="number"
                    {...regPlan('storage_limit_gb', { required: true, min: 1 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Retention (Days)</label>
                  <input
                    type="number"
                    {...regPlan('recording_retention_days', { required: true, min: 1 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Display Order</label>
                  <input
                    type="number"
                    {...regPlan('display_order', { required: true })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-4 gap-3 border-t border-slate-800/80 pt-4">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Setup Charge ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('setup_charges', { required: true, min: 0 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Min Users</label>
                  <input
                    type="number"
                    {...regPlan('minimum_users', { required: true, min: 1 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Max Users Bound</label>
                  <input
                    type="number"
                    {...regPlan('maximum_users', { required: true, min: 1 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Min Contract (m)</label>
                  <input
                    type="number"
                    {...regPlan('minimum_contract_months', { required: true, min: 1 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
              </div>

              <div className="flex gap-6 border-t border-slate-800/80 pt-4">
                <label className="flex items-center gap-2 text-xs text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('priority_support')}
                    className="w-4 h-4 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  Priority Support SLA Enabled
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('api_access')}
                    className="w-4 h-4 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  API Credentials Access Enabled
                </label>
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
                  {isModalLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Plan Template'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* CREATE TENANT MODAL */}
      {activeModal === 'createTenant' && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-lg glass-panel border border-slate-800/90 rounded-2xl shadow-2xl relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
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
                  className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
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
                  {isModalLoading ? <Loader2 className="w-4 h-4 animate-spin" /> : 'Save Settings'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* VIEW USERS SIDE DRAWER */}
      {activeModal === 'users' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md h-screen bg-slate-950 border-l border-slate-800 flex flex-col justify-between shadow-2xl animate-slide-in">
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

      {/* VIEW INVOICES MODAL */}
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
                <div className="glass-panel p-5 border border-slate-800/70 rounded-xl space-y-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Generate Manual Invoice</h4>
                  
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
                      className="w-full flex items-center justify-center gap-1.5 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 text-white rounded-xl text-xs font-bold transition-all cursor-pointer disabled:opacity-50"
                    >
                      {isModalLoading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />}
                      Generate Invoice
                    </button>
                  </form>
                </div>

                <div className="md:col-span-2 space-y-3">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-indigo-400">Invoice Ledger</h4>

                  {isModalLoading && invoices.length === 0 ? (
                    <div className="text-center py-10 text-slate-400">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-brand-500" />
                      <p className="text-xs">Loading invoices history...</p>
                    </div>
                  ) : invoices.length === 0 ? (
                    <div className="p-8 border border-dashed border-slate-800 rounded-xl text-center text-slate-500">
                      <FileText className="w-6 h-6 mx-auto mb-2 text-slate-600" />
                      <p className="text-xs font-semibold">No invoices generated</p>
                      <p className="text-[10px] text-slate-600 mt-0.5">Generate a billing invoice on the left form to begin history.</p>
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
                            title="Click to toggle status: Paid -> Pending -> Overdue -> Paid"
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

      {/* DELETE TENANT CONFIRMATION MODAL */}
      {activeModal === 'deleteTenantConfirm' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel border border-red-500/30 rounded-2xl shadow-2xl relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
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
                className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-red-500/40"
              />
            </div>

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
