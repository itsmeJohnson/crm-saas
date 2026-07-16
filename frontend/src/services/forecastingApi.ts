import { api } from './api';

export const FORECAST_METRICS = ['revenue', 'sales', 'leads', 'collections', 'staff'] as const;
export const FORECAST_METHODS = ['linear', 'moving_average', 'seasonal'] as const;
export const FORECAST_GRANULARITIES = ['daily', 'weekly', 'monthly'] as const;

export interface ForecastPoint { bucket: string; value: number; lower: number; upper: number; }
export interface HistoryPoint { bucket: string; value: number; }
export interface Trend { slope: number; direction: string; growth_rate: number; avg: number; }
export interface Forecast {
  metric: string; method: string; granularity: string;
  history: HistoryPoint[]; forecast: ForecastPoint[]; total_forecast: number; history_avg: number; trend: Trend;
}
export interface Scenario {
  metric: string; granularity: string;
  scenarios: Record<'pessimistic' | 'base' | 'optimistic', { factor: number; series: HistoryPoint[]; total: number }>;
}
export interface Seasonality {
  metric: string; granularity: string;
  indices: { label: string; index: number }[];
  peak: { label: string; index: number } | null; trough: { label: string; index: number } | null;
}
export interface TrendAnalysis extends Trend { metric: string; granularity: string; history: HistoryPoint[]; }
export interface HistoricalComparison {
  metric: string; granularity: string;
  comparison: { bucket: string; actual: number; forecast: number; error_pct: number }[];
  mape: number | null; accuracy: number | null; note?: string;
}
export interface PipelineForecast {
  open_pipeline_value: number; conversion_rate: number; expected_close_total: number;
  granularity: string; forecast: HistoryPoint[];
}
export interface GoalForecast {
  targets: any[]; total: number; on_track: number; at_risk: number;
}
export interface ForecastDashboard {
  revenue: { next_month: number; history_avg: number; direction: string };
  sales: { next_month: number; history_avg: number; direction: string };
  leads: { next_month: number; history_avg: number; direction: string };
  collections: { next_month: number; history_avg: number; direction: string };
  pipeline_expected_close: number; goals_on_track: number; goals_total: number;
}

type P = { metric?: string; periods?: number; method?: string; granularity?: string };

export const forecastingApi = {
  catalog: async () => (await api.get<{ metrics: string[]; methods: string[]; granularities: string[] }>('/forecasting/catalog')).data,
  forecast: async (p: P = {}) => (await api.get<Forecast>('/forecasting/forecast', { params: p })).data,
  scenario: async (p: P = {}) => (await api.get<Scenario>('/forecasting/scenario', { params: p })).data,
  seasonality: async (p: { metric?: string; granularity?: string } = {}) => (await api.get<Seasonality>('/forecasting/seasonality', { params: p })).data,
  trend: async (p: { metric?: string; granularity?: string } = {}) => (await api.get<TrendAnalysis>('/forecasting/trend', { params: p })).data,
  historicalComparison: async (p: { metric?: string; granularity?: string; holdout?: number } = {}) => (await api.get<HistoricalComparison>('/forecasting/historical-comparison', { params: p })).data,
  pipeline: async (p: { periods?: number; granularity?: string } = {}) => (await api.get<PipelineForecast>('/forecasting/pipeline', { params: p })).data,
  goals: async () => (await api.get<GoalForecast>('/forecasting/goals')).data,
  dashboard: async () => (await api.get<ForecastDashboard>('/forecasting/dashboard')).data,
  exportCsv: async (p: P = {}) => (await api.get('/forecasting/export', { params: p, responseType: 'blob' })).data as Blob,
};
