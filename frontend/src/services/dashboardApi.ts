import { api } from './api';

export interface AssignedLeadBreakdown {
  user_id: string;
  user_name: string;
  lead_count: number;
}

export interface DashboardSummaryResponse {
  total_leads: number;
  contacts_count: number;
  companies_count: number;
  user_count: number;
  activities_count: number;
  leads_by_status: Record<string, number>;
  assigned_leads_breakdown: AssignedLeadBreakdown[];
}

export interface RecentActivityItem {
  id: string;
  activity_type: string;
  subject: string;
  description: string | null;
  due_date: string | null;
  status: string;
  assigned_user_id: string | null;
  assigned_user_name: string;
  created_at: string;
}

export interface RecentActivitiesResponse {
  items: RecentActivityItem[];
  total: number;
  page: number;
  limit: number;
}

export const dashboardApi = {
  getSummary: async () => {
    const response = await api.get<DashboardSummaryResponse>('/dashboard/summary');
    return response.data;
  },

  getRecentActivities: async (params?: { page?: number; limit?: number }) => {
    const response = await api.get<RecentActivitiesResponse>('/dashboard/recent-activities', { params });
    return response.data;
  },
};
