import { api } from './api';

export interface NotificationResponse {
  id: string;
  category: string;
  title: string;
  body: string;
  link_url: string | null;
  is_read: boolean;
  read_at: string | null;
  action_metadata: Record<string, any> | null;
  priority: string;
  is_dismissed: boolean;
  actions: { label: string; url?: string; style?: string }[] | null;
  channels_sent: string[] | null;
  created_at: string;
}

export interface NotificationPreference {
  category: string;
  in_app: boolean;
  email: boolean;
  sms: boolean;
  whatsapp: boolean;
  push: boolean;
}

export interface ReportBucket { label: string; count: number; }

export interface NotificationStats {
  total: number;
  unread: number;
  read: number;
  read_rate: number;
  by_category: ReportBucket[];
  by_priority: ReportBucket[];
}

export interface ListFilters {
  skip?: number;
  limit?: number;
  unread_only?: boolean;
  category?: string;
  priority?: string;
  include_dismissed?: boolean;
}

export const notificationApi = {
  list: async (params?: ListFilters) => (await api.get<NotificationResponse[]>('/notifications/', { params })).data,
  getUnreadCount: async () => (await api.get<{ unread_count: number }>('/notifications/unread-count')).data.unread_count,
  unreadByCategory: async () => (await api.get<{ category: string; count: number }[]>('/notifications/unread-by-category')).data,
  categories: async () => (await api.get<string[]>('/notifications/categories')).data,
  stats: async () => (await api.get<NotificationStats>('/notifications/stats')).data,

  markRead: async (id: string) => (await api.patch<NotificationResponse>(`/notifications/${id}/read`)).data,
  markAllRead: async () => (await api.post<{ marked_read: number }>('/notifications/mark-all-read')).data,
  bulkRead: async (payload: { ids?: string[]; category?: string }) =>
    (await api.post<{ marked_read: number }>('/notifications/bulk-read', payload)).data,
  dismiss: async (id: string) => (await api.post<NotificationResponse>(`/notifications/${id}/dismiss`)).data,

  getPreferences: async () => (await api.get<NotificationPreference[]>('/notifications/preferences')).data,
  updatePreferences: async (items: NotificationPreference[]) =>
    (await api.put<NotificationPreference[]>('/notifications/preferences', { items })).data,

  subscribePush: async (payload: { endpoint: string; p256dh?: string; auth?: string; user_agent?: string }) =>
    (await api.post<{ id: string }>('/notifications/push/subscribe', payload)).data,
  unsubscribePush: async (endpoint: string) => { await api.post('/notifications/push/unsubscribe', { endpoint }); },

  broadcast: async (payload: { title: string; body: string; category?: string; priority?: string; role?: string | null; link_url?: string; fanout?: boolean }) =>
    (await api.post<{ recipients: number; sent: number }>('/notifications/broadcast', payload)).data,
};
