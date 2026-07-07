import { api } from './api';

export interface RBColumnMeta { field: string; type: string; label: string; }
export interface RBDataset { key: string; label: string; columns: RBColumnMeta[]; }
export interface RBCatalog {
  datasets: RBDataset[];
  aggregations: string[];
  operators: { comparison: string[]; date: string[]; time: string[]; boolean: string[] };
  logic: string[];
  chart_types: string[];
  frequencies: string[];
  visibilities: string[];
}

export interface RBColumn { field: string; label?: string; agg?: string | null; }
export interface ReportDef {
  id: string;
  name: string;
  description: string | null;
  dataset: string;
  columns: RBColumn[];
  filters: any | null;
  group_by: string[] | null;
  sort: { field: string; dir: string }[] | null;
  calculated_fields: { name: string; expression: string; type?: string }[] | null;
  pivot: { row?: string; col?: string; measure?: string; agg?: string } | null;
  chart: { type?: string; x?: string; y?: string } | null;
  is_template: boolean;
  visibility: string;
  pinned_to_dashboard: boolean;
  schedule_frequency: string | null;
  schedule_recipients: string[];
  next_run: string | null;
  last_run: string | null;
  run_count: number;
  version: number;
  created_by: string;
  created_at: string | null;
}

export interface RunResult {
  columns: { key: string; label: string; agg: string | null }[];
  rows: Record<string, any>[];
  total: number;
  scanned?: number;
  pivot?: any | null;
  chart?: any | null;
}

export interface ReportVersion { id: string; version_no: number; note: string | null; snapshot: any; created_at: string | null; }

export const reportBuilderApi = {
  catalog: async () => (await api.get<RBCatalog>('/report-builder/catalog')).data,
  dashboard: async () => (await api.get<{ reports: any[] }>('/report-builder/dashboard')).data,

  list: async (params: { box?: string; dataset?: string } = {}) => (await api.get<ReportDef[]>('/report-builder', { params })).data,
  get: async (id: string) => (await api.get<ReportDef>(`/report-builder/${id}`)).data,
  create: async (payload: any) => (await api.post<ReportDef>('/report-builder', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<ReportDef>(`/report-builder/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/report-builder/${id}`); },
  clone: async (id: string) => (await api.post<ReportDef>(`/report-builder/${id}/clone`, {})).data,
  preview: async (payload: any) => (await api.post<RunResult>('/report-builder/preview', payload)).data,
  run: async (id: string, params: { limit?: number; offset?: number } = {}) => (await api.get<RunResult>(`/report-builder/${id}/run`, { params })).data,
  exportCsv: async (id: string) => (await api.get(`/report-builder/${id}/export`, { responseType: 'blob' })).data as Blob,

  listTemplates: async () => (await api.get<ReportDef[]>('/report-builder/templates')).data,
  seedTemplates: async () => (await api.post<{ created: number }>('/report-builder/templates/seed', {})).data,
  instantiate: async (id: string) => (await api.post<ReportDef>(`/report-builder/templates/${id}/instantiate`, {})).data,

  setSchedule: async (id: string, payload: any) => (await api.patch<ReportDef>(`/report-builder/${id}/schedule`, payload)).data,
  versions: async (id: string) => (await api.get<ReportVersion[]>(`/report-builder/${id}/versions`)).data,
  restore: async (id: string, version_no: number) => (await api.post<ReportDef>(`/report-builder/${id}/versions/restore`, { version_no })).data,
};
