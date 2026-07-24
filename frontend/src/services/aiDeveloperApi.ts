import { api } from './api';

export interface ApiKey {
  id: string; name: string; environment: string;
  key_prefix: string; masked_key: string; scopes: string[];
  rate_limit_per_min: number; daily_quota: number;
  allowed_providers: string[]; allowed_models: string[]; allowed_ips: string[];
  expires_at: string | null; last_used_at: string | null; use_count: number;
  is_active: boolean; revoked_at: string | null; created_at: string | null;
  api_key?: string; // returned once on create/rotate
}

export interface DevWebhook {
  id: string; name: string; url: string; events: string[]; subscribes_all: boolean;
  is_active: boolean; max_attempts: number; delivered_count: number; failed_count: number;
  last_status: string | null; last_delivery_at: string | null; created_at: string | null;
  secret: string;
}

export interface WebhookDelivery {
  id: string; webhook_id: string; event_type: string; status: string; attempts: number;
  response_code: number | null; error: string | null; duration_ms: number | null;
  next_retry_at: string | null; delivered_at: string | null;
  payload: Record<string, any>; created_at: string | null;
}

export interface ApiRequestLog {
  id: string; api_key_id: string | null; endpoint: string; method: string; api_version: string;
  status_code: number; latency_ms: number; tokens: number; cost_usd: number;
  provider: string | null; model: string | null; error: string | null; created_at: string | null;
}

export interface SdkLanguage {
  key: string; label: string; filename: string; language: string;
  install: string; min_version: string;
}

export interface DevPortal {
  base_url: string; current_version: string;
  versions: { version: string; status: string; released: string; sunset: string | null; notes: string }[];
  keys_total: number; keys_active: number;
  webhooks_total: number; webhooks_active: number;
  requests_30d: number; failed_30d: number; throttled_30d: number;
  tokens_30d: number; cost_30d: number; success_rate: number;
  dead_letter_deliveries: number;
  sdk_languages: SdkLanguage[];
  scopes: { key: string; description: string }[];
  webhook_events: { key: string; description: string }[];
  keys: ApiKey[];
}

export interface DevDocs {
  title: string; version: string; base_url: string;
  authentication: { schemes: string[]; key_format: string; notes: string };
  rate_limits: { per_minute: string; daily_quota: string; headers: string[] };
  versioning: { current: string; versions: any[]; header: string; policy: string };
  scopes: { key: string; description: string }[];
  endpoints: {
    method: string; path: string; scope: string | null; summary: string;
    description?: string; request: Record<string, string>; response: Record<string, string>;
  }[];
  webhooks: {
    events: { key: string; description: string }[];
    signature_header: string; signature_scheme: string;
    retry_backoff_minutes: number[]; headers: string[];
  };
  errors: { status: number; meaning: string }[];
  sdks: SdkLanguage[];
}

export interface DevAnalytics {
  window_days: number; requests: number; errors: number; throttled: number;
  tokens: number; cost_usd: number; p50_latency_ms: number; p95_latency_ms: number;
  by_endpoint: Record<string, { requests: number; errors: number; tokens: number; avg_latency_ms: number }>;
  by_key: Record<string, { requests: number; errors: number; tokens: number; cost_usd: number }>;
  by_day: Record<string, number>;
  by_status: Record<string, number>;
}

export interface CodeExample {
  key: string; title: string; language: string; code: string;
}

/** The public API's base URL for whatever host the app is served from. */
export const publicApiBaseUrl = () => `${window.location.origin}/api/v1/ai-api`;

export const aiDeveloperApi = {
  catalog: async () => (await api.get<any>('/ai-developer/catalog')).data,
  portal: async () => (await api.get<DevPortal>('/ai-developer/portal', { params: { base_url: publicApiBaseUrl() } })).data,

  listKeys: async () => (await api.get<ApiKey[]>('/ai-developer/keys')).data,
  createKey: async (payload: Partial<ApiKey> & { name: string; expires_in_days?: number | null }) =>
    (await api.post<ApiKey>('/ai-developer/keys', payload)).data,
  updateKey: async (id: string, payload: Partial<ApiKey>) =>
    (await api.patch<ApiKey>(`/ai-developer/keys/${id}`, payload)).data,
  rotateKey: async (id: string) => (await api.post<ApiKey>(`/ai-developer/keys/${id}/rotate`)).data,
  revokeKey: async (id: string) => (await api.post<ApiKey>(`/ai-developer/keys/${id}/revoke`)).data,
  deleteKey: async (id: string) => (await api.delete(`/ai-developer/keys/${id}`)).data,

  listWebhooks: async () => (await api.get<DevWebhook[]>('/ai-developer/webhooks')).data,
  createWebhook: async (payload: { name: string; url: string; events?: string[]; max_attempts?: number }) =>
    (await api.post<DevWebhook>('/ai-developer/webhooks', payload)).data,
  updateWebhook: async (id: string, payload: Partial<DevWebhook>) =>
    (await api.patch<DevWebhook>(`/ai-developer/webhooks/${id}`, payload)).data,
  rotateWebhookSecret: async (id: string) =>
    (await api.post<DevWebhook>(`/ai-developer/webhooks/${id}/rotate-secret`)).data,
  testWebhook: async (id: string) => (await api.post<WebhookDelivery>(`/ai-developer/webhooks/${id}/test`)).data,
  deleteWebhook: async (id: string) => (await api.delete(`/ai-developer/webhooks/${id}`)).data,
  deliveries: async (params: any = {}) =>
    (await api.get<WebhookDelivery[]>('/ai-developer/webhooks/deliveries', { params })).data,
  replayDelivery: async (id: string) =>
    (await api.post<WebhookDelivery>(`/ai-developer/webhooks/deliveries/${id}/replay`)).data,

  analytics: async (days = 30) => (await api.get<DevAnalytics>('/ai-developer/analytics', { params: { days } })).data,
  requests: async (params: any = {}) => (await api.get<ApiRequestLog[]>('/ai-developer/requests', { params })).data,
  exportCsv: async (days = 30) => (await api.get<string>('/ai-developer/export', { params: { days } })).data,

  docs: async () => (await api.get<DevDocs>('/ai-developer/docs', { params: { base_url: publicApiBaseUrl() } })).data,
  openapi: async () => (await api.get<any>('/ai-developer/openapi', { params: { base_url: publicApiBaseUrl() } })).data,
  examples: async () => (await api.get<CodeExample[]>('/ai-developer/examples', { params: { base_url: publicApiBaseUrl() } })).data,
  sdkList: async () => (await api.get<SdkLanguage[]>('/ai-developer/sdk')).data,
  sdk: async (language: string) =>
    (await api.get<SdkLanguage & { source: string; version: string; base_url: string }>(
      `/ai-developer/sdk/${language}`, { params: { base_url: publicApiBaseUrl() } })).data,
};

export const DELIVERY_TONE: Record<string, string> = {
  success: 'bg-emerald-500/15 text-emerald-300',
  failed: 'bg-amber-500/15 text-amber-300',
  dead_letter: 'bg-red-500/15 text-red-300',
  pending: 'bg-sky-500/15 text-sky-300',
};

export const statusTone = (code: number) =>
  code >= 500 ? 'text-red-400' : code === 429 ? 'text-amber-400' : code >= 400 ? 'text-orange-400' : 'text-emerald-400';
