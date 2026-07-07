import { api } from './api';

// ── Phase 1: Dashboard ────────────────────────────────────────────────────────
export interface DashboardOrgMetrics { total: number; active: number; trial: number; expired: number; suspended: number; new_today: number; }
export interface DashboardRevenueMetrics { mrr: number; arr: number; total_collected: number; pending: number; failed_count: number; overdue_count: number; currency: string; period_collected: number; period_onboarded: number; period: string; }
export interface DashboardLicensingMetrics { total_licensed_seats: number; active_seats: number; available_seats: number; utilization_percent: number; }
export interface DashboardInfraMetrics { total_storage_gb: number; call_recording_gb: number; db_status: string; redis_status: string; }
export interface DashboardActivityMetrics { new_orgs_today: number; renewals_due_7days: number; trials_expiring_7days: number; new_invoices_today: number; payments_today: number; }
export interface SuperAdminDashboard { orgs: DashboardOrgMetrics; revenue: DashboardRevenueMetrics; licensing: DashboardLicensingMetrics; infra: DashboardInfraMetrics; activity: DashboardActivityMetrics; generated_at: string; }

// ── Phase 6: Currency ─────────────────────────────────────────────────────────
export interface CurrencyResponse { code: string; name: string; symbol: string; exchange_rate: number; is_base: boolean; is_active: boolean; source: string; last_updated: string | null; }
export interface CurrencyCreate { code: string; name: string; symbol: string; exchange_rate: number; is_base?: boolean; }
export interface CurrencyUpdate { name?: string; symbol?: string; exchange_rate?: number; is_active?: boolean; is_base?: boolean; }

// ── Phase 7: Tax Engine ───────────────────────────────────────────────────────
export interface TaxConfigResponse { id: string; country_code: string; country_name: string; tax_type: string; tax_rate: number; tax_label: string; tax_inclusive: boolean; is_active: boolean; is_default: boolean; state_code: string | null; created_at: string; }
export interface TaxConfigCreate { country_code: string; country_name: string; tax_type: string; tax_rate: number; tax_label: string; tax_inclusive?: boolean; is_active?: boolean; is_default?: boolean; }
export interface TaxConfigUpdate { tax_rate?: number; tax_label?: string; tax_type?: string; tax_inclusive?: boolean; is_active?: boolean; is_default?: boolean; }

// ── Phase 9: Payment Gateways ─────────────────────────────────────────────────
export interface PaymentGatewayResponse { id: string; name: string; display_name: string; is_enabled: boolean; is_sandbox: boolean; api_key_set: boolean; webhook_secret_set: boolean; sort_order: number; description: string | null; extra_config: Record<string, any> | null; }
export interface PaymentGatewayCreate { name: string; display_name: string; is_enabled?: boolean; is_sandbox?: boolean; api_key?: string; api_secret?: string; webhook_secret?: string; description?: string; }
export interface PaymentGatewayUpdate { display_name?: string; is_enabled?: boolean; is_sandbox?: boolean; api_key?: string; api_secret?: string; webhook_secret?: string; description?: string; }

// ── Phase 12: Notification Templates ─────────────────────────────────────────
export interface NotificationTemplateResponse { id: string; template_key: string; template_name: string; channel: string; subject: string | null; body: string; variables: string[] | null; is_active: boolean; category: string; description: string | null; created_at: string; updated_at: string; }
export interface NotificationTemplateCreate { template_key: string; template_name: string; channel: string; subject?: string; body: string; variables?: string[]; category?: string; description?: string; }
export interface NotificationTemplateUpdate { template_name?: string; subject?: string; body?: string; variables?: string[]; is_active?: boolean; description?: string; }

