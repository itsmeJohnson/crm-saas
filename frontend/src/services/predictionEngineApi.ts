import { api } from './api';

export interface PeModel {
  key: string; name: string; version: string; type: string; target: string; unit: string;
  features: string[]; status: string; trained_at: string | null;
}

export interface PeConfidence {
  confidence: number; confidence_band: string;
  confidence_factors: { sample_size: number; sample_factor: number;
    feature_completeness: number; signal_strength: number };
}

export interface PeDashboard {
  engine_version: string; algorithm: string; models_active: number;
  sales: { open_deals: number; weighted_expected_value: number; win_rate: number; confidence: number };
  revenue: { total_forecast: number; trend: string; backtest_accuracy: number | null; confidence: number };
  tasks: { open: number; at_risk: number; top: any[] };
  campaigns: { count: number; top: any[] };
  customers_at_risk: { customer_id: string; customer_name: string; churn_risk: number }[];
}

export interface PeAccuracy {
  engine_version: string; overall_accuracy: number | null;
  regression: { model: string; metric: string; type: string; mape: number | null; accuracy: number | null }[];
  classification: { model: string; type: string; samples: number; accuracy: number | null;
    brier: number | null; positive_rate?: number }[];
}

export interface PeTaskPrediction {
  task_id: string; title: string; status: string; due_date: string | null;
  hours_to_due: number | null; delay_risk: number; band: string; predicted_late: boolean;
  factors: { factor: string; impact: number }[]; assignee_on_time_rate?: number | null;
  assignee_open_load?: number;
}

export interface PeCampaignPrediction {
  campaign_id: string; name: string; channel: string; status: string; audience_size: number;
  predicted: { delivered: number; opened: number; clicked: number; converted: number;
    revenue: number; cost: number; roi_pct: number | null };
  rates: { delivery: number; open: number; click: number; conversion: number };
  benchmark_source: string; benchmark_sample: number;
}

export const predictionEngineApi = {
  models: async () => (await api.get<{ engine_version: string; count: number; models: PeModel[] }>(
    '/prediction-engine/models')).data,
  dashboard: async () => (await api.get<PeDashboard>('/prediction-engine/dashboard')).data,
  report: async () => (await api.get<any>('/prediction-engine/report')).data,
  accuracy: async () => (await api.get<PeAccuracy>('/prediction-engine/accuracy')).data,
  exportCsv: async () => (await api.get<string>('/prediction-engine/export')).data,

  sales: async (periods = 3) => (await api.get<any>('/prediction-engine/predict/sales', { params: { periods } })).data,
  revenue: async (periods = 6) => (await api.get<any>('/prediction-engine/predict/revenue', { params: { periods } })).data,
  tasks: async (limit = 50) =>
    (await api.get<{ open_tasks: number; at_risk: number; predictions: PeTaskPrediction[] }>(
      '/prediction-engine/predict/tasks', { params: { limit } })).data,
  campaigns: async (limit = 50) =>
    (await api.get<{ count: number; channel_benchmarks: any; predictions: PeCampaignPrediction[] }>(
      '/prediction-engine/predict/campaigns', { params: { limit } })).data,

  predictLead: async (id: string) => (await api.get<any>(`/prediction-engine/predict/lead/${id}`)).data,
  predictChurn: async (id: string) => (await api.get<any>(`/prediction-engine/predict/churn/${id}`)).data,
  predictTask: async (id: string) => (await api.get<any>(`/prediction-engine/predict/task/${id}`)).data,
  predictCampaign: async (id: string) => (await api.get<any>(`/prediction-engine/predict/campaign/${id}`)).data,
};
