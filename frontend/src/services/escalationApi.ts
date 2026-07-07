import { api } from './api';

export interface EscalationLevel { after_hours: number; escalate_to: string; value?: string | null; notify?: boolean; }

export interface EscalationRule {
  id: string;
  name: string;
  description: string | null;
  entity_type: string;
  trigger_condition: string;
  conditions: any | null;
  levels: EscalationLevel[];
  business_hours_only: boolean;
  is_active: boolean;
  run_count: number;
  escalation_count: number;
  created_at: string | null;
}

export interface EscalationEvent {
  id: string;
  rule_id: string;
  entity_type: string;
  entity_id: string;
  level: number;
  escalate_to: string | null;
  escalated_to_user_id: string | null;
  reason: string | null;
  hours_elapsed: number | null;
  escalated_at: string | null;
}

export interface EscalationCatalog {
  entity_types: string[];
  trigger_conditions: string[];
  escalate_targets: string[];
}

export interface EscalationDashboard {
  rules: number;
  active: number;
  escalations: number;
  last_7_days: number;
  by_entity: Record<string, number>;
  recent: EscalationEvent[];
}

export interface EscalationReport {
  rules: number;
  active: number;
  escalations: number;
  by_entity: Record<string, number>;
  by_level: Record<string, number>;
}

export const escalationApi = {
  catalog: async () => (await api.get<EscalationCatalog>('/escalation/catalog')).data,
  dashboard: async () => (await api.get<EscalationDashboard>('/escalation/dashboard')).data,
  report: async () => (await api.get<EscalationReport>('/escalation/report')).data,

  listRules: async () => (await api.get<EscalationRule[]>('/escalation/rules')).data,
  createRule: async (payload: any) => (await api.post<EscalationRule>('/escalation/rules', payload)).data,
  updateRule: async (id: string, payload: any) => (await api.patch<EscalationRule>(`/escalation/rules/${id}`, payload)).data,
  removeRule: async (id: string) => { await api.delete(`/escalation/rules/${id}`); },
  enableRule: async (id: string, enabled: boolean) => (await api.post<EscalationRule>(`/escalation/rules/${id}/enable`, { enabled })).data,

  events: async (params: { rule_id?: string; entity_type?: string; limit?: number } = {}) =>
    (await api.get<EscalationEvent[]>('/escalation/events', { params })).data,
  scan: async () => (await api.post<{ escalations: number }>('/escalation/scan', {})).data,
};
