import { create } from 'zustand';
import { dialerApi } from '../services/dialerApi';
import { LeadResponse } from '../services/leadApi';

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
  
  fetchCurrentState: () => Promise<void>;
  startCalling: (
    collectivePooling?: boolean,
    knowlarityApiKey?: string,
    knowlaritySrn?: string,
    agentPhoneNumber?: string
  ) => Promise<void>;
  submitDisposition: (dispositionData: {
    status: string;
    remarks: string;
    custom_pipeline_stage_id?: string;
  }) => Promise<void>;
  goOnBreak: (reason: string) => Promise<void>;
  endBreak: () => Promise<void>;
  answerInboundCall: (lead: LeadResponse) => Promise<void>;
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

  startCalling: async (
    collectivePooling = false,
    knowlarityApiKey?: string,
    knowlaritySrn?: string,
    agentPhoneNumber?: string
  ) => {
    set({ isLoading: true, error: null });
    try {
      const lead = await dialerApi.getNextLead({
        collective_pooling: collectivePooling,
        knowlarity_api_key: knowlarityApiKey,
        knowlarity_srn: knowlaritySrn,
        agent_phone_number: agentPhoneNumber,
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
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to fetch next lead';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  submitDisposition: async (dispositionData) => {
    const lead = get().currentLead;
    if (!lead) {
      throw new Error('No active lead to disposition');
    }
    set({ isLoading: true, error: null });
    try {
      await dialerApi.submitDisposition(lead.id, dispositionData);
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
      const errMsg = err.response?.data?.detail || err.message || 'Failed to submit disposition';
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

  answerInboundCall: async (lead) => {
    set({ isLoading: true, error: null });
    try {
      await dialerApi.updateState({ state: 'ACTIVE_CALLING' });
      const nowStr = new Date().toISOString();
      set({
        currentLead: lead,
        agentState: 'ACTIVE_CALLING',
        callDirection: 'INBOUND',
        stateTimestamp: nowStr,
        isLoading: false,
      });
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
        localStorage.setItem('crm_dialer_call_direction', 'INBOUND');
      }
      startTimer(set, 0);
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to answer inbound call';
      set({ error: errMsg, isLoading: false });
      throw err;
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
