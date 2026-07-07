import { api } from './api';

export interface CalendarItem {
  source: string; type: string; id: string; title: string;
  start: string; end: string | null; all_day: boolean; status: string | null;
  link: string | null; metadata: Record<string, any> | null;
}

export interface CalendarEvent {
  id: string; organization_id: string; title: string; description: string | null;
  event_type: string; location: string | null; start_at: string; end_at: string; all_day: boolean;
  status: string; assigned_user_id: string | null; created_by: string; attendees: any[] | null;
  lead_id: string | null; contact_id: string | null; company_id: string | null;
  recurrence: string; recurrence_until: string | null; remind_at: string | null;
  created_at: string; updated_at: string;
}

export interface Holiday { id: string; name: string; holiday_date: string; recurring_annual: boolean }
export interface WorkingHours { id: string; organization_id: string; timezone: string; days: Record<string, { enabled: boolean; start: string; end: string }> }
export interface CalendarReport {
  total_events: number; upcoming_7d: number; tasks_due_7d: number;
  by_type: { label: string; count: number }[]; by_user: { label: string; count: number }[];
}

type EventWrite = Partial<{
  title: string; description: string | null; event_type: string; location: string | null;
  start_at: string; end_at: string; all_day: boolean; status: string; assigned_user_id: string | null;
  attendees: any[] | null; lead_id: string | null; contact_id: string | null; company_id: string | null;
  recurrence: string; recurrence_until: string | null; remind_at: string | null;
}>;

export const calendarApi = {
  unified: async (from: string, to: string, types?: string) =>
    (await api.get<CalendarItem[]>('/calendar/', { params: { date_from: from, date_to: to, types } })).data,
  report: async () => (await api.get<CalendarReport>('/calendar/reports')).data,

  createEvent: async (payload: EventWrite & { title: string; start_at: string; end_at: string }) =>
    (await api.post<CalendarEvent>('/calendar/events', payload)).data,
  getEvent: async (id: string) => (await api.get<CalendarEvent>(`/calendar/events/${id}`)).data,
  updateEvent: async (id: string, payload: EventWrite) => (await api.patch<CalendarEvent>(`/calendar/events/${id}`, payload)).data,
  deleteEvent: async (id: string) => { await api.delete(`/calendar/events/${id}`); },

  listHolidays: async () => (await api.get<Holiday[]>('/calendar/holidays')).data,
  createHoliday: async (payload: { name: string; holiday_date: string; recurring_annual?: boolean }) =>
    (await api.post<Holiday>('/calendar/holidays', payload)).data,
  deleteHoliday: async (id: string) => { await api.delete(`/calendar/holidays/${id}`); },

  getWorkingHours: async () => (await api.get<WorkingHours>('/calendar/working-hours')).data,
  updateWorkingHours: async (payload: Partial<{ timezone: string; days: Record<string, any> }>) =>
    (await api.patch<WorkingHours>('/calendar/working-hours', payload)).data,

  feedUrl: async () => (await api.get<{ url: string; token: string }>('/calendar/feed-url')).data,
};
