import { api } from './api';

export interface HistMetric { key: string; label: string; category: string; unit: string; comparison: string; }
export interface HistMeta { metrics: HistMetric[]; comparison_periods: string[]; rolling_windows: number[]; key_metrics: string[]; }

export interface HistPoint { date: string; value: number; granularity: string; rolling_avg?: number; }

export interface HistTrend {
  metric: string; label: string; unit: string; days: number; points: HistPoint[];
  latest: number | null; min: number | null; max: number | null; change_pct: number | null;
}

export interface ComparisonRow {
  metric: string; label: string; unit: string; comparison: string;
  current: number; previous: number; change: number; change_pct: number; improved: boolean | null;
}
export interface HistComparison {
  period: string; current_window: { start: string; end: string }; previous_window: { start: string; end: string };
  rows: ComparisonRow[]; improved?: number; declined?: number; flat?: number;
}

export interface HistSnapshotRow { id: string; date: string; metric: string; label: string; value: number; granularity: string; }

export interface HistSettings { retention_days: number; archive_enabled: boolean; capture_enabled: boolean; }

export interface HistDashboard {
  days_covered: number; metrics_tracked: number; archived_rows: number; last_capture: string | null;
  top_movers: ComparisonRow[];
  sparklines: Record<string, { label: string; unit: string; points: HistPoint[] }>;
  settings: HistSettings;
}

export const historyApi = {
  meta: async () => (await api.get<HistMeta>('/historical-analytics/meta')).data,
  dashboard: async () => (await api.get<HistDashboard>('/historical-analytics/dashboard')).data,
  trends: async (metric: string, days = 90) =>
    (await api.get<HistTrend>('/historical-analytics/trends', { params: { metric, days } })).data,
  comparison: async (period = 'month') =>
    (await api.get<HistComparison>('/historical-analytics/comparison', { params: { period } })).data,
  rolling: async (metric: string, window = 30, days = 180) =>
    (await api.get<HistTrend & { window: number }>('/historical-analytics/rolling', { params: { metric, window, days } })).data,
  snapshots: async (params: { snapshot_date?: string; metric?: string; granularity?: string; limit?: number } = {}) =>
    (await api.get<HistSnapshotRow[]>('/historical-analytics/snapshots', { params })).data,
  capture: async () => (await api.post<{ captured: number; date: string }>('/historical-analytics/capture', {})).data,
  report: async (period = 'month') => (await api.get<HistComparison>('/historical-analytics/report', { params: { period } })).data,
  exportCsv: async (params: { kind: string; metric?: string; period?: string; days?: number }) =>
    (await api.get<string>('/historical-analytics/export', { params, responseType: 'text' as any })).data,
  settings: async () => (await api.get<HistSettings>('/historical-analytics/settings')).data,
  updateSettings: async (payload: Partial<HistSettings>) =>
    (await api.patch<HistSettings>('/historical-analytics/settings', payload)).data,
};
