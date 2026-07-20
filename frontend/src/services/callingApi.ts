import { api } from './api';

export interface CallItem {
  id: string;
  subject: string;
  description: string | null;
  direction: 'INBOUND' | 'OUTBOUND' | null;
  disposition: string | null;
  status: string;
  duration: number | null;
  recording_url: string | null;
  tags: string[];
  timestamp: string;
  agent_id: string | null;
  agent_name: string | null;
  lead_id: string | null;
  lead_title: string | null;
  contact_id: string | null;
  company_id: string | null;
}

export interface CallHistoryResponse {
  items: CallItem[];
  total: number;
}

export interface ReportBucket {
  label: string;
  count: number;
}

export interface CallReport {
  total: number;
  missed: number;
  avg_duration: number;
  connect_rate: number;
  connected: number;
  dispositioned: number;
  by_direction: ReportBucket[];
  by_disposition: ReportBucket[];
  by_agent: ReportBucket[];
  by_day: ReportBucket[];
}

export interface CurrentCall {
  activity_id: string;
  direction: string | null;
  lead_id: string | null;
  lead_title: string | null;
  started_at: string;
}

export interface QueueAgent {
  user_id: string;
  user_name: string;
  state: 'IDLE' | 'ACTIVE_CALLING' | 'BREAK';
  since: string | null;
  current_call: CurrentCall | null;
}

export interface CallQueue {
  pending_queue: number;
  agents: QueueAgent[];
}

export interface CallHistoryFilters {
  direction?: string;
  disposition?: string;
  agent_id?: string;
  status?: string;
  tag?: string;
  has_recording?: boolean;
  missed_only?: boolean;
  search?: string;
  date_from?: string;
  date_to?: string;
  skip?: number;
  limit?: number;
}

export const callingApi = {
  history: async (filters: CallHistoryFilters = {}) => {
    const response = await api.get<CallHistoryResponse>('/calling/history', { params: filters });
    return response.data;
  },

  reports: async (params: { date_from?: string; date_to?: string } = {}) => {
    const response = await api.get<CallReport>('/calling/reports', { params });
    return response.data;
  },

  queue: async () => {
    const response = await api.get<CallQueue>('/calling/queue');
    return response.data;
  },

  listTags: async () => {
    const response = await api.get<string[]>('/calling/tags');
    return response.data;
  },

  setTags: async (activityId: string, tags: string[]) => {
    const response = await api.patch<CallItem>(`/calling/${activityId}/tags`, { tags });
    return response.data;
  },
};
