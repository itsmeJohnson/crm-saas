import { api } from './api';

export interface WorkflowBlock {
  total_runs: number; completed: number; failed: number; paused: number;
  success_rate: number; failure_rate: number; avg_execution_ms: number; max_execution_ms: number;
}
export interface QueueBlock {
  total: number; succeeded: number; failed: number; dead_letter: number; queued: number; running: number;
  success_rate: number; avg_duration_ms: number;
}
export interface JobsBlock {
  runs: number; success: number; failed: number; partial: number; success_rate: number;
  items_processed: number; avg_duration_ms: number; enabled_jobs: number;
}
export interface RulesBlock { total: number; active: number; evaluations: number; matches: number; match_rate: number; }
export interface SLABlock { tracked: number; breached: number; met: number; open_breaches: number; compliance_rate: number; }
export interface EscalationBlock { total: number; by_level: Record<string, number>; by_entity: Record<string, number>; }
export interface ApprovalBlock {
  total: number; approved: number; rejected: number; pending: number; cancelled: number;
  approval_rate: number; avg_decision_hours: number;
}

export interface AutomationOverview {
  from: string; to: string;
  workflow: WorkflowBlock; queue: QueueBlock; automation_jobs: JobsBlock;
  rules: RulesBlock; sla: SLABlock; escalation: EscalationBlock; approval: ApprovalBlock;
}

export interface WorkflowsAnalytics extends WorkflowBlock {
  top_workflows: { workflow_id: string; name: string; runs: number; failed: number }[];
  failures: { id: string; workflow_id: string; name: string; trigger_event: string; error: string | null; started_at: string | null }[];
}
export interface QueueAnalytics extends QueueBlock {
  by_queue: { queue: string; count: number }[];
  by_type: { job_type: string; count: number }[];
}
export interface RuleUsage extends RulesBlock {
  top_rules: { id: string; name: string; entity_type: string; evaluations: number; matches: number; match_rate: number }[];
}
export interface TopAutomations { items: { kind: string; name: string; runs: number }[]; }
export interface SLACompliance extends SLABlock { breaches_by_metric: Record<string, number>; breaches_by_entity: Record<string, number>; }
export interface EscalationAnalytics extends EscalationBlock { by_target: Record<string, number>; }
export interface ApprovalAnalytics extends ApprovalBlock { by_type: Record<string, number>; }
export interface AutomationTrend { granularity: string; from: string; to: string; series: any[]; }

export interface AutomationAnalyticsDashboard {
  workflow_runs: number; workflow_success_rate: number; workflow_failed: number; queue_failed: number;
  sla_compliance_rate: number; open_breaches: number; escalations: number; approvals_pending: number;
}

type Range = { date_from?: string; date_to?: string };

export const automationAnalyticsApi = {
  overview: async (params: Range = {}) => (await api.get<AutomationOverview>('/automation-analytics/overview', { params })).data,
  dashboard: async () => (await api.get<AutomationAnalyticsDashboard>('/automation-analytics/dashboard')).data,
  workflows: async (params: Range = {}) => (await api.get<WorkflowsAnalytics>('/automation-analytics/workflows', { params })).data,
  queue: async (params: Range = {}) => (await api.get<QueueAnalytics>('/automation-analytics/queue', { params })).data,
  rules: async (params: Range = {}) => (await api.get<RuleUsage>('/automation-analytics/rules', { params })).data,
  top: async (params: Range & { limit?: number } = {}) => (await api.get<TopAutomations>('/automation-analytics/top', { params })).data,
  sla: async (params: Range = {}) => (await api.get<SLACompliance>('/automation-analytics/sla', { params })).data,
  escalation: async (params: Range = {}) => (await api.get<EscalationAnalytics>('/automation-analytics/escalation', { params })).data,
  approval: async (params: Range = {}) => (await api.get<ApprovalAnalytics>('/automation-analytics/approval', { params })).data,
  trend: async (params: Range & { granularity?: string } = {}) => (await api.get<AutomationTrend>('/automation-analytics/trend', { params })).data,
  exportCsv: async (params: Range = {}) => (await api.get('/automation-analytics/export', { params, responseType: 'blob' })).data as Blob,
};
