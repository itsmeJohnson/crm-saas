import { api } from './api';
import { Pipeline } from './pipelineApi';

export type CustomFieldType =
  | 'text'
  | 'textarea'
  | 'number'
  | 'currency'
  | 'percentage'
  | 'date'
  | 'datetime'
  | 'boolean'
  | 'email'
  | 'phone'
  | 'url'
  | 'select'
  | 'multiselect'
  | 'checkbox'; // legacy alias of boolean, still accepted

export interface CustomFieldOption {
  value: string;
  label: string;
}

/** Options may arrive as canonical {value,label} objects or legacy plain strings. */
export type CustomFieldOptionInput = string | CustomFieldOption;

export interface CustomFieldDefinition {
  id: string;
  organization_id: string;
  entity_type: string;
  key: string;
  label: string;
  field_type: CustomFieldType | string;
  options: CustomFieldOptionInput[] | null;
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

export interface CrmConfig {
  industry: string;
  template: string;
  enabled_modules: string[];
}

export interface MetadataBootstrap {
  metadata_version: number;
  custom_fields: CustomFieldDefinition[];
  /** Per-entity definition map (Phase 4.1). Backward-compatible with `custom_fields`. */
  custom_fields_by_entity?: Record<string, CustomFieldDefinition[]>;
  /** Custom object definitions, eager-loaded (Phase 4.2). Field defs load lazily per object. */
  custom_objects?: CustomObjectDefinitionLite[];
  pipelines: Pipeline[];
  crm_config?: CrmConfig;
}

/** Minimal object-definition shape carried in bootstrap. */
export interface CustomObjectDefinitionLite {
  id: string;
  key: string;
  label: string;
  label_plural: string | null;
  icon: string | null;
  color: string | null;
  display_field_key: string | null;
  is_active: boolean;
  is_system: boolean;
}

/** Coerce a definition's options (legacy strings or objects) to {value,label}[]. */
export function normalizeFieldOptions(
  options: CustomFieldOptionInput[] | null | undefined,
): CustomFieldOption[] {
  if (!options) return [];
  return options.map((o) =>
    typeof o === 'string' ? { value: o, label: o } : { value: o.value, label: o.label ?? o.value },
  );
}

/** Field types that are backed by a fixed option list. */
export const OPTION_FIELD_TYPES: CustomFieldType[] = ['select', 'multiselect'];

export interface CustomFieldInput {
  key?: string;
  label?: string;
  field_type?: string;
  options?: CustomFieldOptionInput[] | null;
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
