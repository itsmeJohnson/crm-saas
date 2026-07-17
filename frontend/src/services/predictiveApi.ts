import { api } from './api';

export interface PredDataset {
  key: string; label: string; entity: string; target: string; description: string; features: string[];
}
export interface PredCatalog { method: string; ai_ready: boolean; note: string; datasets: PredDataset[]; }

export interface PredDatasetResult {
  dataset: string; label: string; entity: string; target: string; description: string;
  columns: string[]; rows: any[]; count: number; generated_at: string;
}

export interface Recommendation {
  entity_type: string; entity_id: string; entity_name: string; action: string; reason: string; priority: string;
}

export interface PredDashboard {
  method: string; ai_ready: boolean; datasets: Record<string, string>;
  open_leads: number; expected_pipeline_value: number; customers_tracked: number;
  customers_at_high_churn_risk: number; open_invoices: number; invoices_at_collection_risk: number;
  recommendations: number; hot_leads: any[]; at_risk_customers: any[]; top_recommendations: Recommendation[];
}

export const predictiveApi = {
  catalog: async () => (await api.get<PredCatalog>('/predictive/catalog')).data,
  dashboard: async () => (await api.get<PredDashboard>('/predictive/dashboard')).data,
  dataset: async (key: string, limit = 200) =>
    (await api.get<PredDatasetResult>(`/predictive/datasets/${key}`, { params: { limit } })).data,
  exportDataset: async (key: string, format: 'csv' | 'json') =>
    (await api.get<Blob>(`/predictive/datasets/${key}/export`, { params: { format }, responseType: 'blob' as any })).data,
  recommendations: async (scope = 'all', limit = 50) =>
    (await api.get<Recommendation[]>('/predictive/recommendations', { params: { scope, limit } })).data,
  predictLead: async (leadId: string) => (await api.get(`/predictive/predict/lead/${leadId}`)).data as any,
  predictChurn: async (companyId: string) => (await api.get(`/predictive/predict/churn/${companyId}`)).data as any,
  predictClv: async (companyId: string, horizon = 12) =>
    (await api.get(`/predictive/predict/clv/${companyId}`, { params: { horizon_months: horizon } })).data as any,
  predictRisk: async (companyId: string) => (await api.get(`/predictive/predict/risk/${companyId}`)).data as any,
  predictCollection: async (invoiceId: string) => (await api.get(`/predictive/predict/collection/${invoiceId}`)).data as any,
  predictEmployee: async (userId: string) => (await api.get(`/predictive/predict/employee/${userId}`)).data as any,
};
