import { create } from 'zustand';
import { dialerApi, CallCreds } from '../services/dialerApi';
import { LeadResponse, leadApi } from '../services/leadApi';
import { telecmiWebRTC, WebRTCPhoneStatus } from '../services/telecmiWebRTC';

export type AgentState = 'IDLE' | 'ACTIVE_CALLING' | 'BREAK';
export type CallLifecycle = 'idle' | 'initiating' | 'ringing' | 'connected' | 'disposition';
export type NetworkStatus = 'online' | 'unstable';

export interface CallDispositionPayload {
  status: string;
  disposition_category?: string;
  remarks: string;
  custom_pipeline_stage_id?: string;
  follow_up_date?: string;
  follow_up_time?: string;
  follow_up_priority?: 'Low' | 'Medium' | 'High' | 'Urgent';
}

interface DialerState {
  agentState: AgentState;
  callLifecycle: CallLifecycle;
  networkStatus: NetworkStatus;
  reconnectCountdown: number;
  currentLead: LeadResponse | null;
  breakReason: string | null;
  callDuration: number;
  stateTimestamp: string | null;
  isLoading: boolean;
  error: string | null;
  callDirection: 'INBOUND' | 'OUTBOUND' | null;
  webrtcStatus: WebRTCPhoneStatus;
  isMuted: boolean;
  isKeypadOpen: boolean;
  isReconnecting: boolean;
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
  toggleKeypad: (force?: boolean) => void;
  sendDTMF: (digit: string | number) => void;
  hangupWebRTC: () => void;
  cancelInitiatingCall: () => void;
  fetchCurrentState: () => Promise<void>;
  startCalling: (
    collectivePooling?: boolean,
    creds?: CallCreds
  ) => Promise<void>;
  submitDisposition: (dispositionData: CallDispositionPayload) => Promise<void>;
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
let networkCountdownIntervalId: any = null;
let isWebRTCSubscribed = false;

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
  callLifecycle: 'idle',
  networkStatus: 'online',
  reconnectCountdown: 15,
  currentLead: null,
  breakReason: null,
  callDuration: 0,
  stateTimestamp: null,
  isLoading: false,
  error: null,
  callDirection: null,
  webrtcStatus: 'idle',
  isMuted: false,
  isKeypadOpen: false,
  isReconnecting: false,
  incomingCall: null,

  setIncomingCall: (call) => set({ incomingCall: call }),

  rejectInboundCall: () => {
    telecmiWebRTC.reject();
    set({ incomingCall: null, callLifecycle: 'idle', callDirection: null, currentLead: null });
  },

  toggleKeypad: (force?: boolean) => {
    set((state) => ({ isKeypadOpen: typeof force === 'boolean' ? force : !state.isKeypadOpen }));
  },

  sendDTMF: (digit: string | number) => {
    telecmiWebRTC.sendDTMF(digit);
  },

