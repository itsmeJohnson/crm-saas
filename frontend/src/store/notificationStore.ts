import { create } from 'zustand';
import { notificationApi, NotificationResponse } from '../services/notificationApi';

interface NotificationState {
  notifications: NotificationResponse[];
  unreadCount: number;
  isLoading: boolean;
  error: string | null;
  fetchNotifications: () => Promise<void>;
  fetchUnreadCount: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
}

export const useNotificationStore = create<NotificationState>((set, get) => ({
  notifications: [],
  unreadCount: 0,
  isLoading: false,
  error: null,

  fetchNotifications: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await notificationApi.list({ limit: 20 });
      set({ notifications: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch notifications',
        isLoading: false,
      });
    }
  },

  fetchUnreadCount: async () => {
    try {
      const count = await notificationApi.getUnreadCount();
      set({ unreadCount: count });
    } catch {
      // Silent — the bell just won't show a badge if this fails; not worth surfacing an error for.
    }
  },

  markRead: async (id: string) => {
    try {
      await notificationApi.markRead(id);
      set({
        notifications: get().notifications.map((n) => (n.id === id ? { ...n, is_read: true } : n)),
        unreadCount: Math.max(0, get().unreadCount - 1),
      });
    } catch {
      // No-op on failure — next refresh will reconcile state.
    }
  },

  markAllRead: async () => {
    try {
      await notificationApi.markAllRead();
      set({
        notifications: get().notifications.map((n) => ({ ...n, is_read: true })),
        unreadCount: 0,
      });
    } catch {
      // No-op on failure — next refresh will reconcile state.
    }
  },
}));
