import { api } from './api';

export interface AutomationJob {
  id: string | null;
  job_key: string;
  name: string;
  category: string;
  description: string | null;
  is_enabled: boolean;
  schedule: string;
  max_retries: number;
  last_run_at: string | null;
  last_status: string | null;
  next_run_at: string | null;
  run_count: number;
  fail_count: number;
}

export interface AutomationRun {
  id: string;
  job_key: string;
  status: string;
  triggered_by: string;
  items_processed: number;
  retry_count: number;
  error: string | null;
  duration_ms: number | null;
  started_at: string | null;
  finished_at: string | null;
}

export interface SLAPolicy {
  id: string;
  name: string;
  description: string | null;
  entity_type: string;
  metric: string;
  threshold_hours: number;
  conditions: any | null;
  on_breach: string;
  is_active: boolean;
  breach_count: number;
  created_at: string | null;
}

export interface SLABreach {
  id: string;
  policy_id: string;
  entity_type: string;
  entity_id: string;
  metric: string;
  hours_elapsed: number;
  resolved: boolean;
  notified: boolean;
  breached_at: string | null;
}

export interface ScheduledReport {
  id: string;
  name: string;
  report_type: string;
  frequency: string;
  channel: string;
  recipients: string[];
  is_active: boolean;
  last_sent_at: string | null;
  next_run_at: string | null;
  send_count: number;
}

export interface AutomationCatalog {
  jobs: { job_key: string; name: string; category: string; description: string; schedule: string }[];
  sla_metrics: string[];
  sla_breach_actions: string[];
  report_types: string[];
  frequencies: string[];
}

export interface AutomationDashboard {
  jobs: number;
  enabled: number;
  success_rate: number;
  open_breaches: number;
  active_reports: number;
  recent: AutomationRun[];
}

export interface AutomationReport {
  total_runs: number;
  failed: number;
  succeeded: number;
  success_rate: number;
  runs_by_job: Record<string, number>;
  open_breaches: number;
  active_reports: number;
}

export const automationApi = {
  catalog: async () => (await api.get<AutomationCatalog>('/automation/catalog')).data,
  dashboard: async () => (await api.get<AutomationDashboard>('/automation/dashboard')).data,
  report: async () => (await api.get<AutomationReport>('/automation/report')).data,

  // jobs
  listJobs: async () => (await api.get<AutomationJob[]>('/automation/jobs')).data,
  syncJobs: async () => (await api.post<AutomationJob[]>('/automation/jobs/sync', {})).data,
  enableJob: async (jobKey: string, enabled: boolean) =>
    (await api.post<AutomationJob>(`/automation/jobs/${jobKey}/enable`, { enabled })).data,
  configJob: async (jobKey: string, payload: { max_retries?: number; schedule?: string }) =>
    (await api.patch<AutomationJob>(`/automation/jobs/${jobKey}`, payload)).data,
  runJob: async (jobKey: string) => (await api.post<AutomationRun>(`/automation/jobs/${jobKey}/run`, {})).data,

  // runs
  runs: async (params: { job_key?: string; status?: string; limit?: number } = {}) =>
    (await api.get<AutomationRun[]>('/automation/runs', { params })).data,
  retryRun: async (id: string) => (await api.post<AutomationRun>(`/automation/runs/${id}/retry`, {})).data,

  // SLA
  listSla: async () => (await api.get<SLAPolicy[]>('/automation/sla')).data,
  createSla: async (payload: any) => (await api.post<SLAPolicy>('/automation/sla', payload)).data,
  updateSla: async (id: string, payload: any) => (await api.patch<SLAPolicy>(`/automation/sla/${id}`, payload)).data,
  removeSla: async (id: string) => { await api.delete(`/automation/sla/${id}`); },
  breaches: async (params: { resolved?: boolean; limit?: number } = {}) =>
    (await api.get<SLABreach[]>('/automation/breaches', { params })).data,
  resolveBreach: async (id: string) => (await api.post<SLABreach>(`/automation/breaches/${id}/resolve`, {})).data,

  // scheduled reports
  listReports: async () => (await api.get<ScheduledReport[]>('/automation/reports')).data,
  createReport: async (payload: any) => (await api.post<ScheduledReport>('/automation/reports', payload)).data,
  updateReport: async (id: string, payload: any) => (await api.patch<ScheduledReport>(`/automation/reports/${id}`, payload)).data,
  removeReport: async (id: string) => { await api.delete(`/automation/reports/${id}`); },
  runReport: async (id: string) => (await api.post<{ delivered: number }>(`/automation/reports/${id}/run`, {})).data,
};
