import { api } from './api';

export interface CommItem {
  id: string; channel: string; direction: string | null; subject: string; body: string | null;
  status: string; timestamp: string; actor_user_id: string | null; actor_name: string | null;
  lead_id: string | null; contact_id: string | null; company_id: string | null;
  recording_url: string | null; attachments: any[] | null; is_read: boolean; is_pinned: boolean; internal: boolean;
}

export interface Conversation {
  entity_type: string; entity_id: string; name: string; last_channel: string; last_subject: string;
  last_at: string; unread_count: number; total: number; pinned: boolean;
}

export interface CommStats {
  total: number; unread: number; this_week: number;
  by_channel: { label: string; count: number }[]; by_direction: { label: string; count: number }[];
}

export interface CommTemplate { id: string; organization_id: string; name: string; channel: string; subject: string | null; body: string; created_at: string }

export interface FeedFilters {
  lead_id?: string; contact_id?: string; company_id?: string; channel?: string; direction?: string;
  search?: string; unread_only?: boolean; pinned_only?: boolean; include_notes?: boolean;
}

export const communicationApi = {
  log: async (payload: {
    channel: string; direction?: string; subject: string; body?: string;
    lead_id?: string | null; contact_id?: string | null; company_id?: string | null;
    send_email?: boolean; to_email?: string | null;
  }) => (await api.post<CommItem>('/communications/', payload)).data,

  feed: async (filters: FeedFilters) => (await api.get<CommItem[]>('/communications/', { params: filters })).data,
  conversations: async (search?: string) => (await api.get<Conversation[]>('/communications/conversations', { params: { search } })).data,
  stats: async () => (await api.get<CommStats>('/communications/stats')).data,

  markRead: async (id: string) => { await api.post(`/communications/${id}/read`); },
  markAllRead: async (params: { contact_id?: string; company_id?: string; lead_id?: string }) =>
    (await api.post('/communications/read-all', null, { params })).data,
  togglePin: async (id: string) => (await api.post<{ pinned: boolean }>(`/communications/${id}/pin`)).data,

  listAttachments: async (id: string) => (await api.get(`/communications/${id}/attachments`)).data,
  uploadAttachment: async (id: string, file: File) => {
    const form = new FormData(); form.append('file', file);
    return (await api.post(`/communications/${id}/attachments`, form, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
  },

  listTemplates: async () => (await api.get<CommTemplate[]>('/communications/templates')).data,
  createTemplate: async (payload: { name: string; channel: string; subject?: string; body: string }) =>
    (await api.post<CommTemplate>('/communications/templates', payload)).data,
  deleteTemplate: async (id: string) => { await api.delete(`/communications/templates/${id}`); },
  renderTemplate: async (id: string, payload: { contact_id?: string; company_id?: string; lead_id?: string }) =>
    (await api.post<{ subject: string | null; body: string }>(`/communications/templates/${id}/render`, payload)).data,
};
