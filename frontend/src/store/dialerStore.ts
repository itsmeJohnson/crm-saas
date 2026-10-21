import { create } from 'zustand';
import { dialerApi, CallCreds } from '../services/dialerApi';
import { LeadResponse, leadApi } from '../services/leadApi';
import { telecmiWebRTC, WebRTCPhoneStatus } from '../services/telecmiWebRTC';

export type AgentState = 'IDLE' | 'ACTIVE_CALLING' | 'BREAK';

interface DialerState {
  agentState: AgentState;
  currentLead: LeadResponse | null;
  breakReason: string | null;
  callDuration: number;
  stateTimestamp: string | null;
  isLoading: boolean;
  error: string | null;
  callDirection: 'INBOUND' | 'OUTBOUND' | null;
  webrtcStatus: WebRTCPhoneStatus;
  isMuted: boolean;
  incomingCall: {
    from: string;
    name?: string;
    call_id: string;
    to_number?: string;
    lead?: any;
  } | null;

  setIncomingCall: (call: any) => void;
  rejectInboundCall: () => void;
  initWebRTC: () => Promise<void>;
  toggleMute: () => void;
  hangupWebRTC: () => void;
  fetchCurrentState: () => Promise<void>;
  startCalling: (
    collectivePooling?: boolean,
    creds?: CallCreds
  ) => Promise<void>;
  submitDisposition: (dispositionData: {
    status: string;
    remarks: string;
    custom_pipeline_stage_id?: string;
  }) => Promise<void>;
  goOnBreak: (reason: string) => Promise<void>;
  endBreak: () => Promise<void>;
  answerInboundCall: (lead?: any) => Promise<void>;
  callSpecificLead: (
    leadId: string,
    creds?: CallCreds
  ) => Promise<void>;
  resetStore: () => void;
}


let timerIntervalId: any = null;

const startTimer = (set: any, initialSeconds = 0) => {
  if (timerIntervalId) {
    clearInterval(timerIntervalId);
  }
  set({ callDuration: initialSeconds });
  timerIntervalId = setInterval(() => {
    set((state: any) => ({ callDuration: state.callDuration + 1 }));
  }, 1000);
};

const stopTimer = () => {
  if (timerIntervalId) {
    clearInterval(timerIntervalId);
    timerIntervalId = null;
  }
};

