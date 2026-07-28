import { api } from './api';
import { LeadResponse } from './leadApi';

export interface AgentStateResponse {
  state: 'IDLE' | 'ACTIVE_CALLING' | 'BREAK';
  timestamp: string;
  metadata: Record<string, any>;
}

// Provider-agnostic click-to-call credentials sent with dialer requests.
// `provider` selects the gateway; only that provider's fields are used server-side.
export interface CallCreds {
  provider?: string; // 'knowlarity' | 'myoperator'
  agent_phone_number?: string;
  knowlarity_api_key?: string;
  knowlarity_srn?: string;
  myop_x_api_key?: string;
  myop_secret_key?: string;
  myop_company_id?: string;
  myop_public_ivr_id?: string;
  myop_type?: string;
}

export const dialerApi = {
  getNextLead: async (payload: { collective_pooling: boolean } & CallCreds = { collective_pooling: false }) => {
    const response = await api.post<LeadResponse>('/dialer/next-lead', payload);
    return response.data;
  },

  updateState: async (payload: { state: 'IDLE' | 'ACTIVE_CALLING' | 'BREAK'; metadata?: Record<string, any> }) => {
    const response = await api.post<AgentStateResponse>('/dialer/state', payload);
    return response.data;
  },

  getState: async () => {
    const response = await api.get<AgentStateResponse>('/dialer/state');
    return response.data;
  },

  submitDisposition: async (
    leadId: string,
    payload: {
      status: string;
      remarks: string;
      custom_pipeline_stage_id?: string;
    }
  ) => {
    const response = await api.post<LeadResponse>(`/dialer/leads/${leadId}/disposition`, payload);
    return response.data;
  },

  // Manually place a server-side click-to-call to a specific lead (any status)
  // from the Leads list. The customer number is dialed server-side so a masked
  // telecaller never sees it.
  callLead: async (leadId: string, payload: CallCreds) => {
    const response = await api.post<LeadResponse>(`/dialer/leads/${leadId}/call`, payload);
    return response.data;
  },
};
