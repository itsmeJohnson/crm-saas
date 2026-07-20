import { api } from './api';

export const TARGET_SCOPES = ['individual', 'team', 'department'] as const;
export const TARGET_PERIODS = ['daily', 'weekly', 'monthly', 'quarterly', 'yearly'] as const;

export interface TargetRow {
  id: string;
  scope: string;
  scope_name: string | null;
  name: string;
  metric: string | null;
  unit: string;
  period: string;
  target_value: number;
  actual: number;
  attainment: number;
  achieved: boolean;
  status_label: string;
  start_date: string;
  end_date: string;
  status: string;
}

export interface TargetDashboard {
  total: number;
  achieved: number;
  on_track: number;
  at_risk: number;
  missed: number;
  avg_attainment: number;
  by_scope: Record<string, number>;
  by_period: Record<string, number>;
  at_risk_targets: TargetRow[];
}

export interface TargetReport { rows: TargetRow[]; count: number; }

export const targetApi = {
  dashboard: async () => (await api.get<TargetDashboard>('/targets/dashboard')).data,
  list: async (params: { scope?: string; period?: string; status?: string } = {}) =>
    (await api.get<TargetRow[]>('/targets', { params })).data,
  report: async (params: { scope?: string; period?: string } = {}) =>
    (await api.get<TargetReport>('/targets/report', { params })).data,
  create: async (payload: any) => (await api.post<{ scope: string; created: boolean }>('/targets', payload)).data,
};