export const useDialerStore = create<DialerState>((set, get) => ({
  agentState: 'IDLE',
  currentLead: null,
  breakReason: null,
  callDuration: 0,
  stateTimestamp: null,
  isLoading: false,
  error: null,
  callDirection: null,
  webrtcStatus: 'idle',
  isMuted: false,
  incomingCall: null,

  setIncomingCall: (call) => set({ incomingCall: call }),

  rejectInboundCall: () => {
    telecmiWebRTC.reject();
    set({ incomingCall: null });
  },

  initWebRTC: async () => {
    telecmiWebRTC.subscribe((status, details) => {
      set({ webrtcStatus: status, isMuted: telecmiWebRTC.getIsMuted() });
      if (status === 'incoming' && details) {
        set({ incomingCall: details });
        if (details.from) {
          leadApi.getLeads({ search: details.from, limit: 1 }).then((res: any) => {
            const matched = res?.items?.[0] || null;
            if (matched) {
              set((s) => ({
                incomingCall: s.incomingCall ? { ...s.incomingCall, lead: matched } : null
              }));
            }
          }).catch(() => {});
        }
      } else if (status === 'ended' || status === 'idle') {
        set({ incomingCall: null });
      }
    });
    try {
      const session = await dialerApi.getWebRTCSession();
      if (session.enabled && session.provider === 'telecmi' && session.user_id && session.password) {
        telecmiWebRTC.init({
          user_id: session.user_id,
          password: session.password,
          region: session.region,
          caller_id: session.caller_id,
          agent_name: session.agent_name,
        });
        return;
      }
    } catch (e) {
      console.warn('[WebRTC] Backend session API not available, using tenant default:', e);
    }

    // Default tenant fallback for Samartha Sankalpa
    telecmiWebRTC.init({
      user_id: '5001_33339071',
      password: 'admin@123',
      region: 'sbcind.telecmi.com',
      caller_id: '917949817390',
      agent_name: 'Sandya S',
    });
  },

  toggleMute: () => {
    const isMuted = telecmiWebRTC.toggleMute();
    set({ isMuted });
  },

  hangupWebRTC: () => {
    telecmiWebRTC.hangup();
  },

  fetchCurrentState: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await dialerApi.getState();
      
      let lead = get().currentLead;
      let direction = get().callDirection;
      if (data.state === 'ACTIVE_CALLING') {
        if (!lead && typeof localStorage !== 'undefined') {
          const cachedLead = localStorage.getItem('crm_dialer_current_lead');
          if (cachedLead) {
            try {
              lead = JSON.parse(cachedLead);
            } catch (e) {}
          }
        }
        if (!lead && data.metadata?.lead_id) {
          try {
            lead = await leadApi.getLead(data.metadata.lead_id);
            if (lead && typeof localStorage !== 'undefined') {
              localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
            }
          } catch (e) {}
        }
        if (!direction && typeof localStorage !== 'undefined') {
          direction = localStorage.getItem('crm_dialer_call_direction') as 'INBOUND' | 'OUTBOUND' | null;
        }
      } else {
        lead = null;
        direction = null;
      }

      const elapsed = data.timestamp ? Math.floor((Date.now() - new Date(data.timestamp).getTime()) / 1000) : 0;
      
      set({
        agentState: data.state,
        breakReason: data.state === 'BREAK' ? (data.metadata?.break_reason || null) : null,
        currentLead: lead,
        callDirection: direction,
        stateTimestamp: data.timestamp || null,
        isLoading: false,
      });

      if (data.state === 'ACTIVE_CALLING') {
        startTimer(set, Math.max(0, elapsed));
      } else {
        stopTimer();
        set({ callDuration: 0 });
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to fetch agent state';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  startCalling: async (collectivePooling = false, creds?: CallCreds) => {
    set({ isLoading: true, error: null });
    try {
      const lead = await dialerApi.getNextLead({
        collective_pooling: collectivePooling,
        ...(creds || {}),
      });
      const nowStr = new Date().toISOString();
      set({
        currentLead: lead,
        agentState: 'ACTIVE_CALLING',
        callDirection: 'OUTBOUND',
        stateTimestamp: nowStr,
        isLoading: false,
      });
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
        localStorage.setItem('crm_dialer_call_direction', 'OUTBOUND');
      }
      startTimer(set, 0);
      if (lead && lead.phone) {
        telecmiWebRTC.makeCall(lead.phone).catch((e) => console.warn('[WebRTC] Call trigger error:', e));
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to fetch next lead';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  submitDisposition: async (dispositionData) => {
    let lead = get().currentLead;
    if (!lead && typeof localStorage !== 'undefined') {
      const cachedLead = localStorage.getItem('crm_dialer_current_lead');
      if (cachedLead) {
        try {
          lead = JSON.parse(cachedLead);
        } catch {}
      }
    }

    set({ isLoading: true, error: null });
    telecmiWebRTC.hangup();
    try {
      if (lead && lead.id) {
        await dialerApi.submitDisposition(lead.id, dispositionData);
      } else {
        // Orphaned active call session: reset agent back to IDLE so telecaller is never trapped
        await dialerApi.updateState({ state: 'IDLE' });
      }

      stopTimer();
      set({
        currentLead: null,
        callDuration: 0,
        agentState: 'IDLE',
        callDirection: null,
        stateTimestamp: null,
        isLoading: false,
      });
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('crm_dialer_current_lead');
        localStorage.removeItem('crm_dialer_call_direction');
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to save call disposition';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  goOnBreak: async (reason) => {
    set({ isLoading: true, error: null });
    try {
      const data = await dialerApi.updateState({ state: 'BREAK', metadata: { break_reason: reason } });
      stopTimer();
      set({
        agentState: 'BREAK',
        breakReason: reason,
        stateTimestamp: data.timestamp || null,
        currentLead: null,
        callDuration: 0,
        isLoading: false,
      });
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('crm_dialer_current_lead');
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to go on break';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  endBreak: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await dialerApi.updateState({ state: 'IDLE' });
      set({
        agentState: 'IDLE',
        breakReason: null,
        stateTimestamp: data.timestamp || null,
        isLoading: false,
      });
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to end break';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  answerInboundCall: async (lead?: any) => {
    set({ isLoading: true, error: null });
    telecmiWebRTC.answer();
    try {
      await dialerApi.updateState({ state: 'ACTIVE_CALLING' });
    } catch (e) {
      console.warn('[Dialer] updateState failed, proceeding with in-browser active calling session:', e);
    }
    const incoming = get().incomingCall;
    const targetLead = lead || incoming?.lead || {
      id: incoming?.call_id || `inbound-${Date.now()}`,
      first_name: incoming?.name || 'Inbound',
      last_name: 'Caller',
      phone: incoming?.from || '',
      company: '',
      title: 'Incoming Call',
      status: 'Contacted',
    };
    const nowStr = new Date().toISOString();
    set({
      currentLead: targetLead,
      agentState: 'ACTIVE_CALLING',
      callDirection: 'INBOUND',
      stateTimestamp: nowStr,
      incomingCall: null,
      isLoading: false,
    });
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_dialer_current_lead', JSON.stringify(targetLead));
      localStorage.setItem('crm_dialer_call_direction', 'INBOUND');
    }
    startTimer(set, 0);
  },

  // Manually call a specific already-known lead from the Leads list (any status),
  // rather than pulling the next 'New' lead from the queue. Mirrors startCalling
  // so the same ActiveCallDisposition form drives the outcome afterwards.
  callSpecificLead: async (leadId, creds?: CallCreds) => {
    set({ isLoading: true, error: null });
    let lead: any = null;
    try {
      lead = await dialerApi.callLead(leadId, { ...(creds || {}) });
    } catch (err: any) {
      console.warn('[Dialer] Backend callLead check returned error, initiating direct in-browser WebRTC call:', err);
      try {
        lead = await leadApi.getLead(leadId);
      } catch (getLeadErr) {
        const errMsg = err.response?.data?.detail || err.message || 'Failed to place the call';
        set({ error: errMsg, isLoading: false });
        throw err;
      }
    }

    const nowStr = new Date().toISOString();
    set({
      currentLead: lead,
      agentState: 'ACTIVE_CALLING',
      callDirection: 'OUTBOUND',
      stateTimestamp: nowStr,
      isLoading: false,
    });
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
      localStorage.setItem('crm_dialer_call_direction', 'OUTBOUND');
    }
    startTimer(set, 0);
    if (lead && lead.phone) {
      telecmiWebRTC.makeCall(lead.phone).catch((e) => console.warn('[WebRTC] Call trigger error:', e));
    }
  },

  resetStore: () => {
    stopTimer();
    set({
      agentState: 'IDLE',
      currentLead: null,
      breakReason: null,
      callDuration: 0,
      stateTimestamp: null,
      isLoading: false,
      error: null,
      callDirection: null,
    });
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('crm_dialer_current_lead');
      localStorage.removeItem('crm_dialer_call_direction');
    }
  },
}));
