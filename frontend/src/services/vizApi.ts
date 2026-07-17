import { api } from './api';

export interface VizTypeMeta { key: string; label: string; needs: string[]; optional: string[]; }
export interface VizDatasetCol { field: string; type: string; label: string; }
export interface VizCatalog {
  viz_types: VizTypeMeta[];
  datasets: { key: string; label: string; columns: VizDatasetCol[] }[];
  aggregations: string[]; intervals: string[]; visibilities: string[];
}

export interface VizSpec { viz_type: string; dataset: string; config: any; filters?: any; }
export interface VizRenderResult { viz_type: string; dataset: string; config: any; data: any; }

export interface SavedViz {
  id: string; name: string; description: string | null; viz_type: string; dataset: string;
  config: any; filters: any; visibility: string; is_pinned: boolean; created_at: string | null;
}
export interface VizDashboard { pinned: (SavedViz & { data: any })[]; count: number; }

export interface DrillResult {
  columns: { key: string; label: string }[]; rows: any[]; total: number; field: string; value: any;
}

export const vizApi = {
  catalog: async () => (await api.get<VizCatalog>('/visualizations/catalog')).data,
  render: async (spec: VizSpec) => (await api.post<VizRenderResult>('/visualizations/render', spec)).data,
  drilldown: async (payload: { dataset: string; field: string; value: any; filters?: any; limit?: number }) =>
    (await api.post<DrillResult>('/visualizations/drilldown', payload)).data,
  dashboard: async () => (await api.get<VizDashboard>('/visualizations/dashboard')).data,

  list: async (params: { viz_type?: string } = {}) => (await api.get<SavedViz[]>('/visualizations', { params })).data,
  create: async (payload: any) => (await api.post<SavedViz>('/visualizations', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<SavedViz>(`/visualizations/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/visualizations/${id}`); },
  data: async (id: string) => (await api.get<SavedViz & VizRenderResult>(`/visualizations/${id}/data`)).data,
  exportCsv: async (id: string) => (await api.get<string>(`/visualizations/${id}/export`, { responseType: 'text' as any })).data,
};
