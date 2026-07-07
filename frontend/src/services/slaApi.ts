import { api } from './api';

export interface PriorityTier { level: string; response_hours?: number | null; resolution_hours?: number | null; }

export interface SLAPolicy {
  id: string;
  name: string;
  description: string | null;
  entity_type: string;
  metric: string;
  conditions: any | null;
  on_breach: string;
  is_active: boolean;
  breach_count: number;
  priority_field: string;
  priorities: PriorityTier[] | null;
  response_hours: number | null;
  resolution_hours: number | null;
  business_hours_only: boolean;
  skip_holidays: boolean;
  escalate_after_hours: number | null;
  escalate_to_role: string | null;
  created_at: string | null;
}

export interface SLATracker {
  id: string;
  policy_id: string;
  entity_type: string;
  entity_id: string;
  priority_level: string | null;
  status: string;
  response_hours: number | null;
  resolution_hours: number | null;
  started_at: string | null;
  response_due_at: string | null;
  resolution_due_at: string | null;
  first_response_at: string | null;
  resolved_at: string | null;
  response_breached: boolean;
  resolution_breached: boolean;
  breach_type: string | null;
  escalated: boolean;
  paused_seconds: number;
}

export interface SLABreach {
  id: string;
  policy_id: string;
  entity_type: string;
  entity_id: string;
  metric: string;
  hours_elapsed: number;
  resolved: boolean;
  breached_at: string | null;
}

export interface SLACatalog {
  entity_types: string[];
  metrics: string[];
  breach_actions: string[];
  tracker_statuses: string[];
}

export interface SLADashboard {
  policies: number;
  active: number;
  compliance_rate: number;
  open_breaches: number;
  at_risk: number;
  running: number;
  recent_breaches: SLATracker[];
}

export interface SLAReport {
  policies: number;
  active: number;
  total_trackers: number;
  met: number;
  breached: number;
  compliance_rate: number;
  open_breaches: number;
  by_status: Record<string, number>;
  avg_response_hours: number;
}

export const slaApi = {
  catalog: async () => (await api.get<SLACatalog>('/sla/catalog')).data,
  dashboard: async () => (await api.get<SLADashboard>('/sla/dashboard')).data,
  report: async () => (await api.get<SLAReport>('/sla/report')).data,

  listPolicies: async () => (await api.get<SLAPolicy[]>('/sla/policies')).data,
  createPolicy: async (payload: any) => (await api.post<SLAPolicy>('/sla/policies', payload)).data,
  updatePolicy: async (id: string, payload: any) => (await api.patch<SLAPolicy>(`/sla/policies/${id}`, payload)).data,
  removePolicy: async (id: string) => { await api.delete(`/sla/policies/${id}`); },
  enablePolicy: async (id: string, enabled: boolean) => (await api.post<SLAPolicy>(`/sla/policies/${id}/enable`, { enabled })).data,

  trackers: async (params: { status?: string; breached?: boolean; limit?: number } = {}) =>
    (await api.get<SLATracker[]>('/sla/trackers', { params })).data,
  pause: async (id: string, reason?: string) => (await api.post<SLATracker>(`/sla/trackers/${id}/pause`, { reason })).data,
  resume: async (id: string) => (await api.post<SLATracker>(`/sla/trackers/${id}/resume`, {})).data,

  breaches: async (params: { resolved?: boolean; limit?: number } = {}) =>
    (await api.get<SLABreach[]>('/sla/breaches', { params })).data,
  scan: async () => (await api.post<{ breaches: number }>('/sla/scan', {})).data,
};
