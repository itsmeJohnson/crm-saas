import { api } from './api';

export interface BiConnector { tool: string; label: string; steps: string[]; url_template: string; }
export interface BiMeta {
  formats: string[]; sync_formats: string[]; destinations: string[]; modes: string[];
  frequencies: string[]; storage_providers: string[];
  datasets: { key: string; label: string }[];
  connectors: BiConnector[];
}

export interface BiToken {
  id: string; name: string; token: string; datasets: string[] | null; is_active: boolean;
  last_used_at: string | null; use_count: number; created_at: string | null;
}

export interface BiSettings {
  storage_provider: string; s3_bucket: string | null; s3_region: string | null;
  s3_prefix: string | null; s3_access_key: string | null; s3_secret_key: string | null;
}

export interface BiSync {
  id: string; name: string; source_type: string; source_key: string; format: string;
  destination: string; target_url: string | null; path_prefix: string | null; mode: string;
  last_cursor: string | null; frequency: string; is_active: boolean;
  next_run_at: string | null; last_run_at: string | null; last_status: string | null;
  run_count: number; created_at: string | null;
}

export interface ExportJob {
  id: string; kind: string; source_type: string; source_key: string; format: string;
  target: string | null; status: string; rows: number; size_bytes: number;
  error: string | null; detail: any; created_at: string | null;
}

export interface BiDashboard {
  active_tokens: number; active_syncs: number; exports: number; failed: number;
  success_rate: number; by_kind: Record<string, number>; recent: ExportJob[];
}

export const biApi = {
  meta: async () => (await api.get<BiMeta>('/bi/meta')).data,
  dashboard: async () => (await api.get<BiDashboard>('/bi/dashboard')).data,
  history: async (params: { kind?: string; limit?: number } = {}) =>
    (await api.get<ExportJob[]>('/bi/history', { params })).data,

  download: async (sourceType: string, sourceKey: string, format: string) =>
    (await api.get<Blob>('/bi/export', {
      params: { source_type: sourceType, source_key: sourceKey, format },
      responseType: 'blob' as any,
    })).data,
  webhookExport: async (payload: { source_type?: string; source_key: string; url: string; format?: string }) =>
    (await api.post('/bi/export/webhook', payload)).data as { status: string; rows: number; error: string | null },
  cloudExport: async (payload: { source_type?: string; source_key: string; format?: string; path_prefix?: string }) =>
    (await api.post('/bi/export/cloud', payload)).data as { status: string; target: string | null; rows: number; error: string | null },

  settings: async () => (await api.get<BiSettings>('/bi/settings')).data,
  updateSettings: async (payload: any) => (await api.patch<BiSettings>('/bi/settings', payload)).data,

  tokens: async () => (await api.get<BiToken[]>('/bi/tokens')).data,
  createToken: async (payload: { name: string; datasets?: string[] | null }) =>
    (await api.post<BiToken>('/bi/tokens', payload)).data,
  updateToken: async (id: string, payload: any) => (await api.patch<BiToken>(`/bi/tokens/${id}`, payload)).data,
  rotateToken: async (id: string) => (await api.post<BiToken>(`/bi/tokens/${id}/rotate`, {})).data,
  removeToken: async (id: string) => { await api.delete(`/bi/tokens/${id}`); },

  syncs: async () => (await api.get<BiSync[]>('/bi/syncs')).data,
  createSync: async (payload: any) => (await api.post<BiSync>('/bi/syncs', payload)).data,
  updateSync: async (id: string, payload: any) => (await api.patch<BiSync>(`/bi/syncs/${id}`, payload)).data,
  removeSync: async (id: string) => { await api.delete(`/bi/syncs/${id}`); },
  runSync: async (id: string) => (await api.post(`/bi/syncs/${id}/run`, {})).data as { status: string; rows: number; error: string | null },
};
