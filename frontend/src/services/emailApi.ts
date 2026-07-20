import { api } from './api';

export interface EmailSettings {
  id: string;
  organization_id: string;
  auth_method: string;
  from_email: string | null;
  from_name: string | null;
  smtp_host: string | null;
  smtp_port: number | null;
  smtp_username: string | null;
  smtp_use_tls: boolean;
  imap_host: string | null;
  imap_port: number | null;
  imap_username: string | null;
  imap_use_ssl: boolean;
  oauth_email: string | null;
  tracking_enabled: boolean;
  tracking_base_url: string | null;
  provider: string;
  is_active: boolean;
  last_synced_at: string | null;
}

export interface EmailItem {
  id: string;
  direction: 'INBOUND' | 'OUTBOUND' | null;
  subject: string;
  body: string | null;
  email_from: string | null;
  email_to: string | null;
  email_cc: string | null;
  status: string | null;
  is_draft: boolean;
  open_count: number;
  click_count: number;
  opened_at: string | null;
  clicked_at: string | null;
  thread_id: string | null;
  attachments: any[] | null;
  timestamp: string;
  agent_id: string | null;
  agent_name: string | null;
  lead_id: string | null;
  contact_id: string | null;
  company_id: string | null;
}

export interface EmailList { items: EmailItem[]; total: number; }

export interface ThreadSummary {
  thread_id: string;
  subject: string;
  last_at: string;
  count: number;
  last_direction: string | null;
  opened: boolean;
  clicked: boolean;
  lead_id: string | null;
  contact_id: string | null;
}

export interface ThreadDetail { thread_id: string; subject: string; messages: EmailItem[]; }

export interface ReportBucket { label: string; count: number; }

export interface EmailReport {
  total: number;
  sent: number;
  inbound: number;
  drafts: number;
  failed: number;
  opened: number;
  clicked: number;
  open_rate: number;
  click_rate: number;
  by_status: ReportBucket[];
  by_direction: ReportBucket[];
  by_day: ReportBucket[];
}

export const emailApi = {
  getSettings: async () => (await api.get<EmailSettings>('/email/settings')).data,
  updateSettings: async (payload: Partial<EmailSettings> & { smtp_password?: string; imap_password?: string }) =>
    (await api.put<EmailSettings>('/email/settings', payload)).data,
  oauthConnect: async (payload: { provider: string; email?: string; access_token: string; refresh_token?: string }) =>
    (await api.post<EmailSettings>('/email/oauth/connect', payload)).data,

  messages: async (params: { folder?: string; search?: string; skip?: number; limit?: number } = {}) =>
    (await api.get<EmailList>('/email/messages', { params })).data,
  threads: async (params: { search?: string } = {}) => (await api.get<ThreadSummary[]>('/email/threads', { params })).data,
  thread: async (threadId: string) => (await api.get<ThreadDetail>(`/email/threads/${threadId}`)).data,

  send: async (payload: { subject: string; body?: string; to?: string; cc?: string; lead_id?: string; contact_id?: string }) =>
    (await api.post<EmailItem>('/email/send', payload)).data,
  reply: async (activityId: string, payload: { body?: string; to?: string; cc?: string }) =>
    (await api.post<EmailItem>(`/email/${activityId}/reply`, payload)).data,
  forward: async (activityId: string, payload: { to: string; cc?: string; body?: string }) =>
    (await api.post<EmailItem>(`/email/${activityId}/forward`, payload)).data,

  createDraft: async (payload: { subject?: string; body?: string; to?: string; cc?: string; lead_id?: string; contact_id?: string }) =>
    (await api.post<EmailItem>('/email/drafts', payload)).data,
  updateDraft: async (id: string, payload: { subject?: string; body?: string; to?: string; cc?: string }) =>
    (await api.patch<EmailItem>(`/email/drafts/${id}`, payload)).data,
  sendDraft: async (id: string) => (await api.post<EmailItem>(`/email/drafts/${id}/send`)).data,
  deleteDraft: async (id: string) => { await api.delete(`/email/drafts/${id}`); },

  sync: async () => (await api.post<{ ingested: number }>('/email/sync')).data,
  reports: async (params: { date_from?: string; date_to?: string } = {}) =>
    (await api.get<EmailReport>('/email/reports', { params })).data,
};
