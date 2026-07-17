import { api } from './api';

export interface ComplianceCategory { key: string; label: string; }

export interface AuditRow {
  id: string; action: string; category: string; resource_type: string; resource_id: string | null;
  actor_user_id: string | null; actor_name: string; metadata: any; created_at: string | null;
}

export interface LoginRow {
  id: string; event: string; success: boolean; user_id: string | null; user_name: string;
  ip_address: string | null; browser: string | null; description: string | null; created_at: string | null;
}

export interface ComplianceDashboard {
  counts: { last_24h: number; last_7d: number; last_30d: number };
  by_category: { key: string; label: string; count: number }[];
  top_actors: { user_id: string; name: string; events: number }[];
  failed_logins_30d: number;
  recent_sensitive: AuditRow[];
}

export interface ComplianceReport {
  generated_at: string; days: number; window_start: string;
  total_events: number; unique_actors: number; failed_logins: number;
  categories: { key: string; label: string; count: number; top_actions: { action: string; count: number }[] }[];
  permission_changes: AuditRow[]; configuration_changes: AuditRow[]; data_exports: AuditRow[];
}

export const complianceApi = {
  meta: async () => (await api.get<{ categories: ComplianceCategory[] }>('/compliance/meta')).data,
  dashboard: async () => (await api.get<ComplianceDashboard>('/compliance/dashboard')).data,
  logs: async (params: { category?: string; action?: string; actor_user_id?: string; q?: string; days?: number; limit?: number; offset?: number } = {}) =>
    (await api.get<{ total: number; rows: AuditRow[] }>('/compliance/logs', { params })).data,
  loginHistory: async (params: { user_id?: string; days?: number; limit?: number } = {}) =>
    (await api.get<LoginRow[]>('/compliance/login-history', { params })).data,
  userActivity: async (userId: string, days = 30) =>
    (await api.get(`/compliance/user-activity/${userId}`, { params: { days } })).data as any,
  report: async (days = 30) => (await api.get<ComplianceReport>('/compliance/report', { params: { days } })).data,
  exportCsv: async (params: { category?: string; days?: number } = {}) =>
    (await api.get<string>('/compliance/export', { params, responseType: 'text' as any })).data,
};
