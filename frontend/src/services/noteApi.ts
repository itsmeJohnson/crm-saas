import { api } from './api';

export interface NoteResponse {
  id: string;
  organization_id: string;
  content: string;
  lead_id: string | null;
  contact_id: string | null;
  company_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export const noteApi = {
  getNotes: async (params: {
    skip?: number;
    limit?: number;
    lead_id?: string;
    contact_id?: string;
    company_id?: string;
  }) => {
    const response = await api.get<NoteResponse[]>('/notes/', { params });
    return response.data;
  },

  createNote: async (payload: {
    content: string;
    lead_id?: string | null;
    contact_id?: string | null;
    company_id?: string | null;
  }) => {
    const response = await api.post<NoteResponse>('/notes/', payload);
    return response.data;
  },

  updateNote: async (noteId: string, payload: {
    content: string;
  }) => {
    const response = await api.patch<NoteResponse>(`/notes/${noteId}`, payload);
    return response.data;
  },

  deleteNote: async (noteId: string) => {
    const response = await api.delete<NoteResponse>(`/notes/${noteId}`);
    return response.data;
  },
};