  initWebRTC: async () => {
    if (!isWebRTCSubscribed) {
      isWebRTCSubscribed = true;
      telecmiWebRTC.subscribe((status, _details) => {
        set({ webrtcStatus: status, isMuted: telecmiWebRTC.getIsMuted() });

        if (status === 'incoming') {
          const incData = (_details || telecmiWebRTC.getIncomingCall()) as any;
          const callerPhone = incData?.from || '';
          const callerName = incData?.name || '';
          const callId = incData?.call_id || `inbound-${Date.now()}`;
          const toNumber = incData?.to_number || '917949817390';

          const currentIncoming = get().incomingCall;
          // Deduplicate incoming call event if already ringing for this number/callId
          if (currentIncoming && (currentIncoming.from === callerPhone || currentIncoming.call_id === callId)) {
            return;
          }

          // 1. Immediately trigger incoming call ringing UI
          set({
            incomingCall: {
              from: callerPhone,
              name: callerName || 'Customer',
              call_id: callId,
              to_number: toNumber,
              lead: null,
            },
            callLifecycle: 'ringing',
            callDirection: 'INBOUND',
          });

          // 2. Concurrently lookup or auto-create lead so details populate in popup
          if (callerPhone) {
            dialerApi.getOrCreateInboundLead({
              phone: callerPhone,
              caller_name: callerName,
              call_id: callId,
            }).then((lead) => {
              if (lead) {
                set((state) => ({
                  incomingCall: state.incomingCall ? { ...state.incomingCall, lead } : null,
                }));
              }
            }).catch((err) => {
              console.warn('[WebRTC] Inbound lead lookup error:', err);
            });
          }
        } else if (status === 'calling') {
          set({ callLifecycle: 'initiating' });
        } else if (status === 'ringing') {
          if (get().callDirection !== 'INBOUND') {
            set({ callLifecycle: 'ringing' });
          }
        } else if (status === 'connected') {
          set({ callLifecycle: 'connected', isReconnecting: false });
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem('crm_dialer_lifecycle', 'connected');
          }
          if (!timerIntervalId) {
            startTimer(set, get().callDuration || 0);
          }
        } else if (status === 'ended') {
          stopTimer();
          const wasRinging = get().callLifecycle === 'ringing' || Boolean(get().incomingCall);
          const wasConnected = get().callLifecycle === 'connected';
          const isOutbound = get().callDirection === 'OUTBOUND';

          // Scenario 1: Inbound ringing dropped before answer -> dismiss popup cleanly to idle
          if (wasRinging && !isOutbound) {
            set({
              callLifecycle: 'idle',
              incomingCall: null,
              currentLead: null,
              agentState: 'IDLE',
              callDirection: null,
              webrtcStatus: 'registered'
            });
            if (typeof localStorage !== 'undefined') {
              localStorage.removeItem('crm_dialer_lifecycle');
              localStorage.removeItem('crm_dialer_current_lead');
              localStorage.removeItem('crm_dialer_call_direction');
              localStorage.removeItem('crm_dialer_start_time');
            }
            return;
          }

          // Scenario 2: Active conversation ended (either party hung up) OR Outbound call concluded -> Proceed to Disposition Wrap-Up
          if (wasConnected || isOutbound) {
            let lead = get().currentLead;
            if (!lead && typeof localStorage !== 'undefined') {
              try {
                const cached = localStorage.getItem('crm_dialer_current_lead');
                if (cached) lead = JSON.parse(cached);
              } catch {}
            }
            if (!lead) {
              const activeNum = telecmiWebRTC.getActiveCallNumber() || 'Customer';
              lead = {
                id: `call-${Date.now()}`,
                first_name: activeNum,
                last_name: '',
                phone: activeNum,
                title: 'Inbound Call',
                status: 'Contacted',
              } as any;
            }

            set({
              callLifecycle: 'disposition',
              currentLead: lead,
              webrtcStatus: 'ended',
              incomingCall: null,
              agentState: 'ACTIVE_CALLING',
            });
            if (typeof localStorage !== 'undefined') {
              localStorage.setItem('crm_dialer_lifecycle', 'disposition');
              localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
            }
          } else {
            set({
              callLifecycle: 'idle',
              incomingCall: null,
              currentLead: null,
              agentState: 'IDLE',
              callDirection: null,
              webrtcStatus: 'registered'
            });
            if (typeof localStorage !== 'undefined') {
              localStorage.removeItem('crm_dialer_lifecycle');
              localStorage.removeItem('crm_dialer_current_lead');
              localStorage.removeItem('crm_dialer_call_direction');
              localStorage.removeItem('crm_dialer_start_time');
            }
          }
        } else if (status === 'idle') {
          if (!get().currentLead || get().callLifecycle === 'idle' || get().callLifecycle === 'ringing' || Boolean(get().incomingCall)) {
            set({ callLifecycle: 'idle', incomingCall: null, webrtcStatus: 'registered' });
          }
        }
      });
    }

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

