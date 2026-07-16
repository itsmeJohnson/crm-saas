import { api } from './api';

export interface FinOverview {
  from: string; to: string; revenue_billed: number; revenue_collected: number; expenses: number;
  gross_profit: number; profit_margin: number; collections: number; outstanding: number; overdue: number;
  tax_collected: number; invoice_count: number; payment_count: number; mrr: number; arr: number; active_contracts: number;
}
export interface Recurring {
  subscription_revenue: number; mrr: number; arr: number; active_contracts: number; active_customers: number;
  arpa: number; churned_contracts: number; churn_rate: number; ltv: number; ltv_saas: number;
  cac: number; acquisition_spend: number; new_customers: number; ltv_cac_ratio: number;
}
export interface Collections { collected: number; billed: number; collection_rate: number; by_method: { method: string; amount: number }[]; }
export interface Outstanding { outstanding: number; overdue: number; aging: { bucket: string; amount: number }[]; }
export interface InvoicesReport { count: number; total: number; avg: number; by_status: { status: string; count: number; amount: number }[]; }
export interface PaymentsReport { count: number; total: number; avg: number; by_method: { method: string; count: number; amount: number }[]; }
export interface ExpensesReport { total: number; count: number; by_category: { category: string; amount: number }[]; }
export interface Profitability { revenue: number; expenses: number; gross_profit: number; profit_margin: number; cash_profit: number; collected: number; }
export interface Taxes { tax_collected: number; taxable_base: number; effective_rate: number; invoice_count: number; }
export interface RevenueReport { billed: number; collected: number; invoice_count: number; avg_invoice: number; top_customers: { company: string; revenue: number }[]; }
export interface Forecast { monthly_run_rate: number; mrr: number; expected_ar_collection: number; projected_next_month: number; projected_arr: number; }
export interface FinTrend { granularity: string; from: string; to: string; series: { bucket: string; revenue: number; collected: number; expenses: number; profit: number }[]; }
export interface FinDashboard { revenue: number; collected: number; expenses: number; gross_profit: number; profit_margin: number; outstanding: number; mrr: number; arr: number; churn_rate: number; }
export interface ExpenseRecord { id: string; category: string; amount: number; description: string | null; vendor: string | null; incurred_at: string | null; created_at: string | null; }

type R = { date_from?: string; date_to?: string };
export const EXPENSE_CATEGORIES = ['Marketing', 'Sales', 'Payroll', 'Software', 'Office', 'General'] as const;

export const financialAnalyticsApi = {
  overview: async (p: R = {}) => (await api.get<FinOverview>('/financial-analytics/overview', { params: p })).data,
  dashboard: async () => (await api.get<FinDashboard>('/financial-analytics/dashboard')).data,
  revenue: async (p: R = {}) => (await api.get<RevenueReport>('/financial-analytics/revenue', { params: p })).data,
  expenses: async (p: R = {}) => (await api.get<ExpensesReport>('/financial-analytics/expenses', { params: p })).data,
  profitability: async (p: R = {}) => (await api.get<Profitability>('/financial-analytics/profitability', { params: p })).data,
  collections: async (p: R = {}) => (await api.get<Collections>('/financial-analytics/collections', { params: p })).data,
  outstanding: async () => (await api.get<Outstanding>('/financial-analytics/outstanding')).data,
  invoices: async (p: R = {}) => (await api.get<InvoicesReport>('/financial-analytics/invoices', { params: p })).data,
  payments: async (p: R = {}) => (await api.get<PaymentsReport>('/financial-analytics/payments', { params: p })).data,
  taxes: async (p: R = {}) => (await api.get<Taxes>('/financial-analytics/taxes', { params: p })).data,
  recurring: async (p: R = {}) => (await api.get<Recurring>('/financial-analytics/recurring', { params: p })).data,
  forecast: async (p: R = {}) => (await api.get<Forecast>('/financial-analytics/forecast', { params: p })).data,
  trend: async (p: R & { granularity?: string } = {}) => (await api.get<FinTrend>('/financial-analytics/trend', { params: p })).data,
  exportCsv: async (p: R = {}) => (await api.get('/financial-analytics/export', { params: p, responseType: 'blob' })).data as Blob,

  listExpenses: async (p: R & { category?: string } = {}) => (await api.get<ExpenseRecord[]>('/financial-analytics/expense-records', { params: p })).data,
  createExpense: async (payload: any) => (await api.post<ExpenseRecord>('/financial-analytics/expense-records', payload)).data,
  updateExpense: async (id: string, payload: any) => (await api.patch<ExpenseRecord>(`/financial-analytics/expense-records/${id}`, payload)).data,
  deleteExpense: async (id: string) => { await api.delete(`/financial-analytics/expense-records/${id}`); },
};
