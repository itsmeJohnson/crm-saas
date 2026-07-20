import { api } from './api';

export interface Territory {
  id: string;
  organization_id: string;
  name: string;
  code: string | null;
  level: string;
  parent_id: string | null;
  manager_user_id: string | null;
  manager_name: string | null;
  description: string | null;
  status: string;
  color: string | null;
  branch_count: number;
  pincode_count: number;
  created_at: string;
}

export interface TerritoryTreeNode {
  id: string;
  name: string;
  code: string | null;
  level: string;
  status: string;
  manager_user_id: string | null;
  children: TerritoryTreeNode[];
}

export interface Locations {
  regions: { id: string; name: string }[];
  zones: { id: string; name: string }[];
  cities: { id: string; name: string }[];
  areas: { id: string; name: string }[];
}

export interface Branch {
  id: string;
  organization_id: string;
  name: string;
  code: string | null;
  branch_manager_id: string | null;
  manager_name: string | null;
  territory_id: string | null;
  territory_name: string | null;
  address_line: string | null;
  city: string | null;
  state: string | null;
  country: string | null;
  pin_code: string | null;
  phone: string | null;
  email: string | null;
  is_head_office: boolean;
  status: string;
  lead_count: number;
  created_at: string;
}

export interface BranchList { items: Branch[]; total: number; }

export interface Pincode {
  id: string;
  pin_code: string;
  city: string | null;
  territory_id: string;
  territory_name: string | null;
  branch_id: string | null;
  branch_name: string | null;
}

export interface PincodeList { items: Pincode[]; total: number; }

export interface BranchDashboard {
  total_branches: number;
  active_branches: number;
  archived_branches: number;
  total_territories: number;
  mapped_pincodes: number;
  unmapped_leads: number;
  top_branches: { id: string; name: string; lead_count: number }[];
}

export interface BranchPerformance {
  branch_id: string;
  name: string;
  metrics: Record<string, number>;
  by_status: { status: string; count: number }[];
}

export interface BranchAnalyticsRow {
  branch_id: string;
  name: string;
  city: string | null;
  manager_name: string | null;
  leads: number;
  converted: number;
  conversion_rate: number;
  revenue: number;
  activities: number;
}

export interface TerritoryAnalyticsRow {
  territory_id: string;
  name: string;
  level: string;
  leads: number;
  converted: number;
  conversion_rate: number;
  revenue: number;
  activities: number;
}

export const branchApi = {
  // Territories
  listTerritories: async (params: { search?: string; level?: string; status?: string; parent_id?: string } = {}) =>
    (await api.get<Territory[]>('/territories', { params })).data,
  territoryTree: async () => (await api.get<TerritoryTreeNode[]>('/territories/tree')).data,
  locations: async () => (await api.get<Locations>('/territories/locations')).data,
  territoryAnalytics: async () => (await api.get<TerritoryAnalyticsRow[]>('/territories/analytics')).data,
  createTerritory: async (payload: any) => (await api.post<Territory>('/territories', payload)).data,
  updateTerritory: async (id: string, payload: any) => (await api.patch<Territory>(`/territories/${id}`, payload)).data,
  removeTerritory: async (id: string) => { await api.delete(`/territories/${id}`); },

  // Branches
  listBranches: async (params: { search?: string; status?: string; territory_id?: string; city?: string } = {}) =>
    (await api.get<BranchList>('/branches', { params })).data,
  getBranch: async (id: string) => (await api.get<Branch>(`/branches/${id}`)).data,
  createBranch: async (payload: any) => (await api.post<Branch>('/branches', payload)).data,
  updateBranch: async (id: string, payload: any) => (await api.patch<Branch>(`/branches/${id}`, payload)).data,
  removeBranch: async (id: string) => { await api.delete(`/branches/${id}`); },
  branchPerformance: async (id: string) => (await api.get<BranchPerformance>(`/branches/${id}/performance`)).data,
  dashboard: async () => (await api.get<BranchDashboard>('/branches/dashboard')).data,
  branchAnalytics: async () => (await api.get<BranchAnalyticsRow[]>('/branches/analytics')).data,
  exportBranches: async () => (await api.get('/branches/export', { responseType: 'blob' })).data as Blob,

  // PIN mapping
  listPincodes: async (params: { search?: string; territory_id?: string } = {}) =>
    (await api.get<PincodeList>('/branches/pincodes', { params })).data,
  upsertPincode: async (payload: any) => (await api.post<Pincode>('/branches/pincodes', payload)).data,
  deletePincode: async (id: string) => { await api.delete(`/branches/pincodes/${id}`); },
  importPincodes: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    return (await api.post<{ created: number; updated: number; skipped: number; errors: any[] }>(
      '/branches/pincodes/import', form, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
  },

  // Lead assignment
  assignLeads: async (payload: { lead_ids: string[]; branch_id?: string; territory_id?: string; auto?: boolean }) =>
    (await api.post<{ assigned: number; unresolved: number }>('/branches/assign-leads', payload)).data,
};
