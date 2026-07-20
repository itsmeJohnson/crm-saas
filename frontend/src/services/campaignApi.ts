import { api } from './api';

export type CampaignChannel = 'SMS' | 'Email' | 'WhatsApp' | 'Call';
export type CampaignStatus = 'draft' | 'scheduled' | 'running' | 'paused' | 'completed' | 'cancelled';

export interface Campaign {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  channel: CampaignChannel;
  template_id: string | null;
  subject: string | null;
  body: string | null;
  status: CampaignStatus;
  audience_type: string;
  audience_definition: Record<string, any> | null;
  segment_id: string | null;
  entity_type: string;
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_recipients: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  opened_count: number;
  clicked_count: number;
  converted_count: number;
  cost_per_message: number;
  revenue: number;
  max_retries: number;
  created_by: string;
  created_at: string;
}

export interface AudiencePreview { count: number; sample_ids: string[]; channel: string; entity_type: string; }

export interface CampaignReport {
  campaign_id: string;
  name: string;
  channel: string;
  status: string;
  total_recipients: number;
  sent: number;
  delivered: number;
  failed: number;
  opened: number;
  clicked: number;
  converted: number;
  delivery_rate: number;
  open_rate: number;
  click_rate: number;
  conversion_rate: number;
  cost: number;
  revenue: number;
  roi: number;
  roi_pct: number;
}

export interface Recipient {
  id: string;
  lead_id: string | null;
  contact_id: string | null;
  to_address: string | null;
  status: string;
  error: string | null;
  retry_count: number;
  activity_id: string | null;
  sent_at: string | null;
}

export interface ReportBucket { label: string; count: number; }

export interface CampaignDashboard {
  total: number;
  running: number;
  scheduled: number;
  completed: number;
  total_sent: number;
  total_converted: number;
  total_revenue: number;
  total_roi: number;
  by_status: ReportBucket[];
}

export interface Segment {
  id: string;
  name: string;
  description: string | null;
  entity_type: string;
  definition: Record<string, any>;
  cached_count: number | null;
  created_at: string;
}

export const campaignApi = {
  list: async (params: { status?: string; channel?: string; search?: string } = {}) =>
    (await api.get<Campaign[]>('/campaigns', { params })).data,
  get: async (id: string) => (await api.get<Campaign>(`/campaigns/${id}`)).data,
  create: async (payload: any) => (await api.post<Campaign>('/campaigns', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Campaign>(`/campaigns/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/campaigns/${id}`); },

  previewAudience: async (payload: any) => (await api.post<AudiencePreview>('/campaigns/audience/preview', payload)).data,
  build: async (id: string, ids?: string[]) => (await api.post<Campaign>(`/campaigns/${id}/build`, { ids })).data,
  schedule: async (id: string, scheduled_at: string) => (await api.post<Campaign>(`/campaigns/${id}/schedule`, { scheduled_at })).data,
  launch: async (id: string) => (await api.post<Campaign>(`/campaigns/${id}/launch`)).data,
  pause: async (id: string) => (await api.post<Campaign>(`/campaigns/${id}/pause`)).data,
  resume: async (id: string) => (await api.post<Campaign>(`/campaigns/${id}/resume`)).data,
  cancel: async (id: string) => (await api.post<Campaign>(`/campaigns/${id}/cancel`)).data,
  retry: async (id: string) => (await api.post<Campaign>(`/campaigns/${id}/retry`)).data,

  recipients: async (id: string, params: { status?: string } = {}) =>
    (await api.get<{ items: Recipient[]; total: number }>(`/campaigns/${id}/recipients`, { params })).data,
  reports: async (id: string) => (await api.get<CampaignReport>(`/campaigns/${id}/reports`)).data,
  dashboard: async () => (await api.get<CampaignDashboard>('/campaigns/dashboard')).data,

  listSegments: async () => (await api.get<Segment[]>('/campaigns/segments')).data,
  createSegment: async (payload: any) => (await api.post<Segment>('/campaigns/segments', payload)).data,
  deleteSegment: async (id: string) => { await api.delete(`/campaigns/segments/${id}`); },
};