// ── Phase 5: Coupons ──────────────────────────────────────────────────────────
export interface CouponResponse { id: string; code: string; description: string | null; discount_type: string; discount_value: number; max_uses: number | null; uses_count: number; valid_from: string; valid_until: string | null; min_order_value: number; applicable_plans: string[] | null; is_active: boolean; notes: string | null; created_at: string; }
export interface CouponCreate { code: string; description?: string; discount_type: string; discount_value: number; max_uses?: number; valid_from: string; valid_until?: string; min_order_value?: number; applicable_plans?: string[]; is_active?: boolean; notes?: string; }
export interface CouponUpdate { description?: string; discount_value?: number; max_uses?: number; valid_until?: string; is_active?: boolean; notes?: string; }

// ── Phase 4: Feature Create ───────────────────────────────────────────────────
export interface FeatureCreate { code: string; display_name: string; description?: string; category: string; icon?: string; active?: boolean; }

// ── Phase 15: Reports ─────────────────────────────────────────────────────────
export interface RevenueReport { period_start: string; period_end: string; currency: string; mrr: number; arr: number; total_collected: number; pending: number; top_plans: Array<{ name: string; active_subscriptions: number }>; }
export interface TenantReport { total: number; active: number; trial: number; expired: number; suspended: number; by_plan: Array<{ plan: string; count: number }>; }
export interface SeatUtilizationReport { total_licensed: number; total_active: number; utilization_pct: number; by_organization: Array<{ name: string; licensed: number; active: number; utilization_pct: number }>; }
export interface InvoiceReport { period_start: string; period_end: string; total_invoices: number; paid_count: number; paid_amount: number; unpaid_count: number; unpaid_amount: number; }
export interface ChurnReport { period: string; churned_subscriptions: number; active_at_period_start: number; churn_rate_pct: number; healthy: boolean; benchmark: string; }

// ── Audit log ─────────────────────────────────────────────────────────────────
export interface AuditLogEntry { id: string; organization_id?: string; actor_user_id?: string; action: string; resource_type: string; resource_id?: string; metadata?: Record<string, any>; created_at: string; }
export interface AuditLogPage { total: number; limit: number; offset: number; data: AuditLogEntry[]; }

export interface TenantResponse {
  id: string;
  name: string;
  slug: string;
  is_active: boolean;
  subscription_plan: string;
  subscription_expires_at: string | null;
  subscription_status: string;
  max_users: number;
  user_count: number;
  invoice_count: number;
  call_recording_usage: number;
}

export interface TenantUserResponse {
  id: string;
  email: string;
  first_name: string | null;
  last_name: string | null;
  role: string;
  is_active: boolean;
}

export interface TenantInvoiceResponse {
  id: string;
  invoice_number: string;
  amount: number;
  status: string;
  due_date: string;
  created_at: string;
}

export interface SubscriptionUpdateRequest {
  subscription_plan: string;
  subscription_expires_at: string | null;
  subscription_status: string;
  max_users: number;
}

export interface InvoiceCreateRequest {
  amount: number;
  due_date: string;
  status?: string;
}

export interface CreateTenantRequest {
  company_name: string;
  slug: string;
  admin_email: string;
  admin_password: string;
  first_name?: string | null;
  last_name?: string | null;
  licensed_seats?: number;
  contract_months?: number;
  plan_name?: string;
  billing_cycle?: string;
  is_trial?: boolean;
}

