import { api } from './api';

export interface EmployeeRow {
  user_id: string; name: string; role: string; calls: number; leads_converted: number;
  conversion_rate: number; revenue: number; activities: number; tasks_total: number; tasks_done: number;
  task_completion_rate: number; attendance_rate: number; present_days: number; leave_days: number;
  training_score: number; productivity_score: number;
}
export interface Roster { from: string; to: string; headcount: number; employees: EmployeeRow[]; }

export interface EmployeeDetail {
  user_id: string; name: string; role: string; from: string; to: string; productivity_score: number;
  lead_productivity: { leads_converted: number; conversion_rate: number; revenue: number };
  call_productivity: { calls: number; activities: number };
  task_completion: { total: number; done: number; completion_rate: number };
  attendance: { present: number; late: number; half_day: number; absent: number; on_leave: number; attendance_rate: number; working_days: number };
  leave_analysis: { approved_days: number };
  training: { count: number; completed: number; avg_score: number; records: Training[] };
}

export interface Training {
  id: string; user_id: string; name: string; category: string | null;
  status: string; score: number | null; completed_at: string | null; created_at: string | null;
}

export interface ManagerComparison {
  managers: { manager_id: string; manager_name: string; team_size: number; leads_converted: number;
    calls: number; revenue: number; activities: number; avg_task_completion: number; avg_attendance: number }[];
}
export interface AttendanceTrend { from: string; to: string; series: { date: string; present: number; late: number; half_day: number; absent: number; on_leave: number }[]; }
export interface Heatmap { weekdays: string[]; grid: number[][]; peak: { weekday: number; hour: number; count: number; weekday_label: string }; total: number; }
export interface EmployeeDashboard { headcount: number; avg_productivity: number; avg_attendance: number; avg_training_score: number; top_performer: { name: string; productivity_score: number } | null; }
export interface PerformanceTrend { user_id: string; granularity: string; series: any[]; }

type R = { date_from?: string; date_to?: string };
export const EMP_METRICS = ['leads_converted', 'calls_made', 'conversion_rate', 'sales_revenue', 'tasks_completed', 'activities', 'attendance_score'] as const;

export const employeeAnalyticsApi = {
  roster: async (p: R = {}) => (await api.get<Roster>('/employee-analytics/roster', { params: p })).data,
  dashboard: async () => (await api.get<EmployeeDashboard>('/employee-analytics/dashboard')).data,
  employee: async (id: string, p: R = {}) => (await api.get<EmployeeDetail>(`/employee-analytics/${id}`, { params: p })).data,
  performanceTrend: async (id: string, p: { granularity?: string; count?: number } = {}) =>
    (await api.get<PerformanceTrend>(`/employee-analytics/${id}/performance-trend`, { params: p })).data,
  attendanceTrend: async (p: R & { user_id?: string } = {}) => (await api.get<AttendanceTrend>('/employee-analytics/attendance-trend', { params: p })).data,
  managerComparison: async (p: R = {}) => (await api.get<ManagerComparison>('/employee-analytics/manager-comparison', { params: p })).data,
  comparison: async (kind: 'department' | 'branch', p: R = {}) => (await api.get<{ kind: string; rows: any[] }>(`/employee-analytics/comparison/${kind}`, { params: p })).data,
  leaderboard: async (p: R & { metric?: string; limit?: number } = {}) => (await api.get<any[]>('/employee-analytics/leaderboard', { params: p })).data,
  heatmap: async (p: R & { user_id?: string } = {}) => (await api.get<Heatmap>('/employee-analytics/heatmap', { params: p })).data,
  exportCsv: async (p: R = {}) => (await api.get('/employee-analytics/export', { params: p, responseType: 'blob' })).data as Blob,

  listTrainings: async (p: { user_id?: string } = {}) => (await api.get<Training[]>('/employee-analytics/trainings', { params: p })).data,
  createTraining: async (payload: any) => (await api.post<Training>('/employee-analytics/trainings', payload)).data,
  updateTraining: async (id: string, payload: any) => (await api.patch<Training>(`/employee-analytics/trainings/${id}`, payload)).data,
  deleteTraining: async (id: string) => { await api.delete(`/employee-analytics/trainings/${id}`); },
};
