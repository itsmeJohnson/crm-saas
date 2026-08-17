import { api } from './api';

export interface WaSettings {
  id: string;
  organization_id: string;
  provider: string;
  friendly_name: string | null;
  phone_number_id: string | null;
  business_account_id: string | null;
  sender_number: string | null;
  meta_app_id: string | null;
  webhook_token: string | null;
  webhook_verify_token: string | null;
  webhook_url: string | null;
  api_version: string;
  default_country_code: string;
  daily_limit: number;
  auto_reply_enabled: boolean;
  auto_reply_message: string | null;
  is_active: boolean;
  health_status: string;
  is_default: boolean;
  quality_rating: string | null;
  messaging_limit: string | null;
  display_name_status: string | null;
  created_at: string;
  updated_at: string | null;
}

export interface WaLabel {
  id: string;
  organization_id: string;
  name: string;
  color: string;
}

export interface WaAttachment {
  id: string;
  media_id: string | null;
  media_url: string;
  media_type: string;
  file_name: string;
  file_size: number | null;
  mime_type: string | null;
  local_path: string | null;
}

export interface WaMessage {
  id: string;
  conversation_id: string;
  direction: 'INBOUND' | 'OUTBOUND';
  body: string | null;
  wa_message_id: string | null;
  wa_status: string;
  media_type: string;
  template_name: string | null;
  error: string | null;
  is_internal: boolean;
  sent_at: string | null;
  delivered_at: string | null;
  read_at: string | null;
  failed_at: string | null;
  retry_count: number;
  attachments: WaAttachment[];
  created_at: string;
  
  // AI fields
  ai_summary: string | null;
  ai_sentiment: string | null;
  ai_intent: string | null;
  suggested_reply: string | null;
  language: string | null;
  translation: string | null;
}

export interface WaConversation {
  id: string;
  whatsapp_settings_id: string;
  phone: string;
  display_name: string | null;
  status: string;
  is_pinned: boolean;
  unread_count: number;
  assigned_user_id: string | null;
  assigned_user_name: string | null;
  window_open: boolean;
  window_expires_at: string | null;
  last_message_at: string | null;
  last_inbound_at: string | null;
  lead_id: string | null;
  contact_id: string | null;
  whatsapp_contact_id: string | null;
  
  // SLA
  sla_status: string;
  sla_due_at: string | null;
  
  // Lock
  locked_by_user_id: string | null;
  locked_by_user_name: string | null;
  lock_expires_at: string | null;
  is_locked: boolean;
  
  labels: WaLabel[];
}

export interface WaThread {
  conversation: WaConversation;
  messages: WaMessage[];
}

export interface ReportBucket {
  label: string;
  count: number;
}

export interface WaReport {
  total: number;
  outbound: number;
  inbound: number;
  delivered: number;
  read: number;
  failed: number;
  delivery_rate: number;
  read_rate: number;
  response_time_avg_sec: number;
  by_status: ReportBucket[];
  by_direction: ReportBucket[];
  by_media_type: ReportBucket[];
  by_day: ReportBucket[];
}

export interface WaDashboardMetrics {
  connected_accounts: number;
  disconnected_accounts: number;
  expired_tokens: number;
  rate_limited_accounts: number;
  maintenance_accounts: number;
  quality_ratings: any[];
  messaging_limits: any[];
  webhook_status: string;
  template_sync_status: string;
  last_sync_time: string;
  graph_api_latency_ms: number;
  queue_size: number;
  queue_health: string;
  failed_messages: number;
  success_rate: number;
  daily_volume: number;
}

export interface QuickReply {
  id: string;
  shortcut: string;
  text: string;
}

export interface WaTemplate {
  id: string;
  organization_id: string;
  meta_template_id: string | null;
  name: string;
  category: string;
  language: string;
  status: string;
  header_format: string | null;
  header_text: string | null;
  body_text: string;
  footer_text: string | null;
  buttons: any | null;
}

