import { api } from './api';

export interface Schedule {
  id: string;
  name: string;
  description: string | null;
  task_type: string;
  task_config: any | null;
  schedule_kind: string;
  cron_expr: string | null;
  time_of_day: string | null;
  day_of_week: number | null;
  day_of_month: number | null;
  interval_minutes: number | null;
  timezone: string;
  business_hours_only: boolean;
  skip_holidays: boolean;
  is_active: boolean;
  max_retries: number;
  last_run_at: string | null;
  last_status: string | null;
  next_run_at: string | null;
  run_count: number;
  fail_count: number;
  skip_count: number;
}

export interface ScheduleRun {
  id: string;
  schedule_id: string;
  status: string;
  reason: string | null;
  triggered_by: string;
  attempts: number;
  error: string | null;
  result: any | null;
  scheduled_for: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
}

export interface SchedulerCatalog {
  task_types: string[];
  schedule_kinds: string[];
  weekdays: string[];
}

export interface SchedulerDashboard {
  total: number;
  active: number;
  success_rate: number;
  failed: number;
  skipped: number;
  upcoming: { id: string; name: string; next_run_at: string | null }[];
  recent: ScheduleRun[];
}

export interface SchedulerReport {
  total: number;
  active: number;
  inactive: number;
  runs: number;
  failed: number;
  skipped: number;
  success_rate: number;
}

export const schedulerApi = {
  catalog: async () => (await api.get<SchedulerCatalog>('/scheduler/catalog')).data,
  dashboard: async () => (await api.get<SchedulerDashboard>('/scheduler/dashboard')).data,
  report: async () => (await api.get<SchedulerReport>('/scheduler/report')).data,

  list: async (params: { active_only?: boolean } = {}) => (await api.get<Schedule[]>('/scheduler', { params })).data,
  get: async (id: string) => (await api.get<Schedule>(`/scheduler/${id}`)).data,
  create: async (payload: any) => (await api.post<Schedule>('/scheduler', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Schedule>(`/scheduler/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/scheduler/${id}`); },
  enable: async (id: string, enabled: boolean) => (await api.post<Schedule>(`/scheduler/${id}/enable`, { enabled })).data,
  runNow: async (id: string) => (await api.post<ScheduleRun>(`/scheduler/${id}/run`, {})).data,
  nextRuns: async (id: string, count = 5) => (await api.get<{ next_runs: string[] }>(`/scheduler/${id}/next-runs`, { params: { count } })).data,

  runs: async (params: { schedule_id?: string; status?: string; limit?: number } = {}) =>
    (await api.get<ScheduleRun[]>('/scheduler/runs', { params })).data,
};
