import { api } from './api';

export interface ExecWidgetMeta { id: string; label: string; category: string; drill: string | null; }
export interface ExecCatalog {
  personas: string[];
  scopes: string[];
  widgets: ExecWidgetMeta[];
  persona_layouts: Record<string, string[]>;
}

export interface ExecDashboard {
  persona: string;
  scope: string;
  from: string;
  to: string;
  generated_at: string;
  widgets: string[];
  blocks: Record<string, any>;
}

export interface ExecView {
  id: string;
  name: string;
  persona: string;
  scope: string;
  widgets: string[];
  is_default: boolean;
  created_at: string | null;
}

type Range = { persona?: string; scope?: string; date_from?: string; date_to?: string };

export const executiveDashboardApi = {
  catalog: async () => (await api.get<ExecCatalog>('/executive-dashboard/catalog')).data,
  dashboard: async (params: Range = {}) => (await api.get<ExecDashboard>('/executive-dashboard/dashboard', { params })).data,
  dashboardCustom: async (body: { persona?: string; scope?: string; widgets?: string[]; date_from?: string; date_to?: string }) =>
    (await api.post<ExecDashboard>('/executive-dashboard/dashboard', body)).data,
  exportCsv: async (params: Range = {}) => (await api.get('/executive-dashboard/export', { params, responseType: 'blob' })).data as Blob,

  listViews: async () => (await api.get<ExecView[]>('/executive-dashboard/views')).data,
  createView: async (payload: any) => (await api.post<ExecView>('/executive-dashboard/views', payload)).data,
  updateView: async (id: string, payload: any) => (await api.patch<ExecView>(`/executive-dashboard/views/${id}`, payload)).data,
  deleteView: async (id: string) => { await api.delete(`/executive-dashboard/views/${id}`); },
};