export const whatsappApi = {
  getSettings: async (settingsId?: string) => 
    (await api.get<WaSettings>('/whatsapp/settings', { params: { settings_id: settingsId } })).data,
  listSettings: async () => 
    (await api.get<WaSettings[]>('/whatsapp/settings/list')).data,
  updateSettings: async (settingsId: string, payload: Partial<WaSettings> & { access_token?: string; webhook_secret?: string; regenerate_webhook_token?: boolean; regenerate_verify_token?: boolean }) =>
    (await api.put<WaSettings>(`/whatsapp/settings/${settingsId}`, payload)).data,
  checkHealth: async (settingsId: string) =>
    (await api.post<{ health_status: string }>(`/whatsapp/settings/${settingsId}/health`)).data,
  syncTemplates: async (settingsId: string) =>
    (await api.post<WaTemplate[]>(`/whatsapp/settings/${settingsId}/sync-templates`)).data,
  deleteSettings: async (settingsId: string) =>
    (await api.delete(`/whatsapp/settings/${settingsId}`)),
  refreshMetadata: async (settingsId: string) =>
    (await api.post<{ status: string; reason?: string }>(`/whatsapp/settings/${settingsId}/refresh`)).data,
  getDiagnostics: async (settingsId: string) =>
    (await api.get<Record<string, 'green' | 'yellow' | 'red'>>(`/whatsapp/settings/${settingsId}/diagnostics`)).data,
  exchangeSignupOAuth: async (code: string, redirectUri: string) =>
    (await api.post<WaSettings[]>('/whatsapp/signup/exchange', { code, redirect_uri: redirectUri })).data,

  conversations: async (params: { status?: string; assigned_to?: string; search?: string; unread_only?: boolean; label_id?: string; settings_id?: string } = {}) =>
    (await api.get<WaConversation[]>('/whatsapp/conversations', { params })).data,
  thread: async (conversationId: string, params: { skip?: number; limit?: number } = {}) => 
    (await api.get<WaThread>(`/whatsapp/conversations/${conversationId}/thread`, { params })).data,
  assign: async (conversationId: string, userId: string | null) =>
    (await api.post<WaConversation>(`/whatsapp/conversations/${conversationId}/assign`, { user_id: userId })).data,
  changeStatus: async (conversationId: string, status: string) =>
    (await api.post<WaConversation>(`/whatsapp/conversations/${conversationId}/status`, null, { params: { status } })).data,
  lock: async (conversationId: string) =>
    (await api.post<WaConversation>(`/whatsapp/conversations/${conversationId}/lock`)).data,
  unlock: async (conversationId: string) =>
    (await api.post<WaConversation>(`/whatsapp/conversations/${conversationId}/unlock`)).data,

  sendText: async (payload: { body: string; conversation_id?: string; to_number?: string; lead_id?: string; contact_id?: string; settings_id?: string; is_internal?: boolean }) =>
    (await api.post<WaMessage>('/whatsapp/send-text', payload)).data,
  sendTemplate: async (payload: { template_id?: string; template_name?: string; body?: string; conversation_id?: string; to_number?: string; lead_id?: string; contact_id?: string; settings_id?: string; language?: string; variables?: string[] }) =>
    (await api.post<WaMessage>('/whatsapp/send-template', payload)).data,
  sendMedia: async (payload: FormData) =>
    (await api.post<WaMessage>('/whatsapp/send-media', payload, {
      headers: { 'Content-Type': 'multipart/form-data' }
    })).data,

  promoteContact: async (contactId: string) =>
    (await api.post<{ status: string; lead_id: string; title: string }>(`/whatsapp/contacts/${contactId}/convert-lead`)).data,

  listLabels: async () => 
    (await api.get<WaLabel[]>('/whatsapp/labels')).data,
  createLabel: async (payload: { name: string; color: string }) =>
    (await api.post<WaLabel>('/whatsapp/labels', payload)).data,
  deleteLabel: async (id: string) => { 
    await api.delete(`/whatsapp/labels/${id}`); 
  },
  assignLabel: async (conversationId: string, labelId: string) =>
    (await api.post<WaConversation>(`/whatsapp/conversations/${conversationId}/labels/${labelId}`)).data,
  removeLabel: async (conversationId: string, labelId: string) =>
    (await api.delete<WaConversation>(`/whatsapp/conversations/${conversationId}/labels/${labelId}`)).data,

  listQuickReplies: async () => (await api.get<QuickReply[]>('/whatsapp/quick-replies')).data,
  createQuickReply: async (payload: { shortcut: string; text: string }) =>
    (await api.post<QuickReply>('/whatsapp/quick-replies', payload)).data,
  deleteQuickReply: async (id: string) => { await api.delete(`/whatsapp/quick-replies/${id}`); },

  getDashboardMetrics: async () => (await api.get<WaDashboardMetrics>('/whatsapp/monitoring/dashboard')).data,
  reports: async (params: { date_from?: string; date_to?: string } = {}) =>
    (await api.get<WaReport>('/whatsapp/reports', { params })).data,
  exportReportsUrl: (format: 'excel' | 'pdf', dateFrom?: string, dateTo?: string) => {
    const base = `${api.defaults.baseURL}/whatsapp/reports/export?format=${format}`;
    const fromQuery = dateFrom ? `&date_from=${encodeURIComponent(dateFrom)}` : '';
    const toQuery = dateTo ? `&date_to=${encodeURIComponent(dateTo)}` : '';
    return `${base}${fromQuery}${toQuery}`;
  }
};
