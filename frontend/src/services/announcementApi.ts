import { api } from './api';

export const ANNOUNCEMENT_AUDIENCES = ['all', 'OrgAdmin', 'Manager', 'Employee'] as const;

export interface Announcement {
  id: string;
  title: string;
  body: string;
  audience: string;
  is_pinned: boolean;
  is_active: boolean;
  published_at: string | null;
  expires_at: string | null;
  author_name: string | null;
  created_at: string;
}

export const announcementApi = {
  list: async (scope: 'mine' | 'all' = 'mine') => (await api.get<Announcement[]>('/announcements', { params: { scope } })).data,
  create: async (payload: any) => (await api.post<Announcement>('/announcements', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Announcement>(`/announcements/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/announcements/${id}`); },
};
