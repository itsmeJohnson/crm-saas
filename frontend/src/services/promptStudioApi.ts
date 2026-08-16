import { api } from './api';

export interface Prompt {
  id: string; key: string; name: string; task_type: string; status: string; version: number;
  is_active: boolean; is_builtin: boolean; usage_count: number; variables: string[]; tags: string[];
  description: string | null; model_override: string | null; provider_override: string | null;
  temperature: number | null; created_by: string | null; reviewed_by: string | null;
  review_note: string | null; last_tested_at: string | null; updated_at: string | null;
  system_prompt?: string | null; template?: string;
}

export interface PromptVersion {
  version: number; name: string; task_type: string; system_prompt: string | null; template: string;
  model_override: string | null; provider_override: string | null; temperature: number | null;
  edited_by: string | null; change_note: string | null; created_at: string | null;
}

export interface TestResult {
  rendered_prompt: string; rendered_system_prompt: string | null;
  declared_variables: string[]; missing_variables: string[]; ran: boolean;
  output?: string; provider?: string; model?: string;
  tokens?: { prompt: number; completion: number; total: number }; cached?: boolean;
}

export interface PromptAnalytics {
  totals: { prompts: number; builtin: number; custom: number; total_usage: number; active: number; pending_review: number };
  by_status: Record<string, number>; by_category: Record<string, number>;
  top_used: { id: string; key: string; name: string; task_type: string; usage_count: number }[];
  pending_queue: { id: string; name: string; key: string }[];
}

export interface PromptDashboard { prompts: number; active: number; pending_review: number; total_usage: number; categories: number; }

export const promptStudioApi = {
  dashboard: async () => (await api.get<PromptDashboard>('/prompt-studio/dashboard')).data,
  analytics: async () => (await api.get<PromptAnalytics>('/prompt-studio/analytics')).data,
  categories: async () => (await api.get<{ categories: { task_type: string; count: number }[]; tags: { tag: string; count: number }[] }>('/prompt-studio/categories')).data,
  library: async () => (await api.get<{ count: number; items: Prompt[] }>('/prompt-studio/library')).data,
  exportCsv: async () => (await api.get<string>('/prompt-studio/export')).data,

  list: async (params: any = {}) => (await api.get<{ total: number; items: Prompt[] }>('/prompt-studio/prompts', { params })).data,
  get: async (id: string) => (await api.get<Prompt>(`/prompt-studio/prompts/${id}`)).data,
  create: async (payload: any) => (await api.post<Prompt>('/prompt-studio/prompts', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Prompt>(`/prompt-studio/prompts/${id}`, payload)).data,
  remove: async (id: string) => (await api.delete(`/prompt-studio/prompts/${id}`)).data,
  duplicate: async (id: string) => (await api.post<Prompt>(`/prompt-studio/prompts/${id}/duplicate`)).data,
  versions: async (id: string) => (await api.get<PromptVersion[]>(`/prompt-studio/prompts/${id}/versions`)).data,
  restore: async (id: string, version: number) => (await api.post<Prompt>(`/prompt-studio/prompts/${id}/versions/${version}/restore`)).data,

  submit: async (id: string) => (await api.post(`/prompt-studio/prompts/${id}/submit`)).data,
  approve: async (id: string, note?: string) => (await api.post(`/prompt-studio/prompts/${id}/approve`, { note })).data,
  reject: async (id: string, note?: string) => (await api.post(`/prompt-studio/prompts/${id}/reject`, { note })).data,
  archive: async (id: string) => (await api.post(`/prompt-studio/prompts/${id}/archive`)).data,

  test: async (payload: any) => (await api.post<TestResult>('/prompt-studio/test', payload)).data,
};

export const PROMPT_STATUS_TONE: Record<string, string> = {
  draft: 'bg-slate-500/15 text-slate-300', pending_review: 'bg-amber-500/15 text-amber-300',
  approved: 'bg-emerald-500/15 text-emerald-300', rejected: 'bg-red-500/15 text-red-300',
  archived: 'bg-slate-600/20 text-slate-400',
};
