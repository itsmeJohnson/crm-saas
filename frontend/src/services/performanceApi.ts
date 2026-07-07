import { api } from './api';

export const PERFORMANCE_METRICS = [
  'calls_made', 'leads_converted', 'conversion_rate', 'sales_revenue',
  'recovery_amount', 'tasks_completed', 'activities', 'attendance_score',
] as const;

export interface KPI {
  id: string;
  name: string;
  code: string | null;
  metric: string;
  description: string | null;
  unit: string;
  weight: number;
  higher_is_better: boolean;
  status: string;
  color: string | null;
  created_at: string;
}

export interface Goal {
  id: string;
  user_id: string;
  user_name: string | null;
  kpi_id: string;
  kpi_name: string | null;
  metric: string | null;
  unit: string | null;
  period: string;
  target_value: number;
  actual: number;
  attainment: number;
  start_date: string;
  end_date: string;
  status: string;
  created_at: string;
}

export interface ScorecardKPIRow {
  kpi_id: string;
  name: string;
  metric: string;
  unit: string;
  actual: number;
  target: number | null;
  attainment: number | null;
  weight: number;
}

export interface Scorecard {
  user_id: string;
  user_name: string | null;
  date_from: string;
  date_to: string;
  metrics: Record<string, number>;
  kpis: ScorecardKPIRow[];
  composite_score: number | null;
}

export interface LeaderboardRow { rank: number; user_id: string; name: string; value: number; }

export interface Achievement {
  id: string;
  user_id: string;
  user_name: string | null;
  title: string;
  badge: string | null;
  period_label: string | null;
  achieved_value: number;
  target_value: number;
  attainment: number;
  awarded_at: string;
}

export interface Trend { user_id: string; granularity: string; series: any[]; }

export interface PerformanceDashboard {
  my_metrics: Record<string, number>;
  my_composite_score: number | null;
  my_open_goals: number;
  my_achievements: number;
  top_sales: { rank: number; user_id: string; name: string; value: number }[];
}

export interface PerformanceReport { date_from: string; date_to: string; rows: any[]; }

export const performanceApi = {
  dashboard: async () => (await api.get<PerformanceDashboard>('/performance/dashboard')).data,
  scorecard: async (params: { user_id?: string; date_from?: string; date_to?: string } = {}) =>
    (await api.get<Scorecard>('/performance/scorecard', { params })).data,
  trend: async (params: { user_id?: string; granularity?: string; count?: number; metric?: string } = {}) =>
    (await api.get<Trend>('/performance/trend', { params })).data,
  leaderboard: async (params: { metric?: string; date_from?: string; date_to?: string; limit?: number } = {}) =>
    (await api.get<LeaderboardRow[]>('/performance/leaderboard', { params })).data,
  report: async (params: { date_from?: string; date_to?: string; user_id?: string } = {}) =>
    (await api.get<PerformanceReport>('/performance/report', { params })).data,

  listKpis: async (params: { status?: string } = {}) => (await api.get<KPI[]>('/performance/kpis', { params })).data,
  createKpi: async (payload: any) => (await api.post<KPI>('/performance/kpis', payload)).data,
  seedKpis: async () => (await api.post<{ created: number }>('/performance/kpis/seed', {})).data,
  updateKpi: async (id: string, payload: any) => (await api.patch<KPI>(`/performance/kpis/${id}`, payload)).data,
  deleteKpi: async (id: string) => { await api.delete(`/performance/kpis/${id}`); },

  listGoals: async (params: { user_id?: string; status?: string } = {}) =>
    (await api.get<Goal[]>('/performance/goals', { params })).data,
  createGoal: async (payload: any) => (await api.post<Goal>('/performance/goals', payload)).data,
  updateGoal: async (id: string, payload: any) => (await api.patch<Goal>(`/performance/goals/${id}`, payload)).data,
  deleteGoal: async (id: string) => { await api.delete(`/performance/goals/${id}`); },

  listAchievements: async (params: { user_id?: string } = {}) =>
    (await api.get<Achievement[]>('/performance/achievements', { params })).data,
  evaluate: async () => (await api.post<{ awarded: number }>('/performance/achievements/evaluate', {})).data,
};