  cancelInitiatingCall: () => {
    telecmiWebRTC.hangup();
    stopTimer();
    set({
      agentState: 'IDLE',
      callLifecycle: 'idle',
      currentLead: null,
      callDuration: 0,
      callDirection: null,
      stateTimestamp: null,
      isLoading: false,
    });
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('crm_dialer_current_lead');
      localStorage.removeItem('crm_dialer_call_direction');
      localStorage.removeItem('crm_dialer_lifecycle');
      localStorage.removeItem('crm_dialer_start_time');
    }
  },

  hangupWebRTC: () => {
    telecmiWebRTC.hangup();
    stopTimer();
    if (get().currentLead) {
      set({ callLifecycle: 'disposition' });
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('crm_dialer_lifecycle', 'disposition');
      }
    } else {
      set({ callLifecycle: 'idle', agentState: 'IDLE' });
    }
  },

  fetchCurrentState: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await dialerApi.getState();
      
      let lead = get().currentLead;
      let direction = get().callDirection;
      let lifecycle = get().callLifecycle;
      let startTime = null;

      if (typeof localStorage !== 'undefined') {
        const cachedLead = localStorage.getItem('crm_dialer_current_lead');
        if (cachedLead) {
          try { lead = JSON.parse(cachedLead); } catch {}
        }
        direction = (localStorage.getItem('crm_dialer_call_direction') as any) || direction;
        lifecycle = (localStorage.getItem('crm_dialer_lifecycle') as any) || (data.state === 'ACTIVE_CALLING' ? 'connected' : 'idle');
        startTime = localStorage.getItem('crm_dialer_start_time');
      }

      if (data.state === 'ACTIVE_CALLING' && !lead && data.metadata?.lead_id) {
        try {
          lead = await leadApi.getLead(data.metadata.lead_id);
          if (lead && typeof localStorage !== 'undefined') {
            localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
          }
        } catch {}
      }

      let elapsed = 0;
      if (startTime) {
        elapsed = Math.max(0, Math.floor((Date.now() - new Date(startTime).getTime()) / 1000));
      } else if (data.timestamp) {
        elapsed = Math.max(0, Math.floor((Date.now() - new Date(data.timestamp).getTime()) / 1000));
      }

      const isLiveActive = data.state === 'ACTIVE_CALLING' || lifecycle !== 'idle';

      set({
        agentState: isLiveActive ? 'ACTIVE_CALLING' : data.state,
        breakReason: data.state === 'BREAK' ? (data.metadata?.break_reason || null) : null,
        currentLead: isLiveActive ? lead : null,
        callDirection: isLiveActive ? direction : null,
        callLifecycle: isLiveActive ? lifecycle : 'idle',
        stateTimestamp: data.timestamp || null,
        isLoading: false,
        isReconnecting: false,
      });

      if (isLiveActive && lifecycle === 'connected') {
        startTimer(set, elapsed);
      } else if (!isLiveActive) {
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
        callLifecycle: 'initiating',
        callDirection: 'OUTBOUND',
        stateTimestamp: nowStr,
        isLoading: false,
        isKeypadOpen: false,
      });

      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
        localStorage.setItem('crm_dialer_call_direction', 'OUTBOUND');
        localStorage.setItem('crm_dialer_lifecycle', 'initiating');
        localStorage.setItem('crm_dialer_start_time', nowStr);
      }

      startTimer(set, 0);
      if (lead && lead.phone) {
        telecmiWebRTC.setOutboundPending(lead.phone);
        telecmiWebRTC.makeCall(lead.phone).catch((e) => console.warn('[WebRTC] Call trigger error:', e));
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to fetch next lead';
      set({ error: errMsg, isLoading: false, callLifecycle: 'idle' });
      throw err;
    }
  },

  callSpecificLead: async (leadId: string, creds?: CallCreds) => {
    set({ isLoading: true, error: null });
    let lead: any = null;
    try {
      console.log('[Dialer] Placing click-to-call to lead:', leadId);
      lead = await leadApi.getLead(leadId);
    } catch (e) {
      console.warn('[Dialer] Pre-fetch lead info failed:', e);
    }

    const nowStr = new Date().toISOString();
    set({
      currentLead: lead,
      agentState: 'ACTIVE_CALLING',
      callLifecycle: 'initiating',
      callDirection: 'OUTBOUND',
      stateTimestamp: nowStr,
      isLoading: false,
      isKeypadOpen: false,
    });

    if (lead?.phone) {
      telecmiWebRTC.setOutboundPending(lead.phone);
    }

    if (typeof localStorage !== 'undefined' && lead) {
      localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
      localStorage.setItem('crm_dialer_call_direction', 'OUTBOUND');
      localStorage.setItem('crm_dialer_lifecycle', 'initiating');
      localStorage.setItem('crm_dialer_start_time', nowStr);
    }

    startTimer(set, 0);

    try {
      const serverLead = await dialerApi.callLead(leadId, { ...(creds || {}) });
      if (serverLead) {
        set({ currentLead: serverLead });
        if (serverLead.phone) {
          telecmiWebRTC.setOutboundPending(serverLead.phone);
        }
        if (typeof localStorage !== 'undefined') {
          localStorage.setItem('crm_dialer_current_lead', JSON.stringify(serverLead));
        }
      }
    } catch (err: any) {
      console.error('[Dialer] Server callLead failed:', err);
      let errMsg = 'Failed to initiate outbound call';
      if (typeof err.response?.data?.detail === 'string') {
        errMsg = err.response.data.detail;
      } else if (Array.isArray(err.response?.data?.detail)) {
        errMsg = err.response.data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
      } else if (err.message) {
        errMsg = String(err.message);
      }
      set({ error: errMsg, isLoading: false, callLifecycle: 'idle' });
      telecmiWebRTC.clearOutboundPending();
      stopTimer();
      throw err;
    }
  },

  answerInboundCall: async (lead?: any) => {
    set({ isLoading: true, error: null });
    await telecmiWebRTC.answer();
    try {
      await dialerApi.updateState({ state: 'ACTIVE_CALLING' });
    } catch (e) {
      console.warn('[Dialer] updateState failed, proceeding with in-browser active calling session:', e);
    }

    const incoming = get().incomingCall;
    let targetLead = lead || incoming?.lead;

    if (!targetLead || !targetLead.id || String(targetLead.id).length !== 36) {
      if (incoming?.from) {
        try {
          targetLead = await dialerApi.getOrCreateInboundLead({
            phone: incoming.from,
            caller_name: incoming.name,
            call_id: incoming.call_id,
          });
        } catch (fetchErr) {
          console.warn('[Dialer] getOrCreateInboundLead failed, using fallback:', fetchErr);
        }
      }
    }

    if (!targetLead) {
      targetLead = {
        id: incoming?.call_id || `inbound-${Date.now()}`,
        first_name: incoming?.name || 'Inbound',
        last_name: 'Caller',
        phone: incoming?.from || '',
        company: '',
        title: 'Incoming Call',
        status: 'Contacted',
      };
    }

    const nowStr = new Date().toISOString();
    set({
      currentLead: targetLead,
      agentState: 'ACTIVE_CALLING',
      callLifecycle: 'connected',
      callDirection: 'INBOUND',
      stateTimestamp: nowStr,
      incomingCall: null,
      isLoading: false,
      isKeypadOpen: false,
    });

    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_dialer_current_lead', JSON.stringify(targetLead));
      localStorage.setItem('crm_dialer_call_direction', 'INBOUND');
      localStorage.setItem('crm_dialer_lifecycle', 'connected');
      localStorage.setItem('crm_dialer_start_time', nowStr);
    }
    startTimer(set, 0);
  },

  submitDisposition: async (dispositionData: CallDispositionPayload) => {
    let lead = get().currentLead;
    if (!lead && typeof localStorage !== 'undefined') {
      const cachedLead = localStorage.getItem('crm_dialer_current_lead');
      if (cachedLead) {
        try { lead = JSON.parse(cachedLead); } catch {}
      }
    }

    set({ isLoading: true, error: null });
    telecmiWebRTC.hangup();

    try {
      if (lead && lead.id) {
        let targetLeadId = String(lead.id);
        if (targetLeadId.length !== 36 && lead.phone) {
          try {
            const dbLead = await dialerApi.getOrCreateInboundLead({
              phone: lead.phone,
              caller_name: `${lead.first_name || ''} ${lead.last_name || ''}`.trim(),
              call_id: targetLeadId,
            });
            if (dbLead && dbLead.id) {
              targetLeadId = String(dbLead.id);
              lead = dbLead;
            }
          } catch (resErr) {
            console.warn('[Dialer] Could not resolve lead before disposition:', resErr);
          }
        }

        await dialerApi.submitDisposition(targetLeadId, {
          status: dispositionData.status,
          remarks: dispositionData.remarks,
          custom_pipeline_stage_id: dispositionData.custom_pipeline_stage_id,
        });
      } else {
        await dialerApi.updateState({ state: 'IDLE' });
      }

      stopTimer();
      set({
        currentLead: null,
        callDuration: 0,
        agentState: 'IDLE',
        callLifecycle: 'idle',
        callDirection: null,
        stateTimestamp: null,
        isLoading: false,
        isKeypadOpen: false,
        error: null,
      });

      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('crm_dialer_current_lead');
        localStorage.removeItem('crm_dialer_call_direction');
        localStorage.removeItem('crm_dialer_lifecycle');
        localStorage.removeItem('crm_dialer_start_time');
      }
    } catch (err: any) {
      let errMsg = 'Failed to save call disposition';
      if (typeof err.response?.data?.detail === 'string') {
        errMsg = err.response.data.detail;
      } else if (Array.isArray(err.response?.data?.detail)) {
        errMsg = err.response.data.detail.map((d: any) => d.msg || JSON.stringify(d)).join(', ');
      } else if (err.message) {
        errMsg = String(err.message);
      }
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
        callLifecycle: 'idle',
        breakReason: reason,
        stateTimestamp: data.timestamp || null,
        currentLead: null,
        callDuration: 0,
        isLoading: false,
      });
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('crm_dialer_current_lead');
        localStorage.removeItem('crm_dialer_lifecycle');
        localStorage.removeItem('crm_dialer_start_time');
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

  resetStore: () => {
    stopTimer();
    set({
      agentState: 'IDLE',
      callLifecycle: 'idle',
      networkStatus: 'online',
      currentLead: null,
      breakReason: null,
      callDuration: 0,
      stateTimestamp: null,
      isLoading: false,
      error: null,
      callDirection: null,
      isKeypadOpen: false,
    });
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('crm_dialer_current_lead');
      localStorage.removeItem('crm_dialer_call_direction');
      localStorage.removeItem('crm_dialer_lifecycle');
      localStorage.removeItem('crm_dialer_start_time');
    }
  },
}));

