import { api } from './api';

/** Masked telephony config — the server NEVER returns secret values, only
 *  `has_*` presence flags. */
export interface TelephonyConfig {
  provider: string;
  is_active: boolean;
  is_connected: boolean;
  company_id: string | null;
  public_ivr_id: string | null;
  call_type: string;
  user_uuid: string | null;
  default_caller_id: string | null;
  std_code: string | null;
  webhook_url: string | null;
  has_authentication_token: boolean;
  has_x_api_key: boolean;
  has_secret_token: boolean;
  has_webhook_secret: boolean;
  call_recording: boolean;
  power_dialer: boolean;
  predictive_dialer: boolean;
  auto_assignment: boolean;
  call_retry_count: number;
  retry_interval_seconds: number;
  max_call_duration_seconds: number;
}

/** Write-only update. Secrets are plaintext going in; blank leaves them unchanged. */
export interface TelephonyConfigUpdate {
  provider?: string;
  is_active?: boolean;
  company_id?: string;
  public_ivr_id?: string;
  call_type?: string;
  user_uuid?: string;
  default_caller_id?: string;
  std_code?: string;
  webhook_url?: string;
  authentication_token?: string;
  x_api_key?: string;
  secret_token?: string;
  webhook_secret?: string;
  call_recording?: boolean;
  power_dialer?: boolean;
  predictive_dialer?: boolean;
  auto_assignment?: boolean;
  call_retry_count?: number;
  retry_interval_seconds?: number;
  max_call_duration_seconds?: number;
}

export const settingsApi = {
  getCalling: async (): Promise<TelephonyConfig> =>
    (await api.get<TelephonyConfig>('/settings/calling')).data,

  updateCalling: async (payload: TelephonyConfigUpdate): Promise<TelephonyConfig> =>
    (await api.put<TelephonyConfig>('/settings/calling', payload)).data,

  testCalling: async (): Promise<{ success: boolean; message?: string }> =>
    (await api.post('/settings/calling/test')).data,

  connectCalling: async (): Promise<{ success: boolean; message?: string }> =>
    (await api.post('/settings/calling/connect')).data,

  disconnectCalling: async (): Promise<{ success: boolean; message?: string }> =>
    (await api.post('/settings/calling/disconnect')).data,
};
