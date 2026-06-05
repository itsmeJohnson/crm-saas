import { api } from './api';

export interface ImportPreviewResponse {
  file_token: string;
  headers: string[];
  suggested_mapping: Record<string, { column: string | null; confidence: number }>;
  preview_rows: Record<string, any>[];
}

export interface LeadImportProcessRequest {
  file_token: string;
  source_type: string;
  column_mapping: Record<string, string>;
  auto_assign: boolean;
}

export interface LeadImportResponse {
  id: string;
  organization_id: string;
  filename: string;
  status: string;
  total_rows: number;
  successful_rows: number;
  failed_rows: number;
  mapping_confidence: number;
  error_summary: { row: number; email: string | null; reason: string }[] | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface AssignmentConfigResponse {
  organization_id: string;
  is_active: boolean;
  last_assigned_user_id: string | null;
}

export const leadImportApi = {
  downloadTemplate: async (format: 'csv' | 'xlsx') => {
    const response = await api.get('/leads/import/template', {
      params: { format },
      responseType: 'blob',
    });
    return response.data;
  },

  uploadImportFile: async (file: File) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await api.post<ImportPreviewResponse>('/leads/import/upload', formData, {
      headers: {
        'Content-Type': 'multipart/form-data',
      },
    });
    return response.data;
  },

  previewGoogleSheets: async (url: string) => {
    const response = await api.post<ImportPreviewResponse>('/leads/import/google-sheets', { url });
    return response.data;
  },

  processImport: async (payload: LeadImportProcessRequest) => {
    const response = await api.post<LeadImportResponse>('/leads/import/process', payload);
    return response.data;
  },

  getImportHistory: async (params?: { skip?: number; limit?: number }) => {
    const response = await api.get<LeadImportResponse[]>('/leads/import/history', { params });
    return response.data;
  },

  downloadFailedRows: async (importId: string) => {
    const response = await api.get(`/leads/import/${importId}/failed-rows`, {
      responseType: 'blob',
    });
    return response.data;
  },

  getAssignmentConfig: async () => {
    const response = await api.get<AssignmentConfigResponse>('/leads/assignment/config');
    return response.data;
  },

  updateAssignmentConfig: async (isActive: boolean) => {
    const response = await api.patch<AssignmentConfigResponse>('/leads/assignment/config', { is_active: isActive });
    return response.data;
  },
};
