import { api } from './api';

export interface LeaveType {
  id: string;
  name: string;
  code: string | null;
  description: string | null;
  is_paid: boolean;
  annual_quota: number;
  max_consecutive_days: number | null;
  allow_half_day: boolean;
  requires_approval: boolean;
  deducts_balance: boolean;
  color: string | null;
  status: string;
  created_at: string;
}

export interface BalanceRow {
  leave_type_id: string;
  leave_type_name: string;
  color: string | null;
  year: number;
  allocated: number;
  carried_forward: number;
  used: number;
  pending: number;
  available: number;
}

export interface LeaveRequest {
  id: string;
  user_id: string;
  user_name: string | null;
  request_type: string;
  leave_type_id: string | null;
  leave_type_name: string | null;
  start_date: string;
  end_date: string;
  is_half_day: boolean;
  half_day_period: string | null;
  day_count: number;
  reason: string | null;
  status: string;
  reviewed_by_name: string | null;
  review_note: string | null;
  created_at: string;
}

export interface RequestList { items: LeaveRequest[]; total: number; }

export interface LeaveCalendarItem {
  type: string;
  id: string;
  user_id: string | null;
  user_name: string | null;
  request_type: string;
  leave_type_name: string | null;
  start_date: string;
  end_date: string;
  is_half_day: boolean;
  day_count: number;
  status: string;
}

export interface LeaveDashboard {
  my_pending: number;
  my_available_days: number;
  pending_approvals: number;
  on_leave_today: { user_id: string; name: string }[];
}

export interface LeaveReport {
  year: number;
  rows: {
    user_id: string;
    name: string;
    used: number;
    pending: number;
    available: number;
    by_type: BalanceRow[];
  }[];
}

export const leaveApi = {
  dashboard: async () => (await api.get<LeaveDashboard>('/leaves/dashboard')).data,
  calendar: async (date_from: string, date_to: string) =>
    (await api.get<LeaveCalendarItem[]>('/leaves/calendar', { params: { date_from, date_to } })).data,
  report: async (year: number, user_id?: string) =>
    (await api.get<LeaveReport>('/leaves/report', { params: { year, user_id } })).data,

  listTypes: async (params: { status?: string } = {}) => (await api.get<LeaveType[]>('/leaves/types', { params })).data,
  createType: async (payload: any) => (await api.post<LeaveType>('/leaves/types', payload)).data,
  updateType: async (id: string, payload: any) => (await api.patch<LeaveType>(`/leaves/types/${id}`, payload)).data,
  deleteType: async (id: string) => { await api.delete(`/leaves/types/${id}`); },

  balances: async (user_id?: string, year?: number) =>
    (await api.get<BalanceRow[]>('/leaves/balances', { params: { user_id, year } })).data,
  allocate: async (payload: { user_id: string; leave_type_id: string; year?: number; allocated: number; carried_forward?: number }) =>
    (await api.post<BalanceRow>('/leaves/balances/allocate', payload)).data,

  listRequests: async (params: { scope?: string; status?: string; request_type?: string } = {}) =>
    (await api.get<RequestList>('/leaves/requests', { params })).data,
  apply: async (payload: {
    request_type?: string; leave_type_id?: string; start_date: string; end_date: string;
    is_half_day?: boolean; half_day_period?: string; reason?: string;
  }) => (await api.post<LeaveRequest>('/leaves/requests', payload)).data,
  review: async (id: string, approve: boolean, note?: string) =>
    (await api.post<LeaveRequest>(`/leaves/requests/${id}/review`, { approve, note })).data,
  cancel: async (id: string) => (await api.post<LeaveRequest>(`/leaves/requests/${id}/cancel`, {})).data,
};
