import { api } from './api';

export interface DiCapabilities {
  pdf: boolean; docx: boolean; xlsx: boolean; images: boolean; ocr: boolean;
  text_formats: string[]; image_formats: string[]; embedding_model: string;
}

export interface DiDocument {
  id: string; filename: string; content_type: string | null; size_bytes: number;
  source: string; context_type: string | null; context_id: string | null;
  status: string; error: string | null; page_count: number; ocr_used: boolean;
  doc_type: string; classification_confidence: number;
  extraction: Record<string, any>; tables: { headers: string[]; rows: string[][]; source: string }[];
  image_info: Record<string, any>; summary: string | null; embedding_model: string;
  uploaded_by: string | null; processed_at: string | null; created_at: string | null;
  text_content?: string | null;
}

export interface DiDashboard {
  totals: {
    documents: number; by_type: Record<string, number>; by_status: Record<string, number>;
    pages: number; ocr_used: number; with_tables: number; with_structured_extraction: number;
  };
  recent: DiDocument[];
  capabilities: DiCapabilities;
}

export interface DiSearchResult {
  id: string; filename: string; doc_type: string; score: number; excerpt: string;
}

export const documentIntelligenceApi = {
  capabilities: async () => (await api.get<DiCapabilities>('/document-intelligence/capabilities')).data,
  dashboard: async () => (await api.get<DiDashboard>('/document-intelligence/dashboard')).data,
  exportCsv: async () => (await api.get<string>('/document-intelligence/export')).data,

  upload: async (file: File, contextType?: string, contextId?: string) => {
    const fd = new FormData();
    fd.append('file', file);
    if (contextType) fd.append('context_type', contextType);
    if (contextId) fd.append('context_id', contextId);
    return (await api.post<DiDocument>('/document-intelligence/upload', fd,
      { headers: { 'Content-Type': 'multipart/form-data' } })).data;
  },
  processText: async (text: string, filename = 'pasted.txt') =>
    (await api.post<DiDocument>('/document-intelligence/process-text', { text, filename })).data,

  documents: async (params: any = {}) =>
    (await api.get<{ total: number; items: DiDocument[] }>('/document-intelligence/documents', { params })).data,
  document: async (id: string) => (await api.get<DiDocument>(`/document-intelligence/documents/${id}`)).data,
  deleteDocument: async (id: string) => (await api.delete(`/document-intelligence/documents/${id}`)).data,
  reprocess: async (id: string) => (await api.post<DiDocument>(`/document-intelligence/documents/${id}/reprocess`)).data,
  summarize: async (id: string, length = 5) =>
    (await api.post<{ id: string; summary: string; provider: string; model: string }>(
      `/document-intelligence/documents/${id}/summarize`, { length })).data,

  search: async (query: string, docType?: string, limit = 10) =>
    (await api.post<{ query: string; results: DiSearchResult[]; count: number }>(
      '/document-intelligence/search', { query, doc_type: docType || null, limit })).data,
};
