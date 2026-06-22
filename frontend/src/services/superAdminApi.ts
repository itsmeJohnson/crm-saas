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
};
