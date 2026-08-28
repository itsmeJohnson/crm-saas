import { api } from './api';

export interface FormFieldEntry {
  key: string;
  required?: boolean | null;
  hidden?: boolean | null;
  read_only?: boolean | null;
}

export interface FormSection {
  title?: string | null;
  columns?: number | null;
  fields: FormFieldEntry[];
}

export interface FormSchema {
  sections: FormSection[];
}

export interface FormDefinition {
  id: string;
  organization_id: string;
  entity_type: string;
  key: string;
  name: string;
  description: string | null;
  schema: FormSchema | null;
  is_active: boolean;
  is_default: boolean;
  created_at: string;
  updated_at: string;
}

export interface FormInput {
  key?: string;
  name?: string;
  description?: string | null;
  schema?: FormSchema;
  is_active?: boolean;
  is_default?: boolean;
}

export const formApi = {
  listForms: async (entityType: string, includeInactive = false) => {
    const res = await api.get<FormDefinition[]>('/forms', {
      params: { entity_type: entityType, include_inactive: includeInactive },
    });
    return res.data;
  },

  getForm: async (formId: string) => {
    const res = await api.get<FormDefinition>(`/forms/${formId}`);
    return res.data;
  },

  createForm: async (entityType: string, payload: FormInput) => {
    const res = await api.post<FormDefinition>('/forms', payload, { params: { entity_type: entityType } });
    return res.data;
  },

  updateForm: async (formId: string, payload: FormInput) => {
    const res = await api.patch<FormDefinition>(`/forms/${formId}`, payload);
    return res.data;
  },

  deleteForm: async (formId: string) => {
    const res = await api.delete(`/forms/${formId}`);
    return res.data;
  },
};

/** Resolve the form to use for an entity: the default active form, else the first. */
export function pickForm(forms: FormDefinition[]): FormDefinition | null {
  if (!forms.length) return null;
  return forms.find((f) => f.is_default && f.is_active) ?? forms.find((f) => f.is_active) ?? null;
}
