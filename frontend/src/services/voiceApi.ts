import { api } from './api';

export interface VoiceRecipient {
  id: string;
  number: string;
  unique_id: string | null;
  status: string;
  vendor_status: string | null;
  dtmf: string | null;
  call_duration: string | null;
  lead_id: string | null;
  contact_id: string | null;
}

export interface VoiceBroadcast {
  id: string;
  name: string;
  mode: 'voice_note' | 'tts';
  status: string;
  voice_type: string | null;
  voice_medias_id: string | null;
  tts_language: string | null;
  tts_gender: string | null;
  total_recipients: number;
  provider_job_id: string | null;
  scheduled: boolean;
  sent_at: string | null;
  last_error: string | null;
  created_at: string;
}

export interface VoiceBroadcastDetail extends VoiceBroadcast {
  tts_content: string | null;
  recipients: VoiceRecipient[];
}

export interface VoiceBroadcastList {
  items: VoiceBroadcast[];
  total: number;
}

export interface VoiceMedia {
  [k: string]: any;
}

export interface VoiceSendPayload {
  name?: string;
  mode: 'voice_note' | 'tts';
  numbers?: string[];
  lead_ids?: string[];
  contact_ids?: string[];
  voice_type?: string;
  voice_medias_id?: string;
  obd_type?: string;
  tts_content?: string;
  tts_language?: string;
  tts_gender?: string;
  scheduled?: boolean;
  scheduled_datetime?: string;
  retry_interval?: number;
  retry_count?: number;
}

export const voiceApi = {
  send: async (payload: VoiceSendPayload) =>
    (await api.post<VoiceBroadcastDetail>('/voice/broadcasts', payload)).data,
  list: async (params: { skip?: number; limit?: number } = {}) =>
    (await api.get<VoiceBroadcastList>('/voice/broadcasts', { params })).data,
  get: async (id: string) => (await api.get<VoiceBroadcastDetail>(`/voice/broadcasts/${id}`)).data,
  refresh: async (id: string) => (await api.post<VoiceBroadcastDetail>(`/voice/broadcasts/${id}/refresh`)).data,

  listMedia: async () => (await api.get<{ success: boolean; items: VoiceMedia[]; message?: string }>('/voice/media')).data,
  uploadMedia: async (form: FormData) =>
    (await api.post<{ success: boolean; announcement_id?: any; message?: string }>('/voice/media', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    })).data,

  missedCalls: async (payload: { did_number: string; start_date: string; end_date: string }) =>
    (await api.post<{ success: boolean; rows: any[]; message?: string }>('/voice/missed-calls', payload)).data,
};
