import { api } from './api';

export const APPROVAL_TYPES = ['leave', 'expense', 'discount', 'quotation', 'target', 'user', 'role', 'generic'] as const;
export const APPROVER_ROLES = ['Manager', 'OrgAdmin', 'SuperAdmin'] as const;

export interface ChainStep { level?: number; approver_role: string | null; approver_user_id: string | null; }

export interface Chain {
  id: string;
  name: string;
  request_type: string;
  min_amount: number;
  steps: ChainStep[];
  escalation_hours: number | null;
  is_active: boolean;
  created_at: string;
}

export interface ApprovalRequest {
  id: string;
  request_type: string;
  title: string;
  description: string | null;
  amount: number | null;
  reference_type: string | null;
  reference_id: string | null;
  payload: Record<string, any> | null;
  current_level: number;
  total_levels: number;
  status: string;
  escalated: boolean;
  requested_by: string;
  requested_by_name: string | null;
  created_at: string;
  decided_at: string | null;
}

export interface RequestList { items: ApprovalRequest[]; total: number; }

export interface HistoryRow {
  id: string;
  level: number;
  action: string;
  actor_name: string | null;
  on_behalf_of_name: string | null;
  note: string | null;
  created_at: string | null;
}

export interface Delegation {
  id: string;
  delegator_id: string;
  delegate_id: string;
  request_type: string | null;
  start_date: string;
  end_date: string | null;
  is_active: boolean;
  created_at: string;
}

export interface ApprovalDashboard {
  my_pending: number;
  awaiting_my_action: number;
  total: number;
  approved: number;
  rejected: number;
  pending: number;
}

export interface ApprovalReport { rows: any[]; }

export const approvalApi = {
  dashboard: async () => (await api.get<ApprovalDashboard>('/approvals/dashboard')).data,
  report: async (params: { request_type?: string } = {}) => (await api.get<ApprovalReport>('/approvals/report', { params })).data,
  escalateOverdue: async () => (await api.post<{ escalated: number }>('/approvals/escalate-overdue', {})).data,

  listChains: async (params: { request_type?: string } = {}) => (await api.get<Chain[]>('/approvals/chains', { params })).data,
  createChain: async (payload: any) => (await api.post<Chain>('/approvals/chains', payload)).data,
  updateChain: async (id: string, payload: any) => (await api.patch<Chain>(`/approvals/chains/${id}`, payload)).data,
  deleteChain: async (id: string) => { await api.delete(`/approvals/chains/${id}`); },

  listDelegations: async () => (await api.get<Delegation[]>('/approvals/delegations')).data,
  createDelegation: async (payload: any) => (await api.post<Delegation>('/approvals/delegations', payload)).data,
  revokeDelegation: async (id: string) => (await api.post<Delegation>(`/approvals/delegations/${id}/revoke`, {})).data,

  list: async (params: { box?: string; request_type?: string; status?: string } = {}) =>
    (await api.get<RequestList>('/approvals', { params })).data,
  create: async (payload: any) => (await api.post<ApprovalRequest>('/approvals', payload)).data,
  history: async (id: string) => (await api.get<HistoryRow[]>(`/approvals/${id}/history`)).data,
  act: async (id: string, approve: boolean, note?: string) =>
    (await api.post<ApprovalRequest>(`/approvals/${id}/act`, { approve, note })).data,
  cancel: async (id: string) => (await api.post<ApprovalRequest>(`/approvals/${id}/cancel`, {})).data,
};
