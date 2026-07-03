import { api } from './api';

export interface WaSettings {
  id: string;
  organization_id: string;
  provider: string;
  phone_number_id: string | null;
  business_account_id: string | null;
  sender_number: string | null;
  webhook_token: string | null;
  webhook_verify_token: string | null;
  daily_limit: number;
  auto_reply_enabled: boolean;
  auto_reply_message: string | null;
  is_active: boolean;
}

export interface WaMessage {
  id: string;
  direction: 'INBOUND' | 'OUTBOUND' | null;
  body: string | null;
  wa_status: string | null;
  media_type: string | null;
  template_name: string | null;
  error: string | null;
  attachments: any[] | null;
  timestamp: string;
  from_number: string | null;
  to_number: string | null;
}

export interface WaConversation {
  id: string;
  phone: string;
  display_name: string | null;
  status: string;
  unread_count: number;
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  window_open: boolean;
  window_expires_at: string | null;
  last_message_at: string | null;
  last_inbound_at: string | null;
  lead_id: string | null;
  contact_id: string | null;
}

export interface WaThread {
  conversation: WaConversation;
  messages: WaMessage[];
}

export interface ReportBucket { label: string; count: number; }

export interface WaReport {
  total: number;
  outbound: number;
  inbound: number;
  delivered: number;
  read: number;
  failed: number;
  delivery_rate: number;
  read_rate: number;
  by_status: ReportBucket[];
  by_direction: ReportBucket[];
  by_media_type: ReportBucket[];
  by_day: ReportBucket[];
}

export interface QuickReply { id: string; shortcut: string; text: string; }

export const whatsappApi = {
  getSettings: async () => (await api.get<WaSettings>('/whatsapp/settings')).data,
  updateSettings: async (payload: Partial<WaSettings> & { access_token?: string; regenerate_webhook_token?: boolean; regenerate_verify_token?: boolean }) =>
    (await api.put<WaSettings>('/whatsapp/settings', payload)).data,

  conversations: async (params: { status?: string; assigned_to?: string; search?: string; unread_only?: boolean } = {}) =>
    (await api.get<WaConversation[]>('/whatsapp/conversations', { params })).data,
  thread: async (conversationId: string) => (await api.get<WaThread>(`/whatsapp/conversations/${conversationId}`)).data,
  assign: async (conversationId: string, userId: string | null) =>
    (await api.post<WaConversation>(`/whatsapp/conversations/${conversationId}/assign`, { user_id: userId })).data,

  sendText: async (payload: { body: string; conversation_id?: string; to_number?: string; lead_id?: string; contact_id?: string }) =>
    (await api.post<WaMessage>('/whatsapp/send', payload)).data,
  sendTemplate: async (payload: { template_id?: string; template_name?: string; body?: string; conversation_id?: string; to_number?: string; lead_id?: string; contact_id?: string }) =>
    (await api.post<WaMessage>('/whatsapp/send-template', payload)).data,
  sendMedia: async (form: FormData) =>
    (await api.post<WaMessage>('/whatsapp/send-media', form, { headers: { 'Content-Type': 'multipart/form-data' } })).data,

  listQuickReplies: async () => (await api.get<QuickReply[]>('/whatsapp/quick-replies')).data,
  createQuickReply: async (payload: { shortcut: string; text: string }) =>
    (await api.post<QuickReply>('/whatsapp/quick-replies', payload)).data,
  deleteQuickReply: async (id: string) => { await api.delete(`/whatsapp/quick-replies/${id}`); },

  reports: async (params: { date_from?: string; date_to?: string } = {}) =>
    (await api.get<WaReport>('/whatsapp/reports', { params })).data,
};
