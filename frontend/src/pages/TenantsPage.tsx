import React, { useEffect, useState } from 'react';
import { useForm } from 'react-hook-form';
import { 
  Building, Users, FileText, Edit, Plus, X, ShieldAlert, 
  Loader2, Calendar, DollarSign, CheckCircle2, AlertCircle, Clock, Trash2,
  Workflow, CheckSquare, Settings, Lock, Unlock, Check, Key, ArrowUpDown, FolderKanban,
  Upload, Mail, CreditCard, Image, Receipt, Percent, LayoutDashboard,
  Globe, Tag, Bell, Shield, BarChart3, RefreshCw, ToggleLeft, ToggleRight,
  Download, Eye, EyeOff
} from 'lucide-react';
import { 
  superAdminApi, TenantResponse, TenantUserResponse, TenantInvoiceResponse,
  SubscriptionUpdateRequest, InvoiceCreateRequest, CreateTenantRequest,
  PlanResponse, FeatureResponse, PlanFeatureResponse, PlanCreatePayload,
  CommercialSettingsUpdate, CurrencyResponse, TaxConfigResponse,
  PaymentGatewayResponse, NotificationTemplateResponse, CouponResponse
} from '../services/superAdminApi';

type SectionKey = 'dashboard' | 'tenants' | 'plans' | 'features' | 'commercial' | 'currencies' | 'tax' | 'gateways' | 'coupons' | 'invoice' | 'notifications' | 'audit' | 'reports' | 'global';

const CommercialSummaryPanel: React.FC<{ regPlan?: any }> = (_props) => (
  <div className="border-t border-[var(--border-strong)]/80 pt-4">
    <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 mb-3">Commercial Summary</h4>
    <div className="bg-[var(--bg-subtle)]/60 border border-[var(--border-strong)]/60 rounded-xl overflow-hidden text-xs">
      {[
        { label: 'Price Per Licensed Seat', hint: 'As entered above' },
        { label: 'Minimum Initial Purchase', hint: '10 Licensed Seats' },
        { label: 'Minimum Contract', hint: '3 Months' },
        { label: 'Starting Monthly Billing', hint: 'Price x Min Seats' },
        { label: 'GST', hint: 'Extra (as configured)' },
        { label: 'Additional Seat Price', hint: 'Per extra seat / month' },
      ].map((row, i) => (
        <div key={i} className={`flex items-center justify-between px-4 py-2.5 ${i !== 5 ? 'border-b border-[var(--border-strong)]/60' : ''}`}>
          <span className="text-[var(--text-secondary)] font-medium">{row.label}</span>
          <span className="text-[var(--text-secondary)] font-semibold">{row.hint}</span>
        </div>
      ))}
    </div>
  </div>
);

const NavItem: React.FC<{ icon: React.ElementType; label: string; active: boolean; onClick: () => void }> = ({ icon: Icon, label, active, onClick }) => (
  <button
    onClick={onClick}
    className={`w-full flex items-center gap-2.5 px-4 py-2.5 text-xs font-semibold transition-all cursor-pointer text-left relative ${
      active ? 'bg-brand-500/10 text-brand-400 border-r-2 border-brand-500' : 'text-[var(--text-secondary)] hover:bg-[var(--bg-card)]/50 hover:text-[var(--text-primary)]'
    }`}
  >
    <Icon className="w-4 h-4 shrink-0" />
    {label}
  </button>
);

