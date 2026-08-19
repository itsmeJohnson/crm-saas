import { api } from './api';

export interface CustomObjectDefinition {
  id: string;
  organization_id: string;
  key: string;
  label: string;
  label_plural: string | null;
  description: string | null;
  icon: string | null;
  color: string | null;
  display_field_key: string | null;
  is_active: boolean;
  is_system: boolean;
  created_at: string;
  updated_at: string;
}

export interface CustomObjectRecord {
  id: string;
  organization_id: string;
  object_definition_id: string;
  data: Record<string, any> | null;
  created_at: string;
  updated_at: string;
}

export interface RecordListResponse {
  items: CustomObjectRecord[];
  total: number;
  page: number;
  page_size: number;
}

export type FilterOperator =
  | 'eq' | 'ne' | 'gt' | 'gte' | 'lt' | 'lte'
  | 'contains' | 'startswith' | 'in' | 'is_empty';

export interface RecordFilter {
  field: string;
  op: FilterOperator;
  value: any;
}

export interface ObjectInput {
  key?: string;
  label?: string;
  label_plural?: string | null;
  description?: string | null;
  icon?: string | null;
  color?: string | null;
  display_field_key?: string | null;
  is_active?: boolean;
}

export const objectApi = {
  listObjects: async (includeInactive = false) => {
    const res = await api.get<CustomObjectDefinition[]>('/objects', {
      params: { include_inactive: includeInactive },
    });
    return res.data;
  },

  createObject: async (payload: ObjectInput) => {
    const res = await api.post<CustomObjectDefinition>('/objects', payload);
    return res.data;
  },

  updateObject: async (objectId: string, payload: ObjectInput) => {
    const res = await api.patch<CustomObjectDefinition>(`/objects/${objectId}`, payload);
    return res.data;
  },

  deleteObject: async (objectId: string) => {
    const res = await api.delete(`/objects/${objectId}`);
    return res.data;
  },

  listRecords: async (
    objectKey: string,
    opts: { filters?: RecordFilter[]; sort?: string; page?: number; pageSize?: number } = {},
  ) => {
    const params: Record<string, any> = {
      page: opts.page ?? 1,
      page_size: opts.pageSize ?? 50,
    };
    if (opts.filters && opts.filters.length) params.filters = JSON.stringify(opts.filters);
    if (opts.sort) params.sort = opts.sort;
    const res = await api.get<RecordListResponse>(`/objects/${objectKey}/records`, { params });
    return res.data;
  },

  createRecord: async (objectKey: string, data: Record<string, any>) => {
    const res = await api.post<CustomObjectRecord>(`/objects/${objectKey}/records`, { data });
    return res.data;
  },

  updateRecord: async (objectKey: string, recordId: string, data: Record<string, any>) => {
    const res = await api.patch<CustomObjectRecord>(`/objects/${objectKey}/records/${recordId}`, { data });
    return res.data;
  },

  deleteRecord: async (objectKey: string, recordId: string) => {
    const res = await api.delete(`/objects/${objectKey}/records/${recordId}`);
    return res.data;
  },
};