export const superAdminApi = {
  getTenants: async () => {
    const response = await api.get<TenantResponse[]>('/super-admin/tenants');
    return response.data;
  },

  createTenant: async (payload: CreateTenantRequest) => {
    const response = await api.post<TenantResponse>('/super-admin/tenants', payload);
    return response.data;
  },

  getTenantUsers: async (orgId: string) => {
    const response = await api.get<TenantUserResponse[]>(`/super-admin/tenants/${orgId}/users`);
    return response.data;
  },

  updateSubscription: async (orgId: string, payload: SubscriptionUpdateRequest) => {
    const response = await api.put<TenantResponse>(`/super-admin/tenants/${orgId}/subscription`, payload);
    return response.data;
  },

  updateTenantUsage: async (orgId: string, call_recording_usage: number) => {
    const response = await api.put<TenantResponse>(`/super-admin/tenants/${orgId}/usage`, { call_recording_usage });
    return response.data;
  },

  getTenantInvoices: async (orgId: string) => {
    const response = await api.get<TenantInvoiceResponse[]>(`/super-admin/tenants/${orgId}/invoices`);
    return response.data;
  },

  createInvoice: async (orgId: string, payload: InvoiceCreateRequest) => {
    const response = await api.post<TenantInvoiceResponse>(`/super-admin/tenants/${orgId}/invoices`, payload);
    return response.data;
  },

  updateInvoiceStatus: async (invoiceId: string, statusVal: string) => {
    const response = await api.patch<TenantInvoiceResponse>(
      `/super-admin/invoices/${invoiceId}`,
      null,
      { params: { status_val: statusVal } }
    );
    return response.data;
  },

  deleteTenant: async (orgId: string) => {
    const response = await api.delete<{ detail: string }>(`/super-admin/tenants/${orgId}`);
    return response.data;
  },

  // Plans CRUD
  getPlans: async () => {
    const response = await api.get<PlanResponse[]>('/super-admin/plans');
    return response.data;
  },
  createPlan: async (payload: PlanCreatePayload) => {
    const response = await api.post<PlanResponse>('/super-admin/plans', payload);
    return response.data;
  },
  updatePlan: async (planId: string, payload: Partial<PlanCreatePayload>) => {
    const response = await api.patch<PlanResponse>(`/super-admin/plans/${planId}`, payload);
    return response.data;
  },
  deletePlan: async (planId: string) => {
    const response = await api.delete<{ detail: string }>(`/super-admin/plans/${planId}`);
    return response.data;
  },
  reorderPlans: async (planIds: string[]) => {
    const response = await api.post<{ detail: string }>('/super-admin/plans/reorder', planIds);
    return response.data;
  },

  // Features CRUD
  getFeatures: async () => {
    const response = await api.get<FeatureResponse[]>('/super-admin/features');
    return response.data;
  },
  updateFeature: async (featureId: string, payload: Partial<FeatureResponse>) => {
    const response = await api.patch<FeatureResponse>(`/super-admin/features/${featureId}`, payload);
    return response.data;
  },
  createFeature: async (payload: FeatureCreate) => {
    const response = await api.post<FeatureResponse>('/super-admin/features', payload);
    return response.data;
  },
  deleteFeature: async (featureId: string) => {
    const response = await api.delete<{ detail: string }>(`/super-admin/features/${featureId}`);
    return response.data;
  },

  // Phase 1: Dashboard
  getDashboard: async (period?: 'day' | 'week' | 'month') => {
    const response = await api.get<SuperAdminDashboard>('/super-admin/dashboard', {
      params: { period: period || 'month' }
    });
    return response.data;
  },

  // Phase 2: Enhanced Tenant Actions
  extendTrial: async (orgId: string, days: number) => {
    const response = await api.post(`/super-admin/tenants/${orgId}/extend-trial`, null, { params: { days } });
    return response.data;
  },
  activateTenant: async (orgId: string) => {
    const response = await api.post(`/super-admin/tenants/${orgId}/activate`);
    return response.data;
  },
  impersonateTenant: async (orgId: string) => {
    const response = await api.post<{ access_token: string; impersonating: { org_name: string; admin_email: string } }>(`/super-admin/tenants/${orgId}/impersonate`);
    return response.data;
  },
  getTenantAuditLogs: async (orgId: string, limit = 50, offset = 0) => {
    const response = await api.get(`/super-admin/tenants/${orgId}/audit-logs`, { params: { limit, offset } });
    return response.data;
  },

  // Phase 5: Coupons
  getCoupons: async () => { const r = await api.get<CouponResponse[]>('/super-admin/coupons'); return r.data; },
  createCoupon: async (p: CouponCreate) => { const r = await api.post<CouponResponse>('/super-admin/coupons', p); return r.data; },
  updateCoupon: async (id: string, p: CouponUpdate) => { const r = await api.patch<CouponResponse>(`/super-admin/coupons/${id}`, p); return r.data; },
  deleteCoupon: async (id: string) => { const r = await api.delete(`/super-admin/coupons/${id}`); return r.data; },

  // Phase 6: Currency
  getCurrencies: async () => { const r = await api.get<CurrencyResponse[]>('/super-admin/currencies'); return r.data; },
  createCurrency: async (p: CurrencyCreate) => { const r = await api.post<CurrencyResponse>('/super-admin/currencies', p); return r.data; },
  updateCurrency: async (code: string, p: CurrencyUpdate) => { const r = await api.patch<CurrencyResponse>(`/super-admin/currencies/${code}`, p); return r.data; },
  deleteCurrency: async (code: string) => { const r = await api.delete(`/super-admin/currencies/${code}`); return r.data; },

  // Phase 7: Tax Configs
  getTaxConfigs: async () => { const r = await api.get<TaxConfigResponse[]>('/super-admin/tax-configs'); return r.data; },
  createTaxConfig: async (p: TaxConfigCreate) => { const r = await api.post<TaxConfigResponse>('/super-admin/tax-configs', p); return r.data; },
  updateTaxConfig: async (id: string, p: TaxConfigUpdate) => { const r = await api.patch<TaxConfigResponse>(`/super-admin/tax-configs/${id}`, p); return r.data; },
  deleteTaxConfig: async (id: string) => { const r = await api.delete(`/super-admin/tax-configs/${id}`); return r.data; },

  // Phase 9: Payment Gateways
  getPaymentGateways: async () => { const r = await api.get<PaymentGatewayResponse[]>('/super-admin/payment-gateways'); return r.data; },
  createPaymentGateway: async (p: PaymentGatewayCreate) => { const r = await api.post<PaymentGatewayResponse>('/super-admin/payment-gateways', p); return r.data; },
  updatePaymentGateway: async (id: string, p: PaymentGatewayUpdate) => { const r = await api.patch<PaymentGatewayResponse>(`/super-admin/payment-gateways/${id}`, p); return r.data; },
  togglePaymentGateway: async (id: string) => { const r = await api.post<{ is_enabled: boolean }>(`/super-admin/payment-gateways/${id}/toggle`); return r.data; },

  // Phase 12: Notification Templates
  getNotificationTemplates: async () => { const r = await api.get<NotificationTemplateResponse[]>('/super-admin/notification-templates'); return r.data; },
  createNotificationTemplate: async (p: NotificationTemplateCreate) => { const r = await api.post<NotificationTemplateResponse>('/super-admin/notification-templates', p); return r.data; },
  updateNotificationTemplate: async (id: string, p: NotificationTemplateUpdate) => { const r = await api.patch<NotificationTemplateResponse>(`/super-admin/notification-templates/${id}`, p); return r.data; },
  deleteNotificationTemplate: async (id: string) => { const r = await api.delete(`/super-admin/notification-templates/${id}`); return r.data; },

  // Phase 13: Audit Center
  getAuditLogs: async (params: { org_id?: string; action?: string; resource_type?: string; start_date?: string; end_date?: string; limit?: number; offset?: number }) => {
    const r = await api.get<AuditLogPage>('/super-admin/audit-logs', { params });
    return r.data;
  },

  // Phase 15: Reports
  getRevenueReport: async (start_date?: string, end_date?: string, currency = 'INR') => {
    const r = await api.get<RevenueReport>('/super-admin/reports/revenue', { params: { start_date, end_date, currency } });
    return r.data;
  },
  getTenantReport: async () => { const r = await api.get<TenantReport>('/super-admin/reports/tenants'); return r.data; },
  getSeatUtilization: async () => { const r = await api.get<SeatUtilizationReport>('/super-admin/reports/seat-utilization'); return r.data; },
  getInvoiceReport: async (start_date?: string, end_date?: string) => {
    const r = await api.get<InvoiceReport>('/super-admin/reports/invoices', { params: { start_date, end_date } });
    return r.data;
  },
  getChurnReport: async () => {
    const r = await api.get<ChurnReport>('/super-admin/reports/churn');
    return r.data;
  },

  // Plan Feature Mappings
  getPlanFeatures: async () => {
    const response = await api.get<PlanFeatureResponse[]>('/super-admin/plan-features');
    return response.data;
  },
  togglePlanFeature: async (payload: { plan_id: string; feature_id: string; enabled: boolean }) => {
    const response = await api.post<PlanFeatureResponse>('/super-admin/plan-features/toggle', payload);
    return response.data;
  },
  clonePlanFeatures: async (payload: { from_plan_id: string; to_plan_id: string }) => {
    const response = await api.post<{ detail: string }>('/super-admin/plan-features/clone', payload);
    return response.data;
  },

  // System Settings
  getSystemSettings: async () => {
    const response = await api.get<SystemSettingResponse[]>('/super-admin/system-settings');
    return response.data;
  },
  upsertSystemSetting: async (payload: { key: string; value: any }) => {
    const response = await api.post<SystemSettingResponse>('/super-admin/system-settings', payload);
    return response.data;
  },

  // Manual Overrides
  suspendTenant: async (orgId: string) => {
    const response = await api.post<TenantResponse>(`/super-admin/tenants/${orgId}/suspend`);
    return response.data;
  },
  resetTenantOwnerPassword: async (orgId: string, newPassword: string) => {
    const response = await api.post<{ detail: string }>(`/super-admin/tenants/${orgId}/reset-password`, null, {
      params: { new_password: newPassword }
    });
    return response.data;
  },
  createManualInvoice: async (orgId: string, payload: InvoiceCreateRequest) => {
    const response = await api.post<TenantInvoiceResponse>(`/super-admin/tenants/${orgId}/invoices/manual`, payload);
    return response.data;
  },

  // Invoice Config CRUD
  getInvoiceConfig: async () => {
    const response = await api.get<InvoiceConfigResponse>('/super-admin/invoice-config');
    return response.data;
  },
  updateInvoiceConfig: async (payload: InvoiceConfigUpdate) => {
    const response = await api.put<InvoiceConfigResponse>('/super-admin/invoice-config', payload);
    return response.data;
  },
  uploadCompanyLogo: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<InvoiceConfigResponse>('/super-admin/invoice-config/upload-logo', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },
  uploadPaymentQr: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<InvoiceConfigResponse>('/super-admin/invoice-config/upload-qr', formData, {
      headers: { 'Content-Type': 'multipart/form-data' }
    });
    return response.data;
  },
  deleteCompanyLogo: async () => {
    const response = await api.delete<InvoiceConfigResponse>('/super-admin/invoice-config/logo');
    return response.data;
  },
  deletePaymentQr: async () => {
    const response = await api.delete<InvoiceConfigResponse>('/super-admin/invoice-config/qr');
    return response.data;
  },

  // Commercial Settings CRUD
  getCommercialSettings: async () => {
    const response = await api.get<CommercialSettingsResponse>('/super-admin/commercial-settings');
    return response.data;
  },
  updateCommercialSettings: async (payload: CommercialSettingsUpdate) => {
    const response = await api.put<CommercialSettingsResponse>('/super-admin/commercial-settings', payload);
    return response.data;
  },
};

