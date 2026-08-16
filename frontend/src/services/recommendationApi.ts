import { api } from './api';

export interface Recommendation {
  id?: string; rec_type: string; rec_key: string; title: string; reason: string;
  priority: string; score: number; personalized_score?: number;
  target_type: string | null; target_id: string | null; payload: Record<string, any>;
  action?: string;
}

export interface RecFeed {
  generated_at: string; count: number; personalization: Record<string, number>;
  recommendations: Recommendation[]; types_present: string[];
  explanation?: { boosted_types: string[]; muted_types: string[]; note: string };
}

export interface RecAnalytics {
  totals: Record<string, number>; overall_acceptance_rate: number | null;
  by_type: { rec_type: string; shown: number; accepted: number; dismissed: number;
    completed: number; snoozed: number; pending: number; acceptance_rate: number | null }[];
  top_accepted: { title: string; rec_type: string; acted_at: string | null }[];
}

export interface RecDashboard {
  top_recommendations: Recommendation[]; types_present: string[]; total: number;
  my_pending: number; my_accepted: number;
}

export const recommendationApi = {
  feed: async (limit = 25) => (await api.get<RecFeed>('/recommendations/feed', { params: { limit } })).data,
  personalized: async (limit = 25) => (await api.get<RecFeed>('/recommendations/personalized', { params: { limit } })).data,
  dashboard: async () => (await api.get<RecDashboard>('/recommendations/dashboard')).data,
  analytics: async () => (await api.get<RecAnalytics>('/recommendations/analytics')).data,
  report: async () => (await api.get<any>('/recommendations/report')).data,
  exportCsv: async () => (await api.get<string>('/recommendations/export')).data,
  feedback: async (payload: { action: string; feedback_id?: string; rec_key?: string;
    rec_type?: string; title?: string; snooze_hours?: number }) =>
    (await api.post('/recommendations/feedback', payload)).data,

  agents: async (leadId?: string) =>
    (await api.get<Recommendation[]>('/recommendations/agents', { params: leadId ? { lead_id: leadId } : {} })).data,
  knowledge: async (q: string) =>
    (await api.get<Recommendation[]>('/recommendations/knowledge', { params: { q } })).data,
};
