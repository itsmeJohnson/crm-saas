import { api } from './api';

export interface AiaDashboard {
  days: number; requests: number; tokens: number; cost_usd: number;
  success_rate: number; failure_rate: number;
  avg_latency_ms: number; p95_latency_ms: number;
  quality_score: number; quality_band: string;
  adoption_rate: number; ai_users: number;
  top_features: { feature: string; requests: number; share_pct: number }[];
  top_models: { provider: string; model: string; requests: number; success_rate: number; avg_latency_ms: number }[];
  latency_trend: { day: string; avg_ms: number; p95_ms: number; samples: number }[];
}

export interface AiaOverview {
  days: number;
  usage: { requests: number; billable_requests: number; cached: number; cache_hit_rate: number; fallbacks: number; fallback_rate: number };
  tokens: { prompt: number; completion: number; total: number; avg_per_request: number };
  cost: { total_usd: number; avg_per_request_usd: number; cost_per_1k_tokens_usd: number };
  reliability: { success: number; failed: number; success_rate: number; failure_rate: number };
}

export interface AiaLatency {
  days: number; samples: number; avg_ms: number; p50_ms: number; p95_ms: number; p99_ms: number;
  max_ms: number; sla_ms: number; within_sla_rate: number;
  slowest_models: { model: string; avg_ms: number; p95_ms: number; samples: number }[];
  trend: { day: string; avg_ms: number; p95_ms: number; samples: number }[];
}

export interface AiaQuality {
  days: number; quality_score: number; band: string;
  components: Record<string, number>; weights: Record<string, number>;
  sample_size: number; note: string;
  signals: { failed: number; fallbacks: number; governance_blocked_or_flagged: number; slow_calls: number };
}

export interface AiaUserAdoption {
  days: number; total_active_users: number; ai_users: number; adoption_rate: number;
  avg_requests_per_ai_user: number; non_adopters: number;
  top_users: { user_id: string; user_name: string; requests: number; tokens: number; cost_usd: number; failed: number; features_used: number; last_used: string | null }[];
}

export interface AiaFeatureAdoption {
  days: number; total_requests: number; features_used: number; most_used: string | null; least_used: string | null;
  features: { feature: string; requests: number; share_pct: number; tokens: number; cost_usd: number; unique_users: number; success_rate: number }[];
}

export interface AiaPromptPerformance {
  days: number; prompts_used: number;
  prompts: { template_key: string; name: string; category: string | null; status: string | null;
    requests: number; success_rate: number; failure_rate: number; cache_hit_rate: number;
    tokens: number; avg_tokens: number; cost_usd: number; avg_latency_ms: number; p95_latency_ms: number }[];
  worst_by_failure: any[];
}

export interface AiaModelPerformance {
  days: number; models_used: number;
  models: { provider: string; model: string; requests: number; success_rate: number; failure_rate: number;
    fallback_count: number; tokens: number; cost_usd: number; cost_per_1k_tokens_usd: number;
    avg_latency_ms: number; p95_latency_ms: number }[];
  by_provider: { provider: string; requests: number; failed: number; cost: number; tokens: number; success_rate: number }[];
}

const d = (days: number) => ({ params: { days } });

export const aiAnalyticsApi = {
  dashboard: async (days = 30) => (await api.get<AiaDashboard>('/ai-analytics/dashboard', d(days))).data,
  overview: async (days = 30) => (await api.get<AiaOverview>('/ai-analytics/overview', d(days))).data,
  latency: async (days = 30) => (await api.get<AiaLatency>('/ai-analytics/latency', d(days))).data,
  quality: async (days = 30) => (await api.get<AiaQuality>('/ai-analytics/quality', d(days))).data,
  userAdoption: async (days = 30) => (await api.get<AiaUserAdoption>('/ai-analytics/user-adoption', d(days))).data,
  featureAdoption: async (days = 30) => (await api.get<AiaFeatureAdoption>('/ai-analytics/feature-adoption', d(days))).data,
  promptPerformance: async (days = 30) => (await api.get<AiaPromptPerformance>('/ai-analytics/prompt-performance', d(days))).data,
  modelPerformance: async (days = 30) => (await api.get<AiaModelPerformance>('/ai-analytics/model-performance', d(days))).data,
  report: async (days = 30) => (await api.get<any>('/ai-analytics/report', d(days))).data,
  exportCsv: async (days = 30) => (await api.get<string>('/ai-analytics/export', d(days))).data,
};

export const QUALITY_TONE: Record<string, string> = {
  excellent: 'text-emerald-400', good: 'text-emerald-300',
  fair: 'text-amber-400', poor: 'text-red-400',
};
