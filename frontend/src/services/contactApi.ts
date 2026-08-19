import { api } from './api';

export interface ContactAttachment {
  filename: string;
  url: string;
  size?: number;
  uploaded_by?: string;
  uploaded_at?: string;
}

export interface ContactResponse {
  id: string;
  organization_id: string;
  company_id: string | null;
  first_name: string;
  last_name: string;
  email: string | null;
  phone: string | null;
  job_title: string | null;
  assigned_user_id: string | null;
  tags: string[] | null;
  custom_fields: Record<string, any> | null;
  attachments: ContactAttachment[] | null;
  created_by: string;
  created_at: string;
  updated_at: string;
}

export interface ContactListFilters {
  skip?: number;
  limit?: number;
  search?: string;
  company_id?: string;
  assigned_user_id?: string;
  tag?: string;
  has_email?: boolean;
  created_from?: string;
  created_to?: string;
}

export interface ContactTimelineEvent {
  type: 'note' | 'activity' | 'audit';
  id: string;
  timestamp: string;
  title: string;
  description: string | null;
  actor_user_id: string | null;
  event_metadata: Record<string, any> | null;
}

export interface ContactCommunication {
  id: string;
  channel: string;
  subject: string;
  description: string | null;
  direction: string | null;
  status: string;
  timestamp: string;
  recording_url: string | null;
}

export interface ContactRelationship {
  id: string;
  contact_id: string;
  related_contact_id: string;
  relationship_type: string;
  related_contact_name: string | null;
}

// Single source of truth for the custom-field definition shape (Phase 4.1):
// re-export the canonical type so contacts, leads and the shared renderer agree.
import type { CustomFieldDefinition, CustomFieldOptionInput } from './metadataApi';
export type { CustomFieldDefinition, CustomFieldOptionInput } from './metadataApi';

export interface ContactReportBucket {
  label: string;
  count: number;
}

export interface ContactReport {
  total_contacts: number;
  with_email: number;
  with_phone: number;
  with_company: number;
  by_company: ContactReportBucket[];
  by_owner: ContactReportBucket[];
  by_tag: ContactReportBucket[];
}

type ContactWritePayload = {
  first_name?: string;
  last_name?: string;
  email?: string | null;
  phone?: string | null;
  job_title?: string | null;
  company_id?: string | null;
  assigned_user_id?: string | null;
  tags?: string[] | null;
  custom_fields?: Record<string, any> | null;
};

export const contactApi = {
  getContacts: async (params: ContactListFilters) => {
    const response = await api.get<ContactResponse[]>('/contacts/', { params });
    return response.data;
  },

  createContact: async (payload: ContactWritePayload & { first_name: string; last_name: string }) => {
    const response = await api.post<ContactResponse>('/contacts/', payload);
    return response.data;
  },

  getContact: async (contactId: string) => {
    const response = await api.get<ContactResponse>(`/contacts/${contactId}`);
    return response.data;
  },

  updateContact: async (contactId: string, payload: ContactWritePayload) => {
    const response = await api.patch<ContactResponse>(`/contacts/${contactId}`, payload);
    return response.data;
  },

  deleteContact: async (contactId: string) => {
    const response = await api.delete<ContactResponse>(`/contacts/${contactId}`);
    return response.data;
  },

  exportContacts: async (params: ContactListFilters & { format?: 'csv' | 'xlsx' }) => {
    const response = await api.get('/contacts/export', { params, responseType: 'blob' });
    return response.data as Blob;
  },

  importContacts: async (file: File) => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post<{ created: number; failed: number; errors: any[] }>(
      '/contacts/import', form, { headers: { 'Content-Type': 'multipart/form-data' } },
    );
    return response.data;
  },

  findDuplicates: async (params: { email?: string; phone?: string; exclude_contact_id?: string }) => {
    const response = await api.get<ContactResponse[]>('/contacts/duplicates', { params });
    return response.data;
  },

  bulkUpdate: async (payload: {
    contact_ids: string[];
    fields: { company_id?: string; assigned_user_id?: string; add_tags?: string[]; remove_tags?: string[] };
  }) => {
    const response = await api.post<{ affected_count: number; contact_ids: string[] }>('/contacts/bulk-update', payload);
    return response.data;
  },

  bulkDelete: async (contactIds: string[]) => {
    const response = await api.post<{ affected_count: number; contact_ids: string[] }>('/contacts/bulk-delete', { contact_ids: contactIds });
    return response.data;
  },

  merge: async (primaryId: string, secondaryId: string) => {
    const response = await api.post<ContactResponse>('/contacts/merge', { primary_id: primaryId, secondary_id: secondaryId });
    return response.data;
  },

  listTags: async () => {
    const response = await api.get<string[]>('/contacts/tags');
    return response.data;
  },

  getReport: async (params?: { date_from?: string; date_to?: string }) => {
    const response = await api.get<ContactReport>('/contacts/reports', { params });
    return response.data;
  },

  getTimeline: async (contactId: string) => {
    const response = await api.get<ContactTimelineEvent[]>(`/contacts/${contactId}/timeline`);
    return response.data;
  },

  getCommunications: async (contactId: string) => {
    const response = await api.get<ContactCommunication[]>(`/contacts/${contactId}/communications`);
    return response.data;
  },

  listAttachments: async (contactId: string) => {
    const response = await api.get<ContactAttachment[]>(`/contacts/${contactId}/attachments`);
    return response.data;
  },

  uploadAttachment: async (contactId: string, file: File) => {
    const form = new FormData();
    form.append('file', file);
    const response = await api.post<ContactAttachment>(`/contacts/${contactId}/attachments`, form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  deleteAttachment: async (contactId: string, filename: string) => {
    await api.delete(`/contacts/${contactId}/attachments/${encodeURIComponent(filename)}`);
  },

  listRelationships: async (contactId: string) => {
    const response = await api.get<ContactRelationship[]>(`/contacts/${contactId}/relationships`);
    return response.data;
  },

  addRelationship: async (contactId: string, payload: { related_contact_id: string; relationship_type: string }) => {
    const response = await api.post<ContactRelationship>(`/contacts/${contactId}/relationships`, payload);
    return response.data;
  },

  deleteRelationship: async (contactId: string, relationshipId: string) => {
    await api.delete(`/contacts/${contactId}/relationships/${relationshipId}`);
  },

  listCustomFields: async () => {
    const response = await api.get<CustomFieldDefinition[]>('/contacts/custom-fields');
    return response.data;
  },

  createCustomField: async (payload: { key: string; label: string; field_type?: string; options?: CustomFieldOptionInput[] }) => {
    const response = await api.post<CustomFieldDefinition>('/contacts/custom-fields', payload);
    return response.data;
  },

  deleteCustomField: async (definitionId: string) => {
    await api.delete(`/contacts/custom-fields/${definitionId}`);
  },
};
