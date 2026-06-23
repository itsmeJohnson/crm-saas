import { api } from './api';

export interface ActivityResponse {
  id: string;
  organization_id: string;
  activity_type: string;
  subject: string;
  description: string | null;
  due_date: string | null;
  status: string;
  assigned_user_id: string | null;
  lead_id: string | null;
  contact_id: string | null;
  company_id: string | null;
  created_by: string;
  created_at: string;
  updated_at: string;
  call_sid?: string | null;
  recording_url?: string | null;
  call_duration?: number | null;
  call_direction?: string | null;
}

export const activityApi = {
  getActivities: async (params: {
    skip?: number;
    limit?: number;
    activity_type?: string;
    status?: string;
    assigned_user_id?: string;
    lead_id?: string;
    contact_id?: string;
    company_id?: string;
  }) => {
    const response = await api.get<ActivityResponse[]>('/activities/', { params });
    return response.data;
  },

  createActivity: async (payload: {
    activity_type: string;
    subject: string;
    description?: string | null;
    due_date?: string | null;
    status?: string;
    assigned_user_id?: string | null;
    lead_id?: string | null;
    contact_id?: string | null;
    company_id?: string | null;
  }) => {
    const response = await api.post<ActivityResponse>('/activities/', payload);
    return response.data;
  },

  getActivity: async (activityId: string) => {
    const response = await api.get<ActivityResponse>(`/activities/${activityId}`);
    return response.data;
  },

  updateActivity: async (activityId: string, payload: {
    activity_type?: string;
    subject?: string;
    description?: string | null;
    due_date?: string | null;
    status?: string;
    assigned_user_id?: string | null;
    lead_id?: string | null;
    contact_id?: string | null;
    company_id?: string | null;
  }) => {
    const response = await api.patch<ActivityResponse>(`/activities/${activityId}`, payload);
    return response.data;
  },

  deleteActivity: async (activityId: string) => {
    const response = await api.delete<ActivityResponse>(`/activities/${activityId}`);
    return response.data;
  },
};
