import { api } from './api';

export interface Connector {
  key: string; label: string; auth_type: string;
  base_url: string | null; health_path: string | null;
  capabilities: string[]; docs: string | null;
  credential_fields: string[]; config_fields: string[];
}

export interface CatalogCategory {
  key: string; label: string; managed_by: string | null; connectors: Connector[];
}

export interface IntegrationCatalog {
  categories: CatalogCategory[];
  auth_types: string[];
  auth_fields: Record<string, string[]>;
  total_connectors: number;
}

export interface Integration {
  id: string; category: string; provider: string; provider_label: string;
  name: string; environment: string; auth_type: string;
  credentials: Record<string, any>; config: Record<string, any>;
  capabilities: string[];
  is_enabled: boolean; is_managed_elsewhere: boolean; managed_by: string | null;
  status: string;
  last_check_at: string | null; last_success_at: string | null; last_error: string | null;
  consecutive_failures: number; latency_ms: number | null;
  max_attempts: number; retry_backoff_seconds: number; timeout_seconds: number;
  fallback_integration_id: string | null;
  total_calls: number; failed_calls: number;
  has_inbound_endpoint: boolean; created_at: string | null;
  inbound_token?: string; inbound_secret?: string;
}

export interface IntegrationLog {
  id: string; integration_id: string; operation: string; method: string | null;
  endpoint: string | null; status: string; status_code: number | null;
  attempts: number; latency_ms: number; error: string | null;
  fallback_from_id: string | null; created_at: string | null;
}

export interface IntegrationEvent {
  id: string; integration_id: string; event_type: string;
  payload: Record<string, any>; signature_valid: boolean | null;
  processed: boolean; error: string | null; received_at: string | null;
}

export interface IntegrationDashboard {
  total: number; active: number; managed_elsewhere: number;
  healthy: number; degraded: number; down: number; unconfigured: number;
  categories_used: number; categories_available: number; connectors_available: number;
  by_category: Record<string, { total: number; healthy: number; down: number; degraded: number }>;
  calls_7d: number; failures_7d: number; retries_7d: number; fallbacks_7d: number;
  success_rate: number;
  needs_attention: Integration[];
}

export interface HealthResult {
  integration_id: string; name: string; status: string;
  checked: boolean; ok?: boolean; latency_ms?: number | null;
  error?: string | null; reason?: string;
}

export interface CallResult {
  ok: boolean; status_code: number | null; attempts: number; latency_ms: number;
  error?: string; integration_id: string; name: string; fell_back_from: string | null;
}

/** The inbound webhook URL an external system should POST to. */
export const inboundUrl = (token: string) =>
  `${window.location.origin}/api/v1/integrations/inbound/${token}`;

export const integrationApi = {
  catalog: async () => (await api.get<IntegrationCatalog>('/integrations/catalog')).data,
  dashboard: async () => (await api.get<IntegrationDashboard>('/integrations/dashboard')).data,

  list: async (params: any = {}) => (await api.get<Integration[]>('/integrations', { params })).data,
  get: async (id: string) => (await api.get<Integration>(`/integrations/${id}`)).data,
  create: async (payload: any) => (await api.post<Integration>('/integrations', payload)).data,
  update: async (id: string, payload: any) =>
    (await api.patch<Integration>(`/integrations/${id}`, payload)).data,
  remove: async (id: string) => (await api.delete(`/integrations/${id}`)).data,

  syncManaged: async () =>
    (await api.post<{ discovered: number; created: number; updated: number }>('/integrations/sync-managed')).data,

  healthCheck: async (id: string) => (await api.post<HealthResult>(`/integrations/${id}/health-check`)).data,
  healthCheckAll: async () =>
    (await api.post<{ checked: number; healthy: number; failed: number }>('/integrations/health-check')).data,
  call: async (id: string, payload: any) =>
    (await api.post<CallResult>(`/integrations/${id}/call`, payload)).data,
  rotateInbound: async (id: string) =>
    (await api.post<Integration>(`/integrations/${id}/rotate-inbound`)).data,

  logs: async (params: any = {}) => (await api.get<IntegrationLog[]>('/integrations/logs', { params })).data,
  events: async (params: any = {}) => (await api.get<IntegrationEvent[]>('/integrations/events', { params })).data,
  exportCsv: async () => (await api.get<string>('/integrations/export')).data,
};

export const STATUS_TONE: Record<string, string> = {
  healthy: 'bg-emerald-500/15 text-emerald-300',
  degraded: 'bg-amber-500/15 text-amber-300',
  down: 'bg-red-500/15 text-red-300',
  unconfigured: 'bg-slate-500/15 text-slate-300',
  disabled: 'bg-slate-700/40 text-slate-500',
};

export const LOG_TONE: Record<string, string> = {
  success: 'bg-emerald-500/15 text-emerald-300',
  failed: 'bg-red-500/15 text-red-300',
  fallback: 'bg-sky-500/15 text-sky-300',
  retrying: 'bg-amber-500/15 text-amber-300',
};
