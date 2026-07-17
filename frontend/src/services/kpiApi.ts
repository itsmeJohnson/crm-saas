import { api } from './api';

export interface KpiMetric { key: string; label: string; category: string; unit: string; comparison: string; }
export interface KpiCatalog { categories: string[]; comparisons: string[]; units: string[]; metrics: KpiMetric[]; }

export interface Kpi {
  id: string; name: string; description: string | null; category: string; metric: string; unit: string;
  comparison: string; target_value: number | null; warning_value: number | null; critical_value: number | null;
  manual_value: number | null; window_days: number; is_active: boolean; notify: boolean; notify_roles: string[];
  created_at: string | null;
}
export interface KpiEval extends Kpi { value: number | null; status: string; attainment: number | null; }

export interface KpiDashboard {
  summary: { total: number; on_track: number; warning: number; critical: number; unknown: number };
  open_alerts: number;
  kpis: KpiEval[];
  by_category: Record<string, KpiEval[]>;
}
export interface KpiReport {
  summary: KpiDashboard['summary']; open_alerts: number;
  by_category: { category: string; count: number; on_track: number; warning: number; critical: number }[];
}
export interface KpiAlert {
  id: string; kpi_id: string; kpi_name: string; status: string; value: number | null; target_value: number | null;
  message: string | null; resolved: boolean; created_at: string | null; resolved_at: string | null;
}

export const kpiApi = {
  catalog: async () => (await api.get<KpiCatalog>('/kpi/catalog')).data,
  dashboard: async () => (await api.get<KpiDashboard>('/kpi/dashboard')).data,
  report: async () => (await api.get<KpiReport>('/kpi/report')).data,
  evaluateAll: async () => (await api.post<{ evaluated: number; raised: number; resolved: number }>('/kpi/evaluate', {})).data,

  list: async (params: { category?: string; active_only?: boolean } = {}) => (await api.get<Kpi[]>('/kpi', { params })).data,
  create: async (payload: any) => (await api.post<Kpi>('/kpi', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Kpi>(`/kpi/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/kpi/${id}`); },
  evaluate: async (id: string) => (await api.get<KpiEval>(`/kpi/${id}/evaluate`)).data,

  alerts: async (params: { resolved?: boolean; limit?: number } = {}) => (await api.get<KpiAlert[]>('/kpi/alerts', { params })).data,
  resolveAlert: async (id: string) => (await api.post<{ id: string; resolved: boolean }>(`/kpi/alerts/${id}/resolve`, {})).data,
};
