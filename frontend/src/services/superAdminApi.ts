import { api } from './api';

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

