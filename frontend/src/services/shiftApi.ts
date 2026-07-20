import { api } from './api';

export interface Shift {
  id: string;
  name: string;
  code: string | null;
  shift_type: string;
  start_time: string;
  end_time: string;
  break_minutes: number;
  grace_minutes: number;
  working_days: string[];
  is_night_shift: boolean;
  is_flexible: boolean;
  works_on_holidays: boolean;
  status: string;
  color: string | null;
  created_at: string;
}

export interface Rotation {
  id: string;
  name: string;
  code: string | null;
  description: string | null;
  shift_sequence: string[];
  shift_names: string[];
  rotation_days: number;
  status: string;
  member_count: number;
  created_at: string;
}

export interface RotationMember {
  id: string;
  user_id: string;
  user_name: string | null;
  anchor_date: string;
  end_date: string | null;
}

export interface ShiftCalendarItem {
  user_id: string;
  user_name: string | null;
  date: string;
  shift_id: string | null;
  shift_name: string | null;
  shift_type: string | null;
  start_time: string | null;
  end_time: string | null;
  state: string;
}

export interface ShiftReportRow {
  shift_id: string;
  shift_name: string;
  shift_type: string;
  assigned: number;
  records: number;
  present: number;
  late: number;
  early_logout: number;
  on_leave: number;
  worked_hours: number;
}

export interface ShiftAttendanceRow {
  user_id: string;
  user_name: string | null;
  work_date: string;
  status: string;
  is_late: boolean;
  late_minutes: number;
  is_early_logout: boolean;
  worked_minutes: number;
}

export interface ShiftDashboard {
  total_shifts: number;
  flexible_shifts: number;
  night_shifts: number;
  active_rotations: number;
  by_type: Record<string, number>;
  my_shift_today: Shift | null;
}

export const shiftApi = {
  dashboard: async () => (await api.get<ShiftDashboard>('/shifts/dashboard')).data,
  calendar: async (date_from: string, date_to: string, user_id?: string) =>
    (await api.get<ShiftCalendarItem[]>('/shifts/calendar', { params: { date_from, date_to, user_id } })).data,
  reports: async (date_from: string, date_to: string) =>
    (await api.get<ShiftReportRow[]>('/shifts/reports', { params: { date_from, date_to } })).data,
  shiftAttendance: async (shiftId: string, date_from: string, date_to: string) =>
    (await api.get<{ shift_id: string; shift_name: string; records: ShiftAttendanceRow[] }>(
      `/shifts/${shiftId}/attendance`, { params: { date_from, date_to } })).data,

  list: async (params: { status?: string; shift_type?: string } = {}) => (await api.get<Shift[]>('/shifts', { params })).data,
  create: async (payload: any) => (await api.post<Shift>('/shifts', payload)).data,
  createPresets: async () => (await api.post<{ created: number }>('/shifts/presets', {})).data,
  update: async (id: string, payload: any) => (await api.patch<Shift>(`/shifts/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/shifts/${id}`); },
  assign: async (payload: { shift_id: string; user_ids: string[]; start_date?: string; end_date?: string }) =>
    (await api.post<{ assigned: number }>('/shifts/assign', payload)).data,

  listRotations: async (params: { status?: string } = {}) => (await api.get<Rotation[]>('/shifts/rotations', { params })).data,
  createRotation: async (payload: any) => (await api.post<Rotation>('/shifts/rotations', payload)).data,
  updateRotation: async (id: string, payload: any) => (await api.patch<Rotation>(`/shifts/rotations/${id}`, payload)).data,
  removeRotation: async (id: string) => { await api.delete(`/shifts/rotations/${id}`); },
  assignRotation: async (id: string, payload: { user_ids: string[]; anchor_date?: string; end_date?: string }) =>
    (await api.post<{ assigned: number }>(`/shifts/rotations/${id}/assign`, payload)).data,
  rotationMembers: async (id: string) => (await api.get<RotationMember[]>(`/shifts/rotations/${id}/members`)).data,
  removeRotationMember: async (id: string, userId: string) =>
    (await api.post(`/shifts/rotations/${id}/members/remove`, {}, { params: { user_id: userId } })).data,
};
