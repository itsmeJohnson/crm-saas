import { api } from './api';

export interface GovPolicy {
  is_enabled: boolean;
  pii_detection: boolean; pii_action: string; pii_types: string[];
  injection_protection: boolean; injection_action: string;
  content_filter: boolean; blocked_terms: string[];
  allowed_providers: string[]; allowed_models: string[];
  role_restrictions: Record<string, string[]>;
  max_prompt_chars: number; require_grounding: boolean; log_prompt_snippets: boolean;
}

export interface GovEvent {
  id: string; event_type: string; action_taken: string; rule: string | null;
  task_type: string | null; provider: string | null; model: string | null;
  findings: Record<string, any>; prompt_snippet: string | null;
  user_id: string | null; created_at: string | null;
}

export interface GovDashboard {
  policy_enabled: boolean; controls_active: number;
  controls: Record<string, boolean>;
  events_30d: number; blocked_30d: number; masked_30d: number; flagged_30d: number;
  by_type: Record<string, number>; by_action: Record<string, number>;
  recent: GovEvent[];
}

export interface GovPreview {
  pii: Record<string, number>; masked_preview: string;
  injection: string[]; blocked_terms: string[];
  length: number; max_prompt_chars: number;
}

export const aiGovernanceApi = {
  catalog: async () => (await api.get<{ pii_types: string[]; injection_rules: string[]; pii_actions: string[]; injection_actions: string[] }>('/ai-governance/catalog')).data,
  policy: async () => (await api.get<GovPolicy>('/ai-governance/policy')).data,
  updatePolicy: async (payload: Partial<GovPolicy>) => (await api.patch<GovPolicy>('/ai-governance/policy', payload)).data,
  dashboard: async () => (await api.get<GovDashboard>('/ai-governance/dashboard')).data,
  events: async (params: any = {}) => (await api.get<{ count: number; items: GovEvent[] }>('/ai-governance/events', { params })).data,
  report: async () => (await api.get<any>('/ai-governance/report')).data,
  exportCsv: async () => (await api.get<string>('/ai-governance/export')).data,
  preview: async (text: string) => (await api.post<GovPreview>('/ai-governance/preview', { text })).data,
};

export const GOV_ACTION_TONE: Record<string, string> = {
  blocked: 'bg-red-500/15 text-red-300', masked: 'bg-amber-500/15 text-amber-300',
  flagged: 'bg-sky-500/15 text-sky-300', allowed: 'bg-emerald-500/15 text-emerald-300',
};
