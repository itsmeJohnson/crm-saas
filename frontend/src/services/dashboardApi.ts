import { api } from './api';

export interface AssignedLeadBreakdown {
  user_id: string;
  user_name: string;
  lead_count: number;
}

export interface LeadsByStage {
  stage_id: string;
  stage_name: string;
  count: number;
}

export interface TodayAgenda {
  leads_created: number;
  meetings_due: number;
  tasks_due: number;
  follow_ups_due: number;
}

export interface DashboardSummaryResponse {
  total_leads: number;
  contacts_count: number;
  companies_count: number;
  user_count: number;
  activities_count: number;
  leads_by_status: Record<string, number>;
  assigned_leads_breakdown: AssignedLeadBreakdown[];
  leads_by_source: Record<string, number>;
  leads_by_stage: LeadsByStage[];
  conversion_rate: number | null;
  today: TodayAgenda;
}

export interface TeamStatusMember {
  user_id: string;
  user_name: string;
  role: string;
  state: 'IDLE' | 'ACTIVE_CALLING' | 'BREAK';
  since: string | null;
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

  getTeamStatus: async () => {
    const response = await api.get<TeamStatusMember[]>('/dashboard/team-status');
    return response.data;
  },
};
