import { api } from './api';

export interface OkrMeta {
  levels: string[]; cycle_types: string[]; metrics: string[]; kr_kinds: string[];
  units: string[]; review_types: string[]; statuses: string[];
}

export interface KeyResult {
  id: string; title: string; kind: string; metric: string | null; unit: string;
  start_value: number; target_value: number; current_value: number; weight: number;
  progress: number; status: string; last_checkin_at: string | null;
}

export interface Objective {
  id: string; title: string; description: string | null; level: string;
  department_id: string | null; team_id: string | null; user_id: string | null;
  owner_id: string; owner_name: string | null; parent_id: string | null;
  cycle_type: string; cycle_year: number; cycle_quarter: number | null; cycle_label: string;
  start_date: string; end_date: string; status: string; progress: number; status_label: string;
  key_results: KeyResult[]; created_at: string | null;
}

export interface ObjectiveNode extends Objective { children: ObjectiveNode[]; }

export interface OkrReview {
  id: string; objective_id: string; key_result_id: string | null; reviewer_id: string;
  reviewer_name: string | null; review_type: string; rating: number | null; confidence: number | null;
  comment: string | null; progress_at: number | null; created_at: string | null;
}

export interface OkrDashboard {
  total: number; achieved: number; on_track: number; at_risk: number; missed: number;
  avg_progress: number; by_level: Record<string, number>; reviews: number;
  at_risk_objectives: Objective[];
}

export interface OkrReport {
  rows: Objective[]; count: number;
  by_level: { level: string; count: number; achieved: number; at_risk: number; avg_progress: number }[];
}

export const okrApi = {
  meta: async () => (await api.get<OkrMeta>('/okr/meta')).data,
  dashboard: async () => (await api.get<OkrDashboard>('/okr/dashboard')).data,
  report: async (params: { level?: string; cycle_year?: number; cycle_quarter?: number } = {}) =>
    (await api.get<OkrReport>('/okr/report', { params })).data,
  tree: async (params: { cycle_year?: number } = {}) => (await api.get<ObjectiveNode[]>('/okr/tree', { params })).data,
  scan: async () => (await api.post<{ completed: number; nudged: number }>('/okr/scan', {})).data,

  list: async (params: { level?: string; status?: string; cycle_year?: number; cycle_quarter?: number } = {}) =>
    (await api.get<Objective[]>('/okr', { params })).data,
  get: async (id: string) => (await api.get<Objective & { reviews: OkrReview[] }>(`/okr/${id}`)).data,
  create: async (payload: any) => (await api.post<Objective>('/okr', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Objective>(`/okr/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/okr/${id}`); },

  addKeyResult: async (objectiveId: string, payload: any) =>
    (await api.post<Objective>(`/okr/${objectiveId}/key-results`, payload)).data,
  updateKeyResult: async (krId: string, payload: any) =>
    (await api.patch<Objective>(`/okr/key-results/${krId}`, payload)).data,
  removeKeyResult: async (krId: string) => (await api.delete<Objective>(`/okr/key-results/${krId}`)).data,
  checkin: async (krId: string, payload: { value: number; confidence?: number; comment?: string }) =>
    (await api.post<Objective>(`/okr/key-results/${krId}/checkin`, payload)).data,

  reviews: async (objectiveId: string) => (await api.get<OkrReview[]>(`/okr/${objectiveId}/reviews`)).data,
  addReview: async (objectiveId: string, payload: { review_type: string; rating?: number; comment: string }) =>
    (await api.post<OkrReview>(`/okr/${objectiveId}/reviews`, payload)).data,
};
