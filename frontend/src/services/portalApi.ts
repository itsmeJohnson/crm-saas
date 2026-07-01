import { api } from './api';

export interface DashboardStatsResponse {
  plan_name: string;
  subscription_status: string;
  days_remaining: number;
  users: {
    current: number;
    limit: number;
    percent: number;
  };
  storage: {
    used_gb: number;
    limit_gb: number;
    percent: number;
  };
  recording_count: number;
  pending_invoice_amount: number;
  last_payment_amount: number;
  upcoming_renewal_date: string | null;
  recent_activities: Array<{
    id: string;
    action: string;
    resource_type: string;
    created_at: string;
    metadata: any;
  }>;
}

export interface PortalInvoiceResponse {
  id: string;
  invoice_number: string;
  amount: number;
  status: string;
  due_date: string;
  plan_name: string | null;
  currency: string;
  issue_date: string;
  payment_status: string;
  total_amount: number;
  gst_amount: number;
  discount_amount: number;
  setup_charges: number;
  pdf_file_path: string | null;
}

export interface PortalPaymentResponse {
  id: string;
  amount: number;
  invoice_number: string;
  gateway: string;
  status: string;
  transaction_id: string | null;
  paid_date: string | null;
  remarks: string | null;
}

export interface SupportTicketComment {
  author: string;
  content: string;
  timestamp: string;
}

export interface SupportTicketHistory {
  status: string;
  by: string;
  timestamp: string;
}

export interface SupportTicketResponse {
  id: string;
  organization_id: string;
  created_by_id: string;
  subject: string;
  priority: string;
  description: string;
  attachments: string[] | null;
  status: string;
  assigned_to_id: string | null;
  resolution: string | null;
  comments: SupportTicketComment[];
  history: SupportTicketHistory[];
  created_at: string;
  updated_at: string;
}

export interface OrgProfileDetails {
  id: string;
  name: string;
  slug: string;
  logo_url: string | null;
  website: string | null;
  support_email: string | null;
  support_phone: string | null;
  timezone: string;
  language: string;
  currency: string;
  billing_name: string | null;
  gst_number: string | null;
  pan: string | null;
  billing_address: string | null;
  billing_city: string | null;
  billing_state: string | null;
  billing_country: string | null;
  billing_pin_code: string | null;
  billing_email: string | null;
  billing_phone: string | null;
  notification_invoice_emails: boolean;
  notification_renewal_emails: boolean;
  notification_support_emails: boolean;
  auto_renewal: boolean;
  theme: string;
}

export const portalApi = {
  getStats: async () => {
    const res = await api.get<DashboardStatsResponse>('/portal/stats');
    return res.data;
  },

  getSubscription: async () => {
    const res = await api.get<any>('/portal/subscription');
    return res.data;
  },

  cancelAutoRenew: async () => {
    const res = await api.post<{ success: boolean; message: string }>('/portal/subscription/cancel-auto-renew');
    return res.data;
  },

  getExtraSeatPricing: async () => {
    const res = await api.get<{
      unit_price: number;
      cycle_prices: { monthly: number; quarterly: number; annual: number };
      gst_percentage: number;
      gst_inclusive: boolean;
      plan_name: string | null;
      minimum_users: number;
      users_purchased: number;
      can_add_extra: boolean;
      subscription_status: string;
    }>('/portal/subscription/extra-seat-pricing');
    return res.data;
  },

  buyExtraSeats: async (payload: { user_count: number; gateway: string; billing_cycle: string }) => {
    const res = await api.post<PortalInvoiceResponse>('/portal/subscription/add-users', payload);
    return res.data;
  },

  buyExtraStorage: async (payload: { storage_gb: number; gateway: string }) => {
    const res = await api.post<PortalInvoiceResponse>('/portal/subscription/add-storage', payload);
    return res.data;
  },

  getPlans: async () => {
    const res = await api.get<any[]>('/portal/plans');
    return res.data;
  },

  upgradePlan: async (payload: { plan_id: string; billing_cycle: string; gateway: string }) => {
    const res = await api.post<PortalInvoiceResponse>('/portal/subscription/upgrade', payload);
    return res.data;
  },

  reduceSeats: async (payload: { new_seat_count: number }) => {
    const res = await api.post<any>('/portal/subscription/reduce-seats', payload);
    return res.data;
  },

  getInvoices: async () => {
    const res = await api.get<PortalInvoiceResponse[]>('/portal/invoices');
    return res.data;
  },

  downloadInvoicePdf: async (invoiceId: string) => {
    const res = await api.get(`/portal/invoices/${invoiceId}/pdf`, {
      responseType: 'blob',
    });
    return res.data;
  },

  payInvoice: async (invoiceId: string, payload: { gateway: string; transaction_id?: string }) => {
    const res = await api.post<PortalInvoiceResponse>(`/portal/invoices/${invoiceId}/pay`, payload);
    return res.data;
  },

  getPayments: async () => {
    const res = await api.get<PortalPaymentResponse[]>('/portal/payments');
    return res.data;
  },

  updateProfile: async (payload: Partial<OrgProfileDetails>) => {
    const res = await api.put<OrgProfileDetails>('/portal/profile', payload);
    return res.data;
  },

  updateBilling: async (payload: Partial<OrgProfileDetails>) => {
    const res = await api.put<OrgProfileDetails>('/portal/billing', payload);
    return res.data;
  },

  updateSettings: async (payload: {
    notification_invoice_emails: boolean;
    notification_renewal_emails: boolean;
    notification_support_emails: boolean;
    auto_renewal: boolean;
    theme: string;
  }) => {
    const res = await api.put<{ success: boolean; message: string }>('/portal/settings', payload);
    return res.data;
  },

  getUsage: async () => {
    const res = await api.get<{
      active_seats: number;
      total_leads: number;
      total_calls: number;
      total_imports: number;
    }>('/portal/usage');
    return res.data;
  },

  getRecordings: async () => {
    const res = await api.get<Array<{
      id: string;
      recording_url: string;
      duration: number;
      direction: string;
      subject: string;
      date: string;
      assigned_user: string;
    }>>('/portal/recordings');
    return res.data;
  },

  deleteRecording: async (recordingId: string) => {
    const res = await api.delete<{ success: boolean; message: string }>(`/portal/recordings/${recordingId}`);
    return res.data;
  },

  getTickets: async () => {
    const res = await api.get<SupportTicketResponse[]>('/portal/support');
    return res.data;
  },

  createTicket: async (payload: { subject: string; priority: string; description: string; attachments?: string[] }) => {
    const res = await api.post<SupportTicketResponse>('/portal/support', payload);
    return res.data;
  },

  getTicket: async (ticketId: string) => {
    const res = await api.get<SupportTicketResponse>(`/portal/support/${ticketId}`);
    return res.data;
  },

  commentOnTicket: async (ticketId: string, payload: { content: string }) => {
    const res = await api.post<SupportTicketResponse>(`/portal/support/${ticketId}/comment`, payload);
    return res.data;
  },

  getActivityLogs: async () => {
    const res = await api.get<Array<{
      id: string;
      action: string;
      resource_type: string;
      resource_id: string | null;
      created_at: string;
      metadata: any;
    }>>('/portal/activity-logs');
    return res.data;
  },
};
