import { api } from './api';

export interface KbCategory {
  id: string; name: string; description: string | null; parent_id: string | null;
  display_order: number; article_count: number;
}

export interface KbArticle {
  id: string; title: string; summary: string | null; content?: string;
  article_type: string; status: string; category_id: string | null; tags: string[];
  visibility: string; language: string; source_filename: string | null; version: number;
  created_by: string | null; reviewed_by: string | null; review_note: string | null;
  published_at: string | null; is_indexed: boolean; chunk_count: number;
  view_count: number; helpful_count: number; not_helpful_count: number;
  created_at: string | null; updated_at: string | null;
}

export interface KbSearchResult {
  article_id: string; title: string; article_type: string; score: number; excerpt: string;
}

export interface KbAskResult {
  question: string; answer: string; model: string; provider: string; cached: boolean;
  grounded: boolean; sources: { article_id: string; title: string; score: number }[];
  tokens: { prompt: number; completion: number; total: number } | null;
  embedding_model: string;
}

export interface KbFaq {
  id: string; question: string; answer: string; category: string | null;
  views: number; helpful: number;
}

export interface KbDashboard {
  totals: {
    articles: number; by_status: Record<string, number>; by_type: Record<string, number>;
    categories: number; chunks: number; indexed: number; indexed_pct: number; total_views: number;
  };
  helpful_rate: number | null;
  events_30d: Record<string, number>;
  recent_searches: { query: string; results: number | null; type: string; at: string | null }[];
  unanswered_queries: { query: string; count: number }[];
  top_articles: { id: string; title: string; views: number; helpful: number }[];
  embedding_model: string;
}

export const knowledgeApi = {
  dashboard: async () => (await api.get<KbDashboard>('/knowledge/dashboard')).data,
  exportCsv: async () => (await api.get<string>('/knowledge/export')).data,

  categories: async () => (await api.get<KbCategory[]>('/knowledge/categories')).data,
  createCategory: async (payload: any) => (await api.post<KbCategory>('/knowledge/categories', payload)).data,
  updateCategory: async (id: string, payload: any) => (await api.patch(`/knowledge/categories/${id}`, payload)).data,
  deleteCategory: async (id: string) => (await api.delete(`/knowledge/categories/${id}`)).data,

  articles: async (params: any = {}) =>
    (await api.get<{ total: number; items: KbArticle[] }>('/knowledge/articles', { params })).data,
  article: async (id: string, recordView = true) =>
    (await api.get<KbArticle>(`/knowledge/articles/${id}`, { params: { record_view: recordView } })).data,
  createArticle: async (payload: any) => (await api.post<KbArticle>('/knowledge/articles', payload)).data,
  updateArticle: async (id: string, payload: any) => (await api.patch<KbArticle>(`/knowledge/articles/${id}`, payload)).data,
  deleteArticle: async (id: string) => (await api.delete(`/knowledge/articles/${id}`)).data,
  versions: async (id: string) => (await api.get<any[]>(`/knowledge/articles/${id}/versions`)).data,
  restoreVersion: async (id: string, version: number) =>
    (await api.post<KbArticle>(`/knowledge/articles/${id}/versions/${version}/restore`)).data,

  submit: async (id: string) => (await api.post(`/knowledge/articles/${id}/submit`)).data,
  approve: async (id: string, note?: string) => (await api.post(`/knowledge/articles/${id}/approve`, { note })).data,
  reject: async (id: string, note?: string) => (await api.post(`/knowledge/articles/${id}/reject`, { note })).data,
  archive: async (id: string) => (await api.post(`/knowledge/articles/${id}/archive`)).data,
  feedback: async (id: string, helpful: boolean, comment?: string) =>
    (await api.post(`/knowledge/articles/${id}/feedback`, { helpful, comment })).data,

  faq: async (categoryId?: string) =>
    (await api.get<KbFaq[]>('/knowledge/faq', { params: categoryId ? { category_id: categoryId } : {} })).data,
  search: async (query: string, limit = 10, articleType?: string) =>
    (await api.post<{ query: string; results: KbSearchResult[]; count: number }>(
      '/knowledge/search', { query, limit, article_type: articleType })).data,
  ask: async (question: string) => (await api.post<KbAskResult>('/knowledge/ask', { question })).data,
  reindex: async () => (await api.post<{ articles: number; chunks: number }>('/knowledge/reindex')).data,
};
