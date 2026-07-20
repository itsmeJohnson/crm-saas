import { api } from './api';

export interface Completeness { pct: number; present: string[]; missing: string[]; }
export interface Factor { points: number; factor: string; }
export interface NextBestAction { action: string; priority: string; reason: string; }
export interface DuplicateSuggestion {
  lead_id: string; name: string; email: string | null; phone: string | null;
  status: string; match_on: string[]; confidence: string;
}
export interface EnrichmentHint { field: string; suggestion: string; }

export interface LeadIntelligence {
  lead_id: string; name: string; status: string; value: number; assigned_user_id: string | null;
  score: number; score_grade: string;
  conversion_probability: number; conversion_factors: Factor[];
  temperature: string; quality_grade: string;
  completeness: Completeness; opportunity_score: number;
  risk_score: number; risk_reasons: string[];
  recommended_priority: string; next_best_action: NextBestAction;
  insights: string[]; enrichment_suggestions: EnrichmentHint[];
  duplicate_suggestions?: DuplicateSuggestion[];
  age_days: number; activities: number; method: string; ai_ready: boolean;
}

export interface LeadIntelDashboard {
  total: number;
  by_temperature: Record<string, number>;
  by_quality: Record<string, number>;
  avg_score: number; avg_completeness: number; avg_conversion_probability: number;
  hot_leads: LeadIntelligence[]; at_risk_leads: LeadIntelligence[]; needs_enrichment: LeadIntelligence[];
}

export interface LeadIntelReport {
  total: number;
  by_temperature: Record<string, number>;
  by_quality: Record<string, number>;
  by_score_grade: Record<string, number>;
  by_owner: { owner_id: string; owner_name: string; count: number; hot: number; avg_score: number; avg_opportunity: number }[];
}

export const leadIntelligenceApi = {
  dashboard: async () => (await api.get<LeadIntelDashboard>('/lead-intelligence/dashboard')).data,
  report: async () => (await api.get<LeadIntelReport>('/lead-intelligence/report')).data,
  list: async (params: { temperature?: string; quality?: string; sort?: string; limit?: number } = {}) =>
    (await api.get<{ total: number; rows: LeadIntelligence[] }>('/lead-intelligence/leads', { params })).data,
  lead: async (id: string) => (await api.get<LeadIntelligence>(`/lead-intelligence/leads/${id}`)).data,
  summary: async (id: string) => (await api.get<{ text: string }>(`/lead-intelligence/leads/${id}/summary`)).data,
  duplicates: async (id: string) => (await api.get<DuplicateSuggestion[]>(`/lead-intelligence/leads/${id}/duplicates`)).data,
  exportCsv: async () => (await api.get<string>('/lead-intelligence/export', { responseType: 'text' as any })).data,
};
