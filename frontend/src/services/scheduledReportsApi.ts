import { api } from './api';

export interface SchedMeta { frequencies: string[]; formats: string[]; channels: string[]; }

export interface ReportSchedule {
  id: string; report_id: string; report_name: string; name: string; frequency: string;
  formats: string[]; channels: string[]; recipients: string[]; extra_emails: string[];
  is_active: boolean; max_retries: number; fail_streak: number;
  next_run_at: string | null; last_run_at: string | null; last_status: string | null;
  run_count: number; created_at: string | null;
}

export interface DeliveryLog {
  id: string; schedule_id: string; schedule_name: string | null; status: string; attempt: number;
  triggered_by: string; frequency: string | null; formats: string[]; channels: string[];
  recipient_count: number; rows_count: number; detail: any; error: string | null;
  started_at: string | null; finished_at: string | null;
}

export interface SchedDashboard {
  schedules: number; active: number; deliveries: number;
  by_status: { success: number; partial: number; failed: number };
  success_rate: number; upcoming: ReportSchedule[];
}

export const scheduledReportsApi = {
  meta: async () => (await api.get<SchedMeta>('/scheduled-reports/meta')).data,
  dashboard: async () => (await api.get<SchedDashboard>('/scheduled-reports/dashboard')).data,
  history: async (params: { schedule_id?: string; limit?: number } = {}) =>
    (await api.get<DeliveryLog[]>('/scheduled-reports/history', { params })).data,
  retryDelivery: async (deliveryId: string) =>
    (await api.post<DeliveryLog>(`/scheduled-reports/deliveries/${deliveryId}/retry`, {})).data,

  list: async () => (await api.get<ReportSchedule[]>('/scheduled-reports')).data,
  create: async (payload: any) => (await api.post<ReportSchedule>('/scheduled-reports', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<ReportSchedule>(`/scheduled-reports/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/scheduled-reports/${id}`); },
  runNow: async (id: string) => (await api.post<DeliveryLog>(`/scheduled-reports/${id}/run`, {})).data,
};