// ── Global Network Drop and Unload Event Handlers ──
if (typeof window !== 'undefined') {
  // Prevent accidental tab closure mid-call
  window.addEventListener('beforeunload', (e) => {
    const state = useDialerStore.getState();
    if (
      state.agentState === 'ACTIVE_CALLING' &&
      state.callLifecycle !== 'idle' &&
      state.callLifecycle !== 'disposition'
    ) {
      e.preventDefault();
      e.returnValue = 'You have an active call in progress. Leaving will disconnect the call.';
      return e.returnValue;
    }
  });

  // Network Recovery
  window.addEventListener('online', () => {
    if (networkCountdownIntervalId) {
      clearInterval(networkCountdownIntervalId);
      networkCountdownIntervalId = null;
    }
    useDialerStore.setState({ networkStatus: 'online', reconnectCountdown: 15 });
  });

  // Network Drop
  window.addEventListener('offline', () => {
    const state = useDialerStore.getState();
    if (state.agentState === 'ACTIVE_CALLING' && state.callLifecycle === 'connected') {
      useDialerStore.setState({ networkStatus: 'unstable', reconnectCountdown: 15 });

      if (networkCountdownIntervalId) clearInterval(networkCountdownIntervalId);
      networkCountdownIntervalId = setInterval(() => {
        const cur = useDialerStore.getState().reconnectCountdown;
        if (cur <= 1) {
          clearInterval(networkCountdownIntervalId);
          networkCountdownIntervalId = null;
          // Gracefully disconnect and route to disposition wrap-up
          telecmiWebRTC.hangup();
          stopTimer();
          useDialerStore.setState({
            callLifecycle: 'disposition',
            networkStatus: 'online',
            reconnectCountdown: 15,
            error: 'Call disconnected due to network drop. Please submit disposition.',
          });
        } else {
          useDialerStore.setState({ reconnectCountdown: cur - 1 });
        }
      }, 1000);
    }
  });
}
