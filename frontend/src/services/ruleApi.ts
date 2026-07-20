import { api } from './api';

export type Logic = 'and' | 'or' | 'not';

export interface RuleCondition {
  type: 'condition';
  field: string;
  op: string;
  value?: any;
  value_type?: 'static' | 'field' | 'variable';
  value_field?: string;
  variable?: string;
}
export interface RuleRef {
  type: 'ref';
  ref_id: string;
}
export interface RuleGroup {
  type: 'group';
  logic: Logic;
  children: RuleNode[];
}
export type RuleNode = RuleGroup | RuleCondition | RuleRef;

export interface RuleAction { type: string; role?: string; user_id?: string; message?: string; }

export interface Rule {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  category: string | null;
  entity_type: string;
  definition: RuleGroup;
  actions: RuleAction[];
  priority: number;
  conflict_strategy: string;
  is_active: boolean;
  is_template: boolean;
  condition_count: number;
  action_count: number;
  match_count: number;
  eval_count: number;
  last_evaluated_at: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface RuleComponent {
  id: string; name: string; description: string | null; entity_type: string;
  definition: RuleGroup; is_active: boolean; created_at: string | null;
}

export interface RuleVariable {
  id: string; name: string; description: string | null; value_type: string;
  value: string | null; resolved: any; created_at: string | null;
}

export interface RuleVersion {
  id: string; version_no: number; note: string | null; snapshot: any; created_at: string | null;
}

export interface RuleSimulateResult {
  rule_id: string; name: string; entity_type: string; evaluated: number;
  matched: number; executed: number; action_count: number; samples: { entity_id: string; matched: boolean }[];
}

export interface RuleAuditRow {
  id: string; action: string; resource_type: string; resource_id: string | null;
  actor_name: string | null; metadata: any; created_at: string | null;
}

export interface RuleFieldSpec { field: string; type: string; cross?: boolean; }

export interface RuleCatalog {
  entity_types: string[];
  fields: Record<string, RuleFieldSpec[]>;
  operators: { comparison: string[]; date: string[]; time: string[]; boolean: string[] };
  logic: Logic[];
  variables: string[];
  value_types: string[];
  conflict_strategies: string[];
  categories: string[];
  action_types: string[];
  variable_value_types: string[];
}

export interface RuleTestResult {
  rule_id: string;
  name: string;
  matched: boolean;
  trace: any;
  facts: Record<string, any>;
}

export interface RuleEvaluationRow {
  id: string; rule_id: string; entity_type: string; entity_id: string | null;
  matched: boolean; is_test: boolean; created_at: string | null;
}

export interface RuleReport {
  total: number; active: number; inactive: number; templates: number;
  evaluations: number; matches: number; match_rate: number; by_entity: Record<string, number>;
}

export interface RuleDashboard {
  total: number; active: number; match_rate: number; evaluations: number;
  top: { id: string; name: string; entity_type: string; priority: number; match_count: number }[];
}

export const ruleApi = {
  catalog: async () => (await api.get<RuleCatalog>('/rules/catalog')).data,
  dashboard: async () => (await api.get<RuleDashboard>('/rules/dashboard')).data,
  report: async () => (await api.get<RuleReport>('/rules/report')).data,

  list: async (params: { entity_type?: string; is_template?: boolean; active_only?: boolean } = {}) =>
    (await api.get<Rule[]>('/rules', { params })).data,
  get: async (id: string) => (await api.get<Rule>(`/rules/${id}`)).data,
  create: async (payload: any) => (await api.post<Rule>('/rules', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Rule>(`/rules/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/rules/${id}`); },
  clone: async (id: string) => (await api.post<Rule>(`/rules/${id}/clone`, {})).data,
  setPriority: async (id: string, priority: number) =>
    (await api.post<Rule>(`/rules/${id}/priority`, { priority })).data,
  exportOne: async (id: string) => (await api.get(`/rules/${id}/export`)).data,
  importOne: async (payload: any) => (await api.post<Rule>('/rules/import', payload)).data,
  test: async (id: string, body: { sample?: Record<string, any>; entity_id?: string } = {}) =>
    (await api.post<RuleTestResult>(`/rules/${id}/test`, body)).data,

  seedTemplates: async () => (await api.post<{ created: number }>('/rules/templates/seed', {})).data,
  instantiate: async (id: string) => (await api.post<Rule>(`/rules/templates/${id}/instantiate`, {})).data,

  evaluations: async (params: { rule_id?: string; limit?: number } = {}) =>
    (await api.get<RuleEvaluationRow[]>('/rules/evaluations', { params })).data,

  // Business Rule Designer
  simulate: async (id: string, body: { limit?: number; execute?: boolean } = {}) =>
    (await api.post<RuleSimulateResult>(`/rules/${id}/simulate`, body)).data,
  versions: async (id: string) => (await api.get<RuleVersion[]>(`/rules/${id}/versions`)).data,
  restoreVersion: async (id: string, version_no: number) =>
    (await api.post<Rule>(`/rules/${id}/versions/restore`, { version_no })).data,
  audit: async (params: { limit?: number } = {}) => (await api.get<RuleAuditRow[]>('/rules/audit', { params })).data,

  listComponents: async (params: { entity_type?: string } = {}) =>
    (await api.get<RuleComponent[]>('/rules/components', { params })).data,
  createComponent: async (payload: any) => (await api.post<RuleComponent>('/rules/components', payload)).data,
  updateComponent: async (id: string, payload: any) => (await api.patch<RuleComponent>(`/rules/components/${id}`, payload)).data,
  removeComponent: async (id: string) => { await api.delete(`/rules/components/${id}`); },

  listVariables: async () => (await api.get<RuleVariable[]>('/rules/variables')).data,
  createVariable: async (payload: any) => (await api.post<RuleVariable>('/rules/variables', payload)).data,
  updateVariable: async (id: string, payload: any) => (await api.patch<RuleVariable>(`/rules/variables/${id}`, payload)).data,
  removeVariable: async (id: string) => { await api.delete(`/rules/variables/${id}`); },
};
