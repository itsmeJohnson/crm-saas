import { api } from './api';

export interface WinFactor { points: number; factor: string; }
export interface DealIntelligence {
  lead_id: string; name: string; status: string; stage: string; value: number;
  win_probability: number; win_factors: WinFactor[]; loss_risk: number; expected_value: number;
  sales_risk: number; sales_risk_reasons: string[]; health: string;
  recommended_action: { action: string; priority: string };
  competitors?: string[]; age_days: number; activities: number;
}

export interface SalesIntelDashboard {
  open_deals: number; open_pipeline_value: number; weighted_pipeline_value: number;
  avg_win_probability: number; by_health: Record<string, number>;
  top_deals: DealIntelligence[]; at_risk_deals: DealIntelligence[];
  revenue_forecast_next3: { bucket: string; value: number }[];
}

export interface CompetitorAnalysis {
  competitors: { competitor: string; mentions: number; lost_to: number; won_against: number }[];
  lost_to_competitor: number; total_analyzed: number;
}

export interface UpsellResult {
  upsell: { customer_id: string; customer_name: string; reason: string; total_paid: number; churn_risk: number; priority: string }[];
  cross_sell: { customer_id: string; customer_name: string; reason: string; priority: string }[];
  customers_analyzed: number;
}

export interface Quotation {
  lead_id: string; customer: string;
  line_items: { description: string; qty: number; unit_price: number; amount: number }[];
  subtotal: number; tax: number; total: number; currency: string; terms: string; cover_note: string;
}

export const salesIntelligenceApi = {
  dashboard: async () => (await api.get<SalesIntelDashboard>('/sales-intelligence/dashboard')).data,
  pipelineInsights: async () => (await api.get('/sales-intelligence/pipeline-insights')).data as any,
  revenuePrediction: async () => (await api.get('/sales-intelligence/revenue-prediction')).data as any,
  competitorAnalysis: async () => (await api.get<CompetitorAnalysis>('/sales-intelligence/competitor-analysis')).data,
  upsell: async () => (await api.get<UpsellResult>('/sales-intelligence/upsell')).data,
  report: async () => (await api.get('/sales-intelligence/report')).data as any,
  exportCsv: async () => (await api.get<string>('/sales-intelligence/export', { responseType: 'text' as any })).data,
  deals: async (params: { health?: string; sort?: string; limit?: number } = {}) =>
    (await api.get<{ total: number; rows: DealIntelligence[] }>('/sales-intelligence/deals', { params })).data,
  deal: async (id: string) => (await api.get<DealIntelligence>(`/sales-intelligence/deals/${id}`)).data,
  summary: async (id: string) => (await api.get<{ text: string }>(`/sales-intelligence/deals/${id}/summary`)).data,
  coaching: async (id: string) => (await api.post<{ text: string }>(`/sales-intelligence/deals/${id}/coaching`, {})).data,
  objection: async (id: string, objection: string) =>
    (await api.post<{ text: string }>(`/sales-intelligence/deals/${id}/objection-handling`, { objection })).data,
  proposal: async (id: string) => (await api.post<{ text: string }>(`/sales-intelligence/deals/${id}/proposal`, {})).data,
  quotation: async (id: string) => (await api.post<Quotation>(`/sales-intelligence/deals/${id}/quotation`, {})).data,
};
