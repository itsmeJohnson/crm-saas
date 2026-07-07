import { api } from './api';

export interface LineItem {
  description: string;
  quantity: number;
  unit_price: number;
  amount?: number;
}

export interface CustomerListItem {
  company_id: string;
  name: string;
  industry: string | null;
  annual_revenue: number | null;
  order_count: number;
  total_invoiced: number;
  outstanding_balance: number;
}

export interface CustomerSummary {
  company_id: string;
  name: string;
  company_type: string;
  orders: { count: number; total_value: number };
  invoices: { count: number; total_invoiced: number; total_paid: number; outstanding: number; overdue: number };
  payments: { total_collected: number };
  contracts: { count: number; active: number };
}

export interface Order {
  id: string;
  company_id: string;
  contact_id: string | null;
  order_number: string;
  status: string;
  currency: string;
  order_date: string | null;
  items: LineItem[];
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total_amount: number;
  notes: string | null;
  created_at: string;
}

export interface Invoice {
  id: string;
  company_id: string;
  contact_id: string | null;
  order_id: string | null;
  invoice_number: string;
  status: string;
  currency: string;
  issue_date: string | null;
  due_date: string | null;
  items: LineItem[];
  subtotal: number;
  tax_amount: number;
  discount_amount: number;
  total_amount: number;
  amount_paid: number;
  balance_due: number;
  notes: string | null;
  created_at: string;
}

export interface Payment {
  id: string;
  company_id: string;
  invoice_id: string;
  amount: number;
  currency: string;
  method: string;
  reference: string | null;
  paid_at: string | null;
  notes: string | null;
  created_at: string;
}

export interface Contract {
  id: string;
  company_id: string;
  contact_id: string | null;
  contract_number: string;
  title: string;
  status: string;
  start_date: string | null;
  end_date: string | null;
  value: number | null;
  currency: string;
  renewal_terms: string | null;
  document_url: string | null;
  notes: string | null;
  created_at: string;
}

export interface TimelineEvent {
  type: string;
  id: string;
  timestamp: string;
  group: string;
  title: string;
  description: string | null;
  actor_user_id: string | null;
  actor_name: string | null;
  source: string;
  metadata: Record<string, any> | null;
}

export interface CustomerReport {
  total_customers: number;
  total_orders: number;
  total_order_value: number;
  total_invoiced: number;
  total_collected: number;
  outstanding_ar: number;
  overdue_ar: number;
  active_contracts: number;
  invoices_by_status: { label: string; count: number }[];
  top_customers: { name: string; invoiced: number }[];
}

export const customerApi = {
  listCustomers: async (search?: string) => {
    const response = await api.get<CustomerListItem[]>('/customers/', { params: { search } });
    return response.data;
  },
  getSummary: async (companyId: string) => {
    const response = await api.get<CustomerSummary>(`/customers/${companyId}/summary`);
    return response.data;
  },
  getReport: async (params?: { date_from?: string; date_to?: string }) => {
    const response = await api.get<CustomerReport>('/customers/reports', { params });
    return response.data;
  },
  getTimeline: async (companyId: string, params?: { types?: string; search?: string }) => {
    const response = await api.get<TimelineEvent[]>(`/customers/${companyId}/timeline`, { params });
    return response.data;
  },
  exportTimeline: async (companyId: string, params?: { types?: string; search?: string }) => {
    const response = await api.get(`/customers/${companyId}/timeline/export`, { params, responseType: 'blob' });
    return response.data as Blob;
  },

  // Orders
  listOrders: async (companyId?: string) => {
    const response = await api.get<Order[]>('/customers/orders', { params: { company_id: companyId } });
    return response.data;
  },
  createOrder: async (payload: { company_id: string; contact_id?: string | null; items: LineItem[]; tax_amount?: number; discount_amount?: number; currency?: string; notes?: string | null }) => {
    const response = await api.post<Order>('/customers/orders', payload);
    return response.data;
  },
  updateOrder: async (orderId: string, payload: Partial<{ status: string; items: LineItem[]; tax_amount: number; discount_amount: number; notes: string | null }>) => {
    const response = await api.patch<Order>(`/customers/orders/${orderId}`, payload);
    return response.data;
  },
  deleteOrder: async (orderId: string) => { await api.delete(`/customers/orders/${orderId}`); },

  // Invoices
  listInvoices: async (companyId?: string) => {
    const response = await api.get<Invoice[]>('/customers/invoices', { params: { company_id: companyId } });
    return response.data;
  },
  createInvoice: async (payload: { company_id: string; contact_id?: string | null; items: LineItem[]; tax_amount?: number; discount_amount?: number; currency?: string; due_date?: string | null; notes?: string | null }) => {
    const response = await api.post<Invoice>('/customers/invoices', payload);
    return response.data;
  },
  createInvoiceFromOrder: async (orderId: string, dueDate?: string | null) => {
    const response = await api.post<Invoice>('/customers/invoices/from-order', { order_id: orderId, due_date: dueDate });
    return response.data;
  },
  sendInvoice: async (invoiceId: string) => {
    const response = await api.post<Invoice>(`/customers/invoices/${invoiceId}/send`);
    return response.data;
  },
  invoicePdfUrl: (invoiceId: string) => `/customers/invoices/${invoiceId}/pdf`,
  downloadInvoicePdf: async (invoiceId: string) => {
    const response = await api.get(`/customers/invoices/${invoiceId}/pdf`, { responseType: 'blob' });
    return response.data as Blob;
  },
  deleteInvoice: async (invoiceId: string) => { await api.delete(`/customers/invoices/${invoiceId}`); },

  // Payments
  recordPayment: async (invoiceId: string, payload: { amount: number; method?: string; reference?: string; paid_at?: string; notes?: string }) => {
    const response = await api.post<Payment>(`/customers/invoices/${invoiceId}/payments`, payload);
    return response.data;
  },
  listPayments: async (companyId?: string) => {
    const response = await api.get<Payment[]>('/customers/payments', { params: { company_id: companyId } });
    return response.data;
  },

  // Contracts
  listContracts: async (companyId?: string) => {
    const response = await api.get<Contract[]>('/customers/contracts', { params: { company_id: companyId } });
    return response.data;
  },
  createContract: async (payload: { company_id: string; title: string; status?: string; start_date?: string | null; end_date?: string | null; value?: number | null; currency?: string; renewal_terms?: string | null; notes?: string | null }) => {
    const response = await api.post<Contract>('/customers/contracts', payload);
    return response.data;
  },
  updateContract: async (contractId: string, payload: Partial<{ status: string; title: string; end_date: string | null; value: number | null }>) => {
    const response = await api.patch<Contract>(`/customers/contracts/${contractId}`, payload);
    return response.data;
  },
  deleteContract: async (contractId: string) => { await api.delete(`/customers/contracts/${contractId}`); },
};
