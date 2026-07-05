import { api } from './api';

export const ORG_METRICS = [
  'sales_revenue', 'leads_converted', 'conversion_rate', 'calls_made', 'tasks_completed', 'recovery_amount',
] as const;

export interface OrgOverview {
  date_from: string;
  date_to: string;
  headcount: number;
  present_today: number;
  attendance_rate: number;
  on_leave_today: number;
  departments: number;
  teams: number;
  branches: number;
  pending_leaves: number;
  leads: number;
  converted: number;
  conversion_rate: number;
  revenue: number;
  calls: number;
  activities: number;
  tasks_completed: number;
  task_completion_rate: number;
}

export interface OrgHealth {
  score: number;
  rating: string;
  components: { name: string; score: number; weight: number }[];
}

export interface OrgLeaderboardRow { rank: number; user_id: string; name: string; value: number; }

export interface OrgHeatmap {
  weekdays: string[];
  grid: number[][];
  peak: { weekday: number; hour: number; count: number; weekday_label: string };
}

export interface OrgTrend { granularity: string; series: any[]; }

export const orgAnalyticsApi = {
  overview: async (params: { date_from?: string; date_to?: string } = {}) =>
    (await api.get<OrgOverview>('/org-analytics/overview', { params })).data,
  health: async () => (await api.get<OrgHealth>('/org-analytics/health')).data,
  leaderboard: async (params: { metric?: string; date_from?: string; date_to?: string; limit?: number } = {}) =>
    (await api.get<OrgLeaderboardRow[]>('/org-analytics/leaderboard', { params })).data,
  heatmap: async (params: { date_from?: string; date_to?: string } = {}) =>
    (await api.get<OrgHeatmap>('/org-analytics/heatmap', { params })).data,
  trend: async (params: { granularity?: string; count?: number } = {}) =>
    (await api.get<OrgTrend>('/org-analytics/trend', { params })).data,
  domain: async (kind: 'department' | 'team' | 'branch' | 'territory', params: { date_from?: string; date_to?: string } = {}) =>
    (await api.get<any[]>(`/org-analytics/domain/${kind}`, { params })).data,
  exportCsv: async (params: { date_from?: string; date_to?: string } = {}) =>
    (await api.get('/org-analytics/export', { params, responseType: 'blob' })).data as Blob,
};
