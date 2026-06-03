import { api } from './api';

export interface ContactResponse {
  id: string;
  organization_id: string;
  company_id: string | null;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  job_title: string | null;
  assigned_user_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export const contactApi = {
  getContacts: async (params: { skip?: number; limit?: number; search?: string; company_id?: string }) => {
    const response = await api.get<ContactResponse[]>('/contacts/', { params });
    return response.data;
  },

  createContact: async (payload: {
    first_name: string;
    last_name: string;
    email?: string | null;
    phone?: string | null;
    job_title?: string | null;
    company_id?: string | null;
    assigned_user_id?: string | null;
  }) => {
    const response = await api.post<ContactResponse>('/contacts/', payload);
    return response.data;
  },

  getContact: async (contactId: string) => {
    const response = await api.get<ContactResponse>(`/contacts/${contactId}`);
    return response.data;
  },

  updateContact: async (contactId: string, payload: {
    first_name?: string;
    last_name?: string;
    email?: string | null;
    phone?: string | null;
    job_title?: string | null;
    company_id?: string | null;
    assigned_user_id?: string | null;
  }) => {
    const response = await api.patch<ContactResponse>(`/contacts/${contactId}`, payload);
    return response.data;
  },

  deleteContact: async (contactId: string) => {
    const response = await api.delete<ContactResponse>(`/contacts/${contactId}`);
    return response.data;
  },
};
