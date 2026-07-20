import { api } from './api';

export interface AiSettings {
  is_enabled: boolean; default_provider: string; default_model: string; temperature: number;
  max_tokens: number; daily_request_limit: number; monthly_budget_usd: number;
  cache_enabled: boolean; cache_ttl_minutes: number; streaming_enabled: boolean;
  memory_messages: number; context_max_chars: number;
}

export interface AiProvider {
  id: string; provider: string; name: string; api_key: string | null; base_url: string | null;
  deployment: string | null; api_version: string | null; default_model: string;
  models: { model: string; input_cost_per_1k?: number; output_cost_per_1k?: number }[];
  priority: number; is_active: boolean; created_at: string | null;
}

export interface AiTemplate {
  id: string; key: string; name: string; task_type: string; system_prompt: string | null;
  template: string; model_override: string | null; provider_override: string | null;
  temperature: number | null; is_active: boolean; is_builtin: boolean; usage_count: number;
}

export interface AiGenerateResult {
  text: string; model: string; provider: string;
  tokens: { prompt: number; completion: number; total: number };
  cost_usd: number; cached: boolean; fallback_used: boolean; task_type: string;
  conversation_id?: string | null;
}

export interface AiConversation {
  id: string; title: string; context_type: string | null; context_id: string | null;
  message_count: number; last_message_at: string | null; created_at: string | null;
}

export interface AiMessage {
  id: string; role: string; content: string; model: string | null; provider: string | null;
  tokens: number; cost_usd: number; created_at: string | null;
}

export interface AiUsageDashboard {
  days: number; requests: number; failed: number; cached: number; fallbacks: number;
  tokens: number; cost_usd: number; error_rate: number; cache_hit_rate: number; avg_latency_ms: number;
  by_provider: Record<string, { requests: number; tokens: number; cost: number; failed: number }>;
  by_task: Record<string, number>;
  by_day: { day: string; requests: number; cost: number }[];
  budget: { monthly_budget_usd: number; spent_this_month_usd: number; daily_request_limit: number };
}

export const aiApi = {
  generate: async (payload: any) => (await api.post<AiGenerateResult>('/ai/generate', payload)).data,
  chat: async (payload: { message: string; conversation_id?: string; context_type?: string; context_id?: string }) =>
    (await api.post<AiGenerateResult>('/ai/chat', payload)).data,
  conversations: async () => (await api.get<AiConversation[]>('/ai/conversations')).data,
  messages: async (id: string) => (await api.get<AiMessage[]>(`/ai/conversations/${id}/messages`)).data,

  settings: async () => (await api.get<AiSettings>('/ai/settings')).data,
  updateSettings: async (payload: Partial<AiSettings>) => (await api.patch<AiSettings>('/ai/settings', payload)).data,

  providers: async () => (await api.get<AiProvider[]>('/ai/providers')).data,
  createProvider: async (payload: any) => (await api.post<AiProvider>('/ai/providers', payload)).data,
  updateProvider: async (id: string, payload: any) => (await api.patch<AiProvider>(`/ai/providers/${id}`, payload)).data,
  removeProvider: async (id: string) => { await api.delete(`/ai/providers/${id}`); },
  testProvider: async (id: string) =>
    (await api.post(`/ai/providers/${id}/test`, {})).data as { status: string; latency_ms: number; error: string | null },

  templates: async () => (await api.get<AiTemplate[]>('/ai/templates')).data,
  createTemplate: async (payload: any) => (await api.post<AiTemplate>('/ai/templates', payload)).data,
  updateTemplate: async (id: string, payload: any) => (await api.patch<AiTemplate>(`/ai/templates/${id}`, payload)).data,

  usage: async (days = 30) => (await api.get<AiUsageDashboard>('/ai/usage/dashboard', { params: { days } })).data,
  logs: async (limit = 100) => (await api.get<any[]>('/ai/usage/logs', { params: { limit } })).data,

  crmSummarize: async (contextType: string, contextId: string) =>
    (await api.post<AiGenerateResult>('/ai/crm/summarize', { context_type: contextType, context_id: contextId })).data,
  draftEmail: async (contextType: string, contextId: string, goal: string) =>
    (await api.post<AiGenerateResult>('/ai/crm/draft-email', { context_type: contextType, context_id: contextId, goal })).data,
  kbAsk: async (question: string) => (await api.post<AiGenerateResult>('/ai/knowledge/ask', { question })).data,
  summarize: async (text: string, length = 5) =>
    (await api.post<AiGenerateResult>('/ai/documents/summarize', { text, length })).data,
};
