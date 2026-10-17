import { api } from './api';
import { PipelineStage } from './pipelineApi';

export interface LeadAttachment {
  filename: string;
  url: string;
  size?: number;
  uploaded_by?: string;
  uploaded_at?: string;
}

export interface LeadResponse {
  id: string;
  organization_id: string;
  first_name: string | null;
  last_name: string;
  email: string | null;
  phone: string | null;
  company_name: string | null;
  title: string;
  status: string;
  source: string | null;
  city?: string | null;
  value: number | null;
  priority: string;
  score: number;
  is_archived: boolean;
  archived_at: string | null;
  attachments: LeadAttachment[] | null;
  converted_contact_id: string | null;
  converted_at: string | null;
  assigned_user_id: string | null;
  stage_id: string;
  stage?: PipelineStage;
  custom_fields: Record<string, any> | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface LeadTimelineEvent {
  type: 'note' | 'activity' | 'audit' | 'task' | 'reminder' | 'whatsapp';
  id: string;
  timestamp: string;
  title: string;
  description: string | null;
  actor_user_id: string | null;
  event_metadata: Record<string, any> | null;
}

export interface LeadAuditEvent {
  id: string;
  action: string;
  actor_user_id: string | null;
  created_at: string;
  action_metadata: Record<string, any> | null;
}

export interface SavedFilter {
  id: string;
  organization_id: string;
  user_id: string;
  name: string;
  entity_type: string;
  definition: Record<string, any>;
  is_shared: boolean;
  created_at: string;
  updated_at: string;
}

export interface LeadReportBucket {
  label: string;
  count: number;
  value: number;
}

export interface LeadOwnerBucket {
  user_id: string | null;
  name: string;
  count: number;
  value: number;
}

export interface LeadReport {
  total_leads: number;
  total_value: number;
  converted_count: number;
  conversion_rate: number;
  avg_score: number;
  by_source: LeadReportBucket[];
  by_status: LeadReportBucket[];
  by_priority: LeadReportBucket[];
  by_stage: LeadReportBucket[];
  by_owner: LeadOwnerBucket[];
}

export interface LeadReminder {
  id: string;
  lead_id: string;
  user_id: string;
  remind_at: string;
  note: string | null;
  is_sent: boolean;
  created_at: string;
}

export interface EscalationConfig {
  id: string;
  organization_id: string;
  is_active: boolean;
  idle_days: number;
}

export interface WorkflowCondition {
  field: string;
  op: string;
  value: any;
}

export interface WorkflowAction {
  type: string;
  value?: any;
  user_id?: string;
  stage_id?: string;
  content?: string;
  message?: string;
}

export interface WorkflowRule {
  id: string;
  organization_id: string;
  name: string;
  trigger_event: string;
  is_active: boolean;
  conditions: WorkflowCondition[];
  actions: WorkflowAction[];
  created_at: string;
  updated_at: string;
}

export interface LeadListFilters {
  skip?: number;
  limit?: number;
  search?: string;
  status?: string;
  assigned_user_id?: string;
  name?: string;
  city?: string;
  source?: string;
  stage_id?: string;
  priority?: string;
  min_value?: number;
  max_value?: number;
  created_from?: string;
  created_to?: string;
  include_archived?: boolean;
  custom_fields?: string;
}

export interface SalesKPISummary {
  activePipelineValue: number;
  activeDealsCount: number;
  weightedForecast: number;
  wonRevenueThisMonth: number;
  wonDealsCount: number;
  lostDealsCount: number;
  winRate: number;
  overdueFollowupsCount: number;
  totalLeadsCount: number;
}

export interface KanbanStageSummary {
  stage_id: string;
  stage_name: string;
  order_position: number;
  total_count: number;
  total_value: number;
  cards: LeadResponse[];
  has_more: boolean;
}

export interface KanbanBoardResponse {
  pipeline_id: string | null;
  stages: KanbanStageSummary[];
  total_pipeline_value: number;
  total_deals_count: number;
}

export interface KanbanStageCardsResponse {
  stage_id: string;
  total_count: number;
  cards: LeadResponse[];
  has_more: boolean;
  skip: number;
  limit: number;
}

export interface PaginatedLeadsResponse {
  leads: LeadResponse[];
  totalCount: number;
}

export const leadApi = {
  getLeads: async (params: LeadListFilters) => {
    const response = await api.get<LeadResponse[]>('/leads/', { params });
    return response.data;
  },

  getLeadsPaginated: async (params: LeadListFilters, signal?: AbortSignal): Promise<PaginatedLeadsResponse> => {
    const response = await api.get<LeadResponse[]>('/leads/', { params, signal });
    const totalHeader = response.headers['x-total-count'] || response.headers['X-Total-Count'];
    const totalCount = totalHeader ? parseInt(totalHeader, 10) : response.data.length;
    return {
      leads: response.data,
      totalCount: Number.isFinite(totalCount) ? totalCount : response.data.length,
    };
  },

  getSalesKPISummary: async (): Promise<SalesKPISummary> => {
    const response = await api.get<{
      active_pipeline_value: number | string;
      active_deals_count: number;
      weighted_forecast: number | string;
      won_revenue_this_month: number | string;
      won_deals_count: number;
      lost_deals_count: number;
      win_rate: number;
      overdue_followups_count: number;
      total_leads_count: number;
    }>('/leads/kpi-summary');
    const d = response.data;
    return {
      activePipelineValue: typeof d.active_pipeline_value === 'string' ? parseFloat(d.active_pipeline_value) : d.active_pipeline_value,
      activeDealsCount: d.active_deals_count,
      weightedForecast: typeof d.weighted_forecast === 'string' ? parseFloat(d.weighted_forecast) : d.weighted_forecast,
      wonRevenueThisMonth: typeof d.won_revenue_this_month === 'string' ? parseFloat(d.won_revenue_this_month) : d.won_revenue_this_month,
      wonDealsCount: d.won_deals_count,
      lostDealsCount: d.lost_deals_count,
      winRate: d.win_rate,
      overdueFollowupsCount: d.overdue_followups_count,
      totalLeadsCount: d.total_leads_count,
    };
  },

  getKanbanBoard: async (pipelineId?: string, limit = 10): Promise<KanbanBoardResponse> => {
    const response = await api.get<KanbanBoardResponse>('/leads/kanban-board', {
      params: { pipeline_id: pipelineId || undefined, limit },
    });
    return response.data;
  },

  getKanbanStageCards: async (stageId: string, skip = 0, limit = 10): Promise<KanbanStageCardsResponse> => {
    const response = await api.get<KanbanStageCardsResponse>(`/leads/kanban-stage/${stageId}`, {
      params: { skip, limit },
    });
    return response.data;
  },

  createLead: async (payload: {
    title: string;
    last_name: string;
    first_name?: string | null;
    email?: string | null;
    phone?: string | null;
    company_name?: string | null;
    status?: string;
    source?: string | null;
    city?: string | null;
    value?: number | null;
    priority?: string;
    assigned_user_id?: string | null;
    stage_id?: string | null;
    custom_fields?: Record<string, any> | null;
  }) => {
    const response = await api.post<LeadResponse>('/leads/', payload);
    return response.data;
  },

  getLead: async (leadId: string) => {
    const response = await api.get<LeadResponse>(`/leads/${leadId}`);
    return response.data;
  },

  updateLead: async (leadId: string, payload: {
    title?: string;
    last_name?: string;
    first_name?: string | null;
    email?: string | null;
    phone?: string | null;
    company_name?: string | null;
    status?: string;
    source?: string | null;
    city?: string | null;
    value?: number | null;
    priority?: string;
    assigned_user_id?: string | null;
    stage_id?: string | null;
    custom_fields?: Record<string, any> | null;
  }) => {
    const response = await api.patch<LeadResponse>(`/leads/${leadId}`, payload);
    return response.data;
  },

  deleteLead: async (leadId: string) => {
    const response = await api.delete<LeadResponse>(`/leads/${leadId}`);
    return response.data;
  },

  archiveLead: async (leadId: string) => {
    const response = await api.post<LeadResponse>(`/leads/${leadId}/archive`);
    return response.data;
  },

  restoreLead: async (leadId: string) => {
    const response = await api.post<LeadResponse>(`/leads/${leadId}/restore`);
    return response.data;
  },

  findDuplicates: async (params: { email?: string; phone?: string; exclude_lead_id?: string }) => {
    const response = await api.get<LeadResponse[]>('/leads/duplicates', { params });
    return response.data;
  },

  mergeLeads: async (payload: { primary_id: string; secondary_id: string }) => {
    const response = await api.post<LeadResponse>('/leads/merge', payload);
    return response.data;
  },

  bulkUpdate: async (payload: {
    lead_ids: string[];
    fields: {
      status?: string;
      stage_id?: string;
      priority?: string;
      source?: string;
      assigned_user_id?: string;
    };
  }) => {
    const response = await api.post<{ updated_count: number; lead_ids: string[] }>('/leads/bulk-update', payload);
    return response.data;
  },

  exportLeads: async (params: LeadListFilters & { format?: 'csv' | 'xlsx' }) => {
    const response = await api.get('/leads/export', { params, responseType: 'blob' });
    return response.data as Blob;
  },

  recomputeScore: async (leadId: string) => {
    const response = await api.post<LeadResponse>(`/leads/${leadId}/recompute-score`);
    return response.data;
  },

  getTimeline: async (leadId: string) => {
    const response = await api.get<LeadTimelineEvent[]>(`/leads/${leadId}/timeline`);
    return response.data;
  },

  getAudit: async (leadId: string) => {
    const response = await api.get<LeadAuditEvent[]>(`/leads/${leadId}/audit`);
    return response.data;
  },

  listAttachments: async (leadId: string) => {
    const response = await api.get<LeadAttachment[]>(`/leads/${leadId}/attachments`);
    return response.data;
  },

  uploadAttachment: async (leadId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post<LeadAttachment>(`/leads/${leadId}/attachments`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  deleteAttachment: async (leadId: string, filename: string) => {
    await api.delete(`/leads/${leadId}/attachments/${encodeURIComponent(filename)}`);
  },

  listSavedFilters: async (entityType = 'lead') => {
    const response = await api.get<SavedFilter[]>('/leads/saved-filters', { params: { entity_type: entityType } });
    return response.data;
  },

  createSavedFilter: async (payload: { name: string; entity_type?: string; definition: Record<string, any>; is_shared?: boolean }) => {
    const response = await api.post<SavedFilter>('/leads/saved-filters', payload);
    return response.data;
  },

  deleteSavedFilter: async (filterId: string) => {
    await api.delete(`/leads/saved-filters/${filterId}`);
  },

  getReport: async (params?: { date_from?: string; date_to?: string }) => {
    const response = await api.get<LeadReport>('/leads/reports', { params });
    return response.data;
  },

  assignLeadsBulk: async (payload: {
    lead_ids?: string[] | null;
    import_id?: string | null;
    assignee_ids: string[];
    strategy: 'RANGE' | 'SPLIT';
    range_start?: number | null;
    range_end?: number | null;
  }) => {
    const response = await api.post<{ assigned_count: number; lead_ids: string[]; assignee_ids: string[] }>('/leads/assign-bulk', payload);
    return response.data;
  },

  transferLeads: async (payload: {
    source_user_id: string;
    destination_user_ids: string[];
    quantity?: number | null;
    lead_ids?: string[] | null;
  }) => {
    const response = await api.post<{ transferred_count: number; lead_ids: string[]; destination_user_ids: string[] }>('/leads/transfer', payload);
    return response.data;
  },

  convertLead: async (leadId: string, createCompany = true) => {
    const response = await api.post<{ contact_id: string; company_id: string | null; lead_id: string }>(
      `/leads/${leadId}/convert`,
      { create_company: createCompany },
    );
    return response.data;
  },

  listReminders: async (leadId: string) => {
    const response = await api.get<LeadReminder[]>(`/leads/${leadId}/reminders`);
    return response.data;
  },

  createReminder: async (leadId: string, payload: { remind_at: string; note?: string; user_id?: string }) => {
    const response = await api.post<LeadReminder>(`/leads/${leadId}/reminders`, payload);
    return response.data;
  },

  deleteReminder: async (leadId: string, reminderId: string) => {
    await api.delete(`/leads/${leadId}/reminders/${reminderId}`);
  },

  getEscalationConfig: async () => {
    const response = await api.get<EscalationConfig>('/leads/escalation/config');
    return response.data;
  },

  updateEscalationConfig: async (payload: { is_active?: boolean; idle_days?: number }) => {
    const response = await api.patch<EscalationConfig>('/leads/escalation/config', payload);
    return response.data;
  },

  listWorkflows: async () => {
    const response = await api.get<WorkflowRule[]>('/leads/workflows');
    return response.data;
  },

  createWorkflow: async (payload: {
    name: string;
    trigger_event: string;
    is_active?: boolean;
    conditions: WorkflowCondition[];
    actions: WorkflowAction[];
  }) => {
    const response = await api.post<WorkflowRule>('/leads/workflows', payload);
    return response.data;
  },

  updateWorkflow: async (ruleId: string, payload: Partial<{ name: string; trigger_event: string; is_active: boolean; conditions: WorkflowCondition[]; actions: WorkflowAction[] }>) => {
    const response = await api.patch<WorkflowRule>(`/leads/workflows/${ruleId}`, payload);
    return response.data;
  },

  deleteWorkflow: async (ruleId: string) => {
    await api.delete(`/leads/workflows/${ruleId}`);
  },
};

