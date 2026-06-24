import { api } from './api';

export interface CompanyResponse {
  id: string;
  organization_id: string;
  name: string;
  domain: string | null;
  industry: string | null;
  website: string | null;
  phone: string | null;
  assigned_user_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export const companyApi = {
  getCompanies: async (params: { skip?: number; limit?: number; search?: string }) => {
    const response = await api.get<CompanyResponse[]>('/companies/', { params });
    return response.data;
  },

  createCompany: async (payload: {
    name: string;
    domain?: string;
    industry?: string;
    website?: string;
    phone?: string;
    assigned_user_id?: string | null;
  }) => {
    const response = await api.post<CompanyResponse>('/companies/', payload);
    return response.data;
  },

  getCompany: async (companyId: string) => {
    const response = await api.get<CompanyResponse>(`/companies/${companyId}`);
    return response.data;
  },

  updateCompany: async (companyId: string, payload: {
    name?: string;
    domain?: string | null;
    industry?: string | null;
    website?: string | null;
    phone?: string | null;
    assigned_user_id?: string | null;
  }) => {
    const response = await api.patch<CompanyResponse>(`/companies/${companyId}`, payload);
    return response.data;
  },

  deleteCompany: async (companyId: string) => {
    const response = await api.delete<CompanyResponse>(`/companies/${companyId}`);
    return response.data;
  },
};
