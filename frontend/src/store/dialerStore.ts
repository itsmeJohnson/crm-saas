import { create } from 'zustand';
import { dialerApi } from '../services/dialerApi';
import { LeadResponse } from '../services/leadApi';

export type AgentState = 'IDLE' | 'ACTIVE_CALLING' | 'BREAK';

interface DialerState {
  agentState: AgentState;
  currentLead: LeadResponse | null;
  breakReason: string | null;
  callDuration: number;
  isLoading: boolean;
  error: string | null;
  
  fetchCurrentState: () => Promise<void>;
  startCalling: (collectivePooling?: boolean) => Promise<void>;
  submitDisposition: (dispositionData: {
    status: string;
    remarks: string;
    custom_pipeline_stage_id?: string;
  }) => Promise<void>;
  goOnBreak: (reason: string) => Promise<void>;
  endBreak: () => Promise<void>;
  resetStore: () => void;
}

let timerIntervalId: any = null;

const startTimer = (set: any) => {
  if (timerIntervalId) {
    clearInterval(timerIntervalId);
  }
  set({ callDuration: 0 });
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
  isLoading: false,
  error: null,

  fetchCurrentState: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await dialerApi.getState();
      set({
        agentState: data.state,
        breakReason: data.state === 'BREAK' ? (data.metadata?.break_reason || null) : null,
        isLoading: false,
      });
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to fetch agent state';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  startCalling: async (collectivePooling = false) => {
    set({ isLoading: true, error: null });
    try {
      const lead = await dialerApi.getNextLead({ collective_pooling: collectivePooling });
      set({
        currentLead: lead,
        agentState: 'ACTIVE_CALLING',
        isLoading: false,
      });
      startTimer(set);
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
        isLoading: false,
      });
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to submit disposition';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  goOnBreak: async (reason) => {
    set({ isLoading: true, error: null });
    try {
      await dialerApi.updateState({ state: 'BREAK', metadata: { break_reason: reason } });
      set({
        agentState: 'BREAK',
        breakReason: reason,
        isLoading: false,
      });
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to go on break';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  endBreak: async () => {
    set({ isLoading: true, error: null });
    try {
      await dialerApi.updateState({ state: 'IDLE' });
      set({
        agentState: 'IDLE',
        breakReason: null,
        isLoading: false,
      });
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to end break';
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
      isLoading: false,
      error: null,
    });
  },
}));
