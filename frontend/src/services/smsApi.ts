import { api } from './api';

export interface SmsSettings {
  id: string;
  organization_id: string;
  provider: string;
  account_sid: string | null;
  sender_id: string | null;
  sms_priority: string;
  webhook_token: string | null;
  daily_limit: number;
  is_active: boolean;
}

export interface SmsItem {
  id: string;
  direction: 'INBOUND' | 'OUTBOUND' | null;
  body: string | null;
  sms_status: string | null;
  error: string | null;
  retry_count: number;
  segments: number | null;
  to_number: string | null;
  from_number: string | null;
  timestamp: string;
  agent_id: string | null;
  agent_name: string | null;
  lead_id: string | null;
  contact_id: string | null;
  company_id: string | null;
}

export interface SmsHistory {
  items: SmsItem[];
  total: number;
}

export interface ReportBucket {
  label: string;
  count: number;
}

export interface SmsReport {
  total: number;
  outbound: number;
  inbound: number;
  delivered: number;
  failed: number;
  segments: number;
  delivery_rate: number;
  by_status: ReportBucket[];
  by_direction: ReportBucket[];
  by_day: ReportBucket[];
}

export interface BulkRecipient {
  to_number?: string;
  lead_id?: string;
  contact_id?: string;
  company_id?: string;
}

export interface SmsBulkResult {
  total: number;
  queued: number;
  failed: number;
  activity_ids: string[];
}

export interface SmsHistoryFilters {
  direction?: string;
  sms_status?: string;
  search?: string;
  skip?: number;
  limit?: number;
}

export const smsApi = {
  getSettings: async () => (await api.get<SmsSettings>('/sms/settings')).data,
  updateSettings: async (payload: Partial<SmsSettings> & { auth_token?: string; regenerate_webhook_token?: boolean }) =>
    (await api.put<SmsSettings>('/sms/settings', payload)).data,

  send: async (payload: { body: string; subject?: string; to_number?: string; lead_id?: string; contact_id?: string; company_id?: string }) =>
    (await api.post<SmsItem>('/sms/send', payload)).data,

  sendBulk: async (payload: { body: string; subject?: string; recipients: BulkRecipient[] }) =>
    (await api.post<SmsBulkResult>('/sms/send-bulk', payload)).data,

  retry: async (activityId: string) => (await api.post<SmsItem>(`/sms/${activityId}/retry`)).data,

  messages: async (filters: SmsHistoryFilters = {}) =>
    (await api.get<SmsHistory>('/sms/messages', { params: filters })).data,

  reports: async (params: { date_from?: string; date_to?: string } = {}) =>
    (await api.get<SmsReport>('/sms/reports', { params })).data,
};
