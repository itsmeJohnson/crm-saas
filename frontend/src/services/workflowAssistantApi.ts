import { api } from './api';

export interface WaSuggestion {
  key: string; title: string; reason: string; impact: string; trigger_event: string;
  category: string; already_covered: boolean; draft_graph: { nodes: any[]; edges: any[] };
}

export interface WaAutomationSuggestion {
  key: string; title: string; reason: string; impact: string; area: string;
}

export interface WaRuleRecommendation {
  key: string; title: string; reason: string; impact: string;
  rule_definition: any; suggested_action: string;
}

export interface WaBottleneck {
  area: string; severity: string; title: string; evidence: string; recommendation: string;
}

export interface WaOptimization {
  workflow_id: string | null; workflow: string | null; kind: string; advice: string;
}

export interface WaGenerated {
  prompt: string; name: string; trigger_event: string; entity_type: string;
  graph: { nodes: any[]; edges: any[] }; explanation: string[]; notes: string[];
  created: any | null; status: string;
}

export interface WaValidation {
  workflow_id: string; name: string; valid: boolean; errors: string[]; warnings: string[];
  health_score: number; runs_30d: number;
}

export interface WaInsights {
  window_days: number;
  totals: { runs: number; failed: number; success_rate: number };
  workflows: { workflow_id: string; workflow: string; runs_30d: number; failed: number;
               success_rate: number; avg_duration_s: number | null; last_run: string | null }[];
  trend: { day: string; runs: number; failed: number }[];
}

export interface WaReport {
  generated_at: string;
  summary: { workflow_suggestions: number; automation_suggestions: number; rule_recommendations: number;
             bottlenecks: number; optimizations: number; runs_30d: number; success_rate: number };
  suggestions: WaSuggestion[]; automation: WaAutomationSuggestion[]; rules: WaRuleRecommendation[];
  bottlenecks: WaBottleneck[]; optimizations: WaOptimization[]; insights: WaInsights;
}

export const workflowAssistantApi = {
  suggestions: async () => (await api.get<{ suggestions: WaSuggestion[]; count: number; signals: any }>('/workflow-assistant/suggestions')).data,
  automationSuggestions: async () => (await api.get<{ suggestions: WaAutomationSuggestion[]; count: number }>('/workflow-assistant/automation-suggestions')).data,
  ruleRecommendations: async () => (await api.get<{ recommendations: WaRuleRecommendation[]; count: number }>('/workflow-assistant/rule-recommendations')).data,
  bottlenecks: async () => (await api.get<{ bottlenecks: WaBottleneck[]; count: number; areas: string[] }>('/workflow-assistant/bottlenecks')).data,
  optimizations: async () => (await api.get<{ optimizations: WaOptimization[]; count: number }>('/workflow-assistant/optimizations')).data,
  generate: async (prompt: string, create = false, name?: string) =>
    (await api.post<WaGenerated>('/workflow-assistant/generate', { prompt, create, name: name || null })).data,
  validate: async (workflowId: string) =>
    (await api.get<WaValidation>(`/workflow-assistant/workflows/${workflowId}/validate`)).data,
  simulate: async (workflowId: string) =>
    (await api.post<any>(`/workflow-assistant/workflows/${workflowId}/simulate`)).data,
  insights: async (workflowId?: string) =>
    (await api.get<WaInsights>('/workflow-assistant/insights', { params: workflowId ? { workflow_id: workflowId } : {} })).data,
  report: async () => (await api.get<WaReport>('/workflow-assistant/report')).data,
  exportCsv: async () => (await api.get<string>('/workflow-assistant/export')).data,
};
