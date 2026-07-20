import { api } from './api';

export interface QueueJob {
  id: string;
  queue: string;
  job_type: string;
  priority: number;
  status: string;
  attempts: number;
  max_attempts: number;
  payload: any | null;
  result: any | null;
  error: string | null;
  run_at: string | null;
  started_at: string | null;
  finished_at: string | null;
  duration_ms: number | null;
  created_at: string | null;
}

export interface QueueWorker {
  id: string;
  name: string;
  status: string;
  last_heartbeat: string | null;
  jobs_processed: number;
  current_job_id: string | null;
  queues: string | null;
}

export interface QueueCatalog {
  queues: string[];
  job_types: string[];
  statuses: string[];
  queue_for_type: Record<string, string>;
}

export interface QueueDashboard {
  pending: number;
  running: number;
  succeeded: number;
  failed: number;
  dead_letter: number;
  workers: number;
  recent: QueueJob[];
}

export interface QueueReport {
  total: number;
  by_queue: Record<string, Record<string, number>>;
  success_rate: number;
  avg_duration_ms: number;
}

export const queueApi = {
  catalog: async () => (await api.get<QueueCatalog>('/queue/catalog')).data,
  dashboard: async () => (await api.get<QueueDashboard>('/queue/dashboard')).data,
  report: async () => (await api.get<QueueReport>('/queue/report')).data,

  enqueue: async (payload: any) => (await api.post<QueueJob>('/queue/jobs', payload)).data,
  jobs: async (params: { queue?: string; status?: string; scheduled?: boolean; limit?: number } = {}) =>
    (await api.get<QueueJob[]>('/queue/jobs', { params })).data,
  scheduled: async (params: { limit?: number } = {}) =>
    (await api.get<QueueJob[]>('/queue/jobs/scheduled', { params })).data,
  deadLetter: async (params: { limit?: number } = {}) =>
    (await api.get<QueueJob[]>('/queue/dead-letter', { params })).data,
  get: async (id: string) => (await api.get<QueueJob>(`/queue/jobs/${id}`)).data,
  cancel: async (id: string) => (await api.post<QueueJob>(`/queue/jobs/${id}/cancel`, {})).data,
  retry: async (id: string) => (await api.post<QueueJob>(`/queue/jobs/${id}/retry`, {})).data,
  purge: async (status: string) => (await api.post<{ purged: number }>('/queue/purge', { status })).data,

  workers: async () => (await api.get<QueueWorker[]>('/queue/workers')).data,
};
