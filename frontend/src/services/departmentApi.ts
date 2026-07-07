import { api } from './api';

export interface Department {
  id: string;
  organization_id: string;
  name: string;
  code: string | null;
  description: string | null;
  parent_department_id: string | null;
  head_user_id: string | null;
  head_name: string | null;
  status: string;
  budget: number | null;
  budget_period: string | null;
  cost_center: string | null;
  color: string | null;
  member_count: number;
  created_at: string;
}

export interface DepartmentList { items: Department[]; total: number; }

export interface TreeNode {
  id: string;
  name: string;
  code: string | null;
  status: string;
  head_user_id: string | null;
  member_count: number;
  children: TreeNode[];
}

export interface Member { id: string; name: string; email: string; role: string; is_active: boolean; }

export interface Target {
  id: string;
  name: string;
  metric: string;
  target_value: number;
  period: string;
  start_date: string | null;
  end_date: string | null;
}

export interface KPI {
  target_id: string;
  name: string;
  metric: string;
  target_value: number;
  actual: number;
  attainment: number;
  period: string;
}

export interface Performance {
  department_id: string;
  name: string;
  member_count: number;
  budget: number | null;
  metrics: Record<string, number>;
  kpis: KPI[];
}

export interface Dashboard {
  total: number;
  active: number;
  archived: number;
  total_budget: number;
  unassigned_members: number;
  largest: { id: string; name: string; member_count: number }[];
}

export interface AnalyticsRow {
  department_id: string;
  name: string;
  member_count: number;
  budget: number | null;
  leads_converted: number;
  calls_made: number;
  tasks_completed: number;
  revenue: number;
  activities: number;
}

export const departmentApi = {
  list: async (params: { search?: string; status?: string; parent_id?: string } = {}) =>
    (await api.get<DepartmentList>('/departments', { params })).data,
  tree: async () => (await api.get<TreeNode[]>('/departments/tree')).data,
  get: async (id: string) => (await api.get<Department>(`/departments/${id}`)).data,
  create: async (payload: any) => (await api.post<Department>('/departments', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Department>(`/departments/${id}`, payload)).data,
  setStatus: async (id: string, status: string) => (await api.post<Department>(`/departments/${id}/status`, { status })).data,
  remove: async (id: string) => { await api.delete(`/departments/${id}`); },

  members: async (id: string) => (await api.get<Member[]>(`/departments/${id}/members`)).data,
  assignMembers: async (id: string, user_ids: string[]) => (await api.post(`/departments/${id}/members`, { user_ids })).data,
  removeMembers: async (id: string, user_ids: string[]) => (await api.post(`/departments/${id}/members/remove`, { user_ids })).data,

  targets: async (id: string) => (await api.get<Target[]>(`/departments/${id}/targets`)).data,
  createTarget: async (id: string, payload: any) => (await api.post<Target>(`/departments/${id}/targets`, payload)).data,
  deleteTarget: async (id: string, targetId: string) => { await api.delete(`/departments/${id}/targets/${targetId}`); },

  performance: async (id: string) => (await api.get<Performance>(`/departments/${id}/performance`)).data,
  dashboard: async () => (await api.get<Dashboard>('/departments/dashboard')).data,
  analytics: async () => (await api.get<AnalyticsRow[]>('/departments/analytics')).data,

  exportCsv: async () => (await api.get('/departments/export', { responseType: 'blob' })).data as Blob,
  importCsv: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return (await api.post<{ created: number; updated: number; skipped: number }>('/departments/import', form,
      { headers: { 'Content-Type': 'multipart/form-data' } })).data;
  },
};
