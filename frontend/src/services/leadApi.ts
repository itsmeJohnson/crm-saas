import { api } from './api';
import { PipelineStage } from './pipelineApi';

export interface LeadResponse {
  id: string;
  organization_id: string;
  first_name: string | null;
  last_name: string;
  email: string | null;
  phone: string | null;
  company_name: string | null;
  title: string;
  status: string;
  source: string | null;
  city?: string | null;
  value: number | null;
  assigned_user_id: string | null;
  stage_id: string;
  stage?: PipelineStage;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export const leadApi = {
  getLeads: async (params: {
    skip?: number;
    limit?: number;
    search?: string;
    status?: string;
    assigned_user_id?: string;
    name?: string;
    city?: string;
  }) => {
    const response = await api.get<LeadResponse[]>('/leads/', { params });
    return response.data;
  },

  createLead: async (payload: {
    title: string;
    last_name: string;
    first_name?: string | null;
    email?: string | null;
    phone?: string | null;
    company_name?: string | null;
    status?: string;
    source?: string | null;
    city?: string | null;
    value?: number | null;
    assigned_user_id?: string | null;
  }) => {
    const response = await api.post<LeadResponse>('/leads/', payload);
    return response.data;
  },

  getLead: async (leadId: string) => {
    const response = await api.get<LeadResponse>(`/leads/${leadId}`);
    return response.data;
  },

  updateLead: async (leadId: string, payload: {
    title?: string;
    last_name?: string;
    first_name?: string | null;
    email?: string | null;
    phone?: string | null;
    company_name?: string | null;
    status?: string;
    source?: string | null;
    city?: string | null;
    value?: number | null;
    assigned_user_id?: string | null;
  }) => {
    const response = await api.patch<LeadResponse>(`/leads/${leadId}`, payload);
    return response.data;
  },

  deleteLead: async (leadId: string) => {
    const response = await api.delete<LeadResponse>(`/leads/${leadId}`);
    return response.data;
  },
};

