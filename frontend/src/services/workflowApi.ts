import { api } from './api';

export interface WorkflowNode { id: string; type: string; config: Record<string, any>; }
export interface WorkflowEdge { from: string; to: string; branch?: string | null; }
export interface WorkflowGraph { nodes: WorkflowNode[]; edges: WorkflowEdge[]; }

export interface Workflow {
  id: string;
  name: string;
  description: string | null;
  category: string | null;
  status: string;
  version: number;
  is_enabled: boolean;
  is_template: boolean;
  trigger_event: string;
  entity_type: string;
  node_count: number;
  created_at: string;
  graph?: WorkflowGraph;
}

export interface WorkflowCatalog {
  triggers: { event: string; entity_type: string }[];
  actions: string[];
  node_types: string[];
  categories: string[];
  statuses: string[];
}

export interface WorkflowVersion {
  id: string; version: number; trigger_event: string; notes: string | null;
  published_by_name: string | null; published_at: string | null;
}

export interface ExecutionStep {
  seq: number; node_id: string | null; node_type: string; action_type: string | null; status: string; detail: string | null;
}

export interface Execution {
  id: string; workflow_id: string; workflow_name: string | null; version: number; trigger_event: string;
  entity_type: string; entity_id: string | null; status: string; is_test: boolean; rolled_back: boolean;
  steps_run: number; error: string | null; started_at: string | null; finished_at: string | null;
  steps?: ExecutionStep[];
}

export interface WorkflowDashboard {
  published: number; enabled: number; total_runs: number; success_rate: number; failed: number; recent: Execution[];
}

export interface WorkflowReport {
  total_workflows: number; published: number; enabled: number; total_runs: number;
  completed: number; failed: number; success_rate: number; top_workflows: { workflow_id: string; name: string; runs: number }[];
}

export const workflowApi = {
  catalog: async () => (await api.get<WorkflowCatalog>('/workflows/catalog')).data,
  dashboard: async () => (await api.get<WorkflowDashboard>('/workflows/dashboard')).data,
  report: async () => (await api.get<WorkflowReport>('/workflows/report')).data,

  list: async (params: { category?: string; status?: string; is_template?: boolean; trigger?: string } = {}) =>
    (await api.get<Workflow[]>('/workflows', { params })).data,
  get: async (id: string) => (await api.get<Workflow>(`/workflows/${id}`)).data,
  create: async (payload: any) => (await api.post<Workflow>('/workflows', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Workflow>(`/workflows/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/workflows/${id}`); },
  exportOne: async (id: string) => (await api.get(`/workflows/${id}/export`)).data,
  importOne: async (payload: any) => (await api.post<Workflow>('/workflows/import', payload)).data,

  publish: async (id: string, notes?: string) => (await api.post<Workflow>(`/workflows/${id}/publish`, { notes })).data,
  setEnabled: async (id: string, enabled: boolean) => (await api.post<Workflow>(`/workflows/${id}/enable`, { enabled })).data,
  clone: async (id: string) => (await api.post<Workflow>(`/workflows/${id}/clone`, {})).data,
  versions: async (id: string) => (await api.get<WorkflowVersion[]>(`/workflows/${id}/versions`)).data,
  rollback: async (id: string, version: number) => (await api.post<Workflow>(`/workflows/${id}/rollback`, { version })).data,
  test: async (id: string) => (await api.post<Execution>(`/workflows/${id}/test`, {})).data,

  seedTemplates: async () => (await api.post<{ created: number }>('/workflows/templates/seed', {})).data,
  instantiate: async (id: string) => (await api.post<Workflow>(`/workflows/templates/${id}/instantiate`, {})).data,

  executions: async (params: { workflow_id?: string; is_test?: boolean; limit?: number } = {}) =>
    (await api.get<{ items: Execution[]; total: number }>('/workflows/executions', { params })).data,
  executionLogs: async (id: string) => (await api.get<Execution>(`/workflows/executions/${id}`)).data,
  rollbackExecution: async (id: string) => (await api.post<{ reverted: number }>(`/workflows/executions/${id}/rollback`, {})).data,
};
