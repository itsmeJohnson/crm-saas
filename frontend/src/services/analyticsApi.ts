import { api } from './api';

export interface PerformanceTarget {
  id: string;
  organization_id: string;
  target_type: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'QUARTERLY' | 'YEARLY';
  metric_type: 'CALLS_MADE' | 'LEADS_CONVERTED';
  target_value: number;
  start_date: string;
  end_date: string;
  created_at: string;
  updated_at: string;
}

export interface TelecallerMetrics {
  calls_made: number;
  unique_leads_contacted: number;
  conversions: number;
  date: string;
}

export interface TelecallerPerformanceSummary {
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  email: string;
  calls_made: number;
  unique_leads_contacted: number;
  conversions: number;
  conversion_rate: number;
}

export interface PerformerMetric {
  user_id: string;
  first_name: string | null;
  last_name: string | null;
  email: string;
  calls_made: number;
  conversions: number;
  conversion_rate: number;
}

export interface TeamLeaderMetrics {
  total_calls_made: number;
  total_unique_leads_contacted: number;
  total_conversions: number;
  downlines: TelecallerPerformanceSummary[];
  top_performer: PerformerMetric | null;
  low_performer: PerformerMetric | null;
}

export interface TeamLeaderClusterSummary {
  tl_id: string;
  tl_first_name: string | null;
  tl_last_name: string | null;
  tl_email: string;
  total_calls_made: number;
  total_unique_leads_contacted: number;
  total_conversions: number;
}

export interface ManagerMetrics {
  teams: TeamLeaderClusterSummary[];
  total_calls_made: number;
  total_unique_leads_contacted: number;
  total_conversions: number;
}

export interface TargetProgress {
  target_id: string;
  target_type: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'QUARTERLY' | 'YEARLY';
  metric_type: 'CALLS_MADE' | 'LEADS_CONVERTED';
  target_value: number;
  actual_value: number;
  progress_percentage: number;
  start_date: string;
  end_date: string;
}

export interface SuperAdminMetrics {
  targets_progress: TargetProgress[];
}

export interface UnifiedDashboardResponse {
  role: 'SuperAdmin' | 'Manager' | 'TeamLeader' | 'Telecaller';
  metrics: TelecallerMetrics | TeamLeaderMetrics | ManagerMetrics | SuperAdminMetrics;
}

export interface PerformanceTargetCreate {
  target_type: 'DAILY' | 'WEEKLY' | 'MONTHLY' | 'QUARTERLY' | 'YEARLY';
  metric_type: 'CALLS_MADE' | 'LEADS_CONVERTED';
  target_value: number;
  start_date: string;
  end_date: string;
}

export const analyticsApi = {
  getDashboardMetrics: async (targetDate?: string): Promise<UnifiedDashboardResponse> => {
    const params = targetDate ? { target_date: targetDate } : {};
    const res = await api.get<UnifiedDashboardResponse>('/analytics/dashboard', { params });
    return res.data;
  },

  createTarget: async (targetData: PerformanceTargetCreate): Promise<PerformanceTarget> => {
    const res = await api.post<PerformanceTarget>('/analytics/targets', targetData);
    return res.data;
  },

  getTargets: async (): Promise<PerformanceTarget[]> => {
    const res = await api.get<PerformanceTarget[]>('/analytics/targets');
    return res.data;
  },
};
