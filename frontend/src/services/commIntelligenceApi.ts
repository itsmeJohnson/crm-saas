import { api } from './api';

export interface Sentiment { label: string; score: number; positive_hits: number; negative_hits: number; }
export interface Language { code: string; name: string; confidence: string; script: string; }

export interface TextAnalysis {
  channel: string | null; chars: number; words: number;
  language: Language; sentiment: Sentiment; intents: string[]; primary_intent: string;
  action_items: string[]; follow_up_suggestions: string[]; translation_ready: boolean;
}

export interface ActivityIntelligence extends TextAnalysis {
  activity_id: string; direction: string | null; subject: string;
  duration: number | null; disposition: string | null; created_at: string | null;
}

export interface ConversationAnalysis {
  messages: number; by_channel?: Record<string, number>;
  timeline: { activity_id: string; channel: string; direction: string | null; subject: string; sentiment: string; sentiment_score: number; created_at: string | null }[];
  overall_sentiment: string; avg_sentiment_score?: number; sentiment_trend?: string;
  intents: { intent: string; count: number }[]; primary_intent?: string;
  action_items: string[]; follow_up_suggestions: string[];
  languages: { code: string; count: number }[];
}

export interface CommIntelDashboard {
  days: number; total: number;
  sentiment: { positive: number; neutral: number; negative: number };
  positive_rate: number; action_items: number;
  by_intent: { intent: string; count: number }[];
  by_channel: Record<string, number>;
  languages: { code: string; count: number }[];
}

export const commIntelligenceApi = {
  analyze: async (text: string, channel?: string) =>
    (await api.post<TextAnalysis>('/comm-intelligence/analyze', { text, channel })).data,
  dashboard: async (days = 30) => (await api.get<CommIntelDashboard>('/comm-intelligence/dashboard', { params: { days } })).data,
  report: async (days = 30) => (await api.get('/comm-intelligence/report', { params: { days } })).data as any,
  exportCsv: async (days = 30) => (await api.get<string>('/comm-intelligence/export', { params: { days }, responseType: 'text' as any })).data,
  transcript: async (transcript: string, activityId?: string) =>
    (await api.post<TextAnalysis & { source: string; activity_id?: string }>('/comm-intelligence/transcript', { transcript, activity_id: activityId })).data,
  translate: async (text: string, targetLang: string) =>
    (await api.post<{ source_language: Language; target_lang: string; original: string; translation: string }>('/comm-intelligence/translate', { text, target_lang: targetLang })).data,
  meetingSummary: async (notes: string) =>
    (await api.post<{ summary: string; action_items: string[]; sentiment: Sentiment; intents: string[]; language: Language }>('/comm-intelligence/meeting-summary', { notes })).data,
  conversation: async (params: { lead_id?: string; contact_id?: string }) =>
    (await api.get<ConversationAnalysis>('/comm-intelligence/conversation', { params })).data,
  activity: async (id: string) => (await api.get<ActivityIntelligence>(`/comm-intelligence/activities/${id}`)).data,
  activitySummary: async (id: string) => (await api.get<{ text: string }>(`/comm-intelligence/activities/${id}/summary`)).data,
};
