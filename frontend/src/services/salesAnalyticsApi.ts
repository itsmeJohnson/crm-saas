import { api } from './api';

export interface SalesOverview {
  from: string; to: string;
  total_leads: number; won: number; lost: number; open: number;
  pipeline_value: number; revenue: number; conversion_rate: number; win_rate: number;
  avg_deal_size: number; avg_sales_cycle_days: number; sales_velocity: number;
}
export interface SalesFunnel {
  sales_funnel: { stage: string; count: number; value: number; drop_off_pct: number }[];
  lead_funnel: { status: string; count: number }[];
  total: number;
}
export interface SalesConversion { conversion_rate: number; total_leads: number; won: number; by_source: { source: string; leads: number; won: number; conversion_rate: number }[]; }
export interface SalesRevenue { revenue: number; won_deals: number; avg_deal_size: number; by_source: { source: string; revenue: number }[]; }
export interface SourceROI { sources: { source: string; leads: number; won: number; revenue: number; conversion_rate: number; value_per_lead: number; avg_deal_size: number }[]; }
export interface LostReasons { total_lost: number; lost_value: number; by_reason: { reason: string; count: number; lost_value: number; share_pct: number }[]; }
export interface Velocity {
  win_rate: number; opportunities: number; avg_deal_size: number; avg_sales_cycle_days: number;
  median_cycle_days: number; min_cycle_days: number; max_cycle_days: number; sales_velocity: number; velocity_note: string;
}
export interface SalesForecast { open_pipeline_value: number; conversion_rate: number; weighted_pipeline: number; realised_revenue: number; projected_total: number; open_deals: number; }
export interface SalesTrend { granularity: string; from: string; to: string; series: { bucket: string; leads: number; won: number; lost: number; revenue: number; win_rate: number }[]; }
export interface SalesHeatmap { weekdays: string[]; grid: number[][]; won_grid: number[][]; peak: { weekday: number; hour: number; count: number; weekday_label: string }; }
export interface SalesDashboard { revenue: number; win_rate: number; conversion_rate: number; avg_deal_size: number; sales_velocity: number; pipeline_value: number; won: number; open: number; }

type R = { date_from?: string; date_to?: string };

export const salesAnalyticsApi = {
  overview: async (p: R = {}) => (await api.get<SalesOverview>('/sales-analytics/overview', { params: p })).data,
  dashboard: async () => (await api.get<SalesDashboard>('/sales-analytics/dashboard')).data,
  funnel: async (p: R = {}) => (await api.get<SalesFunnel>('/sales-analytics/funnel', { params: p })).data,
  conversion: async (p: R = {}) => (await api.get<SalesConversion>('/sales-analytics/conversion', { params: p })).data,
  revenue: async (p: R = {}) => (await api.get<SalesRevenue>('/sales-analytics/revenue', { params: p })).data,
  sources: async (p: R = {}) => (await api.get<SourceROI>('/sales-analytics/sources', { params: p })).data,
  lostReasons: async (p: R = {}) => (await api.get<LostReasons>('/sales-analytics/lost-reasons', { params: p })).data,
  velocity: async (p: R = {}) => (await api.get<Velocity>('/sales-analytics/velocity', { params: p })).data,
  forecast: async (p: R = {}) => (await api.get<SalesForecast>('/sales-analytics/forecast', { params: p })).data,
  trend: async (p: R & { granularity?: string } = {}) => (await api.get<SalesTrend>('/sales-analytics/trend', { params: p })).data,
  heatmap: async (p: R = {}) => (await api.get<SalesHeatmap>('/sales-analytics/heatmap', { params: p })).data,
  exportCsv: async (p: R = {}) => (await api.get('/sales-analytics/export', { params: p, responseType: 'blob' })).data as Blob,
};