export const TenantsPage: React.FC = () => {
  const [activeSection, setActiveSection] = useState<SectionKey>('tenants');
  const [tenants, setTenants] = useState<TenantResponse[]>([]);
  const [plans, setPlans] = useState<PlanResponse[]>([]);
  const [features, setFeatures] = useState<FeatureResponse[]>([]);
  const [mappings, setMappings] = useState<PlanFeatureResponse[]>([]);
  const [settingsData, setSettingsData] = useState<Record<string, any>>({});
  const [editedConfig, setEditedConfig] = useState<any>(null);
  const [invoiceConfigSubTab, setInvoiceConfigSubTab] = useState<'general' | 'branding' | 'tax' | 'invoice' | 'payment' | 'email' | 'footer'>('general');
  const [editedCommSettings, setEditedCommSettings] = useState<CommercialSettingsUpdate | null>(null);
  const [commSettingsSubTab, setCommSettingsSubTab] = useState<'general' | 'pricing' | 'tax' | 'contracts' | 'setup' | 'discounts' | 'late-fees' | 'renewals' | 'reminders' | 'emails' | 'advanced'>('general');
  const [isUploading, setIsUploading] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [globalError, setGlobalError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [selectedTenant, setSelectedTenant] = useState<TenantResponse | null>(null);
  const [selectedPlan, setSelectedPlan] = useState<PlanResponse | null>(null);
  const [activeModal, setActiveModal] = useState<'createTenant' | 'editSubscription' | 'users' | 'invoices' | 'deleteTenantConfirm' | 'resetPassword' | 'createPlan' | 'editPlan' | null>(null);
  const [deleteConfirmSlug, setDeleteConfirmSlug] = useState('');
  const [newPassword, setNewPassword] = useState('');
  const [tenantUsers, setTenantUsers] = useState<TenantUserResponse[]>([]);
  const [invoices, setInvoices] = useState<TenantInvoiceResponse[]>([]);
  const [isModalLoading, setIsModalLoading] = useState(false);
  const [modalError, setModalError] = useState<string | null>(null);
  const [dashboard, setDashboard] = useState<any>(null);
  const [dashboardPeriod, setDashboardPeriod] = useState<'day' | 'week' | 'month'>('month');
  const [currencies, setCurrencies] = useState<CurrencyResponse[]>([]);
  const [taxConfigs, setTaxConfigs] = useState<TaxConfigResponse[]>([]);
  const [gateways, setGateways] = useState<PaymentGatewayResponse[]>([]);
  const [coupons, setCoupons] = useState<CouponResponse[]>([]);
  const [notifTemplates, setNotifTemplates] = useState<NotificationTemplateResponse[]>([]);
  const [auditLogs, setAuditLogs] = useState<any[]>([]);
  const [auditSearch, setAuditSearch] = useState('');
  const [revenueReport, setRevenueReport] = useState<any>(null);
  const [seatReport, setSeatReport] = useState<any>(null);
  const [currencyForm, setCurrencyForm] = useState<any>({});
  const [activeCurrencyModal, setActiveCurrencyModal] = useState<'create' | 'edit' | null>(null);
  const [selectedCurrency, setSelectedCurrency] = useState<CurrencyResponse | null>(null);
  const [taxForm, setTaxForm] = useState<any>({});
  const [activeTaxModal, setActiveTaxModal] = useState<'create' | 'edit' | null>(null);
  const [selectedTax, setSelectedTax] = useState<TaxConfigResponse | null>(null);
  const [couponForm, setCouponForm] = useState<any>({});
  const [activeCouponModal, setActiveCouponModal] = useState<'create' | 'edit' | null>(null);
  const [selectedCoupon, setSelectedCoupon] = useState<CouponResponse | null>(null);
  const [notifForm, setNotifForm] = useState<any>({});
  const [activeNotifModal, setActiveNotifModal] = useState<'edit' | null>(null);
  const [selectedNotif, setSelectedNotif] = useState<NotificationTemplateResponse | null>(null);
  const [gatewayForms, setGatewayForms] = useState<Record<string, any>>({});
  const [expandedGateway, setExpandedGateway] = useState<string | null>(null);
  const [showApiKey, setShowApiKey] = useState<Record<string, boolean>>({});

  const fetchAllData = async () => {
    setIsLoading(true); setGlobalError(null);
    try {
      switch (activeSection) {
        case 'dashboard': { const d = await superAdminApi.getDashboard(dashboardPeriod); setDashboard(d); break; }
        case 'tenants': { const d = await superAdminApi.getTenants(); setTenants(d); break; }
        case 'plans': { const d = await superAdminApi.getPlans(); setPlans(d); break; }
        case 'features': {
          const [p,f,m] = await Promise.all([superAdminApi.getPlans(),superAdminApi.getFeatures(),superAdminApi.getPlanFeatures()]);
          setPlans(p); setFeatures(f); setMappings(m); break;
        }
        case 'invoice': { const d = await superAdminApi.getInvoiceConfig(); setEditedConfig(d); break; }
        case 'commercial': {
          const [d,p] = await Promise.all([superAdminApi.getCommercialSettings(),superAdminApi.getPlans()]);
          setEditedCommSettings({ ...d, reason: '' }); setPlans(p); break;
        }
        case 'global': {
          const d = await superAdminApi.getSystemSettings();
          const m: Record<string,any> = {};
          d.forEach((i: any) => { m[i.key] = i.value; });
          setSettingsData(m); break;
        }
        case 'currencies': { const d = await superAdminApi.getCurrencies(); setCurrencies(d); break; }
        case 'tax': { const d = await superAdminApi.getTaxConfigs(); setTaxConfigs(d); break; }
        case 'gateways': { const d = await superAdminApi.getPaymentGateways(); setGateways(d); break; }
        case 'coupons': { const d = await superAdminApi.getCoupons(); setCoupons(d); break; }
        case 'notifications': { const d = await superAdminApi.getNotificationTemplates(); setNotifTemplates(d); break; }
        case 'audit': {
          const d = await superAdminApi.getAuditLogs({ limit: 50, ...(auditSearch ? { action: auditSearch } : {}) });
          setAuditLogs(Array.isArray(d) ? d : (d as any).items || []); break;
        }
        case 'reports': {
          const [rv,st] = await Promise.all([superAdminApi.getRevenueReport(),superAdminApi.getSeatUtilization()]);
          setRevenueReport(rv); setSeatReport(st); break;
        }
        default: break;
      }
    } catch (err: any) { setGlobalError(err.response?.data?.detail || 'Failed to fetch data'); }
    finally { setIsLoading(false); }
  };

  useEffect(() => { fetchAllData(); }, [activeSection, dashboardPeriod]);

  const showSuccess = (msg: string) => { setSuccessMessage(msg); setTimeout(() => setSuccessMessage(null), 4000); };

  const openUsersModal = async (tenant: TenantResponse) => {
    setSelectedTenant(tenant); setTenantUsers([]); setActiveModal('users'); setIsModalLoading(true); setModalError(null);
    try { setTenantUsers(await superAdminApi.getTenantUsers(tenant.id)); }
    catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const openInvoicesModal = async (tenant: TenantResponse) => {
    setSelectedTenant(tenant); setInvoices([]); setActiveModal('invoices'); setIsModalLoading(true); setModalError(null);
    try { setInvoices(await superAdminApi.getTenantInvoices(tenant.id)); }
    catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const handleSuspendTenant = async (tenant: TenantResponse) => {
    setIsLoading(true);
    try { await superAdminApi.suspendTenant(tenant.id); showSuccess('Status updated.'); await fetchAllData(); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleResetPassword = async (e: React.FormEvent) => {
    e.preventDefault(); if (!selectedTenant || !newPassword) return;
    setIsModalLoading(true); setModalError(null);
    try { await superAdminApi.resetTenantOwnerPassword(selectedTenant.id, newPassword); showSuccess('Password reset.'); setNewPassword(''); setActiveModal(null); }
    catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const { register: regTenant, handleSubmit: handleTenantSubmit, reset: resetTenant, formState: { errors: tenantErrors } } = useForm<CreateTenantRequest>();
  const { register: regSub, handleSubmit: handleSubSubmit, setValue: setSubValue, formState: { errors: subErrors } } = useForm<SubscriptionUpdateRequest>();
  const { register: regInv, handleSubmit: handleInvSubmit, reset: resetInv, formState: { errors: invErrors } } = useForm<InvoiceCreateRequest>();
  const { register: regPlan, handleSubmit: handlePlanSubmit, reset: resetPlan, setValue: setPlanValue, formState: { errors: planErrors } } = useForm<PlanCreatePayload>();
  const openEditSubModal = (tenant: TenantResponse) => { setSelectedTenant(tenant); setModalError(null); setActiveModal('editSubscription'); };
  useEffect(() => {
    if (selectedTenant && activeModal === 'editSubscription') {
      setSubValue('subscription_plan', selectedTenant.subscription_plan);
      setSubValue('subscription_status', selectedTenant.subscription_status);
      setSubValue('max_users', selectedTenant.max_users);
      setSubValue('subscription_expires_at', selectedTenant.subscription_expires_at?.substring(0, 10) || '');
    }
  }, [selectedTenant, activeModal, setSubValue]);
  const onCreateTenant = async (data: CreateTenantRequest) => {
    setIsModalLoading(true); setModalError(null);
    try {
      await superAdminApi.createTenant({ ...data, licensed_seats: Number(data.licensed_seats || 10), contract_months: Number(data.contract_months || 3), plan_name: data.plan_name || 'starter', billing_cycle: data.billing_cycle || 'monthly' });
      showSuccess('Tenant created.'); await fetchAllData(); resetTenant(); setActiveModal(null);
    } catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const onUpdateSubscription = async (data: SubscriptionUpdateRequest) => {
    if (!selectedTenant) return; setIsModalLoading(true); setModalError(null);
    try {
      await superAdminApi.updateSubscription(selectedTenant.id, { ...data, max_users: Number(data.max_users), subscription_expires_at: data.subscription_expires_at ? new Date(data.subscription_expires_at).toISOString() : null });
      showSuccess('Subscription updated.'); await fetchAllData(); setActiveModal(null);
    } catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const onCreateInvoice = async (data: InvoiceCreateRequest) => {
    if (!selectedTenant) return; setIsModalLoading(true); setModalError(null);
    try {
      await superAdminApi.createManualInvoice(selectedTenant.id, { amount: Number(data.amount), due_date: new Date(data.due_date).toISOString(), status: data.status || 'Pending' });
      showSuccess('Invoice created.'); setInvoices(await superAdminApi.getTenantInvoices(selectedTenant.id)); resetInv();
    } catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const onToggleInvoiceStatus = async (invoiceId: string, currentStatus: string) => {
    if (!selectedTenant) return;
    const nextStatus = currentStatus === 'Paid' ? 'Pending' : currentStatus === 'Pending' ? 'Overdue' : 'Paid';
    setIsModalLoading(true); setModalError(null);
    try { await superAdminApi.updateInvoiceStatus(invoiceId, nextStatus); setInvoices(await superAdminApi.getTenantInvoices(selectedTenant.id)); }
    catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const onConfirmDeleteTenant = async () => {
    if (!selectedTenant) return; setIsLoading(true);
    try { await superAdminApi.deleteTenant(selectedTenant.id); showSuccess('Tenant purged.'); setActiveModal(null); await fetchAllData(); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const cast = (data: PlanCreatePayload) => ({
    ...data,
    monthly_price: Number(data.monthly_price), quarterly_price: Number(data.quarterly_price), annual_price: Number(data.annual_price),
    max_users: Number(data.max_users), storage_limit_gb: Number(data.storage_limit_gb),
    recording_retention_days: Number(data.recording_retention_days), display_order: Number(data.display_order),
    setup_charges: Number(data.setup_charges), minimum_users: Number(data.minimum_users),
    maximum_users: Number(data.maximum_users), minimum_contract_months: Number(data.minimum_contract_months),
    trial_days: Number(data.trial_days || 0), extra_user_price: Number(data.extra_user_price || 0),
    discount_percentage: Number(data.discount_percentage || 0), gst_percentage: Number(data.gst_percentage || 0),
    popular_plan: Boolean(data.popular_plan), recommended_plan: Boolean(data.recommended_plan),
    allow_upgrade: Boolean(data.allow_upgrade), allow_downgrade: Boolean(data.allow_downgrade),
    allow_trial: Boolean(data.allow_trial), allow_additional_seats: Boolean(data.allow_additional_seats),
    auto_renew: Boolean(data.auto_renew), plan_active: Boolean(data.plan_active)
  });
  const handleCreatePlan = async (data: PlanCreatePayload) => {
    setIsModalLoading(true); setModalError(null);
    try { await superAdminApi.createPlan(cast(data)); showSuccess('Plan created.'); await fetchAllData(); setActiveModal(null); }
    catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const handleEditPlan = async (data: PlanCreatePayload) => {
    if (!selectedPlan) return; setIsModalLoading(true); setModalError(null);
    try { await superAdminApi.updatePlan(selectedPlan.id, cast(data)); showSuccess('Plan updated.'); await fetchAllData(); setActiveModal(null); }
    catch (e: any) { setModalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsModalLoading(false); }
  };
  const handleDeletePlan = async (planId: string) => {
    if (!confirm('Delete this plan?')) return; setIsLoading(true);
    try { await superAdminApi.deletePlan(planId); showSuccess('Plan deleted.'); await fetchAllData(); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleReorderPlans = async (planId: string, dir: 'up' | 'down') => {
    const idx = plans.findIndex(p => p.id === planId); if (idx === -1) return;
    const np = [...plans];
    if (dir === 'up' && idx > 0) { const t = np[idx]; np[idx] = np[idx-1]; np[idx-1] = t; }
    else if (dir === 'down' && idx < np.length - 1) { const t = np[idx]; np[idx] = np[idx+1]; np[idx+1] = t; }
    else return;
    setIsLoading(true);
    try { await superAdminApi.reorderPlans(np.map(p => p.id)); await fetchAllData(); }
    catch { setGlobalError('Failed'); }
    finally { setIsLoading(false); }
  };
  const isFeatureMapped = (planId: string, featureId: string) => mappings.some(m => m.plan_id === planId && m.feature_id === featureId && m.enabled);
  const handleToggleFeature = async (planId: string, featureId: string) => {
    const cur = isFeatureMapped(planId, featureId);
    try {
      await superAdminApi.togglePlanFeature({ plan_id: planId, feature_id: featureId, enabled: !cur });
      const um = [...mappings]; const idx = um.findIndex(m => m.plan_id === planId && m.feature_id === featureId);
      if (idx !== -1) um[idx].enabled = !cur; else um.push({ id: '', plan_id: planId, feature_id: featureId, enabled: !cur });
      setMappings(um); showSuccess('Updated.');
    } catch { setGlobalError('Failed'); }
  };
  const handleSaveConfig = async () => {
    if (!editedConfig) return; setIsLoading(true);
    try { setEditedConfig(await superAdminApi.updateInvoiceConfig(editedConfig)); showSuccess('Saved.'); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleSaveCommSettings = async () => {
    if (!editedCommSettings) return;
    if (!editedCommSettings.reason) { setGlobalError('Reason required.'); return; }
    setIsLoading(true);
    try { const u = await superAdminApi.updateCommercialSettings(editedCommSettings); setEditedCommSettings({ ...u, reason: '' }); showSuccess('Saved.'); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleLogoUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return; setIsUploading(true);
    try { setEditedConfig(await superAdminApi.uploadCompanyLogo(e.target.files[0])); showSuccess('Logo uploaded.'); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsUploading(false); }
  };
  const handleQrUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!e.target.files?.length) return; setIsUploading(true);
    try { setEditedConfig(await superAdminApi.uploadPaymentQr(e.target.files[0])); showSuccess('QR uploaded.'); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsUploading(false); }
  };
  const handleDeleteLogo = async () => {
    if (!confirm('Delete logo?')) return; setIsUploading(true);
    try { setEditedConfig(await superAdminApi.deleteCompanyLogo()); showSuccess('Deleted.'); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsUploading(false); }
  };
  const handleDeleteQr = async () => {
    if (!confirm('Delete QR?')) return; setIsUploading(true);
    try { setEditedConfig(await superAdminApi.deletePaymentQr()); showSuccess('Deleted.'); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsUploading(false); }
  };
  const handleSaveSystemSettings = async (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault(); const fd = new FormData(e.currentTarget); setIsLoading(true);
    try {
      await superAdminApi.upsertSystemSetting({ key: 'smtp_settings', value: { host: fd.get('smtp_host'), port: Number(fd.get('smtp_port')), user: fd.get('smtp_user'), from_name: fd.get('smtp_from_name') } });
      await superAdminApi.upsertSystemSetting({ key: 'telephony_settings', value: { api_key: fd.get('k_key'), agent_number: fd.get('k_agent') } });
      showSuccess('Saved.');
    } catch { setGlobalError('Failed'); }
    finally { setIsLoading(false); }
  };
  const getInvoiceStatusIcon = (status: string) => {
    if (status === 'Paid') return <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" />;
    if (status === 'Pending') return <Clock className="w-4 h-4 text-amber-400 shrink-0" />;
    return <AlertCircle className="w-4 h-4 text-rose-400 shrink-0" />;
  };
  const handleSaveCurrency = async () => {
    setIsLoading(true);
    try {
      if (activeCurrencyModal === 'create') await superAdminApi.createCurrency(currencyForm);
      else if (selectedCurrency) await superAdminApi.updateCurrency(selectedCurrency.code, currencyForm);
      showSuccess('Saved.'); await fetchAllData(); setActiveCurrencyModal(null);
    } catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleDeleteCurrency = async (code: string) => {
    if (!confirm('Delete ' + code + '?')) return; setIsLoading(true);
    try { await superAdminApi.deleteCurrency(code); showSuccess('Deleted.'); await fetchAllData(); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleSaveTax = async () => {
    setIsLoading(true);
    try {
      if (activeTaxModal === 'create') await superAdminApi.createTaxConfig(taxForm);
      else if (selectedTax) await superAdminApi.updateTaxConfig(selectedTax.id, taxForm);
      showSuccess('Saved.'); await fetchAllData(); setActiveTaxModal(null);
    } catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleDeleteTax = async (id: string) => {
    if (!confirm('Delete?')) return; setIsLoading(true);
    try { await superAdminApi.deleteTaxConfig(id); showSuccess('Deleted.'); await fetchAllData(); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleToggleGateway = async (id: string) => {
    setIsLoading(true);
    try { await superAdminApi.togglePaymentGateway(id); showSuccess('Toggled.'); await fetchAllData(); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleSaveGateway = async (name: string) => {
    setIsLoading(true);
    try { await superAdminApi.updatePaymentGateway(name, gatewayForms[name] || {}); showSuccess('Saved.'); await fetchAllData(); setExpandedGateway(null); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleSaveCoupon = async () => {
    setIsLoading(true);
    try {
      const p = { ...couponForm, discount_value: Number(couponForm.discount_value), max_uses: couponForm.max_uses ? Number(couponForm.max_uses) : null, min_order_value: Number(couponForm.min_order_value || 0) };
      if (activeCouponModal === 'create') await superAdminApi.createCoupon(p);
      else if (selectedCoupon) await superAdminApi.updateCoupon(selectedCoupon.id, p);
      showSuccess('Saved.'); await fetchAllData(); setActiveCouponModal(null);
    } catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleDeleteCoupon = async (id: string) => {
    if (!confirm('Delete?')) return; setIsLoading(true);
    try { await superAdminApi.deleteCoupon(id); showSuccess('Deleted.'); await fetchAllData(); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };
  const handleSaveNotif = async () => {
    if (!selectedNotif) return; setIsLoading(true);
    try { await superAdminApi.updateNotificationTemplate(selectedNotif.id, notifForm); showSuccess('Saved.'); await fetchAllData(); setActiveNotifModal(null); }
    catch (e: any) { setGlobalError(e.response?.data?.detail || 'Failed'); }
    finally { setIsLoading(false); }
  };

  const navItems: { key: SectionKey; icon: React.ElementType; label: string }[] = [
    { key: 'dashboard', icon: LayoutDashboard, label: 'Dashboard' },
    { key: 'tenants', icon: Building, label: 'Tenants' },
    { key: 'plans', icon: FolderKanban, label: 'Plans' },
    { key: 'features', icon: Workflow, label: 'Features' },
    { key: 'commercial', icon: DollarSign, label: 'Commercial' },
    { key: 'currencies', icon: Globe, label: 'Currencies' },
    { key: 'tax', icon: Receipt, label: 'Tax Engine' },
    { key: 'gateways', icon: CreditCard, label: 'Gateways' },
    { key: 'coupons', icon: Tag, label: 'Coupons' },
    { key: 'invoice', icon: FileText, label: 'Invoice Config' },
    { key: 'notifications', icon: Bell, label: 'Notifications' },
    { key: 'audit', icon: Shield, label: 'Audit Center' },
    { key: 'reports', icon: BarChart3, label: 'Reports' },
    { key: 'global', icon: Settings, label: 'Global Settings' },
  ];

  return (
    <div style={{ display: 'flex', margin: '-24px', minHeight: 'calc(100vh - 64px)', overflow: 'hidden' }}>
      <nav style={{ width: '188px', flexShrink: 0, borderRight: '1px solid var(--border-color)', backgroundColor: 'var(--bg-surface)', overflowY: 'auto', display: 'flex', flexDirection: 'column' }}>
        <div className="p-4 border-b border-[var(--border-color)]">
          <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)]">Super Admin</p>
          <h2 className="text-sm font-bold text-[var(--text-primary)] mt-0.5">Control Center</h2>
        </div>
        <div className="py-2 flex-1">
          {navItems.map(item => <NavItem key={item.key} icon={item.icon} label={item.label} active={activeSection === item.key} onClick={() => { setActiveSection(item.key); setGlobalError(null); }} />)}
        </div>
      </nav>

      <div style={{ flex: 1, overflowY: 'auto', padding: '24px' }} className="space-y-6">
        {globalError && (
          <div className="p-4 bg-red-950/20 border border-red-900/30 rounded-2xl flex items-start gap-2.5 text-sm text-red-400">
            <ShieldAlert className="w-5 h-5 shrink-0 mt-0.5" /><span>{globalError}</span>
            <button onClick={() => setGlobalError(null)} className="ml-auto cursor-pointer"><X className="w-4 h-4" /></button>
          </div>
        )}
        {successMessage && (
          <div className="p-4 bg-emerald-950/20 border border-emerald-900/30 rounded-2xl flex items-start gap-2.5 text-sm text-emerald-400">
            <CheckCircle2 className="w-5 h-5 shrink-0 mt-0.5" /><span>{successMessage}</span>
          </div>
        )}
        {isLoading ? (
          <div className="glass-panel p-20 rounded-2xl border border-[var(--border-strong)]/80 flex flex-col items-center justify-center text-[var(--text-secondary)]">
            <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-4" />
            <p className="text-sm font-medium">Loading...</p>
          </div>
        ) : (
          <>
            {activeSection === 'dashboard' && (
              <div className="space-y-6">
                {/* Header + Controls */}
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h2 className="text-2xl font-bold text-[var(--text-primary)]">Executive Dashboard</h2>
                    <p className="text-sm text-[var(--text-muted)] mt-1">Real-time platform metrics</p>
                  </div>
                  <div className="flex items-center gap-2">
                    {/* Period Toggle */}
                    <div className="flex items-center gap-1 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl p-1">
                      {(['day', 'week', 'month'] as const).map(p => (
                        <button
                          key={p}
                          onClick={() => setDashboardPeriod(p)}
                          className={`px-3 py-1.5 rounded-lg text-xs font-semibold transition-all cursor-pointer capitalize ${
                            dashboardPeriod === p
                              ? 'bg-brand-500 text-white shadow'
                              : 'text-[var(--text-muted)] hover:text-[var(--text-primary)]'
                          }`}
                        >
                          {p === 'day' ? 'Today' : p === 'week' ? 'This Week' : 'This Month'}
                        </button>
                      ))}
                    </div>
                    <button onClick={fetchAllData} className="flex items-center gap-2 px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-muted)] cursor-pointer hover:text-[var(--text-primary)]">
                      <RefreshCw className="w-3.5 h-3.5" /> Refresh
                    </button>
                  </div>
                </div>

                {dashboard ? (
                  <>
                    {/* Top KPIs: period-sensitive */}
                    <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
                      <div className="glass-panel p-5 border border-[var(--border-color)] rounded-2xl">
                        <p className="text-xs text-[var(--text-muted)] font-semibold uppercase tracking-wider">
                          {dashboardPeriod === 'day' ? "Today's" : dashboardPeriod === 'week' ? "This Week's" : "This Month's"} Collection
                        </p>
                        <p className="text-2xl font-bold mt-2 text-emerald-400">
                          ₹{Number(dashboard.revenue?.period_collected ?? 0).toLocaleString('en-IN')}
                        </p>
                        <p className="text-xs text-[var(--text-muted)] mt-1">
                          Total ever: ₹{Number(dashboard.revenue?.total_collected ?? 0).toLocaleString('en-IN')}
                        </p>
                      </div>
                      <div className="glass-panel p-5 border border-[var(--border-color)] rounded-2xl">
                        <p className="text-xs text-[var(--text-muted)] font-semibold uppercase tracking-wider">Pending Collection</p>
                        <p className="text-2xl font-bold mt-2 text-amber-400">
                          ₹{Number(dashboard.revenue?.pending ?? 0).toLocaleString('en-IN')}
                        </p>
                        <p className="text-xs text-[var(--text-muted)] mt-1">
                          {dashboard.revenue?.overdue_count ?? 0} overdue invoices
                        </p>
                      </div>
                      <div className="glass-panel p-5 border border-[var(--border-color)] rounded-2xl">
                        <p className="text-xs text-[var(--text-muted)] font-semibold uppercase tracking-wider">
                          {dashboardPeriod === 'day' ? "Today's" : dashboardPeriod === 'week' ? "This Week's" : "This Month's"} Onboarded
                        </p>
                        <p className="text-2xl font-bold mt-2 text-brand-400">
                          {dashboard.revenue?.period_onboarded ?? 0}
                        </p>
                        <p className="text-xs text-[var(--text-muted)] mt-1">
                          {dashboard.orgs?.active ?? 0} active of {dashboard.orgs?.total ?? 0} total
                        </p>
                      </div>
                      <div className="glass-panel p-5 border border-[var(--border-color)] rounded-2xl">
                        <p className="text-xs text-[var(--text-muted)] font-semibold uppercase tracking-wider">MRR / ARR</p>
                        <p className="text-2xl font-bold mt-2 text-sky-400">
                          ₹{Number(dashboard.revenue?.mrr ?? 0).toLocaleString('en-IN')}
                        </p>
                        <p className="text-xs text-[var(--text-muted)] mt-1">
                          ARR ₹{Number(dashboard.revenue?.arr ?? 0).toLocaleString('en-IN')}
                        </p>
                      </div>
                    </div>

                    {/* Second row: Org breakdown + Licensing + Infra */}
                    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                      {/* Org breakdown */}
                      <div className="glass-panel p-6 border border-[var(--border-color)] rounded-2xl">
                        <h3 className="text-sm font-bold text-[var(--text-primary)] mb-4">Organization Status</h3>
                        <div className="space-y-3">
                          {[
                            { label: 'Active', val: dashboard.orgs?.active ?? 0, color: 'text-emerald-400' },
                            { label: 'Trial', val: dashboard.orgs?.trial ?? 0, color: 'text-sky-400' },
                            { label: 'Expired', val: dashboard.orgs?.expired ?? 0, color: 'text-rose-400' },
                            { label: 'Suspended', val: dashboard.orgs?.suspended ?? 0, color: 'text-amber-400' },
                          ].map((x, i) => (
                            <div key={i} className="flex items-center justify-between">
                              <span className="text-xs text-[var(--text-muted)]">{x.label}</span>
                              <span className={`text-sm font-bold ${x.color}`}>{x.val}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Licensing */}
                      <div className="glass-panel p-6 border border-[var(--border-color)] rounded-2xl">
                        <h3 className="text-sm font-bold text-[var(--text-primary)] mb-4">Seat Licensing</h3>
                        <div className="space-y-3">
                          {[
                            { label: 'Licensed', val: dashboard.licensing?.total_licensed_seats ?? 0, color: 'text-brand-400' },
                            { label: 'Active', val: dashboard.licensing?.active_seats ?? 0, color: 'text-emerald-400' },
                            { label: 'Available', val: dashboard.licensing?.available_seats ?? 0, color: 'text-sky-400' },
                            { label: 'Utilization', val: (dashboard.licensing?.utilization_percent ?? 0) + '%', color: 'text-amber-400' },
                          ].map((x, i) => (
                            <div key={i} className="flex items-center justify-between">
                              <span className="text-xs text-[var(--text-muted)]">{x.label}</span>
                              <span className={`text-sm font-bold ${x.color}`}>{x.val}</span>
                            </div>
                          ))}
                        </div>
                      </div>

                      {/* Infra + Activity */}
                      <div className="glass-panel p-6 border border-[var(--border-color)] rounded-2xl">
                        <h3 className="text-sm font-bold text-[var(--text-primary)] mb-4">Infrastructure & Activity</h3>
                        <div className="space-y-3">
                          {[
                            { label: 'Database', val: dashboard.infra?.db_status ?? 'unknown', ok: dashboard.infra?.db_status === 'healthy' },
                            { label: 'Redis', val: dashboard.infra?.redis_status ?? 'unknown', ok: dashboard.infra?.redis_status === 'healthy' },
                          ].map((x, i) => (
                            <div key={i} className="flex items-center justify-between">
                              <span className="text-xs text-[var(--text-muted)]">{x.label}</span>
                              <span className={`text-xs font-bold ${x.ok ? 'text-emerald-400' : 'text-rose-400'}`}>{x.val}</span>
                            </div>
                          ))}
                          <div className="border-t border-[var(--border-color)] pt-3 space-y-2">
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-[var(--text-muted)]">New Today</span>
                              <span className="text-xs font-bold text-brand-400">{dashboard.activity?.new_orgs_today ?? 0} orgs</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-[var(--text-muted)]">Renewals in 7d</span>
                              <span className="text-xs font-bold text-amber-400">{dashboard.activity?.renewals_due_7days ?? 0}</span>
                            </div>
                            <div className="flex items-center justify-between">
                              <span className="text-xs text-[var(--text-muted)]">Invoices Today</span>
                              <span className="text-xs font-bold text-sky-400">{dashboard.activity?.new_invoices_today ?? 0}</span>
                            </div>
                          </div>
                        </div>
                      </div>
                    </div>
                  </>
                ) : (
                  <div className="glass-panel p-16 rounded-2xl border border-[var(--border-color)] flex flex-col items-center justify-center text-[var(--text-muted)] text-center">
                    <LayoutDashboard className="w-12 h-12 opacity-30 mb-3" />
                    <p className="font-semibold text-[var(--text-secondary)]">No dashboard data</p>
                    <p className="text-xs mt-1">Backend may be offline.</p>
                  </div>
                )}
              </div>
            )}
          {activeSection === 'tenants' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-secondary)]">Tenants List</h3>
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
                <div className="glass-panel p-16 rounded-2xl border border-[var(--border-strong)]/80 flex flex-col items-center justify-center text-[var(--text-muted)] text-center">
                  <Building className="w-12 h-12 text-[var(--text-muted)] mb-3" />
                  <p className="text-base font-semibold text-[var(--text-secondary)]">No Tenants Found</p>
                  <p className="text-xs text-[var(--text-muted)] mt-1">Spin up a new tenant to initiate database instances.</p>
                </div>
              ) : (
                <div className="glass-panel rounded-2xl border border-[var(--border-strong)]/80 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-[var(--border-color)] bg-[var(--bg-subtle)]/20">
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Company / Subdomain</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Status</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Tier / Licensed Seats</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Expires At</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] text-center">Resources</th>
                          <th className="px-6 py-4 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)] text-right">Actions</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-color)] bg-[var(--bg-app)]/10">
                        {tenants.map((tenant) => (
                          <tr key={tenant.id} className="hover:bg-[var(--bg-subtle)]/10 transition-colors">
                            <td className="px-6 py-4.5">
                              <div>
                                <p className="text-sm font-semibold text-[var(--text-primary)]">{tenant.name}</p>
                                <p className="text-xs text-[var(--text-muted)]">/{tenant.slug}</p>
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
                                <p className="text-[10px] text-[var(--text-secondary)] mt-1">Licensed Seats: {tenant.max_users}</p>
                              </div>
                            </td>
                            <td className="px-6 py-4.5 text-xs text-[var(--text-secondary)]">
                              {tenant.subscription_expires_at 
                                ? new Date(tenant.subscription_expires_at).toLocaleDateString()
                                : 'Lifetime'
                              }
                            </td>
                            <td className="px-6 py-4.5 text-center">
                              <div className="flex justify-center items-center gap-4">
                                <button 
                                  onClick={() => openUsersModal(tenant)}
                                  className="flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-brand-400 transition-colors cursor-pointer"
                                >
                                  <Users className="w-4 h-4 text-[var(--text-muted)]" />
                                  <span>{tenant.user_count}</span>
                                </button>
                                <button 
                                  onClick={() => openInvoicesModal(tenant)}
                                  className="flex items-center gap-1 text-xs text-[var(--text-secondary)] hover:text-indigo-400 transition-colors cursor-pointer"
                                >
                                  <FileText className="w-4 h-4 text-[var(--text-muted)]" />
                                  <span>{tenant.invoice_count}</span>
                                </button>
                              </div>
                            </td>
                            <td className="px-6 py-4.5 text-right">
                              <div className="flex items-center justify-end gap-2.5">
                                <button
                                  onClick={() => openEditSubModal(tenant)}
                                  className="px-2 py-1.5 border border-[var(--border-color)] hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] transition-all text-xs font-semibold flex items-center gap-1 cursor-pointer"
                                  title="Edit Subscription Tier"
                                >
                                  <Edit className="w-3.5 h-3.5" />
                                  Tier
                                </button>
                                <button
                                  onClick={() => {
                                    setSelectedTenant(tenant);
                                    setActiveModal('resetPassword');
                                  }}
                                  className="p-1.5 border border-[var(--border-color)] hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] transition-all cursor-pointer"
                                  title="Reset Owner Password"
                                >
                                  <Key className="w-4 h-4" />
                                </button>
                                <button
                                  onClick={() => handleSuspendTenant(tenant)}
                                  className={`p-1.5 border border-[var(--border-color)] hover:bg-[var(--bg-subtle)] rounded-lg transition-all cursor-pointer ${
                                    tenant.subscription_status === 'suspended'
                                      ? 'text-emerald-400 hover:text-emerald-300'
                                      : 'text-amber-400 hover:text-amber-300'
                                  }`}
                                  title={tenant.subscription_status === 'suspended' ? 'Reactivate Account' : 'Suspend Account'}
                                >
                                  {tenant.subscription_status === 'suspended' ? (
                                    <Lock className="w-4 h-4" />
                                  ) : (
                                    <Unlock className="w-4 h-4" />
                                  )}
                                </button>
                                <button
                                  onClick={() => {
                                    setSelectedTenant(tenant);
                                    setDeleteConfirmSlug('');
                                    setActiveModal('deleteTenantConfirm');
                                  }}
                                  className="p-1.5 border border-[var(--border-color)] hover:bg-red-500/10 hover:border-red-500/20 text-red-400 rounded-lg transition-all cursor-pointer"
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
          {activeSection === 'plans' && (
            <div className="space-y-4">
              <div className="flex justify-between items-center">
                <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-secondary)]">Subscription Plans</h3>
                <button
                  onClick={() => {
                    resetPlan({
                      minimum_users: 10,
                      minimum_contract_months: 3,
                      allow_additional_seats: true,
                      currency: 'INR',
                      monthly_price: 3999,
                      quarterly_price: 11997,
                      annual_price: 47988,
                      max_users: 10,
                      maximum_users: 1000,
                      trial_days: 0,
                      extra_user_price: 3999,
                      discount_percentage: 0,
                      gst_percentage: 18,
                      display_order: 1,
                      setup_charges: 0,
                      storage_limit_gb: 100,
                      recording_retention_days: 90,
                      popular_plan: false,
                      recommended_plan: false,
                      allow_upgrade: true,
                      allow_downgrade: true,
                      allow_trial: true,
                      auto_renew: true,
                      plan_active: true
                    });
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
                <div className="glass-panel p-16 rounded-2xl border border-[var(--border-strong)]/80 flex flex-col items-center justify-center text-[var(--text-muted)] text-center">
                  <FolderKanban className="w-12 h-12 text-[var(--text-muted)] mb-3" />
                  <p className="text-base font-semibold text-[var(--text-secondary)]">No Custom Plans Registered</p>
                  <p className="text-xs text-[var(--text-muted)] mt-1">Add your first commercial pricing plan to begin assigning tenant limits.</p>
                </div>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                  {plans.map((plan) => (
                    <div
                      key={plan.id}
                      className={`glass-panel p-6 border rounded-2xl space-y-4 relative flex flex-col justify-between transition-all ${
                        plan.popular_plan
                          ? 'border-brand-500/40 shadow-lg shadow-brand-500/10 hover:border-brand-500/60'
                          : 'border-[var(--border-strong)]/80 hover:border-[var(--border-strong)]'
                      }`}
                    >
                      {/* MOST POPULAR badge */}
                      {plan.popular_plan && (
                        <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                          <span className="inline-flex items-center gap-1 px-3 py-1 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-[10px] font-bold rounded-full shadow-md shadow-brand-500/30 uppercase tracking-widest whitespace-nowrap">
                            ⭐ Most Popular
                          </span>
                        </div>
                      )}

                      <div className="space-y-2">
                        <div className="flex justify-between items-start">
                          <div>
                            <h4 className="text-lg font-bold text-[var(--text-primary)]">{plan.display_name}</h4>
                            <p className="text-xs text-[var(--text-muted)] font-mono">slug: {plan.name}</p>
                          </div>
                          <div className="flex items-center gap-1 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg p-0.5">
                            <button
                              onClick={() => handleReorderPlans(plan.id, 'up')}
                              className="p-1 hover:bg-[var(--bg-card)] rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                            >
                              <ArrowUpDown className="w-3 h-3 rotate-180" />
                            </button>
                            <button
                              onClick={() => handleReorderPlans(plan.id, 'down')}
                              className="p-1 hover:bg-[var(--bg-card)] rounded text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
                            >
                              <ArrowUpDown className="w-3 h-3" />
                            </button>
                          </div>
                        </div>
                        <p className="text-xs text-[var(--text-secondary)] line-clamp-2">{plan.description || 'No description provided.'}</p>

                        {/* Price block */}
                        <div className="py-3 border-y border-[var(--border-strong)]/80">
                          <p className="text-3xl font-black text-brand-400">
                            {plan.currency === 'INR' ? '₹' : plan.currency}{Number(plan.monthly_price).toLocaleString('en-IN')}
                          </p>
                          <p className="text-[11px] text-[var(--text-secondary)] mt-0.5 font-medium">Per Licensed Seat &nbsp;/&nbsp; Per Month</p>
                        </div>

                        {/* Plan details */}
                        <div className="space-y-1.5 pt-1">
                          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
                            <Users className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                            <span>Starts From: <strong>{plan.minimum_users ?? plan.max_users} Licensed Seats</strong></span>
                          </p>
                          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
                            <Check className="w-3.5 h-3.5 text-emerald-500 shrink-0" />
                            <span>Minimum Contract: <strong>{plan.minimum_contract_months} Months</strong></span>
                          </p>
                          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
                            <Building className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                            <span>Storage: <strong>{plan.storage_limit_gb} GB</strong></span>
                          </p>
                          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
                            <FileText className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                            <span>Call Recording Retention: <strong>{plan.recording_retention_days} Days</strong></span>
                          </p>
                          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
                            <DollarSign className="w-3.5 h-3.5 text-[var(--text-muted)] shrink-0" />
                            <span>Additional Seat Price: <strong>{plan.currency === 'INR' ? '₹' : plan.currency}{Number(plan.extra_user_price ?? 0).toLocaleString('en-IN')}</strong></span>
                          </p>
                          <p className="text-xs text-[var(--text-secondary)] flex items-center gap-2">
                            <Check className={`w-3.5 h-3.5 shrink-0 ${plan.allow_additional_seats ? 'text-emerald-500' : 'text-[var(--text-muted)]'}`} />
                            <span>Additional Seats: <strong>{plan.allow_additional_seats ? 'Allowed' : 'Not Allowed'}</strong></span>
                          </p>
                        </div>

                        {/* Billing Policy */}
                        <div className="mt-3 p-3 bg-[var(--bg-subtle)]/60 border border-[var(--border-strong)]/60 rounded-xl text-[10px] text-[var(--text-secondary)] space-y-1">
                          <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)] mb-1.5">Billing Policy</p>
                          <p className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-[var(--text-muted)] shrink-0" />Per Licensed Seat</p>
                          <p className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-[var(--text-muted)] shrink-0" />Minimum Initial Purchase: {plan.minimum_users ?? plan.max_users} Seats</p>
                          <p className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-[var(--text-muted)] shrink-0" />Minimum Initial Contract: {plan.minimum_contract_months} Months</p>
                          <p className="flex items-center gap-1.5"><span className="w-1 h-1 rounded-full bg-[var(--text-muted)] shrink-0" />{plan.allow_additional_seats ? 'Additional Seats can be purchased anytime' : 'Additional Seats not available'}</p>
                        </div>
                      </div>

                      <div className="flex items-center gap-3 pt-4 border-t border-[var(--border-color)]/50">
                        <button
                          onClick={() => {
                            setSelectedPlan(plan);
                            setModalError(null);
                            Object.keys(plan).forEach((key) => {
                              setPlanValue(key as any, plan[key as keyof PlanResponse]);
                            });
                            setActiveModal('editPlan');
                          }}
                          className="flex-1 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] hover:border-[var(--border-strong)] text-[var(--text-secondary)] rounded-xl text-xs font-semibold transition-all cursor-pointer text-center"
                        >
                          Configure
                        </button>
                        <button
                          onClick={() => handleDeletePlan(plan.id)}
                          className="p-2 border border-[var(--border-color)] hover:border-red-500/30 hover:bg-red-500/10 text-red-400 rounded-xl transition-all cursor-pointer"
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
          {activeSection === 'features' && (
            <div className="space-y-4">
              <div>
                <h3 className="text-sm font-bold uppercase tracking-wider text-[var(--text-secondary)]">Plan Permissions Matrix</h3>
                <p className="text-xs text-[var(--text-muted)] mt-1">Cross-check plans mapping checkbox cells to dynamically authorize API scopes.</p>
              </div>

              {plans.length === 0 || features.length === 0 ? (
                <div className="glass-panel p-16 rounded-2xl border border-[var(--border-strong)]/80 flex flex-col items-center justify-center text-[var(--text-muted)] text-center">
                  <Workflow className="w-12 h-12 text-[var(--text-muted)] mb-3" />
                  <p className="text-base font-semibold text-[var(--text-secondary)]">Setup Required</p>
                  <p className="text-xs text-[var(--text-muted)] mt-1">You must create at least one Plan Template and seed features to build matrix mappings.</p>
                </div>
              ) : (
                <div className="glass-panel rounded-2xl border border-[var(--border-strong)]/80 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left border-collapse">
                      <thead>
                        <tr className="border-b border-[var(--border-color)] bg-[var(--bg-subtle)]/20">
                          <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Feature Description</th>
                          <th className="px-6 py-4.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">Category</th>
                          {plans.map((p) => (
                            <th key={p.id} className="px-6 py-4.5 text-xs font-bold uppercase tracking-wider text-brand-400 text-center">
                              {p.display_name}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[var(--border-color)] bg-[var(--bg-app)]/10">
                        {features.map((feature) => (
                          <tr key={feature.id} className="hover:bg-[var(--bg-subtle)]/10 transition-colors">
                            <td className="px-6 py-4">
                              <div>
                                <p className="text-sm font-semibold text-[var(--text-primary)]">{feature.display_name}</p>
                                <p className="text-[10px] text-[var(--text-muted)] font-mono">code: {feature.code}</p>
                              </div>
                            </td>
                            <td className="px-6 py-4">
                              <span className="inline-block px-1.5 py-0.5 text-[9px] font-semibold bg-[var(--bg-card)] text-[var(--text-secondary)] rounded uppercase tracking-wider">
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
                                        : 'border-[var(--border-color)] hover:border-[var(--border-strong)] bg-[var(--bg-subtle)]/40 text-transparent'
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
          {activeSection === 'invoice' && editedConfig && (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              {/* Left Column: Config Forms (col-span-2) */}
              <div className="xl:col-span-2 space-y-6">
                <div className="glass-panel p-6 border border-[var(--border-strong)]/80 rounded-2xl space-y-6">
                  <div>
                    <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                      <FileText className="w-5 h-5 text-indigo-400" />
                      Dynamic Invoice Ledger settings
                    </h3>
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Configure dynamic values, bank specifications, pan details, prefix parameters, and transaction details.
                    </p>
                  </div>

                  {/* Sub-tab Navigation */}
                  <div className="flex border-b border-[var(--border-color)] pb-2 overflow-x-auto gap-1.5 scrollbar-thin">
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
                            : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]/60 hover:text-[var(--text-primary)] border-transparent'
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
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Company Name (Billing Issuer)</label>
                          <input
                            type="text"
                            value={editedConfig.company_name || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, company_name: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="Enter company billing name"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Tagline</label>
                          <input
                            type="text"
                            value={editedConfig.tagline || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, tagline: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. Beyond boundaries"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Website</label>
                          <input
                            type="text"
                            value={editedConfig.website || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, website: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. www.johnsonsoftwares.com"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Support Contact Email</label>
                          <input
                            type="email"
                            value={editedConfig.support_email || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, support_email: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. billing@johnsonsoftwares.com"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Phone Number</label>
                          <input
                            type="text"
                            value={editedConfig.phone_number || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, phone_number: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. +91 22 5097 2233"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Billing Address</label>
                          <textarea
                            rows={3}
                            value={editedConfig.address || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, address: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="Enter physical billing address"
                          />
                        </div>
                      </div>
                    )}

                    {/* Branding logo/qr uploads */}
                    {invoiceConfigSubTab === 'branding' && (
                      <div className="space-y-6 text-left">
                        <div className="space-y-2">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">Company Logo branding</h4>
                          <p className="text-xs text-[var(--text-muted)]">Served dynamically at the top header of client invoice cards.</p>
                          {editedConfig.company_logo_url ? (
                            <div className="flex items-center gap-4 p-4 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl">
                              <img
                                src={editedConfig.company_logo_url}
                                alt="Company Logo"
                                className="max-h-16 max-w-[200px] object-contain rounded bg-[var(--bg-app)] p-2"
                              />
                              <div>
                                <p className="text-xs font-semibold text-[var(--text-secondary)]">Logo active</p>
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
                            <div className="relative border-2 border-dashed border-[var(--border-color)] hover:border-brand-500/50 transition-all rounded-xl p-6 flex flex-col items-center justify-center bg-[var(--bg-app)]/20 text-center">
                              {isUploading ? (
                                <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-2" />
                              ) : (
                                <Upload className="w-8 h-8 text-[var(--text-muted)] mb-2" />
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
                              <span className="text-[10px] text-[var(--text-muted)] mt-1">PNG, JPG, SVG up to 2MB</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Tax & GST settings */}
                    {invoiceConfigSubTab === 'tax' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">GSTIN / Tax ID Number</label>
                          <input
                            type="text"
                            value={editedConfig.gst_number || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, gst_number: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. 27AAAAA1111A1Z1"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">PAN Number</label>
                          <input
                            type="text"
                            value={editedConfig.pan || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, pan: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. ABCDE1234F"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Business Registration Number</label>
                          <input
                            type="text"
                            value={editedConfig.business_registration_number || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, business_registration_number: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. CIN / U12345MH2026PTC123456"
                          />
                        </div>
                      </div>
                    )}

                    {/* Invoice setup prefix */}
                    {invoiceConfigSubTab === 'invoice' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Invoice Number Prefix</label>
                          <input
                            type="text"
                            value={editedConfig.invoice_prefix || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, invoice_prefix: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. TELE-INV"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Starting Invoice Number</label>
                          <input
                            type="number"
                            min="1"
                            value={editedConfig.starting_invoice_number || 1000}
                            onChange={(e) => setEditedConfig({ ...editedConfig, starting_invoice_number: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Currency Code</label>
                          <input
                            type="text"
                            value={editedConfig.currency || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, currency: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. INR, USD"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Currency Symbol</label>
                          <input
                            type="text"
                            value={editedConfig.currency_symbol || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, currency_symbol: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
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
                            <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Bank Name</label>
                            <input
                              type="text"
                              value={editedConfig.bank_name || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, bank_name: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                              placeholder="e.g. HDFC Bank"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Account Holder</label>
                            <input
                              type="text"
                              value={editedConfig.account_holder || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, account_holder: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                              placeholder="e.g. Johnson Softwares Limited"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Account Number</label>
                            <input
                              type="text"
                              value={editedConfig.account_number || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, account_number: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                              placeholder="e.g. 50100123456789"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">IFSC Code</label>
                            <input
                              type="text"
                              value={editedConfig.ifsc || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, ifsc: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                              placeholder="e.g. HDFC0000101"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Branch Name</label>
                            <input
                              type="text"
                              value={editedConfig.branch || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, branch: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                              placeholder="e.g. BKC Branch, Mumbai"
                            />
                          </div>
                          <div>
                            <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">UPI ID</label>
                            <input
                              type="text"
                              value={editedConfig.upi_id || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, upi_id: e.target.value })}
                              className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                              placeholder="e.g. johnsonsoftwares@hdfc"
                            />
                          </div>
                        </div>

                        <div className="space-y-2 pt-2 border-t border-[var(--border-strong)]/80">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">Payment QR Code image</h4>
                          <p className="text-xs text-[var(--text-muted)]">Rendered on the footer of client invoices for direct scan & pay.</p>
                          {editedConfig.qr_code_url ? (
                            <div className="flex items-center gap-4 p-4 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl">
                              <img
                                src={editedConfig.qr_code_url}
                                alt="Payment QR"
                                className="w-24 h-24 object-contain rounded bg-white p-1"
                              />
                              <div>
                                <p className="text-xs font-semibold text-[var(--text-secondary)]">QR Code active</p>
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
                            <div className="relative border-2 border-dashed border-[var(--border-color)] hover:border-brand-500/50 transition-all rounded-xl p-6 flex flex-col items-center justify-center bg-[var(--bg-app)]/20 text-center">
                              {isUploading ? (
                                <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-2" />
                              ) : (
                                <Upload className="w-8 h-8 text-[var(--text-muted)] mb-2" />
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
                              <span className="text-[10px] text-[var(--text-muted)] mt-1">PNG, JPG up to 2MB</span>
                            </div>
                          )}
                        </div>
                      </div>
                    )}

                    {/* Email Templates settings */}
                    {invoiceConfigSubTab === 'email' && (
                      <div className="space-y-6 text-left">
                        {/* Issued email */}
                        <div className="space-y-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-strong)]/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Invoice Issued Notification</h4>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.invoice_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, invoice_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Body (Rich text markdown supported)</label>
                            <textarea
                              rows={3}
                              value={editedConfig.invoice_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, invoice_body: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* Reminder email */}
                        <div className="space-y-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-strong)]/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Payment Overdue Reminder</h4>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.reminder_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, reminder_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Body</label>
                            <textarea
                              rows={3}
                              value={editedConfig.reminder_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, reminder_body: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* Payment Success email */}
                        <div className="space-y-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-strong)]/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Payment Success Confirmation</h4>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.payment_success_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, payment_success_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Body</label>
                            <textarea
                              rows={3}
                              value={editedConfig.payment_success_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, payment_success_body: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* Payment Failed email */}
                        <div className="space-y-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-strong)]/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Payment Transaction Failed</h4>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.payment_failed_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, payment_failed_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Body</label>
                            <textarea
                              rows={3}
                              value={editedConfig.payment_failed_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, payment_failed_body: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                        </div>

                        {/* Renewal Reminder email */}
                        <div className="space-y-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-strong)]/80 rounded-xl">
                          <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Renewal Reminder Notification</h4>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Subject</label>
                            <input
                              type="text"
                              value={editedConfig.renewal_reminder_subject || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, renewal_reminder_subject: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                          <div>
                            <label className="block text-[10px] text-[var(--text-secondary)] mb-1">Email Body</label>
                            <textarea
                              rows={3}
                              value={editedConfig.renewal_reminder_body || ''}
                              onChange={(e) => setEditedConfig({ ...editedConfig, renewal_reminder_body: e.target.value })}
                              className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-primary)] focus:outline-none"
                            />
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Terms & Footer notes */}
                    {invoiceConfigSubTab === 'footer' && (
                      <div className="grid grid-cols-1 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Standard Payment Terms & Conditions</label>
                          <textarea
                            rows={4}
                            value={editedConfig.payment_terms || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, payment_terms: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. Invoice payment is due within 7 days of issue. Standard SLA rates apply."
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Invoice Footer text note</label>
                          <textarea
                            rows={3}
                            value={editedConfig.footer_text || ''}
                            onChange={(e) => setEditedConfig({ ...editedConfig, footer_text: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. Thank you for your business! Reach billing@johnsonsoftwares.com for support."
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Save Configuration Trigger */}
                  <div className="flex justify-end pt-4 border-t border-[var(--border-strong)]/80">
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
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">Live Invoice Mockup</h4>
                    <span className="text-[10px] text-[var(--text-muted)] italic">Auto updates as you type</span>
                  </div>

                  <div className="glass-panel border border-[var(--border-strong)]/80 rounded-2xl overflow-hidden shadow-2xl p-6 bg-[var(--bg-app)]/60 text-[var(--text-secondary)] space-y-6 text-left relative">
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
                        <h4 className="text-sm font-bold text-[var(--text-primary)] mt-2">{editedConfig.company_name || 'Acme Corporation Ltd.'}</h4>
                        {editedConfig.tagline && <p className="text-[10px] text-[var(--text-muted)] font-medium italic">{editedConfig.tagline}</p>}
                      </div>

                      <div className="text-right text-[10px] text-[var(--text-muted)] space-y-0.5">
                        <p>{editedConfig.website || 'www.acmepower.com'}</p>
                        <p>{editedConfig.support_email || 'billing@acmepower.com'}</p>
                        <p>{editedConfig.phone_number || '+91 22 5555 1234'}</p>
                      </div>
                    </div>

                    {/* Address issuer */}
                    <div className="border-t border-[var(--border-strong)]/80 pt-3 text-[10px] text-[var(--text-secondary)] space-y-1">
                      <p className="font-semibold text-[var(--text-secondary)]">ISSUER ADDRESS & REGISTER DETAILS:</p>
                      <p className="whitespace-pre-line text-[var(--text-muted)] font-medium leading-relaxed">{editedConfig.address || '101, Antigravity Heights, Google DeepMind St, BKC, Mumbai - 400051.'}</p>
                      <div className="grid grid-cols-2 gap-2 mt-1 pt-1.5 border-t border-[var(--border-color)]/60 font-mono">
                        {editedConfig.gst_number && <p><strong>GSTIN:</strong> {editedConfig.gst_number}</p>}
                        {editedConfig.pan && <p><strong>PAN:</strong> {editedConfig.pan}</p>}
                        {editedConfig.business_registration_number && (
                          <p className="col-span-2"><strong>Reg No:</strong> {editedConfig.business_registration_number}</p>
                        )}
                      </div>
                    </div>

                    {/* Invoice ID/Dates */}
                    <div className="border-t border-[var(--border-strong)]/80 pt-3 grid grid-cols-2 gap-4 text-[10px]">
                      <div>
                        <p className="text-[var(--text-muted)] uppercase tracking-wider font-semibold">Invoice Number</p>
                        <p className="text-[var(--text-primary)] font-mono text-xs font-bold mt-0.5">
                          {editedConfig.invoice_prefix || 'INV'}-{editedConfig.starting_invoice_number || '1001'}
                        </p>
                      </div>
                      <div className="text-right font-mono">
                        <p className="text-[var(--text-muted)] uppercase tracking-wider font-semibold">Issue Date</p>
                        <p className="text-[var(--text-secondary)] mt-0.5">{new Date().toLocaleDateString()}</p>
                      </div>
                      <div>
                        <p className="text-[var(--text-muted)] uppercase tracking-wider font-semibold">Bill To</p>
                        <p className="text-[var(--text-primary)] font-bold mt-0.5">Demo Corporation Ltd.</p>
                        <p className="text-[var(--text-muted)] font-mono">billing@democorp.com</p>
                      </div>
                      <div className="text-right font-mono">
                        <p className="text-[var(--text-muted)] uppercase tracking-wider font-semibold">Payment Due</p>
                        <p className="text-rose-400 font-semibold mt-0.5">
                          {new Date(Date.now() + 7 * 24 * 60 * 60 * 1000).toLocaleDateString()}
                        </p>
                      </div>
                    </div>

                    {/* Table charges */}
                    <div className="border-t border-[var(--border-strong)]/80 pt-3 space-y-2">
                      <div className="flex justify-between items-center text-[10px] text-[var(--text-muted)] uppercase font-bold tracking-wider">
                        <span>Line Item description</span>
                        <span>Total amount</span>
                      </div>
                      <div className="flex justify-between items-start text-xs border-b border-[var(--border-color)]/60 pb-2">
                        <div>
                          <p className="text-[var(--text-primary)] font-semibold">Enterprise Pro CRM Subscription</p>
                          <p className="text-[10px] text-[var(--text-muted)]">Includes active system dialers & API credential matrix (Monthly)</p>
                        </div>
                        <span className="text-[var(--text-primary)] font-mono font-bold">
                          {editedConfig.currency_symbol || '$'} 1500.00
                        </span>
                      </div>

                      {/* Math Summary */}
                      <div className="space-y-1 text-[10px] text-[var(--text-secondary)] pt-1.5">
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
                        <div className="flex justify-between text-xs text-[var(--text-primary)] font-bold pt-2 border-t border-[var(--border-strong)]/60">
                          <span>Total Payable ({editedConfig.currency || 'USD'})</span>
                          <span className="font-mono text-brand-400">
                            {editedConfig.currency_symbol || '$'} 1620.00
                          </span>
                        </div>
                      </div>
                    </div>

                    {/* Payment specifications details */}
                    {(editedConfig.bank_name || editedConfig.upi_id) && (
                      <div className="border-t border-[var(--border-strong)]/80 pt-3 text-[10px] space-y-2">
                        <p className="font-semibold text-[var(--text-secondary)] uppercase tracking-wider">Payment Instructions:</p>
                        <div className="grid grid-cols-3 gap-2">
                          {editedConfig.bank_name && (
                            <div className="col-span-2 space-y-0.5 text-[var(--text-muted)] font-mono">
                              <p><strong className="text-[var(--text-secondary)] font-sans">Bank:</strong> {editedConfig.bank_name}</p>
                              {editedConfig.account_holder && <p><strong className="text-[var(--text-secondary)] font-sans">Holder:</strong> {editedConfig.account_holder}</p>}
                              {editedConfig.account_number && <p><strong className="text-[var(--text-secondary)] font-sans">A/C No:</strong> {editedConfig.account_number}</p>}
                              {editedConfig.ifsc && <p><strong className="text-[var(--text-secondary)] font-sans">IFSC:</strong> {editedConfig.ifsc}</p>}
                              {editedConfig.branch && <p><strong className="text-[var(--text-secondary)] font-sans">Branch:</strong> {editedConfig.branch}</p>}
                              {editedConfig.upi_id && <p className="mt-1 pt-1 border-t border-[var(--border-color)]/60"><strong className="text-[var(--text-secondary)] font-sans">UPI:</strong> {editedConfig.upi_id}</p>}
                            </div>
                          )}
                          <div className="col-span-1 flex flex-col items-end justify-center">
                            {editedConfig.qr_code_url ? (
                              <img
                                src={editedConfig.qr_code_url}
                                alt="Payment Scan QR"
                                className="w-16 h-16 object-contain rounded bg-white p-0.5 border border-[var(--border-color)]"
                              />
                            ) : editedConfig.upi_id ? (
                              <div className="w-16 h-16 rounded border border-dashed border-[var(--border-color)] flex items-center justify-center text-center p-1 text-[8px] text-[var(--text-muted)] bg-[var(--bg-subtle)]/10 leading-tight">
                                Scan QR Code
                              </div>
                            ) : null}
                          </div>
                        </div>
                      </div>
                    )}

                    {/* Footer text note */}
                    <div className="border-t border-[var(--border-strong)]/80 pt-3 text-[9px] text-[var(--text-muted)] leading-normal space-y-1">
                      {editedConfig.payment_terms && <p><strong>Terms:</strong> {editedConfig.payment_terms}</p>}
                      <p className="text-center font-medium italic text-[var(--text-secondary)]/80 mt-1">{editedConfig.footer_text || 'Thank you for choosing Johnson Softwares!'}</p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ==========================================
              TAB 4B: COMMERCIAL SETTINGS
             ========================================== */}
          {activeSection === 'commercial' && editedCommSettings && (
            <div className="grid grid-cols-1 xl:grid-cols-3 gap-6">
              {/* Left Column: Config Forms (col-span-2) */}
              <div className="xl:col-span-2 space-y-6">
                <div className="glass-panel p-6 border border-[var(--border-strong)]/80 rounded-2xl space-y-6">
                  <div>
                    <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                      <DollarSign className="w-5 h-5 text-indigo-400" />
                      Dynamic Commercial Configuration Engine
                    </h3>
                    <p className="text-xs text-[var(--text-muted)] mt-1">
                      Configure dynamic prices, grace periods, auto-renewals, discounts, tax structures, setup charges, reminders, and customized templates globally.
                    </p>
                  </div>

                  {/* Sub-tab Navigation */}
                  <div className="flex border-b border-[var(--border-color)] pb-2 overflow-x-auto gap-1.5 scrollbar-thin">
                    {[
                      { id: 'general', label: 'General', icon: Building },
                      { id: 'pricing', label: 'Pricing & Seats', icon: Users },
                      { id: 'tax', label: 'Tax', icon: Percent },
                      { id: 'contracts', label: 'Contracts', icon: Workflow },
                      { id: 'setup', label: 'Setup Charges', icon: CreditCard },
                      { id: 'discounts', label: 'Discounts', icon: Image },
                      { id: 'late-fees', label: 'Late Payments', icon: AlertCircle },
                      { id: 'renewals', label: 'Renewals & Suspension', icon: Lock },
                      { id: 'reminders', label: 'Billing Schedules', icon: Clock },
                      { id: 'emails', label: 'Email Templates', icon: Mail },
                      { id: 'advanced', label: 'Advanced', icon: Settings }
                    ].map((subTab) => (
                      <button
                        key={subTab.id}
                        type="button"
                        onClick={() => setCommSettingsSubTab(subTab.id as any)}
                        className={`flex items-center gap-1.5 px-3.5 py-2 rounded-xl text-xs font-semibold transition-all cursor-pointer whitespace-nowrap border ${
                          commSettingsSubTab === subTab.id
                            ? 'bg-brand-500/10 text-brand-400 border-brand-500/30'
                            : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)]/60 hover:text-[var(--text-primary)] border-transparent'
                        }`}
                      >
                        <subTab.icon className="w-3.5 h-3.5" />
                        {subTab.label}
                      </button>
                    ))}
                  </div>

                  {/* Forms Content */}
                  <div className="space-y-4 pt-2">
                    {/* General Section */}
                    {commSettingsSubTab === 'general' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Default Currency</label>
                          <input
                            type="text"
                            value={editedCommSettings.default_currency || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_currency: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. INR"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Currency Symbol</label>
                          <input
                            type="text"
                            value={editedCommSettings.currency_symbol || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, currency_symbol: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. ₹"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Default System Timezone</label>
                          <input
                            type="text"
                            value={editedCommSettings.default_timezone || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_timezone: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. Asia/Kolkata"
                          />
                        </div>
                      </div>
                    )}

                    {/* Pricing Section */}
                    {commSettingsSubTab === 'pricing' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Minimum User Seats Limit</label>
                          <input
                            type="number"
                            min="1"
                            value={editedCommSettings.minimum_users || 10}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, minimum_users: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Maximum User Seats Limit</label>
                          <input
                            type="number"
                            value={editedCommSettings.maximum_users || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, maximum_users: e.target.value ? Number(e.target.value) : null })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="Leave empty for unlimited seats"
                          />
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Extra Seat Price (per seat/month)</label>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={editedCommSettings.default_extra_user_price || 0}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_extra_user_price: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                      </div>
                    )}

                    {/* Tax Section */}
                    {commSettingsSubTab === 'tax' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Tax Rate (GST %)</label>
                          <input
                            type="number"
                            min="0"
                            step="0.1"
                            value={editedCommSettings.default_gst || 18.0}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_gst: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Tax label</label>
                          <input
                            type="text"
                            value={editedCommSettings.tax_label || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, tax_label: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. GST"
                          />
                        </div>
                        <div className="md:col-span-2 flex items-center gap-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl mt-2">
                          <input
                            type="checkbox"
                            id="gst_inclusive"
                            checked={editedCommSettings.gst_inclusive || false}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, gst_inclusive: e.target.checked })}
                            className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-app)] focus:ring-brand-500/20"
                          />
                          <label htmlFor="gst_inclusive" className="text-xs font-semibold text-[var(--text-secondary)] select-none cursor-pointer">
                            GST Inclusive Pricing (Prices in plan templates already include GST tax)
                          </label>
                        </div>
                      </div>
                    )}

                    {/* Contracts Section */}
                    {commSettingsSubTab === 'contracts' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Minimum Contract Period (Months)</label>
                          <input
                            type="number"
                            min="1"
                            value={editedCommSettings.default_min_contract || 3}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_min_contract: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Termination Notice Period (Days)</label>
                          <input
                            type="number"
                            min="0"
                            value={editedCommSettings.notice_period_days || 15}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, notice_period_days: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div className="md:col-span-2 flex items-center gap-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl mt-2">
                          <input
                            type="checkbox"
                            id="auto_renewal"
                            checked={editedCommSettings.auto_renewal || false}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, auto_renewal: e.target.checked })}
                            className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-app)] focus:ring-brand-500/20"
                          />
                          <label htmlFor="auto_renewal" className="text-xs font-semibold text-[var(--text-secondary)] select-none cursor-pointer">
                            Enable Auto-Renewal by default for new subscriptions
                          </label>
                        </div>
                      </div>
                    )}

                    {/* Setup Charges Section */}
                    {commSettingsSubTab === 'setup' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Default Setup Charges</label>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={editedCommSettings.default_setup_charge || 0}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_setup_charge: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div className="flex items-center gap-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <input
                            type="checkbox"
                            id="allow_setup_discount"
                            checked={editedCommSettings.allow_setup_discount || false}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, allow_setup_discount: e.target.checked })}
                            className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-app)] focus:ring-brand-500/20"
                          />
                          <label htmlFor="allow_setup_discount" className="text-xs font-semibold text-[var(--text-secondary)] select-none cursor-pointer">
                            Allow Setup Fee Discounts
                          </label>
                        </div>
                        <div className="flex items-center gap-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <input
                            type="checkbox"
                            id="free_setup_on_annual"
                            checked={editedCommSettings.free_setup_on_annual || false}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, free_setup_on_annual: e.target.checked })}
                            className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-app)] focus:ring-brand-500/20"
                          />
                          <label htmlFor="free_setup_on_annual" className="text-xs font-semibold text-[var(--text-secondary)] select-none cursor-pointer">
                            Waive Setup Fee on Annual billing
                          </label>
                        </div>
                      </div>
                    )}

                    {/* Discounts Section */}
                    {commSettingsSubTab === 'discounts' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Default Discount Percentage</label>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="0.01"
                            value={editedCommSettings.default_discount_percentage || 0}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_discount_percentage: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Maximum Permitted Discount %</label>
                          <input
                            type="number"
                            min="0"
                            max="100"
                            step="0.01"
                            value={editedCommSettings.maximum_discount_percentage || 25}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, maximum_discount_percentage: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div className="flex items-center gap-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <input
                            type="checkbox"
                            id="allow_custom_discount"
                            checked={editedCommSettings.allow_custom_discount || false}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, allow_custom_discount: e.target.checked })}
                            className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-app)] focus:ring-brand-500/20"
                          />
                          <label htmlFor="allow_custom_discount" className="text-xs font-semibold text-[var(--text-secondary)] select-none cursor-pointer">
                            Allow manual/custom discounts overrides
                          </label>
                        </div>
                        <div className="flex items-center gap-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <input
                            type="checkbox"
                            id="allow_promo_code"
                            checked={editedCommSettings.allow_promo_code || false}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, allow_promo_code: e.target.checked })}
                            className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-app)] focus:ring-brand-500/20"
                          />
                          <label htmlFor="allow_promo_code" className="text-xs font-semibold text-[var(--text-secondary)] select-none cursor-pointer">
                            Enable promo codes support
                          </label>
                        </div>
                      </div>
                    )}

                    {/* Late Payments Section */}
                    {commSettingsSubTab === 'late-fees' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Late Payment Charge Amount/Value</label>
                          <input
                            type="number"
                            min="0"
                            step="0.01"
                            value={editedCommSettings.late_payment_charge || 0}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, late_payment_charge: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Late Payment Charge type</label>
                          <select
                            value={editedCommSettings.late_payment_type || 'flat'}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, late_payment_type: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          >
                            <option value="flat">Flat Charge</option>
                            <option value="percentage">Percentage per month (%)</option>
                          </select>
                        </div>
                        <div className="md:col-span-2">
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Payment Grace Period (Days)</label>
                          <input
                            type="number"
                            min="0"
                            value={editedCommSettings.grace_period_days || 7}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, grace_period_days: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="Days allowed before late fee/restriction starts"
                          />
                        </div>
                      </div>
                    )}

                    {/* Renewals & Suspension Section */}
                    {commSettingsSubTab === 'renewals' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Auto-Suspend Threshold (Days after renewal due)</label>
                          <input
                            type="number"
                            min="0"
                            value={editedCommSettings.auto_suspend_days || 30}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, auto_suspend_days: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Default Trial period duration (Days)</label>
                          <input
                            type="number"
                            min="0"
                            value={editedCommSettings.default_trial_days || 14}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_trial_days: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Default Plan Template ID for new signups</label>
                          <select
                            value={editedCommSettings.default_plan_id || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_plan_id: e.target.value || null })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          >
                            <option value="">No Default Plan (Manual upgrade required)</option>
                            {plans.map(plan => (
                              <option key={plan.id} value={plan.id}>{plan.display_name || plan.name}</option>
                            ))}
                          </select>
                        </div>
                        <div className="flex items-center gap-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl mt-6">
                          <input
                            type="checkbox"
                            id="auto_reactivate"
                            checked={editedCommSettings.auto_reactivate || false}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, auto_reactivate: e.target.checked })}
                            className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-app)] focus:ring-brand-500/20"
                          />
                          <label htmlFor="auto_reactivate" className="text-xs font-semibold text-[var(--text-secondary)] select-none cursor-pointer">
                            Auto-reactivate suspension on payment receipt
                          </label>
                        </div>
                        <div className="flex items-center gap-3 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl md:col-span-2">
                          <input
                            type="checkbox"
                            id="allow_trial"
                            checked={editedCommSettings.allow_trial || false}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, allow_trial: e.target.checked })}
                            className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-app)] focus:ring-brand-500/20"
                          />
                          <label htmlFor="allow_trial" className="text-xs font-semibold text-[var(--text-secondary)] select-none cursor-pointer">
                            Allow Trial Periods for new registration instances
                          </label>
                        </div>
                      </div>
                    )}

                    {/* Billing Schedules / Reminders Section */}
                    {commSettingsSubTab === 'reminders' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Invoice reminders (days before due, comma-separated)</label>
                          <input
                            type="text"
                            value={editedCommSettings.invoice_reminder_days || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, invoice_reminder_days: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. 7,3,1"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Subscription warnings (days before renew, comma-separated)</label>
                          <input
                            type="text"
                            value={editedCommSettings.subscription_reminder_days || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, subscription_reminder_days: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. 15,7,3,0"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Payment Reminders (days after due, comma-separated)</label>
                          <input
                            type="text"
                            value={editedCommSettings.payment_reminder_days || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, payment_reminder_days: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                            placeholder="e.g. 0,3,7,15"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Trial warnings offset (Days before expiry)</label>
                          <input
                            type="number"
                            min="0"
                            value={editedCommSettings.trial_reminder_days || 3}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, trial_reminder_days: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                      </div>
                    )}

                    {/* Email Templates Section */}
                    {commSettingsSubTab === 'emails' && (
                      <div className="space-y-6 text-left">
                        <div className="space-y-2 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <label className="block text-xs font-bold uppercase tracking-wider text-brand-400 mb-1">Welcome Email Override Template</label>
                          <textarea
                            rows={3}
                            value={editedCommSettings.welcome_template || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, welcome_template: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-primary)] focus:outline-none font-mono"
                            placeholder="Use variables like {customer_name}"
                          />
                        </div>
                        <div className="space-y-2 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <label className="block text-xs font-bold uppercase tracking-wider text-brand-400 mb-1">Trial Expiration Notice Template</label>
                          <textarea
                            rows={3}
                            value={editedCommSettings.trial_expiry_template || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, trial_expiry_template: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-primary)] focus:outline-none font-mono"
                            placeholder="Use variables like {customer_name}, {days_left}"
                          />
                        </div>
                        <div className="space-y-2 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <label className="block text-xs font-bold uppercase tracking-wider text-brand-400 mb-1">Subscription Renewal Reminder Template</label>
                          <textarea
                            rows={3}
                            value={editedCommSettings.renewal_reminder_template || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, renewal_reminder_template: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-primary)] focus:outline-none font-mono"
                            placeholder="Use variables like {customer_name}, {renewal_date}"
                          />
                        </div>
                        <div className="space-y-2 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <label className="block text-xs font-bold uppercase tracking-wider text-brand-400 mb-1">Invoice Reminder Template</label>
                          <textarea
                            rows={3}
                            value={editedCommSettings.invoice_reminder_template || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, invoice_reminder_template: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-primary)] focus:outline-none font-mono"
                            placeholder="Use variables like {customer_name}, {invoice_number}"
                          />
                        </div>
                        <div className="space-y-2 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <label className="block text-xs font-bold uppercase tracking-wider text-brand-400 mb-1">Payment Success Template</label>
                          <textarea
                            rows={3}
                            value={editedCommSettings.payment_success_template || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, payment_success_template: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-primary)] focus:outline-none font-mono"
                            placeholder="Use variables like {customer_name}, {invoice_number}"
                          />
                        </div>
                        <div className="space-y-2 p-4 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl">
                          <label className="block text-xs font-bold uppercase tracking-wider text-brand-400 mb-1">Payment Failed Template</label>
                          <textarea
                            rows={3}
                            value={editedCommSettings.payment_failed_template || ''}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, payment_failed_template: e.target.value })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-primary)] focus:outline-none font-mono"
                            placeholder="Use variables like {customer_name}, {invoice_number}"
                          />
                        </div>
                      </div>
                    )}

                    {/* Advanced Section */}
                    {commSettingsSubTab === 'advanced' && (
                      <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-left">
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Default Recording Retention Period (Days)</label>
                          <input
                            type="number"
                            min="1"
                            value={editedCommSettings.default_recording_retention_days || 90}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_recording_retention_days: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                        <div>
                          <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Default Storage Boundary (GB)</label>
                          <input
                            type="number"
                            min="1"
                            value={editedCommSettings.default_storage_gb || 50}
                            onChange={(e) => setEditedCommSettings({ ...editedCommSettings, default_storage_gb: Number(e.target.value) })}
                            className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                          />
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Save Settings Trigger & Audit Reason */}
                  <div className="pt-4 border-t border-[var(--border-strong)]/80 space-y-4">
                    <div className="text-left">
                      <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">
                        Reason for Update (Required for Audit Trail Logs)
                      </label>
                      <input
                        type="text"
                        required
                        value={editedCommSettings.reason || ''}
                        onChange={(e) => setEditedCommSettings({ ...editedCommSettings, reason: e.target.value })}
                        className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                        placeholder="e.g. Revised default currency rules / updated late fee metrics"
                      />
                    </div>
                    <div className="flex justify-end">
                      <button
                        type="button"
                        onClick={handleSaveCommSettings}
                        disabled={isLoading || !editedCommSettings.reason}
                        className="flex items-center justify-center gap-1.5 px-6 py-2.5 bg-gradient-to-tr from-brand-500 to-indigo-500 hover:from-brand-600 hover:to-indigo-600 text-white rounded-xl text-xs font-bold transition-all shadow-md shadow-brand-500/10 cursor-pointer disabled:opacity-50"
                      >
                        {isLoading ? (
                          <Loader2 className="w-3.5 h-3.5 animate-spin" />
                        ) : (
                          <>
                            <Check className="w-3.5 h-3.5" />
                            Save Rules & Settings
                          </>
                        )}
                      </button>
                    </div>
                  </div>
                </div>
              </div>

              {/* Right Column: Live Mock Commercial Card preview */}
              <div className="xl:col-span-1">
                <div className="sticky top-6 space-y-4">
                  <div className="flex justify-between items-baseline px-1">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-[var(--text-secondary)]">Live Active Summary</h4>
                    <span className="text-[10px] text-[var(--text-muted)] italic">Reactive summary card</span>
                  </div>

                  <div className="glass-panel border border-[var(--border-strong)]/80 rounded-2xl overflow-hidden shadow-2xl p-6 bg-[var(--bg-app)]/60 text-[var(--text-secondary)] space-y-6 text-left relative">
                    <div>
                      <h4 className="text-sm font-bold text-[var(--text-primary)] uppercase tracking-wider bg-gradient-to-r from-brand-300 to-brand-500 bg-clip-text text-transparent">
                        Commercial Engine Status
                      </h4>
                      <p className="text-[10px] text-[var(--text-muted)] mt-1">Reflects active global default fallbacks</p>
                    </div>

                    <div className="space-y-4 pt-2 border-t border-[var(--border-strong)]/60 text-xs leading-relaxed">
                      <div className="space-y-1.5">
                        <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-wider">Default Localization</p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Currency: <strong className="text-[var(--text-primary)]">{editedCommSettings.default_currency || 'INR'} ({editedCommSettings.currency_symbol || '₹'})</strong>
                        </p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Timezone: <strong className="text-[var(--text-primary)]">{editedCommSettings.default_timezone || 'Asia/Kolkata'}</strong>
                        </p>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]/60">
                        <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-wider">Seats Pricing & Constraints</p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Seat limits: <strong className="text-[var(--text-primary)]">{editedCommSettings.minimum_users || 10} - {editedCommSettings.maximum_users || 'Unlimited'}</strong>
                        </p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Extra Seat charge: <strong className="text-[var(--text-primary)]">{editedCommSettings.currency_symbol || '₹'}{editedCommSettings.default_extra_user_price || 0.00}/month</strong>
                        </p>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]/60">
                        <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-wider">Trial Periods Policy</p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Trials: <strong className="text-[var(--text-primary)]">{editedCommSettings.allow_trial ? 'Allowed (' + (editedCommSettings.default_trial_days || 14) + ' days)' : 'Disabled'}</strong>
                        </p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Reminder offset: <strong className="text-[var(--text-primary)]">{editedCommSettings.trial_reminder_days || 3} days before expiry</strong>
                        </p>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]/60">
                        <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-wider">Tax & GST Details</p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          GST rate: <strong className="text-[var(--text-primary)]">{editedCommSettings.default_gst || 18.0}% ({editedCommSettings.tax_label || 'GST'})</strong>
                        </p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Price model: <strong className="text-[var(--text-primary)]">{editedCommSettings.gst_inclusive ? 'Tax Inclusive' : 'Tax Exclusive'}</strong>
                        </p>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]/60">
                        <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-wider">Setup Fees Policy</p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Setup charges: <strong className="text-[var(--text-primary)]">{editedCommSettings.currency_symbol || '₹'}{editedCommSettings.default_setup_charge || 0.00}</strong>
                        </p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Waived on Annual: <strong className="text-[var(--text-primary)]">{editedCommSettings.free_setup_on_annual ? 'Yes' : 'No'}</strong>
                        </p>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]/60">
                        <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-wider">Grace & Suspension bounds</p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Late fee: <strong className="text-[var(--text-primary)]">{editedCommSettings.late_payment_charge || 0.00} ({editedCommSettings.late_payment_type || 'flat'})</strong>
                        </p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Payment grace: <strong className="text-[var(--text-primary)]">{editedCommSettings.grace_period_days || 7} days</strong>
                        </p>
                        <p className="text-[var(--text-secondary)] font-mono">
                          Suspends after: <strong className="text-[var(--text-primary)]">{editedCommSettings.auto_suspend_days || 30} days overdue</strong>
                        </p>
                      </div>

                      <div className="space-y-1.5 pt-2 border-t border-[var(--border-color)]/60">
                        <p className="text-[10px] font-semibold text-brand-400 uppercase tracking-wider">Automation schedules</p>
                        <p className="text-[var(--text-muted)] font-mono leading-tight">
                          Invoice notifications: <strong className="text-[var(--text-secondary)]">{editedCommSettings.invoice_reminder_days || '7,3,1'} days before due</strong>
                        </p>
                        <p className="text-[var(--text-muted)] font-mono leading-tight">
                          Renewal warnings: <strong className="text-[var(--text-secondary)]">{editedCommSettings.subscription_reminder_days || '15,7,3,0'} days before renewal</strong>
                        </p>
                        <p className="text-[var(--text-muted)] font-mono leading-tight">
                          Overdue payment reminders: <strong className="text-[var(--text-secondary)]">{editedCommSettings.payment_reminder_days || '0,3,7,15'} days after due</strong>
                        </p>
                      </div>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* ==========================================
              TAB 5: SYSTEM CONFIGURATIONS
             ========================================== */}
          {activeSection === 'global' && (
            <div className="max-w-2xl">
              <div className="glass-panel p-6 border border-[var(--border-strong)]/80 rounded-2xl space-y-6">
                <div>
                  <h3 className="text-lg font-bold text-[var(--text-primary)] flex items-center gap-2">
                    <Settings className="w-5 h-5 text-indigo-400" />
                    SMTP & Telephony Settings
                  </h3>
                  <p className="text-xs text-[var(--text-muted)] mt-1">Register default system mailer connections and external calling gateway keys securely.</p>
                </div>

                <form onSubmit={handleSaveSystemSettings} className="space-y-6">
                  {/* SMTP CONFIG */}
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 border-b border-[var(--border-strong)]/80 pb-2">SMTP Mailer Settings</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">SMTP Host</label>
                        <input
                          type="text"
                          name="smtp_host"
                          defaultValue={settingsData['smtp_settings']?.host || 'smtp.mailgun.org'}
                          className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">SMTP Port</label>
                        <input
                          type="number"
                          name="smtp_port"
                          defaultValue={settingsData['smtp_settings']?.port || 587}
                          className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                        />
                      </div>
                    </div>

                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Sender Username</label>
                        <input
                          type="text"
                          name="smtp_user"
                          defaultValue={settingsData['smtp_settings']?.user || 'postmaster@mg.johnsonsoftwares.com'}
                          className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Sender Display Name</label>
                        <input
                          type="text"
                          name="smtp_from_name"
                          defaultValue={settingsData['smtp_settings']?.from_name || 'TeleCRM Invoices'}
                          className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                        />
                      </div>
                    </div>
                  </div>

                  {/* TELEPHONY CONFIG */}
                  <div className="space-y-4">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 border-b border-[var(--border-strong)]/80 pb-2">Telephony Gateway (Knowlarity)</h4>
                    <div className="grid grid-cols-2 gap-4">
                      <div>
                        <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Knowlarity API Key</label>
                        <input
                          type="password"
                          name="k_key"
                          defaultValue={settingsData['telephony_settings']?.api_key || '••••••••••••••••'}
                          className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                        />
                      </div>
                      <div>
                        <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Primary Agent ID Number</label>
                        <input
                          type="text"
                          name="k_agent"
                          defaultValue={settingsData['telephony_settings']?.agent_number || '+912250972233'}
                          className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
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

            {activeSection === 'currencies' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div><h2 className="text-xl font-bold text-[var(--text-primary)]">Multi-Currency Engine</h2><p className="text-sm text-[var(--text-secondary)] mt-1">Manage exchange rates with base-currency pivot</p></div>
                  <button onClick={() => { setCurrencyForm({ code: '', name: '', symbol: '', exchange_rate: 1, is_active: true }); setActiveCurrencyModal('create'); }} className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 text-white rounded-xl text-xs font-bold cursor-pointer"><Plus className="w-3.5 h-3.5" /> Add Currency</button>
                </div>
                <div className="glass-panel rounded-2xl border border-[var(--border-strong)]/80 overflow-hidden">
                  <table className="w-full text-left border-collapse">
                    <thead><tr className="border-b border-[var(--border-color)] bg-[var(--bg-subtle)]/20">{['Code','Name','Symbol','Rate vs Base','Base','Active','Actions'].map(h=><th key={h} className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{h}</th>)}</tr></thead>
                    <tbody className="divide-y divide-[var(--border-color)]">
                      {currencies.length === 0 ? <tr><td colSpan={7} className="px-5 py-12 text-center text-[var(--text-muted)] text-sm">No currencies configured.</td></tr>
                      : currencies.map(c => (
                        <tr key={c.code} className="hover:bg-[var(--bg-subtle)]/10 transition-colors">
                          <td className="px-5 py-3.5"><span className="font-mono font-bold text-[var(--text-primary)]">{c.code}</span></td>
                          <td className="px-5 py-3.5 text-sm text-[var(--text-secondary)]">{c.name}</td>
                          <td className="px-5 py-3.5 text-sm text-[var(--text-secondary)]">{c.symbol}</td>
                          <td className="px-5 py-3.5 text-sm text-[var(--text-secondary)]">{c.is_base ? '-' : Number(c.exchange_rate).toFixed(4)}</td>
                          <td className="px-5 py-3.5">{c.is_base && <span className="px-2 py-0.5 bg-brand-500/10 text-brand-400 text-[10px] font-bold rounded border border-brand-500/20 uppercase">BASE</span>}</td>
                          <td className="px-5 py-3.5"><span className={'text-xs font-semibold ' + (c.is_active ? 'text-emerald-400' : 'text-[var(--text-muted)]')}>{c.is_active ? 'Active' : 'Off'}</span></td>
                          <td className="px-5 py-3.5"><div className="flex items-center gap-2">
                            <button onClick={() => { setSelectedCurrency(c); setCurrencyForm({ name: c.name, symbol: c.symbol, exchange_rate: c.exchange_rate, is_active: c.is_active }); setActiveCurrencyModal('edit'); }} className="p-1.5 border border-[var(--border-color)] hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] cursor-pointer"><Edit className="w-3.5 h-3.5" /></button>
                            {!c.is_base && <button onClick={() => handleDeleteCurrency(c.code)} className="p-1.5 border border-[var(--border-color)] hover:bg-red-500/10 text-red-400 rounded-lg cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>}
                          </div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeSection === 'tax' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div><h2 className="text-xl font-bold text-[var(--text-primary)]">Tax Engine</h2><p className="text-sm text-[var(--text-secondary)] mt-1">Country-wise GST / VAT / Sales Tax</p></div>
                  <button onClick={() => { setTaxForm({ country_code: '', country_name: '', tax_type: 'GST', tax_rate: 18, tax_label: 'GST', tax_inclusive: false, is_active: true, is_default: false }); setActiveTaxModal('create'); }} className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 text-white rounded-xl text-xs font-bold cursor-pointer"><Plus className="w-3.5 h-3.5" /> Add Tax Config</button>
                </div>
                <div className="glass-panel rounded-2xl border border-[var(--border-strong)]/80 overflow-hidden">
                  <table className="w-full text-left border-collapse">
                    <thead><tr className="border-b border-[var(--border-color)] bg-[var(--bg-subtle)]/20">{['Country','Code','Type','Rate %','Label','Inclusive','Default','Active','Actions'].map(h=><th key={h} className="px-4 py-3.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{h}</th>)}</tr></thead>
                    <tbody className="divide-y divide-[var(--border-color)]">
                      {taxConfigs.length === 0 ? <tr><td colSpan={9} className="px-5 py-12 text-center text-[var(--text-muted)] text-sm">No tax configurations.</td></tr>
                      : taxConfigs.map(t => (
                        <tr key={t.id} className="hover:bg-[var(--bg-subtle)]/10 transition-colors">
                          <td className="px-4 py-3.5 text-sm text-[var(--text-primary)] font-medium">{t.country_name}</td>
                          <td className="px-4 py-3.5"><span className="font-mono text-xs text-[var(--text-secondary)]">{t.country_code}</span></td>
                          <td className="px-4 py-3.5"><span className="px-2 py-0.5 bg-[var(--bg-card)] text-[var(--text-secondary)] text-[10px] font-bold rounded uppercase">{t.tax_type}</span></td>
                          <td className="px-4 py-3.5 text-sm text-[var(--text-secondary)]">{t.tax_rate}%</td>
                          <td className="px-4 py-3.5 text-sm text-[var(--text-secondary)]">{t.tax_label}</td>
                          <td className="px-4 py-3.5 text-xs">{t.tax_inclusive ? <span className="text-emerald-400">Yes</span> : <span className="text-[var(--text-muted)]">No</span>}</td>
                          <td className="px-4 py-3.5 text-xs">{t.is_default ? <span className="text-brand-400 font-bold">Yes</span> : '-'}</td>
                          <td className="px-4 py-3.5"><span className={'text-xs font-semibold ' + (t.is_active ? 'text-emerald-400' : 'text-[var(--text-muted)]')}>{t.is_active ? 'Active' : 'Off'}</span></td>
                          <td className="px-4 py-3.5"><div className="flex items-center gap-2">
                            <button onClick={() => { setSelectedTax(t); setTaxForm({ country_code: t.country_code, country_name: t.country_name, tax_type: t.tax_type, tax_rate: t.tax_rate, tax_label: t.tax_label, tax_inclusive: t.tax_inclusive, is_active: t.is_active, is_default: t.is_default }); setActiveTaxModal('edit'); }} className="p-1.5 border border-[var(--border-color)] hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] cursor-pointer"><Edit className="w-3.5 h-3.5" /></button>
                            <button onClick={() => handleDeleteTax(t.id)} className="p-1.5 border border-[var(--border-color)] hover:bg-red-500/10 text-red-400 rounded-lg cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
                          </div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeSection === 'gateways' && (
              <div className="space-y-4">
                <div><h2 className="text-xl font-bold text-[var(--text-primary)]">Payment Gateways</h2><p className="text-sm text-[var(--text-secondary)] mt-1">API keys encrypted server-side - never returned in responses</p></div>
                <div className="space-y-3">
                  {gateways.length === 0 ? <div className="glass-panel p-12 rounded-2xl border border-[var(--border-strong)]/80 flex items-center justify-center text-[var(--text-muted)]">No gateways seeded.</div>
                  : gateways.map(gw => (
                    <div key={gw.name} className="glass-panel border border-[var(--border-strong)]/80 rounded-2xl overflow-hidden">
                      <div className="flex items-center justify-between p-5">
                        <div className="flex items-center gap-3">
                          <div className={'w-8 h-8 rounded-lg flex items-center justify-center ' + (gw.is_enabled ? 'bg-emerald-500/10 text-emerald-400' : 'bg-[var(--bg-card)] text-[var(--text-muted)]')}><CreditCard className="w-4 h-4" /></div>
                          <div><p className="text-sm font-bold text-[var(--text-primary)]">{gw.display_name}</p>{gw.description && <p className="text-xs text-[var(--text-muted)]">{gw.description}</p>}</div>
                        </div>
                        <div className="flex items-center gap-3">
                          {gw.is_sandbox && <span className="px-2 py-0.5 bg-amber-500/10 text-amber-400 text-[10px] font-bold rounded border border-amber-500/20 uppercase">Sandbox</span>}
                          <span className={'text-xs font-semibold ' + (gw.api_key_set ? 'text-emerald-400' : 'text-[var(--text-muted)]')}>{gw.api_key_set ? 'Key set' : 'No key'}</span>
                          <button onClick={() => handleToggleGateway(gw.name)} className={'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer ' + (gw.is_enabled ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/30' : 'bg-[var(--bg-subtle)] text-[var(--text-secondary)] border-[var(--border-color)]')}>
                            {gw.is_enabled ? <ToggleRight className="w-4 h-4" /> : <ToggleLeft className="w-4 h-4" />}{gw.is_enabled ? 'Enabled' : 'Disabled'}
                          </button>
                          <button onClick={() => setExpandedGateway(expandedGateway === gw.name ? null : gw.name)} className="px-3 py-1.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-secondary)] cursor-pointer">Configure</button>
                        </div>
                      </div>
                      {expandedGateway === gw.name && (
                        <div className="border-t border-[var(--border-color)] p-5 bg-[var(--bg-app)]/20 space-y-4">
                          <div className="grid grid-cols-2 gap-4">
                            <div>
                              <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">API Key</label>
                              <div className="relative">
                                <input type={showApiKey[gw.name] ? 'text' : 'password'} placeholder={gw.api_key_set ? '(already set)' : 'Enter API key'}
                                  value={gatewayForms[gw.name]?.api_key || ''} onChange={e => setGatewayForms(prev => ({ ...prev, [gw.name]: { ...(prev[gw.name] || {}), api_key: e.target.value } }))}
                                  className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none pr-10" />
                                <button type="button" onClick={() => setShowApiKey(prev => ({ ...prev, [gw.name]: !prev[gw.name] }))} className="absolute right-3 top-1/2 -translate-y-1/2 text-[var(--text-muted)] cursor-pointer">
                                  {showApiKey[gw.name] ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                                </button>
                              </div>
                            </div>
                            <div>
                              <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Webhook Secret</label>
                              <input type="password" placeholder={gw.webhook_secret_set ? '(already set)' : 'Enter secret'}
                                value={gatewayForms[gw.name]?.webhook_secret || ''} onChange={e => setGatewayForms(prev => ({ ...prev, [gw.name]: { ...(prev[gw.name] || {}), webhook_secret: e.target.value } }))}
                                className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" />
                            </div>
                          </div>
                          <div className="flex items-center justify-between">
                            <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer">
                              <input type="checkbox" checked={gatewayForms[gw.name]?.is_sandbox ?? gw.is_sandbox} onChange={e => setGatewayForms(prev => ({ ...prev, [gw.name]: { ...(prev[gw.name] || {}), is_sandbox: e.target.checked } }))} className="w-4 h-4 rounded bg-[var(--bg-subtle)] border-[var(--border-color)]" />
                              Sandbox Mode
                            </label>
                            <button onClick={() => handleSaveGateway(gw.name)} className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-xl text-xs font-bold cursor-pointer">Save</button>
                          </div>
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {activeSection === 'coupons' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div><h2 className="text-xl font-bold text-[var(--text-primary)]">Coupon Management</h2><p className="text-sm text-[var(--text-secondary)] mt-1">Discount codes for tenant billing</p></div>
                  <button onClick={() => { setCouponForm({ code: '', description: '', discount_type: 'percentage', discount_value: 10, max_uses: '', valid_from: new Date().toISOString().split('T')[0], valid_until: '', min_order_value: 0, is_active: true }); setActiveCouponModal('create'); }} className="flex items-center gap-1.5 px-4 py-2 bg-gradient-to-tr from-brand-500 to-indigo-500 text-white rounded-xl text-xs font-bold cursor-pointer"><Plus className="w-3.5 h-3.5" /> Create Coupon</button>
                </div>
                <div className="glass-panel rounded-2xl border border-[var(--border-strong)]/80 overflow-hidden">
                  <table className="w-full text-left border-collapse">
                    <thead><tr className="border-b border-[var(--border-color)] bg-[var(--bg-subtle)]/20">{['Code','Type','Discount','Uses','Valid Until','Status','Actions'].map(h=><th key={h} className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{h}</th>)}</tr></thead>
                    <tbody className="divide-y divide-[var(--border-color)]">
                      {coupons.length === 0 ? <tr><td colSpan={7} className="px-5 py-12 text-center text-[var(--text-muted)] text-sm">No coupons yet.</td></tr>
                      : coupons.map(c => (
                        <tr key={c.id} className="hover:bg-[var(--bg-subtle)]/10 transition-colors">
                          <td className="px-5 py-3.5"><p className="font-mono font-bold text-[var(--text-primary)]">{c.code}</p>{c.description && <p className="text-[10px] text-[var(--text-muted)]">{c.description}</p>}</td>
                          <td className="px-5 py-3.5"><span className="px-2 py-0.5 bg-[var(--bg-card)] text-[var(--text-secondary)] text-[10px] font-bold rounded uppercase">{c.discount_type}</span></td>
                          <td className="px-5 py-3.5 text-sm font-semibold text-emerald-400">{c.discount_type === 'percentage' ? c.discount_value + '%' : 'Rs.' + c.discount_value}</td>
                          <td className="px-5 py-3.5 text-xs text-[var(--text-secondary)]">{c.uses_count}{c.max_uses ? ' / ' + c.max_uses : ' / inf'}</td>
                          <td className="px-5 py-3.5 text-xs text-[var(--text-secondary)]">{c.valid_until ? new Date(c.valid_until).toLocaleDateString() : 'No expiry'}</td>
                          <td className="px-5 py-3.5"><span className={'text-xs font-semibold ' + (c.is_active ? 'text-emerald-400' : 'text-[var(--text-muted)]')}>{c.is_active ? 'Active' : 'Off'}</span></td>
                          <td className="px-5 py-3.5"><div className="flex items-center gap-2">
                            <button onClick={() => { setSelectedCoupon(c); setCouponForm({ code: c.code, description: c.description || '', discount_type: c.discount_type, discount_value: c.discount_value, max_uses: c.max_uses ?? '', valid_from: c.valid_from?.split('T')[0] || '', valid_until: c.valid_until?.split('T')[0] || '', min_order_value: c.min_order_value, is_active: c.is_active }); setActiveCouponModal('edit'); }} className="p-1.5 border border-[var(--border-color)] hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] cursor-pointer"><Edit className="w-3.5 h-3.5" /></button>
                            <button onClick={() => handleDeleteCoupon(c.id)} className="p-1.5 border border-[var(--border-color)] hover:bg-red-500/10 text-red-400 rounded-lg cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
                          </div></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeSection === 'notifications' && (
              <div className="space-y-4">
                <div><h2 className="text-xl font-bold text-[var(--text-primary)]">Notification Templates</h2><p className="text-sm text-[var(--text-secondary)] mt-1">Email, SMS, and WhatsApp templates</p></div>
                <div className="glass-panel rounded-2xl border border-[var(--border-strong)]/80 overflow-hidden">
                  <table className="w-full text-left border-collapse">
                    <thead><tr className="border-b border-[var(--border-color)] bg-[var(--bg-subtle)]/20">{['Template','Channel','Category','Status','Actions'].map(h=><th key={h} className="px-5 py-3.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{h}</th>)}</tr></thead>
                    <tbody className="divide-y divide-[var(--border-color)]">
                      {notifTemplates.length === 0 ? <tr><td colSpan={5} className="px-5 py-12 text-center text-[var(--text-muted)] text-sm">No templates. Run backend seeds.</td></tr>
                      : notifTemplates.map(t => (
                        <tr key={t.id} className="hover:bg-[var(--bg-subtle)]/10 transition-colors">
                          <td className="px-5 py-3.5"><p className="text-sm font-semibold text-[var(--text-primary)]">{t.template_name}</p><p className="text-[10px] text-[var(--text-muted)] font-mono">{t.template_key}</p></td>
                          <td className="px-5 py-3.5"><span className={'px-2 py-0.5 text-[10px] font-bold rounded uppercase border ' + (t.channel === 'email' ? 'bg-blue-500/10 text-blue-400 border-blue-500/20' : t.channel === 'sms' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20' : t.channel === 'whatsapp' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-[var(--bg-card)] text-[var(--text-secondary)] border-[var(--border-strong)]')}>{t.channel}</span></td>
                          <td className="px-5 py-3.5 text-xs text-[var(--text-secondary)]">{t.category}</td>
                          <td className="px-5 py-3.5"><span className={'text-xs font-semibold ' + (t.is_active ? 'text-emerald-400' : 'text-[var(--text-muted)]')}>{t.is_active ? 'Active' : 'Off'}</span></td>
                          <td className="px-5 py-3.5"><button onClick={() => { setSelectedNotif(t); setNotifForm({ template_name: t.template_name, subject: t.subject || '', body: t.body, is_active: t.is_active, description: t.description || '' }); setActiveNotifModal('edit'); }} className="p-1.5 border border-[var(--border-color)] hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] cursor-pointer"><Edit className="w-3.5 h-3.5" /></button></td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeSection === 'audit' && (
              <div className="space-y-4">
                <div className="flex items-center justify-between">
                  <div><h2 className="text-xl font-bold text-[var(--text-primary)]">Audit Center</h2><p className="text-sm text-[var(--text-secondary)] mt-1">Immutable log of all sensitive operations</p></div>
                  <div className="flex items-center gap-2">
                    <input type="text" placeholder="Filter by action..." value={auditSearch} onChange={e => setAuditSearch(e.target.value)} onKeyDown={e => e.key === 'Enter' && fetchAllData()} className="px-3.5 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-primary)] placeholder-[var(--text-muted)] focus:outline-none w-48" />
                    <button onClick={fetchAllData} className="p-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-[var(--text-secondary)] cursor-pointer"><RefreshCw className="w-3.5 h-3.5" /></button>
                  </div>
                </div>
                <div className="glass-panel rounded-2xl border border-[var(--border-strong)]/80 overflow-hidden">
                  <table className="w-full text-left border-collapse">
                    <thead><tr className="border-b border-[var(--border-color)] bg-[var(--bg-subtle)]/20">{['Timestamp','User','Action','Resource','IP','Details'].map(h=><th key={h} className="px-4 py-3.5 text-xs font-semibold uppercase tracking-wider text-[var(--text-secondary)]">{h}</th>)}</tr></thead>
                    <tbody className="divide-y divide-[var(--border-color)]">
                      {auditLogs.length === 0 ? <tr><td colSpan={6} className="px-5 py-12 text-center text-[var(--text-muted)] text-sm">No audit logs found.</td></tr>
                      : auditLogs.map((log: any, i: number) => (
                        <tr key={log.id || i} className="hover:bg-[var(--bg-subtle)]/10 transition-colors">
                          <td className="px-4 py-3 text-xs text-[var(--text-secondary)] whitespace-nowrap">{log.created_at ? new Date(log.created_at).toLocaleString() : '-'}</td>
                          <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">{log.user_email || log.actor_id || '-'}</td>
                          <td className="px-4 py-3"><span className="px-2 py-0.5 bg-[var(--bg-card)] text-[var(--text-secondary)] text-[10px] font-bold rounded uppercase">{log.action || '-'}</span></td>
                          <td className="px-4 py-3 text-xs text-[var(--text-secondary)]">{log.resource_type || '-'}</td>
                          <td className="px-4 py-3 text-xs text-[var(--text-muted)] font-mono">{log.ip_address || '-'}</td>
                          <td className="px-4 py-3 text-xs text-[var(--text-muted)] max-w-xs truncate">{log.details ? JSON.stringify(log.details).substring(0,60) : '-'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}

            {activeSection === 'reports' && (
              <div className="space-y-6">
                <div className="flex items-center justify-between">
                  <div><h2 className="text-xl font-bold text-[var(--text-primary)]">Reports and Analytics</h2><p className="text-sm text-[var(--text-secondary)] mt-1">Revenue, seat utilization, tenant health</p></div>
                  <button onClick={fetchAllData} className="flex items-center gap-2 px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs text-[var(--text-secondary)] cursor-pointer"><RefreshCw className="w-3.5 h-3.5" /> Refresh</button>
                </div>
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
                  <div className="glass-panel p-6 border border-[var(--border-strong)]/80 rounded-2xl space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2"><DollarSign className="w-4 h-4 text-emerald-400" />Revenue Report</h3>
                      <button className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-secondary)] cursor-pointer"><Download className="w-3.5 h-3.5" /> Export</button>
                    </div>
                    {revenueReport ? (
                      <div className="space-y-2">
                        {[
                          { label: 'Total Revenue', value: 'Rs.' + Number(revenueReport.total_revenue ?? 0).toLocaleString('en-IN') },
                          { label: 'MRR', value: 'Rs.' + Number(revenueReport.mrr ?? 0).toLocaleString('en-IN') },
                          { label: 'ARR', value: 'Rs.' + Number(revenueReport.arr ?? 0).toLocaleString('en-IN') },
                          { label: 'Currency', value: revenueReport.currency ?? 'INR' },
                        ].map((row, i) => (
                          <div key={i} className="flex items-center justify-between py-2 border-b border-[var(--border-strong)]/60 last:border-0">
                            <span className="text-xs text-[var(--text-secondary)]">{row.label}</span><span className="text-sm font-semibold text-[var(--text-primary)]">{row.value}</span>
                          </div>
                        ))}
                      </div>
                    ) : <p className="text-sm text-[var(--text-muted)] py-4 text-center">No revenue data.</p>}
                  </div>
                  <div className="glass-panel p-6 border border-[var(--border-strong)]/80 rounded-2xl space-y-4">
                    <div className="flex items-center justify-between">
                      <h3 className="text-sm font-bold text-[var(--text-primary)] flex items-center gap-2"><Users className="w-4 h-4 text-sky-400" />Seat Utilization</h3>
                      <button className="flex items-center gap-1.5 px-3 py-1.5 border border-[var(--border-color)] rounded-lg text-xs text-[var(--text-secondary)] cursor-pointer"><Download className="w-3.5 h-3.5" /> Export</button>
                    </div>
                    {seatReport ? (
                      <div className="space-y-2">
                        {[
                          { label: 'Total Licensed', value: seatReport.total_licensed_seats ?? 0 },
                          { label: 'Active Seats', value: seatReport.active_seats ?? 0 },
                          { label: 'Utilization', value: (seatReport.utilization_percentage ?? 0) + '%' },
                          { label: 'Total Orgs', value: seatReport.total_orgs ?? 0 },
                        ].map((row, i) => (
                          <div key={i} className="flex items-center justify-between py-2 border-b border-[var(--border-strong)]/60 last:border-0">
                            <span className="text-xs text-[var(--text-secondary)]">{row.label}</span><span className="text-sm font-semibold text-[var(--text-primary)]">{row.value}</span>
                          </div>
                        ))}
                        {seatReport.utilization_percentage !== undefined && (
                          <div className="h-2 bg-[var(--bg-card)] rounded-full overflow-hidden mt-2">
                            <div className="h-full bg-gradient-to-r from-brand-500 to-indigo-500 rounded-full" style={{ width: Math.min(seatReport.utilization_percentage, 100) + '%' }} />
                          </div>
                        )}
                      </div>
                    ) : <p className="text-sm text-[var(--text-muted)] py-4 text-center">No seat data.</p>}
                  </div>
                </div>
              </div>
            )}

          </>
        )}
      </div>

      {/* ALL MODALS */}
      {/* RESET OWNER PASSWORD MODAL */}
      {activeModal === 'resetPassword' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <Key className="w-5 h-5 text-amber-400" />
                  Reset Admin Password
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">Force password reset for the primary OrgAdmin of <strong>{selectedTenant.name}</strong>.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
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
                <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">New Password</label>
                <input
                  type="password"
                  placeholder="Minimum 8 characters"
                  required
                  minLength={8}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--border-strong)]/80">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  disabled={isModalLoading}
                  className="px-4 py-2.5 bg-[var(--bg-subtle)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl text-sm font-medium text-[var(--text-secondary)] transition-all cursor-pointer"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-2xl glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <FolderKanban className="w-5 h-5 text-brand-400" />
                  {activeModal === 'createPlan' ? 'Create Plan Template' : 'Configure Plan Limits'}
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">Define specifications, pricing bounds, setup costs, and storage limits.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
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
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Plan Code Name (Slug)</label>
                  <input
                    type="text"
                    placeholder="starter"
                    disabled={activeModal === 'editPlan'}
                    {...regPlan('name', { required: 'Slug name is required', pattern: { value: /^[a-z0-9-]+$/i, message: 'Alphanumeric & hyphens only' } })}
                    className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none disabled:opacity-50"
                  />
                  {planErrors.name && <p className="text-xs text-red-400 mt-1">{planErrors.name.message}</p>}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Display Name</label>
                  <input
                    type="text"
                    placeholder="Starter Plan"
                    {...regPlan('display_name', { required: 'Display name is required' })}
                    className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                  {planErrors.display_name && <p className="text-xs text-red-400 mt-1">{planErrors.display_name.message}</p>}
                </div>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Description</label>
                <textarea
                  placeholder="Describe target market or features highlight"
                  rows={2}
                  {...regPlan('description')}
                  className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                />
              </div>

              <div className="grid grid-cols-4 gap-4">
                <div>
                  <label className="block text-[10px] font-bold text-[var(--text-secondary)] uppercase mb-2">Price Per Licensed Seat</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('monthly_price', { required: true, min: 0 })}
                    className="w-full px-3 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-[var(--text-secondary)] uppercase mb-2">Quarterly ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('quarterly_price', { required: true, min: 0 })}
                    className="w-full px-3 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-[var(--text-secondary)] uppercase mb-2">Annual ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('annual_price', { required: true, min: 0 })}
                    className="w-full px-3 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] font-bold text-[var(--text-secondary)] uppercase mb-2">Currency</label>
                  <input
                    type="text"
                    {...regPlan('currency', { required: true })}
                    className="w-full px-3 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
              </div>

              <div className="border-t border-[var(--border-strong)]/80 pt-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 mb-3">Enterprise Seat Licensing Config</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Default Licensed Seat Count</label>
                    <input
                      type="number"
                      {...regPlan('max_users', { required: true, min: 1 })}
                      className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                    />
                  </div>
                  <div className="flex items-center pt-6">
                    <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] font-semibold cursor-pointer">
                      <input
                        type="checkbox"
                        {...regPlan('allow_additional_seats')}
                        className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                      />
                      Allow Additional Seats
                    </label>
                  </div>
                </div>
              </div>

              <div className="grid grid-cols-3 gap-4 border-t border-[var(--border-strong)]/80 pt-4">
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Storage Limit (GB)</label>
                  <input
                    type="number"
                    {...regPlan('storage_limit_gb', { required: true, min: 1 })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Retention (Days)</label>
                  <input
                    type="number"
                    {...regPlan('recording_retention_days', { required: true, min: 1 })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Display Order</label>
                  <input
                    type="number"
                    {...regPlan('display_order', { required: true })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-4 gap-3 border-t border-[var(--border-strong)]/80 pt-4">
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Setup Charge ($)</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('setup_charges', { required: true, min: 0 })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Minimum Initial Licensed Seats</label>
                  <input
                    type="number"
                    {...regPlan('minimum_users', {
                      required: 'Minimum licensed seats is required',
                      min: { value: 10, message: 'Minimum 10 licensed seats' }
                    })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                  {planErrors.minimum_users && <p className="text-[10px] text-red-400 mt-1">{planErrors.minimum_users.message}</p>}
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Maximum Supported Licensed Seats</label>
                  <input
                    type="number"
                    {...regPlan('maximum_users', { required: true, min: 1 })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Min Contract (m)</label>
                  <input
                    type="number"
                    {...regPlan('minimum_contract_months', { 
                      required: 'Min contract is required', 
                      min: { value: 3, message: 'Minimum 3 months' } 
                    })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                  {planErrors.minimum_contract_months && <p className="text-[10px] text-red-400 mt-1">{planErrors.minimum_contract_months.message}</p>}
                </div>
              </div>

              <div className="grid grid-cols-4 gap-3 border-t border-[var(--border-strong)]/80 pt-4">
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Trial Days (0-365)</label>
                  <input
                    type="number"
                    {...regPlan('trial_days', { required: true, min: 0, max: 365 })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                  {planErrors.trial_days && <p className="text-[10px] text-red-400 mt-1">{planErrors.trial_days.message}</p>}
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Additional Seat Price</label>
                  <input
                    type="number"
                    step="0.01"
                    {...regPlan('extra_user_price', { required: true, min: 0 })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                  {planErrors.extra_user_price && <p className="text-[10px] text-red-400 mt-1">{planErrors.extra_user_price.message}</p>}
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Discount % (0-100)</label>
                  <input
                    type="number"
                    step="0.1"
                    {...regPlan('discount_percentage', { required: true, min: 0, max: 100 })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                  {planErrors.discount_percentage && <p className="text-[10px] text-red-400 mt-1">{planErrors.discount_percentage.message}</p>}
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">GST Tax % (0-100)</label>
                  <input
                    type="number"
                    step="0.1"
                    {...regPlan('gst_percentage', { required: true, min: 0, max: 100 })}
                    className="w-full px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                  {planErrors.gst_percentage && <p className="text-[10px] text-red-400 mt-1">{planErrors.gst_percentage.message}</p>}
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 border-t border-[var(--border-strong)]/80 pt-4">
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Plan Color Hex (e.g. #3b82f6)</label>
                  <div className="flex gap-2">
                    <input
                      type="color"
                      {...regPlan('plan_color')}
                      className="w-10 h-10 p-0.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl cursor-pointer"
                    />
                    <input
                      type="text"
                      placeholder="#3b82f6"
                      {...regPlan('plan_color')}
                      className="flex-1 px-3 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-[10px] text-[var(--text-secondary)] mb-1.5">Plan Badge (e.g. Popular, Best Value)</label>
                  <input
                    type="text"
                    placeholder="Enter plan badge"
                    {...regPlan('plan_badge')}
                    className="w-full px-3 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                  />
                </div>
              </div>

              <div className="grid grid-cols-3 gap-3 border-t border-[var(--border-strong)]/80 pt-4">
                <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('popular_plan')}
                    className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  Popular Plan Badge
                </label>
                <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('recommended_plan')}
                    className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  Recommended Plan
                </label>
                <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('plan_active')}
                    className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  Plan Active / Visible
                </label>
              </div>

              <div className="grid grid-cols-4 gap-3 border-t border-[var(--border-strong)]/80 pt-4 col-span-2">
                <label className="flex items-center gap-1.5 text-[10px] text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('allow_upgrade')}
                    className="w-3.5 h-3.5 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  Allow Upgrade
                </label>
                <label className="flex items-center gap-1.5 text-[10px] text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('allow_downgrade')}
                    className="w-3.5 h-3.5 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  Allow Downgrade
                </label>
                <label className="flex items-center gap-1.5 text-[10px] text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('allow_trial')}
                    className="w-3.5 h-3.5 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  Allow Trial
                </label>
                <label className="flex items-center gap-1.5 text-[10px] text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('auto_renew')}
                    className="w-3.5 h-3.5 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  Auto Renew
                </label>
              </div>

              <div className="flex gap-6 border-t border-[var(--border-strong)]/80 pt-4">
                <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('priority_support')}
                    className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  Priority Support SLA Enabled
                </label>
                <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] font-semibold cursor-pointer">
                  <input
                    type="checkbox"
                    {...regPlan('api_access')}
                    className="w-4 h-4 rounded border-[var(--border-color)] text-brand-500 bg-[var(--bg-subtle)] focus:ring-0 cursor-pointer"
                  />
                  API Credentials Access Enabled
                </label>
              </div>

              {/* Commercial Summary (Part 7) */}
              <CommercialSummaryPanel regPlan={regPlan} />

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--border-strong)]/80">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  disabled={isModalLoading}
                  className="px-4 py-2.5 bg-[var(--bg-subtle)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl text-sm font-medium text-[var(--text-secondary)] transition-all cursor-pointer"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-lg glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <Building className="w-5 h-5 text-brand-400" />
                  Spin Up Tenant Instance
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">Creates database entries for a new tenant and assigns its primary admin account.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
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
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Company Name</label>
                  <input
                    type="text"
                    placeholder="Acme Corp"
                    {...regTenant('company_name', { required: 'Company name is required', maxLength: 255 })}
                    className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                  />
                  {tenantErrors.company_name && <p className="text-xs text-red-400 mt-1">{tenantErrors.company_name.message}</p>}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Subdomain Slug</label>
                  <input
                    type="text"
                    placeholder="acme"
                    {...regTenant('slug', { 
                      required: 'Subdomain slug is required', 
                      pattern: { value: /^[a-z0-9-]+$/i, message: 'Only alphanumeric characters and hyphens allowed' } 
                    })}
                    className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                  />
                  {tenantErrors.slug && <p className="text-xs text-red-400 mt-1">{tenantErrors.slug.message}</p>}
                </div>
              </div>

              {/* Plan + Billing Cycle */}
              <div className="grid grid-cols-2 gap-4 border-t border-[var(--border-color)] pt-4 mt-4">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Plan</label>
                  <select
                    {...regTenant('plan_name')}
                    defaultValue="starter"
                    className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                  >
                    <option value="starter">Starter — ₹3,999/user/mo</option>
                    <option value="growth">Growth — ₹4,999/user/mo</option>
                    <option value="enterprise">Enterprise — ₹5,999/user/mo</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Billing Cycle</label>
                  <select
                    {...regTenant('billing_cycle')}
                    defaultValue="monthly"
                    className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                  >
                    <option value="monthly">Monthly</option>
                    <option value="quarterly">Quarterly (advance)</option>
                    <option value="annual">Annual (advance)</option>
                  </select>
                </div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Licensed Seats</label>
                  <input
                    type="number"
                    defaultValue={10}
                    {...regTenant('licensed_seats', {
                      required: 'Seats count is required',
                      min: { value: 10, message: 'Minimum purchase is 10 Licensed Seats' }
                    })}
                    className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                  />
                  {tenantErrors.licensed_seats && <p className="text-xs text-red-400 mt-1">{tenantErrors.licensed_seats.message}</p>}
                </div>
                <div>
                  <label className="block text-xs font-semibold text-[var(--text-muted)] uppercase tracking-wider mb-2">Contract Duration (Months)</label>
                  <input
                    type="number"
                    defaultValue={3}
                    {...regTenant('contract_months', {
                      required: 'Contract duration is required',
                      min: { value: 3, message: 'Minimum contract is 3 months' }
                    })}
                    className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                  />
                  {tenantErrors.contract_months && <p className="text-xs text-red-400 mt-1">{tenantErrors.contract_months.message}</p>}
                </div>
              </div>

              <div className="border-t border-[var(--border-strong)]/80 my-4 pt-4">
                <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400 mb-3">Primary Administrator Credentials</h4>
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">First Name</label>
                      <input
                        type="text"
                        placeholder="John"
                        {...regTenant('first_name')}
                        className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Last Name</label>
                      <input
                        type="text"
                        placeholder="Doe"
                        {...regTenant('last_name')}
                        className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                      />
                    </div>
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Admin Email</label>
                    <input
                      type="email"
                      placeholder="admin@acme.com"
                      {...regTenant('admin_email', { 
                        required: 'Admin email is required',
                        pattern: { value: /^[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}$/i, message: 'Invalid email address' }
                      })}
                      className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                    />
                    {tenantErrors.admin_email && <p className="text-xs text-red-400 mt-1">{tenantErrors.admin_email.message}</p>}
                  </div>

                  <div>
                    <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Admin Password</label>
                    <input
                      type="password"
                      placeholder="Min 8 characters"
                      {...regTenant('admin_password', { 
                        required: 'Password is required',
                        minLength: { value: 8, message: 'Password must be at least 8 characters' }
                      })}
                      className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                    />
                    {tenantErrors.admin_password && <p className="text-xs text-red-400 mt-1">{tenantErrors.admin_password.message}</p>}
                  </div>
                </div>
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--border-strong)]/80">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  disabled={isModalLoading}
                  className="px-4 py-2.5 bg-[var(--bg-subtle)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl text-sm font-medium text-[var(--text-secondary)] transition-all cursor-pointer"
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
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl relative overflow-hidden">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <Edit className="w-5 h-5 text-brand-400" />
                  Subscription Settings
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">Configure parameters for <strong>{selectedTenant.name}</strong>.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
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
                <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Subscription Plan</label>
                <select
                  {...regSub('subscription_plan', { required: 'Plan is required' })}
                  className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                >
                  <option value="Starter">Starter</option>
                  <option value="Growth">Growth</option>
                  <option value="Enterprise">Enterprise</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Subscription Status</label>
                <select
                  {...regSub('subscription_status', { required: 'Status is required' })}
                  className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                >
                  <option value="Active">Active</option>
                  <option value="Suspended">Suspended</option>
                  <option value="Trial">Trial</option>
                </select>
              </div>

              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Licensed Seat Limit</label>
                <input
                  type="number"
                  {...regSub('max_users', { required: 'Licensed seat limit is required', min: { value: 1, message: 'Must allow at least 1 licensed seat' } })}
                  className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                />
                {subErrors.max_users && <p className="text-xs text-red-400 mt-1">{subErrors.max_users.message}</p>}
              </div>

              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2 flex items-center gap-1">
                  <Calendar className="w-3.5 h-3.5 text-[var(--text-muted)]" />
                  Subscription Expiration Date (Optional)
                </label>
                <input
                  type="date"
                  {...regSub('subscription_expires_at')}
                  className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                />
              </div>

              <div className="flex items-center justify-end gap-3 pt-4 border-t border-[var(--border-strong)]/80">
                <button
                  type="button"
                  onClick={() => setActiveModal(null)}
                  disabled={isModalLoading}
                  className="px-4 py-2.5 bg-[var(--bg-subtle)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl text-sm font-medium text-[var(--text-secondary)] transition-all cursor-pointer"
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
        <div className="fixed inset-0 z-50 flex items-center justify-end bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-md h-screen bg-[var(--bg-app)] border-l border-[var(--border-color)] flex flex-col justify-between shadow-2xl animate-slide-in">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <Users className="w-5 h-5 text-brand-400" />
                  Users List
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">Active personnel registered inside <strong>{selectedTenant.name}</strong>.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
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
                <div className="h-full flex flex-col items-center justify-center text-[var(--text-secondary)] py-20">
                  <Loader2 className="w-8 h-8 text-brand-500 animate-spin mb-3" />
                  <p className="text-xs">Querying database users...</p>
                </div>
              ) : tenantUsers.length === 0 ? (
                <div className="text-center py-20 text-[var(--text-muted)]">
                  <Users className="w-8 h-8 mx-auto mb-2 text-[var(--text-muted)]" />
                  <p className="text-sm font-semibold">No Registered Users</p>
                  <p className="text-xs text-[var(--text-muted)] mt-1">This tenant has not created any staff database profiles yet.</p>
                </div>
              ) : (
                <div className="space-y-3">
                  {tenantUsers.map((user) => {
                    const initials = `${user.first_name?.[0] || ''}${user.last_name?.[0] || ''}`.toUpperCase() || 'U';
                    return (
                      <div key={user.id} className="p-3 bg-[var(--bg-subtle)]/30 border border-[var(--border-color)] rounded-xl flex items-center justify-between hover:border-[var(--border-strong)]/80 transition-colors">
                        <div className="flex items-center gap-3">
                          <div className="w-9 h-9 rounded-lg bg-gradient-to-tr from-brand-500/20 to-indigo-500/20 border border-brand-500/20 flex items-center justify-center font-bold text-xs text-brand-300">
                            {initials}
                          </div>
                          <div>
                            <p className="text-sm font-semibold text-[var(--text-primary)]">
                              {user.first_name} {user.last_name}
                            </p>
                            <p className="text-xs text-[var(--text-secondary)]">{user.email}</p>
                          </div>
                        </div>
                        <div className="text-right">
                          <span className={`inline-block text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider ${
                            user.role === 'OrgAdmin'
                              ? 'bg-red-500/10 text-red-400 border-red-500/20'
                              : user.role === 'Manager'
                              ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                              : 'bg-[var(--bg-card)] text-[var(--text-secondary)] border-[var(--border-strong)]'
                          }`}>
                            {user.role}
                          </span>
                          <p className={`text-[10px] mt-1 ${user.is_active ? 'text-emerald-400' : 'text-[var(--text-muted)]'}`}>
                            {user.is_active ? 'Active' : 'Inactive'}
                          </p>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>

            <div className="p-6 border-t border-[var(--border-strong)]/80 bg-[var(--bg-app)]">
              <button
                onClick={() => setActiveModal(null)}
                className="w-full px-4 py-2.5 bg-[var(--bg-subtle)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-strong)] text-[var(--text-secondary)] text-sm font-semibold rounded-xl transition-all cursor-pointer"
              >
                Close Drawer
              </button>
            </div>
          </div>
        </div>
      )}

      {/* VIEW INVOICES MODAL */}
      {activeModal === 'invoices' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-3xl glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl relative overflow-hidden flex flex-col max-h-[90vh]">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between shrink-0">
              <div>
                <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2">
                  <FileText className="w-5 h-5 text-indigo-400" />
                  Tenant Invoices & Billing
                </h3>
                <p className="text-xs text-[var(--text-secondary)]">Generate or check payment invoices for <strong>{selectedTenant.name}</strong>.</p>
              </div>
              <button
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
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
                <div className="glass-panel p-5 border border-[var(--border-color)]/70 rounded-xl space-y-4">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-brand-400">Generate Manual Invoice</h4>
                  
                  <form onSubmit={handleInvSubmit(onCreateInvoice)} className="space-y-4">
                    <div>
                      <label className="block text-[10px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Billing Amount ($)</label>
                      <div className="relative">
                        <DollarSign className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-[var(--text-muted)]" />
                        <input
                          type="number"
                          placeholder="299.00"
                          step="0.01"
                          {...regInv('amount', { required: 'Amount is required', min: { value: 0.01, message: 'Must be positive' } })}
                          className="w-full pl-9 pr-4 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-brand-500/50"
                        />
                      </div>
                      {invErrors.amount && <p className="text-xs text-red-400 mt-1">{invErrors.amount.message}</p>}
                    </div>

                    <div>
                      <label className="block text-[10px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Due Date</label>
                      <input
                        type="date"
                        {...regInv('due_date', { required: 'Due date is required' })}
                        className="w-full px-3.5 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
                      />
                      {invErrors.due_date && <p className="text-xs text-red-400 mt-1">{invErrors.due_date.message}</p>}
                    </div>

                    <div>
                      <label className="block text-[10px] font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Status</label>
                      <select
                        {...regInv('status', { required: 'Status is required' })}
                        className="w-full px-3.5 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none"
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
                    <div className="text-center py-10 text-[var(--text-secondary)]">
                      <Loader2 className="w-6 h-6 animate-spin mx-auto mb-2 text-brand-500" />
                      <p className="text-xs">Loading invoices history...</p>
                    </div>
                  ) : invoices.length === 0 ? (
                    <div className="p-8 border border-dashed border-[var(--border-color)] rounded-xl text-center text-[var(--text-muted)]">
                      <FileText className="w-6 h-6 mx-auto mb-2 text-[var(--text-muted)]" />
                      <p className="text-xs font-semibold">No invoices generated</p>
                      <p className="text-[10px] text-[var(--text-muted)] mt-0.5">Generate a billing invoice on the left form to begin history.</p>
                    </div>
                  ) : (
                    <div className="space-y-2 max-h-[360px] overflow-y-auto pr-1">
                      {invoices.map((invoice) => (
                        <div key={invoice.id} className="p-3 bg-[var(--bg-subtle)]/40 border border-[var(--border-strong)]/80 rounded-xl flex items-center justify-between hover:border-[var(--border-color)] transition-colors">
                          <div>
                            <div className="flex items-center gap-2">
                              <span className="text-xs font-bold text-[var(--text-primary)]">{invoice.invoice_number}</span>
                              <span className="text-xs text-brand-300 font-semibold">${invoice.amount.toFixed(2)}</span>
                            </div>
                            <p className="text-[10px] text-[var(--text-muted)] mt-1">
                              Due: {new Date(invoice.due_date).toLocaleDateString()} | Created: {new Date(invoice.created_at).toLocaleDateString()}
                            </p>
                          </div>

                          <button 
                            onClick={() => onToggleInvoiceStatus(invoice.id, invoice.status)}
                            disabled={isModalLoading}
                            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-[var(--border-color)] hover:border-[var(--border-strong)] bg-[var(--bg-app)]/20 text-xs text-[var(--text-secondary)] transition-colors cursor-pointer disabled:cursor-not-allowed"
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

            <div className="p-6 border-t border-[var(--border-strong)]/80 bg-[var(--bg-app)] shrink-0">
              <button
                onClick={() => setActiveModal(null)}
                className="w-full px-4 py-2.5 bg-[var(--bg-subtle)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] hover:border-[var(--border-strong)] text-[var(--text-secondary)] text-sm font-semibold rounded-xl transition-all cursor-pointer"
              >
                Close Panel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* DELETE TENANT CONFIRMATION MODAL */}
      {activeModal === 'deleteTenantConfirm' && selectedTenant && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel border border-red-500/30 rounded-2xl shadow-2xl relative overflow-hidden animate-in fade-in zoom-in-95 duration-200">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <div className="flex items-center gap-2.5">
                <div className="p-2 bg-red-500/10 rounded-lg text-red-400">
                  <ShieldAlert className="w-5 h-5 animate-pulse" />
                </div>
                <div>
                  <h3 className="text-lg font-semibold text-[var(--text-primary)]">
                    Delete Tenant Instance
                  </h3>
                  <p className="text-xs text-[var(--text-secondary)]">This action is permanent and irreversible.</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition-colors cursor-pointer"
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
              <p className="text-sm text-[var(--text-secondary)]">
                Please type the tenant slug <code className="px-1.5 py-0.5 bg-[var(--bg-subtle)] rounded border border-[var(--border-color)] font-mono text-xs text-brand-400">{selectedTenant.slug}</code> to confirm deletion:
              </p>
              <input
                type="text"
                placeholder={selectedTenant.slug}
                value={deleteConfirmSlug}
                onChange={(e) => setDeleteConfirmSlug(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none focus:border-red-500/40"
              />
            </div>

            <div className="flex items-center justify-end gap-3 p-6 border-t border-[var(--border-strong)]/80 bg-[var(--bg-app)]/20">
              <button
                type="button"
                onClick={() => setActiveModal(null)}
                className="px-4 py-2.5 bg-[var(--bg-subtle)] hover:bg-[var(--bg-card)] border border-[var(--border-color)] rounded-xl text-sm font-medium text-[var(--text-secondary)] transition-all cursor-pointer"
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

      {activeCurrencyModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-md glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2"><Globe className="w-5 h-5 text-brand-400" />{activeCurrencyModal === 'create' ? 'Add Currency' : 'Edit ' + (selectedCurrency?.code ?? '')}</h3>
              <button onClick={() => setActiveCurrencyModal(null)} className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-6 space-y-4">
              {activeCurrencyModal === 'create' && (
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Currency Code</label>
                <input value={currencyForm.code || ''} onChange={e => setCurrencyForm((p: any) => ({...p, code: e.target.value.toUpperCase()}))} placeholder="USD" maxLength={10} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              )}
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Name</label><input value={currencyForm.name || ''} onChange={e => setCurrencyForm((p: any) => ({...p, name: e.target.value}))} placeholder="US Dollar" className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Symbol</label><input value={currencyForm.symbol || ''} onChange={e => setCurrencyForm((p: any) => ({...p, symbol: e.target.value}))} placeholder="$" className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              </div>
              <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Exchange Rate (vs Base INR)</label>
              <input type="number" step="0.0001" value={currencyForm.exchange_rate || ''} onChange={e => setCurrencyForm((p: any) => ({...p, exchange_rate: e.target.value}))} placeholder="0.0120" className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"><input type="checkbox" checked={currencyForm.is_active ?? true} onChange={e => setCurrencyForm((p: any) => ({...p, is_active: e.target.checked}))} className="w-4 h-4 rounded bg-[var(--bg-subtle)] border-[var(--border-color)]" /> Active</label>
              <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border-strong)]/80">
                <button onClick={() => setActiveCurrencyModal(null)} className="px-4 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-secondary)] cursor-pointer">Cancel</button>
                <button onClick={handleSaveCurrency} className="px-5 py-2.5 bg-brand-500 hover:bg-brand-600 text-white rounded-xl text-sm font-semibold cursor-pointer">Save</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeTaxModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-lg glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2"><Receipt className="w-5 h-5 text-brand-400" />{activeTaxModal === 'create' ? 'Add Tax Config' : 'Edit Tax Config'}</h3>
              <button onClick={() => setActiveTaxModal(null)} className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-6 space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Country Code</label><input value={taxForm.country_code || ''} onChange={e => setTaxForm((p: any) => ({...p, country_code: e.target.value.toUpperCase()}))} placeholder="IN" maxLength={10} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Country Name</label><input value={taxForm.country_name || ''} onChange={e => setTaxForm((p: any) => ({...p, country_name: e.target.value}))} placeholder="India" className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              </div>
              <div className="grid grid-cols-3 gap-4">
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Type</label>
                <select value={taxForm.tax_type || 'GST'} onChange={e => setTaxForm((p: any) => ({...p, tax_type: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none">
                  {['GST','VAT','SALES_TAX','NONE'].map(t => <option key={t} value={t}>{t}</option>)}
                </select></div>
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Rate %</label><input type="number" step="0.01" value={taxForm.tax_rate || ''} onChange={e => setTaxForm((p: any) => ({...p, tax_rate: e.target.value}))} placeholder="18" className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Label</label><input value={taxForm.tax_label || ''} onChange={e => setTaxForm((p: any) => ({...p, tax_label: e.target.value}))} placeholder="GST" className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              </div>
              <div className="flex items-center gap-6">
                <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"><input type="checkbox" checked={taxForm.tax_inclusive ?? false} onChange={e => setTaxForm((p: any) => ({...p, tax_inclusive: e.target.checked}))} className="w-4 h-4 rounded bg-[var(--bg-subtle)] border-[var(--border-color)]" /> Inclusive</label>
                <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"><input type="checkbox" checked={taxForm.is_default ?? false} onChange={e => setTaxForm((p: any) => ({...p, is_default: e.target.checked}))} className="w-4 h-4 rounded bg-[var(--bg-subtle)] border-[var(--border-color)]" /> Default</label>
                <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"><input type="checkbox" checked={taxForm.is_active ?? true} onChange={e => setTaxForm((p: any) => ({...p, is_active: e.target.checked}))} className="w-4 h-4 rounded bg-[var(--bg-subtle)] border-[var(--border-color)]" /> Active</label>
              </div>
              <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border-strong)]/80">
                <button onClick={() => setActiveTaxModal(null)} className="px-4 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-secondary)] cursor-pointer">Cancel</button>
                <button onClick={handleSaveTax} className="px-5 py-2.5 bg-brand-500 hover:bg-brand-600 text-white rounded-xl text-sm font-semibold cursor-pointer">Save</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeCouponModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-lg glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2"><Tag className="w-5 h-5 text-brand-400" />{activeCouponModal === 'create' ? 'Create Coupon' : 'Edit Coupon'}</h3>
              <button onClick={() => setActiveCouponModal(null)} className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Code</label><input value={couponForm.code || ''} onChange={e => setCouponForm((p: any) => ({...p, code: e.target.value.toUpperCase()}))} placeholder="SAVE20" disabled={activeCouponModal === 'edit'} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none disabled:opacity-50" /></div>
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Type</label>
                <select value={couponForm.discount_type || 'percentage'} onChange={e => setCouponForm((p: any) => ({...p, discount_type: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none">
                  <option value="percentage">Percentage %</option><option value="flat">Flat Amount</option>
                </select></div>
              </div>
              <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Description</label><input value={couponForm.description || ''} onChange={e => setCouponForm((p: any) => ({...p, description: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Value</label><input type="number" step="0.01" value={couponForm.discount_value || ''} onChange={e => setCouponForm((p: any) => ({...p, discount_value: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Max Uses</label><input type="number" value={couponForm.max_uses || ''} onChange={e => setCouponForm((p: any) => ({...p, max_uses: e.target.value}))} placeholder="blank = unlimited" className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              </div>
              <div className="grid grid-cols-2 gap-4">
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Valid From</label><input type="date" value={couponForm.valid_from || ''} onChange={e => setCouponForm((p: any) => ({...p, valid_from: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Valid Until</label><input type="date" value={couponForm.valid_until || ''} onChange={e => setCouponForm((p: any) => ({...p, valid_until: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              </div>
              <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"><input type="checkbox" checked={couponForm.is_active ?? true} onChange={e => setCouponForm((p: any) => ({...p, is_active: e.target.checked}))} className="w-4 h-4 rounded bg-[var(--bg-subtle)] border-[var(--border-color)]" /> Active</label>
              <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border-strong)]/80">
                <button onClick={() => setActiveCouponModal(null)} className="px-4 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-secondary)] cursor-pointer">Cancel</button>
                <button onClick={handleSaveCoupon} className="px-5 py-2.5 bg-brand-500 hover:bg-brand-600 text-white rounded-xl text-sm font-semibold cursor-pointer">Save Coupon</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {activeNotifModal === 'edit' && selectedNotif && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-[var(--bg-app)]/80 backdrop-blur-sm">
          <div className="w-full max-w-xl glass-panel border border-[var(--border-strong)]/90 rounded-2xl shadow-2xl">
            <div className="px-6 py-5 border-b border-[var(--border-strong)]/80 flex items-center justify-between">
              <div><h3 className="text-lg font-semibold text-[var(--text-primary)] flex items-center gap-2"><Bell className="w-5 h-5 text-brand-400" /> Edit Template</h3><p className="text-xs text-[var(--text-secondary)] mt-0.5 font-mono">{selectedNotif.template_key}</p></div>
              <button onClick={() => setActiveNotifModal(null)} className="p-1.5 hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-secondary)] cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="p-6 space-y-4 max-h-[70vh] overflow-y-auto">
              <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Template Name</label><input value={notifForm.template_name || ''} onChange={e => setNotifForm((p: any) => ({...p, template_name: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              {selectedNotif.channel === 'email' && (
                <div><label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Subject</label><input value={notifForm.subject || ''} onChange={e => setNotifForm((p: any) => ({...p, subject: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none" /></div>
              )}
              <div>
                <label className="block text-xs font-semibold text-[var(--text-secondary)] uppercase tracking-wider mb-2">Body</label>
                {selectedNotif.variables && selectedNotif.variables.length > 0 && <p className="text-[10px] text-[var(--text-muted)] mb-1.5">Variables: {selectedNotif.variables.map((v: string) => '{{' + v + '}}').join(', ')}</p>}
                <textarea rows={6} value={notifForm.body || ''} onChange={e => setNotifForm((p: any) => ({...p, body: e.target.value}))} className="w-full px-3.5 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-primary)] focus:outline-none font-mono" />
              </div>
              <label className="flex items-center gap-2 text-xs text-[var(--text-secondary)] cursor-pointer"><input type="checkbox" checked={notifForm.is_active ?? true} onChange={e => setNotifForm((p: any) => ({...p, is_active: e.target.checked}))} className="w-4 h-4 rounded bg-[var(--bg-subtle)] border-[var(--border-color)]" /> Active</label>
              <div className="flex justify-end gap-3 pt-4 border-t border-[var(--border-strong)]/80">
                <button onClick={() => setActiveNotifModal(null)} className="px-4 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-sm text-[var(--text-secondary)] cursor-pointer">Cancel</button>
                <button onClick={handleSaveNotif} className="px-5 py-2.5 bg-brand-500 hover:bg-brand-600 text-white rounded-xl text-sm font-semibold cursor-pointer">Save Template</button>
              </div>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