export interface InvoiceConfigUpdate {
  company_name: string;
  tagline?: string;
  website?: string;
  support_email?: string;
  phone_number?: string;
  address?: string;
  gst_number?: string;
  pan?: string;
  business_registration_number?: string;
  invoice_prefix: string;
  starting_invoice_number: number;
  currency: string;
  currency_symbol: string;
  bank_name?: string;
  account_holder?: string;
  account_number?: string;
  ifsc?: string;
  branch?: string;
  upi_id?: string;
  payment_terms?: string;
  footer_text?: string;
  invoice_subject?: string;
  invoice_body?: string;
  reminder_subject?: string;
  reminder_body?: string;
  payment_success_subject?: string;
  payment_success_body?: string;
  payment_failed_subject?: string;
  payment_failed_body?: string;
  renewal_reminder_subject?: string;
  renewal_reminder_body?: string;
}

export interface InvoiceConfigResponse extends InvoiceConfigUpdate {
  company_logo_url?: string;
  qr_code_url?: string;
  updated_at: string;
}

export interface PlanCreatePayload {
  name: string;
  display_name: string;
  description?: string;
  monthly_price: number;
  quarterly_price: number;
  annual_price: number;
  currency: string;
  max_users: number;
  max_admins: number;
  max_managers: number;
  max_team_leads: number;
  max_employees: number;
  storage_limit_gb: number;
  recording_retention_days: number;
  priority_support: boolean;
  api_access: boolean;
  display_order: number;
  setup_charges: number;
  minimum_users: number;
  maximum_users: number;
  minimum_contract_months: number;
  trial_days: number;
  extra_user_price: number;
  discount_percentage: number;
  gst_percentage: number;
  plan_color?: string;
  plan_badge?: string;
  popular_plan: boolean;
  recommended_plan: boolean;
  allow_upgrade: boolean;
  allow_downgrade: boolean;
  allow_trial: boolean;
  allow_additional_seats: boolean;
  auto_renew: boolean;
  plan_active: boolean;
}

