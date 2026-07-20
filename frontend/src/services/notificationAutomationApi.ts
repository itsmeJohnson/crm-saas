import { api } from './api';

export interface NotifRecipient { type: string; value?: string | null; }

export interface NotifRule {
  id: string;
  name: string;
  description: string | null;
  trigger_event: string;
  entity_type: string | null;
  conditions: any | null;
  recipients: NotifRecipient[];
  channels: string[];
  template_key: string | null;
  title: string | null;
  body: string | null;
  category: string;
  priority: string;
  digest: boolean;
  is_active: boolean;
  run_count: number;
  notif_count: number;
  created_at: string | null;
}

export interface NotifDelivery {
  id: string;
  rule_id: string | null;
  user_id: string;
  channel: string;
  status: string;
  attempts: number;
  error: string | null;
  title: string | null;
  queue_job_id: string | null;
  sent_at: string | null;
  created_at: string | null;
}

export interface NotifTemplate {
  template_key: string;
  template_name: string;
  channel: string;
  subject: string | null;
  body: string;
  variables: string[] | null;
  category: string;
  description: string | null;
  is_active: boolean;
}

export interface NotifCatalog {
  trigger_events: string[];
  recipient_types: string[];
  channels: string[];
  priorities: string[];
}

export interface NotifAutomationDashboard {
  rules: number;
  active_rules: number;
  deliveries: number;
  delivery_rate: number;
  pending_digest: number;
  failed: number;
  recent: NotifDelivery[];
}

export interface NotifAutomationReport {
  rules: number;
  active_rules: number;
  deliveries: number;
  delivery_rate: number;
  by_channel: Record<string, number>;
  by_status: Record<string, number>;
  pending_digest: number;
}

const BASE = '/notification-automation';

export const notificationAutomationApi = {
  catalog: async () => (await api.get<NotifCatalog>(`${BASE}/catalog`)).data,
  dashboard: async () => (await api.get<NotifAutomationDashboard>(`${BASE}/dashboard`)).data,
  report: async () => (await api.get<NotifAutomationReport>(`${BASE}/report`)).data,

  listRules: async () => (await api.get<NotifRule[]>(`${BASE}/rules`)).data,
  createRule: async (payload: any) => (await api.post<NotifRule>(`${BASE}/rules`, payload)).data,
  updateRule: async (id: string, payload: any) => (await api.patch<NotifRule>(`${BASE}/rules/${id}`, payload)).data,
  removeRule: async (id: string) => { await api.delete(`${BASE}/rules/${id}`); },
  enableRule: async (id: string, enabled: boolean) => (await api.post<NotifRule>(`${BASE}/rules/${id}/enable`, { enabled })).data,

  deliveries: async (params: { status?: string; channel?: string; rule_id?: string; limit?: number } = {}) =>
    (await api.get<NotifDelivery[]>(`${BASE}/deliveries`, { params })).data,
  retryDelivery: async (id: string) => (await api.post<NotifDelivery>(`${BASE}/deliveries/${id}/retry`, {})).data,

  flushDigests: async () => (await api.post<{ digests_sent: number }>(`${BASE}/digests/flush`, {})).data,

  listTemplates: async () => (await api.get<NotifTemplate[]>(`${BASE}/templates`)).data,
  createTemplate: async (payload: any) => (await api.post<NotifTemplate>(`${BASE}/templates`, payload)).data,
  updateTemplate: async (key: string, payload: any) => (await api.patch<NotifTemplate>(`${BASE}/templates/${key}`, payload)).data,
  removeTemplate: async (key: string) => { await api.delete(`${BASE}/templates/${key}`); },
};
