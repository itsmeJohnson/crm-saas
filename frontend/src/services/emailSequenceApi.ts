import { api } from './api';

export interface SequenceStep {
  id?: string;
  step_order?: number;
  subject: string;
  body: string;
  delay_hours: number;
  is_active?: boolean;
}

export interface EmailSequence {
  id: string;
  organization_id: string;
  name: string;
  description?: string | null;
  trigger: 'manual' | 'lead_created';
  is_active: boolean;
  created_at: string;
  steps: SequenceStep[];
}

export interface Enrollment {
  id: string;
  sequence_id: string;
  lead_id: string;
  current_step: number;
  status: string;
  next_run_at?: string | null;
  last_sent_at?: string | null;
}

export interface SequenceInput {
  name: string;
  description?: string;
  trigger: 'manual' | 'lead_created';
  is_active?: boolean;
  steps: { subject: string; body: string; delay_hours: number }[];
}

export const emailSequenceApi = {
  list: async () => (await api.get<EmailSequence[]>('/email-sequences')).data,
  get: async (id: string) => (await api.get<EmailSequence>(`/email-sequences/${id}`)).data,
  create: async (payload: SequenceInput) => (await api.post<EmailSequence>('/email-sequences', payload)).data,
  update: async (id: string, payload: Partial<SequenceInput>) =>
    (await api.patch<EmailSequence>(`/email-sequences/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/email-sequences/${id}`); },
  enrollments: async (id: string) => (await api.get<Enrollment[]>(`/email-sequences/${id}/enrollments`)).data,
  enroll: async (id: string, lead_id: string) =>
    (await api.post<Enrollment>(`/email-sequences/${id}/enroll`, { lead_id })).data,
  cancelEnrollment: async (enrollmentId: string) => { await api.delete(`/email-sequences/enrollments/${enrollmentId}`); },
};
