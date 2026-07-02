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
  created_at: string;
}

export const notificationApi = {
  list: async (params?: { skip?: number; limit?: number; unread_only?: boolean }) => {
    const res = await api.get<NotificationResponse[]>('/notifications/', { params });
    return res.data;
  },

  getUnreadCount: async () => {
    const res = await api.get<{ unread_count: number }>('/notifications/unread-count');
    return res.data.unread_count;
  },

  markRead: async (id: string) => {
    const res = await api.patch<NotificationResponse>(`/notifications/${id}/read`);
    return res.data;
  },

  markAllRead: async () => {
    const res = await api.post<{ marked_read: number }>('/notifications/mark-all-read');
    return res.data;
  },
};
