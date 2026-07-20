import { api } from './api';

export interface RoleCatalog {
  resources: string[];
  actions: string[];
  scopes: string[];
  field_access: string[];
  base_roles: string[];
  fields: Record<string, string[]>;
  feature_gated: Record<string, string>;
}

export interface Role {
  id: string;
  organization_id: string;
  name: string;
  description: string | null;
  base_role: string;
  is_system: boolean;
  status: string;
  user_count: number;
  created_at: string;
}

export interface MatrixCell { actions: Record<string, boolean>; scope: string | null; }

export interface FieldPermissionItem { resource: string; field_name: string; access: string; }

export interface RoleDetail extends Role {
  matrix: Record<string, MatrixCell>;
  field_permissions: FieldPermissionItem[];
}

export interface RoleUser { id: string; name: string; email: string; role: string; is_active: boolean; }

export interface EffectivePermissions {
  base_role: string;
  custom_role: Role | null;
  matrix: Record<string, MatrixCell>;
  fields: Record<string, Record<string, string>>;
}

export interface PermissionAuditRow {
  id: string;
  action: string;
  resource_type: string;
  resource_id: string | null;
  actor_name: string;
  metadata: any;
  created_at: string;
}

export const rolesApi = {
  catalog: async () => (await api.get<RoleCatalog>('/roles/catalog')).data,
  me: async () => (await api.get<EffectivePermissions>('/roles/me')).data,
  audit: async (limit = 100) => (await api.get<PermissionAuditRow[]>('/roles/audit', { params: { limit } })).data,

  list: async (params: { search?: string; status?: string } = {}) =>
    (await api.get<Role[]>('/roles', { params })).data,
  get: async (id: string) => (await api.get<RoleDetail>(`/roles/${id}`)).data,
  create: async (payload: { name: string; description?: string; base_role: string }) =>
    (await api.post<Role>('/roles', payload)).data,
  update: async (id: string, payload: any) => (await api.patch<Role>(`/roles/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/roles/${id}`); },

  setMatrix: async (id: string, matrix: Record<string, MatrixCell>) =>
    (await api.put<RoleDetail>(`/roles/${id}/permissions`, { matrix })).data,
  setFieldPermissions: async (id: string, items: FieldPermissionItem[]) =>
    (await api.put<RoleDetail>(`/roles/${id}/field-permissions`, { items })).data,

  users: async (id: string) => (await api.get<RoleUser[]>(`/roles/${id}/users`)).data,
  assign: async (id: string, user_ids: string[]) => (await api.post(`/roles/${id}/assign`, { user_ids })).data,
  unassign: async (id: string, user_ids: string[]) => (await api.post(`/roles/${id}/unassign`, { user_ids })).data,
};
