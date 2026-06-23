import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { 
  Building, Users, FileText, Edit, Plus, X, ShieldAlert, 
  Loader2, Calendar, DollarSign, CheckCircle2, AlertCircle, Clock, Trash2,
  Workflow, CheckSquare, Settings, Lock, Check, Key, ArrowUpDown, FolderKanban,
  Upload, Mail, CreditCard, Image, Receipt, Percent
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
  const [invoiceConfig, setInvoiceConfig] = useState<any>(null);
  const [editedConfig, setEditedConfig] = useState<any>(null);
  const [invoiceConfigSubTab, setInvoiceConfigSubTab] = useState<'general' | 'branding' | 'tax' | 'invoice' | 'payment' | 'email' | 'footer'>('general');
  const [isUploading, setIsUploading] = useState(false);
  
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
      } else if (activeTab === 'invoice-settings') {
        const data = await superAdminApi.getInvoiceConfig();
        setInvoiceConfig(data);
        setEditedConfig(data);
      } else if (activeTab === 'system-settings') {
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
        minimum_contract_months: Number(data.minimum_contract_months),
        trial_days: Number(data.trial_days || 0),
        extra_user_price: Number(data.extra_user_price || 0),
        discount_percentage: Number(data.discount_percentage || 0),
        gst_percentage: Number(data.gst_percentage || 0),
        popular_plan: Boolean(data.popular_plan),
        recommended_plan: Boolean(data.recommended_plan),
        allow_upgrade: Boolean(data.allow_upgrade),
        allow_downgrade: Boolean(data.allow_downgrade),
        allow_trial: Boolean(data.allow_trial),
        auto_renew: Boolean(data.auto_renew),
        plan_active: Boolean(data.plan_active)
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
        minimum_contract_months: Number(data.minimum_contract_months),
        trial_days: Number(data.trial_days || 0),
        extra_user_price: Number(data.extra_user_price || 0),
        discount_percentage: Number(data.discount_percentage || 0),
        gst_percentage: Number(data.gst_percentage || 0),
        popular_plan: Boolean(data.popular_plan),
        recommended_plan: Boolean(data.recommended_plan),
        allow_upgrade: Boolean(data.allow_upgrade),
        allow_downgrade: Boolean(data.allow_downgrade),
        allow_trial: Boolean(data.allow_trial),
        auto_renew: Boolean(data.auto_renew),
        plan_active: Boolean(data.plan_active)
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
  // INVOICE DYNAMIC CONFIGURATION ACTIONS
  // ==========================================
  const handleSaveConfig = async () => {
    if (!editedConfig) return;
    setIsLoading(true);
    setGlobalError(null);
    try {
      const updated = await superAdminApi.updateInvoiceConfig(editedConfig);
      setInvoiceConfig(updated);
      setEditedConfig(updated);
      showSuccess("Invoice configuration updated successfully.");
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || "Failed to update configuration.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setIsUploading(true);
    setGlobalError(null);
    try {
      const updated = await superAdminApi.uploadCompanyLogo(file);
      setInvoiceConfig(updated);
      setEditedConfig(updated);
      showSuccess("Company logo uploaded successfully.");
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || "Failed to upload logo.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleQrUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files || e.target.files.length === 0) return;
    const file = e.target.files[0];
    setIsUploading(true);
    setGlobalError(null);
    try {
      const updated = await superAdminApi.uploadPaymentQr(file);
      setInvoiceConfig(updated);
      setEditedConfig(updated);
      showSuccess("Payment QR code uploaded successfully.");
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || "Failed to upload QR code.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteLogo = async () => {
    if (!confirm("Are you sure you want to delete the company logo?")) return;
    setIsUploading(true);
    setGlobalError(null);
    try {
      const updated = await superAdminApi.deleteCompanyLogo();
      setInvoiceConfig(updated);
      setEditedConfig(updated);
      showSuccess("Company logo deleted.");
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || "Failed to delete logo.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleDeleteQr = async () => {
    if (!confirm("Are you sure you want to delete the payment QR code?")) return;
    setIsUploading(true);
    setGlobalError(null);
    try {
      const updated = await superAdminApi.deletePaymentQr();
      setInvoiceConfig(updated);
      setEditedConfig(updated);
      showSuccess("Payment QR code deleted.");
    } catch (err: any) {
      setGlobalError(err.response?.data?.detail || "Failed to delete QR code.");
    } finally {
      setIsUploading(false);
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
          {activeTab === 'invoice-settings' && editedConfig && (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              {/* Left Column: Config Forms (col-span-2) */}
              <div className="xl:col-span-2 space-y-6">
                <div className="glass-panel p-6 border border-slate-800/80 rounded-2xl space-y-6">
                  <div>
                    <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2">
                      <FileText className="w-5 h-5 text-indigo-400" />
                      Dynamic Invoice Ledger settings
                    </h3>
                    <p className="text-xs text-slate-500 mt-1">
                      Configure dynamic values, bank specifications, pan details, prefix parameters, and transaction details.
                    </p>
                  </div>

                  {/* Sub-tab Navigation */}
                  <div className="flex border-b border-slate-800 pb-2 overflow-x-auto gap-1.5 scrollbar-thin">
                    {[
                      { id: 'general', label: 'General', icon: Building },
                      { id: 'branding', label: 'Branding', icon: Image },
                      { id: 'tax', label: 'Tax details', icon: Percent },
                      { id: 'invoice', label: 'Invoices', icon: Receipt },
                      { id: 'payment', label: 'Payment Specs', icon: CreditCard },
                      { id: 'email', label: 'Email Templates', icon: Mail },
                      { id: 'footer', label: 'Footer & Terms', icon: Clock }
                    ].map((subTab) => (
                      <button
                        key={subTab.id}
                        type="button"
                        onClick={() => setInvoiceConfigSubTab(subTab.id as any)}
                        className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer whitespace-nowrap border ${
                          invoiceConfigSubTab === subTab.id
                            ? 'bg-brand-500/10 text-brand-400 border-brand-500/30'
                            : 'text-slate-400 hover:bg-slate-900/60 hover:text-slate-200 border-transparent'
                        }`}
                      >
                        <subTab.icon className="w-3.5 h-3.5" />
                        {subTab.label}
                      </button>
                    ))}
                  </div>

                  {/* Forms content */}
                  <div className="space-y-4 pt-2">
                    {/* General Settings */}
                    {invoiceConfigSubTab === 'general' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Company Name (Billing Issuer)</label>
                          <input
                            type="text"
                            value={editedConfig.company_name || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, company_name: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="Enter company billing name"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Tagline</label>
                          <input
                            type="text"
                            value={editedConfig.tagline || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, tagline: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. Beyond boundaries"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Website</label>
                          <input
                            type="text"
                            value={editedConfig.website || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, website: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. www.johnsonsoftwares.com"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Support Contact Email</label>
                          <input
                            type="email"
                            value={editedConfig.support_email || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, support_email: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. billing@johnsonsoftwares.com"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Phone Number</label>
                          <input
                            type="text"
                            value={editedConfig.phone_number || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, phone_number: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. +91 22 5097 2233"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Billing Address</label>
                          <textarea
                            rows={3}
                            value={editedConfig.address || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, address: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="Enter physical billing address"
                          />
                        </div>
                      </div>
                    )}

                    {/* Branding logo/qr uploads */}
                    {invoiceConfigSubTab === 'branding' && (
                      <div className="space-y-6 text-left">
                        <div className="space-y-2">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Company Logo branding</h4>
                          <p className="text-xs text-slate-500">Served dynamically at the top header of client invoice cards.</p>
                          {editedConfig.company_logo_url ? (
                            <div className="flex items-center gap-4 p-4 bg-slate-900 border border-slate-800 rounded-xl">
                              <img
                                src={editedConfig.company_logo_url}
                                alt="Company Logo"
                                className="max-h-16 max-w-[200px] object-contain rounded bg-slate-950 p-2"
                              />
                              <div>
                                <p className="text-xs font-semibold text-slate-300">Logo active</p>
                                <button
                                  type="button"
                                  onClick={handleDeleteLogo}
                                  className="mt-2 text-xs text-red-400 hover:text-red-300 font-bold transition-all flex items-center gap-1 cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                  Delete logo
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="relative border-2 border-dashed border-slate-800 hover:border-brand-500/50 transition-all rounded-xl p-6 flex flex-col items-center justify-center bg-slate-950/20 text-center">
                              {isUploading ? (
                                <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-2" />
                              ) : (
                                <Upload className="w-8 h-8 text-slate-500 mb-2" />
                              )}
                              <label className="text-xs font-semibold text-brand-400 cursor-pointer">
                                <span>Upload logo file</span>
                                <input
                                  type="file"
                                  accept="image/*"
                                  onChange={handleLogoUpload}
                                  className="hidden"
                                />
                              </label>
                              <span className="text-[10px] text-slate-500 mt-1">PNG, JPG, SVG up to 2MB</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Tax & GST settings */}
                    {invoiceConfigSubTab === 'tax' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">GSTIN / Tax ID Number</label>
                          <input
                            type="text"
                            value={editedConfig.gst_number || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, gst_number: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. 27AAAAA1111A1Z1"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">PAN Number</label>
                          <input
                            type="text"
                            value={editedConfig.pan || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, pan: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. ABCDE1234F"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Business Registration Number</label>
                          <input
                            type="text"
                            value={editedConfig.business_registration_number || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, business_registration_number: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. CIN / U12345MH2026PTC123456"
                          />
                        </div>
                      </div>
                    )}

                    {/* Invoice setup prefix */}
                    {invoiceConfigSubTab === 'invoice' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Invoice Number Prefix</label>
                          <input
                            type="text"
                            value={editedConfig.invoice_prefix || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, invoice_prefix: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. TELE-INV"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Starting Invoice Number</label>
                          <input
                            type="number"
                            min="1"
                            value={editedConfig.starting_invoice_number || 1000}
                            onChange={(e) => setEditedConfig({ ...editedConfig, starting_invoice_number: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Currency Code</label>
                          <input
                            type="text"
                            value={editedConfig.currency || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, currency: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. INR, USD"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Currency Symbol</label>
                          <input
                            type="text"
                            value={editedConfig.currency_symbol || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, currency_symbol: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. ₹, $"
                          />
                        </div>
                      </div>
                    )}

                    {/* Payment specifications */}
                    {invoiceConfigSubTab === 'payment' && (
                      <div className="space-y-4 text-left">
                        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Bank Name</label>
                            <input
                              type="text"
                              value={editedConfig.bank_name || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, bank_name: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                              placeholder="e.g. HDFC Bank"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Account Holder</label>
                            <input
                              type="text"
                              value={editedConfig.account_holder || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, account_holder: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                              placeholder="e.g. Johnson Softwares Limited"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Account Number</label>
                            <input
                              type="text"
                              value={editedConfig.account_number || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, account_number: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                              placeholder="e.g. 50100123456789"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">IFSC Code</label>
                            <input
                              type="text"
                              value={editedConfig.ifsc || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, ifsc: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                              placeholder="e.g. HDFC0000101"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Branch Name</label>
                            <input
                              type="text"
                              value={editedConfig.branch || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, branch: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                              placeholder="e.g. BKC Branch, Mumbai"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">UPI ID</label>
                            <input
                              type="text"
                              value={editedConfig.upi_id || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, upi_id: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                              placeholder="e.g. johnsonsoftwares@hdfc"
                            />
                          </div>
                        </div>

                        <div className="space-y-2 pt-2 border-t border-slate-800/80">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Payment QR Code image</h4>
                          <p className="text-xs text-slate-500">Rendered on the footer of client invoices for direct scan & pay.</p>
                          {editedConfig.qr_code_url ? (
                            <div className="flex items-center gap-4 p-4 bg-slate-900 border border-slate-800 rounded-xl">
                              <img
                                src={editedConfig.qr_code_url}
                                alt="Payment QR"
                                className="w-24 h-24 object-contain rounded bg-white p-1"
                              />
                              <div>
                                <p className="text-xs font-semibold text-slate-300">QR Code active</p>
                                <button
                                  type="button"
                                  onClick={handleDeleteQr}
                                  className="mt-2 text-xs text-red-400 hover:text-red-300 font-bold transition-all flex items-center gap-1 cursor-pointer"
                                >
                                  <Trash2 className="w-3.5 h-3.5" />
                                  Delete QR code
                                </button>
                              </div>
                            </div>
                          ) : (
                            <div className="relative border-2 border-dashed border-slate-800 hover:border-brand-500/50 transition-all rounded-xl p-6 flex flex-col items-center justify-center bg-slate-950/20 text-center">
                              {isUploading ? (
                                <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-2" />
                              ) : (
                                <Upload className="w-8 h-8 text-slate-500 mb-2" />
                              )}
                              <label className="text-xs font-semibold text-brand-400 cursor-pointer">
                                <span>Upload QR code file</span>
                                <input
                                  type="file"
                                  accept="image/*"
                                  onChange={handleQrUpload}
                                  className="hidden"
                                />
                              </label>
                              <span className="text-[10px] text-slate-500 mt-1">PNG, JPG up to 2MB</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Email Templates settings */}
                    {invoiceConfigSubTab === 'email' && (
                      <div className="space-y-6 text-left">
                        {/* Issued email */}
                        <div className="space-y-3 p-4 bg-slate-900/30 border border-slate-800/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Invoice Issued Notification</h4>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.invoice_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, invoice_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Body (Rich text markdown supported)</label>
                            <textarea
                              rows={3}
                              value={editedConfig.invoice_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, invoice_body: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* Reminder email */}
                        <div className="space-y-3 p-4 bg-slate-900/30 border border-slate-800/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Payment Overdue Reminder</h4>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.reminder_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, reminder_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Body</label>
                            <textarea
                              rows={3}
                              value={editedConfig.reminder_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, reminder_body: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* Payment Success email */}
                        <div className="space-y-3 p-4 bg-slate-900/30 border border-slate-800/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Payment Success Confirmation</h4>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.payment_success_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, payment_success_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Body</label>
                            <textarea
                              rows={3}
                              value={editedConfig.payment_success_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, payment_success_body: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* Payment Failed email */}
                        <div className="space-y-3 p-4 bg-slate-900/30 border border-slate-800/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Payment Transaction Failed</h4>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.payment_failed_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, payment_failed_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Body</label>
                            <textarea
                              rows={3}
                              value={editedConfig.payment_failed_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, payment_failed_body: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* Renewal Reminder email */}
                        <div className="space-y-3 p-4 bg-slate-900/30 border border-slate-800/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Renewal Reminder Notification</h4>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.renewal_reminder_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, renewal_reminder_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-slate-400 mb-1">Email Body</label>
                            <textarea
                              rows={3}
                              value={editedConfig.renewal_reminder_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, renewal_reminder_body: e.target.value })}
                              className="w-full px-3 py-2 bg-slate-900 border border-slate-850 rounded-lg text-xs text-slate-200 focus:outline-none"
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Terms & Footer notes */}
                    {invoiceConfigSubTab === 'footer' && (
                      <div className="grid grid-cols-1 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Standard Payment Terms & Conditions</label>
                          <textarea
                            rows={4}
                            value={editedConfig.payment_terms || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, payment_terms: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. Invoice payment is due within 7 days of issue. Standard SLA rates apply."
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Invoice Footer text note</label>
                          <textarea
                            rows={3}
                            value={editedConfig.footer_text || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, footer_text: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                            placeholder="e.g. Thank you for your business! Reach billing@johnsonsoftwares.com for support."
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Save Configuration Trigger */}
                  <div className="flex justify-end pt-4 border-t border-slate-800/80">
                    <button
                      type="button"
                      onClick={handleSaveConfig}
                      disabled={isLoading || isUploading}
                      className="flex items-center justify-center gap-1.5 px-6 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer disabled:opacity-50"
                    >
                      {isLoading ? (
                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      ) : (
                        <>
                          <Check className="w-3.5 h-3.5" />
                          Save Configuration
                        </>
                      )}
                    </button>
                  </div>
                </div>
              </div>

              {/* Right Column: Live Mock Invoice Card preview */}
              <div className="xl:col-span-1">
                <div className="sticky top-6 space-y-4">
                  <div className="flex justify-between items-baseline px-1">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Live Invoice Mockup</h4>
                    <span className="text-[10px] text-slate-500 italic">Auto updates as you type</span>
                  </div>

                  <div className="glass-panel border border-slate-800/80 rounded-2xl overflow-hidden shadow-2xl p-6 bg-slate-950/60 text-slate-300 space-y-6 text-left relative">
                    {/* Header: Company branding */}
                    <div className="flex justify-between items-start gap-4">
                      <div className="space-y-1 max-w-[60%]">
                        {editedConfig.company_logo_url ? (
                          <img
                            src={editedConfig.company_logo_url}
                            alt="Logo preview"
                            className="max-h-10 max-w-[120px] object-contain rounded"
                          />
                        ) : (
                          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-brand-500/20 to-indigo-500/20 border border-brand-500/30 flex items-center justify-center text-brand-400 font-black text-xs">
                            {editedConfig.company_name?.substring(0, 2).toUpperCase() || 'JS'}
                          </div>
                        )}
                        <h4 className="text-sm font-bold text-slate-100 mt-2">{editedConfig.company_name || 'Acme Corporation Ltd.'}</h4>
                        {editedConfig.tagline && <p className="text-[10px] text-slate-500 font-medium italic">{editedConfig.tagline}</p>}
                      </div>

                      <div className="text-right text-[10px] text-slate-500 space-y-0.5">
                        <p>{editedConfig.website || 'www.acmepower.com'}</p>
                        <p>{editedConfig.support_email || 'billing@acmepower.com'}</p>
                        <p>{editedConfig.phone_number || '+91 22 5555 1234'}</p>
                      </div>
                    </div>

                    {/* Address issuer */}
                    <div className="border-t border-slate-800/80 pt-3 text-[10px] text-slate-400 space-y-1">
                      <p className="font-semibold text-slate-300">ISSUER ADDRESS & REGISTER DETAILS:</p>
                      <p className="whitespace-pre-line text-slate-500 font-medium leading-relaxed">{editedConfig.address || '101, Antigravity Heights, Google DeepMind St, BKC, Mumbai - 400051.'}</p>
                      <div className="grid grid-cols-2 gap-2 mt-1 pt-1.5 border-t border-slate-900/60 font-mono">
                        {editedConfig.gst_number && <p><strong>GSTIN:</strong> {editedConfig.gst_number}</p>}
                        {editedConfig.pan && <p><strong>PAN:</strong> {editedConfig.pan}</p>}
                        {editedConfig.business_registration_number && (
                          <p className="col-span-2"><strong>Reg No:</strong> {editedConfig.business_registration_number}</p>
                        )}
                      </div>
                    </div>

                    {/* Invoice ID/Dates */}
                    <div className="border-t border-slate-800/80 pt-3 grid grid-cols-2 gap-4 text-[10px]">
                      <div>
                        <p className="text-slate-500 uppercase tracking-wider font-semibold">Invoice Number</p>
                        <p className="text-slate-200 font-mono text-xs font-bold mt-0.5">
                          {editedConfig.invoice_prefix || 'INV'}-{editedConfig.starting_invoice_number || '1001'}
                        </p>
                      </div>
                      <div className="text-right font-mono">
                        <p className="text-slate-500 uppercase tracking-wider font-semibold">Issue Date</p>
                        <p className="text-slate-300 mt-0.5">{new Date().toLocaleDateString()}</p>
                      </div>
                      <div>
                        <p className="text-slate-500 uppercase tracking-wider font-semibold">Bill To</p>
                        <p className="text-slate-200 font-bold mt-0.5">Demo Corporation Ltd.</p>
                        <p className="text-slate-500 font-mono">billing@democorp.com</p>
                      </div>
                      <div className="text-right font-mono">
                        <p className="text-slate-500 uppercase tracking-wider font-semibold">Payment Due</p>
                        <p className="text-rose-400 font-semibold mt-0.5">
                          {new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    {/* Table charges */}
                    <div className="border-t border-slate-800/80 pt-3 space-y-2">
                      <div className="flex justify-between items-center text-[10px] text-slate-500 uppercase font-bold tracking-wider">
                        <span>Line Item description</span>
                        <span>Total amount</span>
                      </div>
                      <div className="flex justify-between items-start text-xs border-b border-slate-900/60 pb-2">
                        <div>
                          <p className="text-slate-200 font-semibold">Enterprise Pro CRM Subscription</p>
                          <p className="text-[10px] text-slate-500">Includes active system dialers & API credential matrix (Monthly)</p>
                        </div>
                        <span className="text-slate-200 font-mono font-bold">
                          {editedConfig.currency_symbol || '$'} 1500.00
                        </span>
                      </div>

                      {/* Math Summary */}
                      <div className="space-y-1 text-[10px] text-slate-400 pt-1.5">
                        <div className="flex justify-between">
                          <span>Subtotal</span>
                          <span className="font-mono">{editedConfig.currency_symbol || '$'} 1500.00</span>
                        </div>
                        <div className="flex justify-between text-amber-400/90">
                          <span>Contract Discount (10.0%)</span>
                          <span className="font-mono">-{editedConfig.currency_symbol || '$'} 150.00</span>
                        </div>
                        <div className="flex justify-between">
                          <span>CGST / SGST Tax (18.0%)</span>
                          <span className="font-mono">{editedConfig.currency_symbol || '$'} 270.00</span>
                        </div>
                        <div className="flex justify-between text-xs text-slate-100 font-bold pt-2 border-t border-slate-800/60">
                          <span>Total Payable ({editedConfig.currency || 'USD'})</span>
                          <span className="font-mono text-brand-400">
                            {editedConfig.currency_symbol || '$'} 1620.00
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Payment specifications details */}
                    {(editedConfig.bank_name || editedConfig.upi_id) && (
                      <div className="border-t border-slate-800/80 pt-3 text-[10px] space-y-2">
                        <p className="font-semibold text-slate-300 uppercase tracking-wider">Payment Instructions:</p>
                        <div className="grid grid-cols-3 gap-2">
                          {editedConfig.bank_name && (
                            <div className="col-span-2 space-y-0.5 text-slate-500 font-mono">
                              <p><strong className="text-slate-400 font-sans">Bank:</strong> {editedConfig.bank_name}</p>
                              {editedConfig.account_holder && <p><strong className="text-slate-400 font-sans">Holder:</strong> {editedConfig.account_holder}</p>}
                              {editedConfig.account_number && <p><strong className="text-slate-400 font-sans">A/C No:</strong> {editedConfig.account_number}</p>}
                              {editedConfig.ifsc && <p><strong className="text-slate-400 font-sans">IFSC:</strong> {editedConfig.ifsc}</p>}
                              {editedConfig.branch && <p><strong className="text-slate-400 font-sans">Branch:</strong> {editedConfig.branch}</p>}
                              {editedConfig.upi_id && <p className="mt-1 pt-1 border-t border-slate-900/60"><strong className="text-slate-400 font-sans">UPI:</strong> {editedConfig.upi_id}</p>}
                            </div>
                          )}
                          <div className="col-span-1 flex flex-col items-end justify-center">
                            {editedConfig.qr_code_url ? (
                              <img
                                src={editedConfig.qr_code_url}
                                alt="Payment Scan QR"
                                className="w-16 h-16 object-contain rounded bg-white p-0.5 border border-slate-800"
                              />
                            ) : editedConfig.upi_id ? (
                              <div className="w-16 h-16 rounded border border-dashed border-slate-800 flex items-center justify-center text-center p-1 text-[8px] text-slate-600 bg-slate-900/10 leading-tight">
                                Scan QR Code
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Footer text note */}
                    <div className="border-t border-slate-800/80 pt-3 text-[9px] text-slate-500 leading-normal space-y-1">
                      {editedConfig.payment_terms && <p><strong>Terms:</strong> {editedConfig.payment_terms}</p>}
                      <p className="text-center font-medium italic text-slate-400/80 mt-1">{editedConfig.footer_text || 'Thank you for choosing Johnson Softwares!'}</p>
                    </div>
                  </div>
                </div>
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

              <div className="grid grid-cols-4 gap-3 border-t border-slate-800/80 pt-4">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Trial Days (0-365)</label>
                  <input
                    type="number"
                    {...regPlan('trial_days', { required: true, min: 0, max: 365 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                  {planErrors.trial_days && <p className="text-[10px] text-red-400 mt-1">{planErrors.trial_days.message}</p>}
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Extra User Price</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('extra_user_price', { required: true, min: 0 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                  {planErrors.extra_user_price && <p className="text-[10px] text-red-400 mt-1">{planErrors.extra_user_price.message}</p>}
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Discount % (0-100)</label>
                  <input
                    type="number"
                    step="0.1"
                    {...regPlan('discount_percentage', { required: true, min: 0, max: 100 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                  {planErrors.discount_percentage && <p className="text-[10px] text-red-400 mt-1">{planErrors.discount_percentage.message}</p>}
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">GST Tax % (0-100)</label>
                  <input
                    type="number"
                    step="0.1"
                    {...regPlan('gst_percentage', { required: true, min: 0, max: 100 })}
                    className="w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                  {planErrors.gst_percentage && <p className="text-[10px] text-red-400 mt-1">{planErrors.gst_percentage.message}</p>}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 border-t border-slate-800/80 pt-4">
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Plan Color Hex (e.g. #3b82f6)</label>
                  <div className="flex gap-2">
                    <input
                      type="color"
                      {...regPlan('plan_color')}
                      className="w-10 h-10 p-0.5 bg-slate-900 border border-slate-800 rounded-xl cursor-pointer"
                    />
                    <input
                      type="text"
                      placeholder="#3b82f6"
                      {...regPlan('plan_color')}
                      className="flex-1 px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] text-slate-400 mb-1.5">Plan Badge (e.g. Popular, Best Value)</label>
                  <input
                    type="text"
                    placeholder="Enter plan badge"
                    {...regPlan('plan_badge')}
                    className="w-full px-3 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 border-t border-slate-800/80 pt-4">
                <label className="flex items-center gap-2 text-xs text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('popular_plan')}
                    className="w-4 h-4 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  Popular Plan Badge
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('recommended_plan')}
                    className="w-4 h-4 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  Recommended Plan
                </label>
                <label className="flex items-center gap-2 text-xs text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('plan_active')}
                    className="w-4 h-4 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  Plan Active / Visible
                </label>
              </div>

              <div className="grid grid-cols-4 gap-3 border-t border-slate-800/80 pt-4 col-span-2">
                <label className="flex items-center gap-1.5 text-[10px] text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('allow_upgrade')}
                    className="w-3.5 h-3.5 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  Allow Upgrade
                </label>
                <label className="flex items-center gap-1.5 text-[10px] text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('allow_downgrade')}
                    className="w-3.5 h-3.5 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  Allow Downgrade
                </label>
                <label className="flex items-center gap-1.5 text-[10px] text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('allow_trial')}
                    className="w-3.5 h-3.5 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  Allow Trial
                </label>
                <label className="flex items-center gap-1.5 text-[10px] text-slate-300 font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('auto_renew')}
                    className="w-3.5 h-3.5 rounded border-slate-800 text-brand-500 bg-slate-900 focus:ring-0 cursor-pointer"
                  />
                  Auto Renew
                </label>
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
