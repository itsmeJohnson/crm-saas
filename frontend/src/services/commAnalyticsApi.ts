import { api } from './api';

export interface Bucket { label: string; count: number; }

export interface Overview {
  total: number;
  outbound: number;
  inbound: number;
  delivered: number;
  failed: number;
  delivery_rate: number;
  by_channel: Bucket[];
  by_direction: Bucket[];
}

export interface ChannelBreakdown {
  channel: string;
  total: number;
  outbound: number;
  inbound: number;
  delivered: number;
  failed: number;
  opened: number;
  clicked: number;
  read: number;
  delivery_rate: number;
  open_rate: number;
  avg_talk_time: number;
}

export interface AgentPerformance {
  agent_id: string;
  agent_name: string;
  total: number;
  outbound: number;
  inbound: number;
  calls: number;
  failed: number;
  avg_talk_time: number;
  avg_response_seconds: number;
  by_channel: Bucket[];
}

export interface ResponseTime { avg_response_seconds: number; median_response_seconds: number; sample_size: number; }
export interface TalkTime { avg_talk_seconds: number; total_talk_seconds: number; calls_with_duration: number; }
export interface Missed { missed_calls: number; failed_messages: number; total_missed: number; by_channel: Bucket[]; }
export interface Conversion { leads_contacted: number; converted: number; conversion_rate: number; revenue: number; }
export interface EngagementItem {
  entity_type: string; entity_id: string; name: string; interactions: number;
  inbound: number; outbound: number; channels: string[]; last_at: string;
}
export interface Heatmap { grid: number[][]; peak: { weekday: number; hour: number; count: number }; total: number; }

export interface CommFilters {
  channel?: string;
  direction?: string;
  agent_id?: string;
  date_from?: string;
  date_to?: string;
}

const q = (f: CommFilters) => ({ params: f });

export const commAnalyticsApi = {
  overview: async (f: CommFilters = {}) => (await api.get<Overview>('/comm-analytics/overview', q(f))).data,
  byChannel: async (f: CommFilters = {}) => (await api.get<ChannelBreakdown[]>('/comm-analytics/by-channel', q(f))).data,
  agents: async (f: CommFilters = {}) => (await api.get<AgentPerformance[]>('/comm-analytics/agents', q(f))).data,
  responseTime: async (f: CommFilters = {}) => (await api.get<ResponseTime>('/comm-analytics/response-time', q(f))).data,
  talkTime: async (f: CommFilters = {}) => (await api.get<TalkTime>('/comm-analytics/talk-time', q(f))).data,
  missed: async (f: CommFilters = {}) => (await api.get<Missed>('/comm-analytics/missed', q(f))).data,
  conversion: async (f: CommFilters = {}) => (await api.get<Conversion>('/comm-analytics/conversion', q(f))).data,
  engagement: async (f: CommFilters = {}) => (await api.get<EngagementItem[]>('/comm-analytics/engagement', q(f))).data,
  heatmap: async (f: CommFilters = {}) => (await api.get<Heatmap>('/comm-analytics/heatmap', q(f))).data,
  trend: async (f: CommFilters = {}) => (await api.get<Bucket[]>('/comm-analytics/trend', q(f))).data,
  exportCsv: async (f: CommFilters = {}) => {
    const res = await api.get('/comm-analytics/export', { params: f, responseType: 'blob' });
    return res.data as Blob;
  },
};
