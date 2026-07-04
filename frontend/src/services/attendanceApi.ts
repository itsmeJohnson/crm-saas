import { api } from './api';

export interface Shift {
  id: string;
  name: string;
  code: string | null;
  start_time: string;
  end_time: string;
  break_minutes: number;
  grace_minutes: number;
  working_days: string[];
  is_night_shift: boolean;
  status: string;
  color: string | null;
  created_at: string;
}

export interface AttendanceRecord {
  id: string;
  user_id: string;
  user_name: string | null;
  work_date: string;
  shift_id: string | null;
  clock_in_at: string | null;
  clock_out_at: string | null;
  status: string;
  is_late: boolean;
  late_minutes: number;
  is_early_logout: boolean;
  early_minutes: number;
  worked_minutes: number;
  break_minutes: number;
  in_latitude: number | null;
  in_longitude: number | null;
  source: string;
  notes: string | null;
}

export interface RecordList { items: AttendanceRecord[]; total: number; }

export interface MyToday {
  work_date: string;
  record: AttendanceRecord | null;
  shift: Shift | null;
  on_break: boolean;
}

export interface Correction {
  id: string;
  attendance_id: string | null;
  user_id: string;
  user_name: string | null;
  work_date: string;
  reason: string;
  proposed: Record<string, any> | null;
  status: string;
  requested_by: string;
  requested_by_name: string | null;
  reviewed_by_name: string | null;
  review_note: string | null;
  created_at: string;
}

export interface AttendanceDashboard {
  work_date: string;
  headcount: number;
  present: number;
  absent: number;
  late: number;
  on_break: number;
  clocked_out: number;
  still_working: number;
  pending_corrections: number;
}

export interface MonthlyReportRow {
  user_id: string;
  name: string;
  present_days: number;
  late_days: number;
  early_days: number;
  half_days: number;
  leave_days: number;
  worked_minutes: number;
  break_minutes: number;
  worked_hours: number;
  break_hours: number;
}

export interface MonthlyReport {
  year: number;
  month: number;
  working_days_in_month: number;
  rows: MonthlyReportRow[];
}

export interface ShiftAssignmentRow {
  id: string;
  shift_id: string;
  shift_name: string | null;
  start_date: string;
  end_date: string | null;
}

export const attendanceApi = {
  myToday: async () => (await api.get<MyToday>('/attendance/me/today')).data,
  clockIn: async (geo?: { latitude?: number; longitude?: number }) =>
    (await api.post<AttendanceRecord>('/attendance/clock-in', geo || {})).data,
  clockOut: async (geo?: { latitude?: number; longitude?: number }) =>
    (await api.post<AttendanceRecord>('/attendance/clock-out', geo || {})).data,
  breakStart: async (reason?: string) => (await api.post<AttendanceRecord>('/attendance/break/start', { reason })).data,
  breakEnd: async () => (await api.post<AttendanceRecord>('/attendance/break/end', {})).data,
  biometricPunch: async (payload: any) => (await api.post<AttendanceRecord>('/attendance/biometric/punch', payload)).data,

  dashboard: async () => (await api.get<AttendanceDashboard>('/attendance/dashboard')).data,
  monthlyReport: async (year: number, month: number, user_id?: string) =>
    (await api.get<MonthlyReport>('/attendance/report/monthly', { params: { year, month, user_id } })).data,
  records: async (params: { user_id?: string; date_from?: string; date_to?: string; status?: string } = {}) =>
    (await api.get<RecordList>('/attendance/records', { params })).data,

  listShifts: async (params: { status?: string } = {}) => (await api.get<Shift[]>('/attendance/shifts', { params })).data,
  createShift: async (payload: any) => (await api.post<Shift>('/attendance/shifts', payload)).data,
  updateShift: async (id: string, payload: any) => (await api.patch<Shift>(`/attendance/shifts/${id}`, payload)).data,
  deleteShift: async (id: string) => { await api.delete(`/attendance/shifts/${id}`); },
  assignShift: async (payload: { shift_id: string; user_ids: string[]; start_date?: string; end_date?: string }) =>
    (await api.post<{ assigned: number }>('/attendance/shifts/assign', payload)).data,
  userAssignments: async (userId: string) => (await api.get<ShiftAssignmentRow[]>(`/attendance/users/${userId}/assignments`)).data,

  listCorrections: async (params: { status?: string; mine?: boolean } = {}) =>
    (await api.get<Correction[]>('/attendance/corrections', { params })).data,
  requestCorrection: async (payload: { user_id?: string; work_date: string; reason: string; proposed?: any }) =>
    (await api.post<Correction>('/attendance/corrections', payload)).data,
  reviewCorrection: async (id: string, approve: boolean, note?: string) =>
    (await api.post<Correction>(`/attendance/corrections/${id}/review`, { approve, note })).data,
};
