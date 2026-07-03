import { api } from './api';

export type TemplateChannel = 'Email' | 'SMS' | 'WhatsApp' | 'Call';
export type TemplateStatus = 'draft' | 'pending_approval' | 'approved' | 'rejected';

export interface Template {
  id: string;
  organization_id: string;
  name: string;
  channel: TemplateChannel;
  subject: string | null;
  body: string;
  category: string | null;
  description: string | null;
  status: TemplateStatus;
  version: number;
  usage_count: number;
  last_used_at: string | null;
  approved_by: string | null;
  approved_at: string | null;
  rejected_reason: string | null;
  is_active: boolean;
  created_by: string;
  created_at: string;
}

export interface TemplateVersion {
  id: string;
  version: number;
  name: string;
  channel: string;
  subject: string | null;
  body: string;
  category: string | null;
  change_note: string | null;
  edited_by: string;
  created_at: string;
}

export interface TemplateVariable { key: string; label: string; }

export interface ReportBucket { label: string; count: number; }

export interface TemplateReport {
  total: number;
  total_usage: number;
  pending_approval: number;
  approved: number;
  drafts: number;
  by_channel: ReportBucket[];
  by_status: ReportBucket[];
  by_category: ReportBucket[];
  most_used: { id: string; name: string; channel: string; usage_count: number }[];
}

export interface Preview { channel: string; subject: string | null; body: string; }
export interface TestResult { sent: boolean; channel: string; activity_id?: string; preview?: string; }

export interface TemplateListFilters {
  channel?: string;
  category?: string;
  status?: string;
  search?: string;
}

export const templateApi = {
  list: async (filters: TemplateListFilters = {}) => (await api.get<Template[]>('/templates', { params: filters })).data,
  get: async (id: string) => (await api.get<Template>(`/templates/${id}`)).data,
  create: async (payload: { name: string; channel: string; subject?: string; body: string; category?: string; description?: string }) =>
    (await api.post<Template>('/templates', payload)).data,
  update: async (id: string, payload: Partial<{ name: string; channel: string; subject: string; body: string; category: string; description: string; is_active: boolean; change_note: string }>) =>
    (await api.patch<Template>(`/templates/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/templates/${id}`); },

  submit: async (id: string) => (await api.post<Template>(`/templates/${id}/submit`)).data,
  approve: async (id: string) => (await api.post<Template>(`/templates/${id}/approve`)).data,
  reject: async (id: string, reason?: string) => (await api.post<Template>(`/templates/${id}/reject`, { reason })).data,

  versions: async (id: string) => (await api.get<TemplateVersion[]>(`/templates/${id}/versions`)).data,
  restore: async (id: string, version: number) => (await api.post<Template>(`/templates/${id}/versions/${version}/restore`)).data,

  preview: async (id: string, payload: { contact_id?: string; lead_id?: string; company_id?: string } = {}) =>
    (await api.post<Preview>(`/templates/${id}/preview`, payload)).data,
  test: async (id: string, payload: { to?: string } = {}) => (await api.post<TestResult>(`/templates/${id}/test`, payload)).data,

  variables: async () => (await api.get<TemplateVariable[]>('/templates/variables')).data,
  categories: async () => (await api.get<string[]>('/templates/categories')).data,
  reports: async () => (await api.get<TemplateReport>('/templates/reports')).data,
};
