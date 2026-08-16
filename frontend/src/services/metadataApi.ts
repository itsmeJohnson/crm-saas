import { api } from './api';
import { Pipeline } from './pipelineApi';

export type CustomFieldType = 'text' | 'number' | 'date' | 'select' | 'checkbox';

export interface CustomFieldDefinition {
  id: string;
  organization_id: string;
  entity_type: string;
  key: string;
  label: string;
  field_type: CustomFieldType | string;
  options: string[] | null;
  placeholder: string | null;
  description: string | null;
  default_value: any | null;
  validation_rules: Record<string, any> | null;
  section: string | null;
  is_active: boolean;
  read_only: boolean;
  visible: boolean;
  searchable: boolean;
  filterable: boolean;
  exportable: boolean;
  importable: boolean;
  created_at: string;
  updated_at: string;
}

export interface MetadataBootstrap {
  metadata_version: number;
  custom_fields: CustomFieldDefinition[];
  pipelines: Pipeline[];
}

export interface CustomFieldInput {
  key?: string;
  label?: string;
  field_type?: string;
  options?: string[] | null;
  placeholder?: string | null;
  description?: string | null;
  default_value?: any | null;
  validation_rules?: Record<string, any> | null;
  section?: string | null;
  is_active?: boolean;
  read_only?: boolean;
  visible?: boolean;
  searchable?: boolean;
  filterable?: boolean;
  exportable?: boolean;
  importable?: boolean;
}

export const metadataApi = {
  bootstrap: async () => {
    const response = await api.get<MetadataBootstrap>('/metadata/bootstrap');
    return response.data;
  },

  listCustomFields: async (entityType = 'lead') => {
    const response = await api.get<CustomFieldDefinition[]>('/metadata/custom-fields', {
      params: { entity_type: entityType },
    });
    return response.data;
  },

  createCustomField: async (payload: CustomFieldInput, entityType = 'lead') => {
    const response = await api.post<CustomFieldDefinition>('/metadata/custom-fields', payload, {
      params: { entity_type: entityType },
    });
    return response.data;
  },

  updateCustomField: async (definitionId: string, payload: CustomFieldInput) => {
    const response = await api.patch<CustomFieldDefinition>(`/metadata/custom-fields/${definitionId}`, payload);
    return response.data;
  },

  deleteCustomField: async (definitionId: string) => {
    const response = await api.delete<{ status: string; message: string }>(`/metadata/custom-fields/${definitionId}`);
    return response.data;
  },
};
