import { api } from './api';

export interface CompanyAttachment {
  filename: string;
  url: string;
  size?: number;
  uploaded_by?: string;
  uploaded_at?: string;
}

export interface CompanyResponse {
  id: string;
  organization_id: string;
  name: string;
  domain: string | null;
  industry: string | null;
  website: string | null;
  phone: string | null;
  assigned_user_id: string | null;
  company_type: string;
  source: string | null;
  employee_count: number | null;
  annual_revenue: number | null;
  tags: string[] | null;
  attachments: CompanyAttachment[] | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface CompanyListFilters {
  skip?: number;
  limit?: number;
  search?: string;
  industry?: string;
  company_type?: string;
  source?: string;
  assigned_user_id?: string;
  tag?: string;
}

export interface CompanyContactSummary {
  id: string;
  first_name: string;
  last_name: string;
  email: string | null;
  job_title: string | null;
}

export interface CompanyLeadSummary {
  id: string;
  title: string;
  status: string;
  stage: string | null;
  value: number | null;
  assigned_user_id: string | null;
}

export interface CompanyDealsSummary {
  total_leads: number;
  open_count: number;
  won_count: number;
  lost_count: number;
  total_value: number;
  won_value: number;
  by_stage: { stage: string; count: number; value: number }[];
}

export interface CompanyTimelineEvent {
  type: 'note' | 'activity' | 'audit';
  id: string;
  timestamp: string;
  title: string;
  description: string | null;
  actor_user_id: string | null;
  event_metadata: Record<string, any> | null;
}

export interface CompanyCommunication {
  id: string;
  channel: string;
  subject: string;
  description: string | null;
  direction: string | null;
  status: string;
  timestamp: string;
  recording_url: string | null;
}

export interface CompanyReportBucket {
  label: string;
  count: number;
  revenue: number;
}

export interface CompanyReport {
  total_companies: number;
  total_revenue: number;
  total_employees: number;
  customers: number;
  prospects: number;
  partners: number;
  by_industry: CompanyReportBucket[];
  by_type: CompanyReportBucket[];
  by_source: CompanyReportBucket[];
  top_by_revenue: { name: string; revenue: number }[];
}

type CompanyWritePayload = {
  name?: string;
  domain?: string | null;
  industry?: string | null;
  website?: string | null;
  phone?: string | null;
  assigned_user_id?: string | null;
  company_type?: string;
  source?: string | null;
  employee_count?: number | null;
  annual_revenue?: number | null;
  tags?: string[] | null;
};

export const companyApi = {
  getCompanies: async (params: CompanyListFilters) => {
    const response = await api.get<CompanyResponse[]>('/companies/', { params });
    return response.data;
  },

  createCompany: async (payload: CompanyWritePayload & { name: string }) => {
    const response = await api.post<CompanyResponse>('/companies/', payload);
    return response.data;
  },

  getCompany: async (companyId: string) => {
    const response = await api.get<CompanyResponse>(`/companies/${companyId}`);
    return response.data;
  },

  updateCompany: async (companyId: string, payload: CompanyWritePayload) => {
    const response = await api.patch<CompanyResponse>(`/companies/${companyId}`, payload);
    return response.data;
  },

  deleteCompany: async (companyId: string) => {
    const response = await api.delete<CompanyResponse>(`/companies/${companyId}`);
    return response.data;
  },

  getContacts: async (companyId: string) => {
    const response = await api.get<CompanyContactSummary[]>(`/companies/${companyId}/contacts`);
    return response.data;
  },

  getLeads: async (companyId: string) => {
    const response = await api.get<CompanyLeadSummary[]>(`/companies/${companyId}/leads`);
    return response.data;
  },

  getDeals: async (companyId: string) => {
    const response = await api.get<CompanyDealsSummary>(`/companies/${companyId}/deals`);
    return response.data;
  },

  getTimeline: async (companyId: string) => {
    const response = await api.get<CompanyTimelineEvent[]>(`/companies/${companyId}/timeline`);
    return response.data;
  },

  getCommunications: async (companyId: string) => {
    const response = await api.get<CompanyCommunication[]>(`/companies/${companyId}/communications`);
    return response.data;
  },

  listAttachments: async (companyId: string) => {
    const response = await api.get<CompanyAttachment[]>(`/companies/${companyId}/attachments`);
    return response.data;
  },

  uploadAttachment: async (companyId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post<CompanyAttachment>(`/companies/${companyId}/attachments`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  deleteAttachment: async (companyId: string, filename: string) => {
    await api.delete(`/companies/${companyId}/attachments/${encodeURIComponent(filename)}`);
  },

  listTags: async () => {
    const response = await api.get<string[]>('/companies/tags');
    return response.data;
  },

  getReport: async (params?: { date_from?: string; date_to?: string }) => {
    const response = await api.get<CompanyReport>('/companies/reports', { params });
    return response.data;
  },
};