export interface PlanResponse extends PlanCreatePayload {
  id: string;
  is_active: boolean;
  created_at: string;
  updated_at: string;
}

export interface FeatureResponse {
  id: string;
  code: string;
  display_name: string;
  description: string | null;
  category: string;
  icon: string | null;
  active: boolean;
}

export interface PlanFeatureResponse {
  id: string;
  plan_id: string;
  feature_id: string;
  enabled: boolean;
  feature?: FeatureResponse;
}

export interface SystemSettingResponse {
  key: string;
  value: any;
}

export interface CommercialSettingsUpdate {
  default_currency: string;
  currency_symbol: string;
  default_timezone: string;
  default_gst: number;
  gst_inclusive: boolean;
  tax_label: string;
  default_trial_days: number;
  allow_trial: boolean;
  trial_reminder_days: number;
  default_min_contract: number;
  auto_renewal: boolean;
  notice_period_days: number;
  default_setup_charge: number;
  allow_setup_discount: boolean;
  free_setup_on_annual: boolean;
  default_extra_user_price: number;
  minimum_users: number;
  maximum_users?: number | null;
  default_discount_percentage: number;
  maximum_discount_percentage: number;
  allow_custom_discount: boolean;
  allow_promo_code: boolean;
  late_payment_charge: number;
  late_payment_type: string;
  grace_period_days: number;
  auto_suspend_days: number;
  auto_reactivate: boolean;
  reminder_schedule: string;
  invoice_reminder_days: string;
  subscription_reminder_days: string;
  payment_reminder_days: string;
  default_plan_id?: string | null;
  default_recording_retention_days: number;
  default_storage_gb: number;
  invoice_reminder_template?: string | null;
  renewal_reminder_template?: string | null;
  trial_expiry_template?: string | null;
  payment_success_template?: string | null;
  payment_failed_template?: string | null;
  welcome_template?: string | null;
  reason?: string;
}

export interface CommercialSettingsResponse extends CommercialSettingsUpdate {
  id: string;
  created_at: string;
  updated_at: string;
}

