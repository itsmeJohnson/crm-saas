import { api } from './api';

export interface Team {
  id: string;
  organization_id: string;
  name: string;
  code: string | null;
  description: string | null;
  team_leader_id: string | null;
  leader_name: string | null;
  leader_email: string | null;
  department_id: string | null;
  department_name: string | null;
  capacity: number | null;
  status: string;
  color: string | null;
  member_count: number;
  created_at: string;
}

export interface TeamList { items: Team[]; total: number; }

export interface TeamMember {
  id: string;
  membership_id: string;
  name: string;
  email: string;
  role: string;
  role_in_team: string;
  is_active: boolean;
  joined_at: string | null;
}

export interface TeamTarget {
  id: string;
  team_id: string;
  name: string;
  metric: string;
  target_value: number;
  period: string;
  start_date: string | null;
  end_date: string | null;
}

export interface TeamKPI {
  target_id: string;
  name: string;
  metric: string;
  target_value: number;
  actual: number;
  attainment: number;
  period: string;
}

export interface TeamPerformance {
  team_id: string;
  name: string;
  member_count: number;
  capacity: number | null;
  metrics: Record<string, number>;
  kpis: TeamKPI[];
  members: ({ user_id: string; name: string } & Record<string, any>)[];
}

export interface TeamDashboard {
  total: number;
  active: number;
  archived: number;
  total_members: number;
  capacity_utilization: number | null;
  largest: { id: string; name: string; member_count: number; capacity: number | null }[];
}

export interface TeamAnalyticsRow {
  team_id: string;
  name: string;
  member_count: number;
  capacity: number | null;
  leads_converted: number;
  calls_made: number;
  tasks_completed: number;
  revenue: number;
  activities: number;
}

export interface TeamCalendarItem {
  type: string;
  id: string;
  title: string;
  start: string | null;
  end: string | null;
  status: string;
  event_type: string;
  user_id: string | null;
  user_name: string;
}

export interface AssignResult { assigned: number; distribution: Record<string, number>; }

export const teamApi = {
  list: async (params: { search?: string; status?: string; department_id?: string; leader_id?: string } = {}) =>
    (await api.get<TeamList>('/teams', { params })).data,
  get: async (id: string) => (await api.get<Team>(`/teams/${id}`)).data,
  create: async (payload: any) => (await api.post<Team>('/teams', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Team>(`/teams/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/teams/${id}`); },
  bulk: async (team_ids: string[], action: string) =>
    (await api.post<{ processed: number; errors: any[] }>('/teams/bulk', { team_ids, action })).data,

  members: async (id: string) => (await api.get<TeamMember[]>(`/teams/${id}/members`)).data,
  addMembers: async (id: string, user_ids: string[]) =>
    (await api.post(`/teams/${id}/members`, { user_ids })).data,
  removeMembers: async (id: string, user_ids: string[]) =>
    (await api.post(`/teams/${id}/members/remove`, { user_ids })).data,

  targets: async (id: string) => (await api.get<TeamTarget[]>(`/teams/${id}/targets`)).data,
  createTarget: async (id: string, payload: any) =>
    (await api.post<TeamTarget>(`/teams/${id}/targets`, payload)).data,
  deleteTarget: async (id: string, targetId: string) => { await api.delete(`/teams/${id}/targets/${targetId}`); },

  performance: async (id: string) => (await api.get<TeamPerformance>(`/teams/${id}/performance`)).data,
  calendar: async (id: string, date_from: string, date_to: string) =>
    (await api.get<TeamCalendarItem[]>(`/teams/${id}/calendar`, { params: { date_from, date_to } })).data,
  dashboard: async () => (await api.get<TeamDashboard>('/teams/dashboard')).data,
  analytics: async () => (await api.get<TeamAnalyticsRow[]>('/teams/analytics')).data,

  assignLeads: async (id: string, lead_ids: string[], strategy = 'round_robin') =>
    (await api.post<AssignResult>(`/teams/${id}/assign-leads`, { lead_ids, strategy })).data,
  assignTasks: async (id: string, task_ids: string[], strategy = 'round_robin') =>
    (await api.post<AssignResult>(`/teams/${id}/assign-tasks`, { task_ids, strategy })).data,

  exportCsv: async () => (await api.get('/teams/export', { responseType: 'blob' })).data as Blob,
  importCsv: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return (await api.post<{ created: number; updated: number; skipped: number; errors: any[] }>(
      '/teams/import', form, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
  },
};
