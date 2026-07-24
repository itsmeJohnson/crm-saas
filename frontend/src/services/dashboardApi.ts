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

  getEmployeeSummary: async () => {
    const response = await api.get<EmployeeSummary>('/dashboard/employee');
    return response.data;
  },

  getWorkQueue: async (limitPerSection = 25) => {
    const response = await api.get<WorkQueue>('/dashboard/work-queue', { params: { limit_per_section: limitPerSection } });
    return response.data;
  },

  logFollowUp: async (leadId: string, payload: FollowUpPayload) => {
    const response = await api.post<FollowUpResult>(`/leads/${leadId}/follow-up`, payload);
    return response.data;
  },
};

export interface WorkQueueItem {
  type: string; id: string; title: string; lead_id?: string | null;
  priority?: string; status?: string; score?: number; value?: number;
  due_date?: string | null; start_at?: string; event_type?: string; overdue?: boolean;
}
export interface WorkQueueSection { key: string; order: number; label: string; count: number; items: WorkQueueItem[]; }
export interface WorkQueue {
  generated_at: string; scope: string;
  next_action: WorkQueueItem | null;
  counts: Record<string, number>;
  sections: WorkQueueSection[];
}

export interface FollowUpPayload {
  outcome: string; remarks?: string; follow_up_type?: string;
  next_follow_up_at?: string | null; priority?: string;
  reminder_minutes_before?: number | null; create_calendar_event?: boolean; set_status?: string | null;
}
export interface FollowUpResult {
  lead_id: string; outcome: string; follow_up_type: string; activity_id: string;
  task_id: string | null; calendar_event_id: string | null; next_follow_up_at: string | null;
  status: string; status_changed: boolean; manager_notified: boolean;
}

export const FOLLOW_UP_OUTCOMES = [
  'Interested', 'Follow-up', 'Call Back Later', 'No Response', 'Switched Off', 'Busy',
  'Wrong Number', 'Invalid Lead', 'Meeting Scheduled', 'Site Visit Scheduled', 'Negotiation',
  'Booking', 'Sale Won', 'Sale Lost', 'Not Interested',
];

export interface EmployeeSummary {
  my_leads_total: number;
  my_leads_converted: number;
  my_leads_by_status: { status: string; count: number }[];
  today_calls: number;
  today_meetings_count: number;
  today_meetings: { id: string; title: string; event_type: string; start_at: string | null; status: string }[];
  open_tasks: number;
  overdue_tasks: number;
  // Employee hero card (Phase 4)
  employee_name?: string;
  is_online?: boolean;
  check_in_at?: string | null;
  check_out_at?: string | null;
  working_minutes?: number;
  calls_made_today?: number;
  todays_follow_ups?: number;
  overdue_follow_ups?: number;
  new_leads?: number;
  interested_leads?: number;
  meetings_today?: number;
  tasks_pending?: number;
}
