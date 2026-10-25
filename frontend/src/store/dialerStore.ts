import { create } from 'zustand';
import { dialerApi, CallCreds } from '../services/dialerApi';
import { LeadResponse, leadApi } from '../services/leadApi';
import { telecmiWebRTC, WebRTCPhoneStatus } from '../services/telecmiWebRTC';
import { whatsappRealtime } from '../services/whatsappRealtime';

export type AgentState = 'IDLE' | 'ACTIVE_CALLING' | 'BREAK';
export type CallLifecycle = 'idle' | 'initiating' | 'ringing' | 'connected' | 'disposition';
export type NetworkStatus = 'online' | 'unstable';

export interface DispositionSession {
  call_sid: string;
  lead: LeadResponse | null;
  duration: number;
  direction: 'INBOUND' | 'OUTBOUND';
  technical_status: 'connected' | 'ringing_no_answer' | 'busy' | 'failed';
  startTime: string;
  endTime: string;
  submitted: boolean;
}

export interface CallDispositionPayload {
  status: string;
  disposition_category?: string;
  remarks: string;
  call_sid?: string;
  call_duration?: number;
  call_direction?: string;
  technical_status?: string;
  custom_pipeline_stage_id?: string;
  follow_up_date?: string;
  follow_up_time?: string;
  follow_up_priority?: 'Low' | 'Medium' | 'High' | 'Urgent';
  dispatch_omnichannel_followup?: boolean;
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
  isDispositionModalOpen: boolean;
  dispositionSession: DispositionSession | null;
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
  openDispositionModal: () => void;
  closeDispositionModal: () => void;
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
  requestMicrophonePermission: () => Promise<boolean>;
  clearError: () => void;
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

const getInitialLead = (): LeadResponse | null => {
  if (typeof window !== 'undefined' && window.localStorage) {
    try {
      const cached = localStorage.getItem('crm_dialer_current_lead');
      return cached ? JSON.parse(cached) : null;
    } catch {
      return null;
    }
  }
  return null;
};

const getInitialLifecycle = (): CallLifecycle => {
  return 'idle';
};

const getInitialAgentState = (): AgentState => {
  return 'IDLE';
};

const getInitialCallDirection = (): 'INBOUND' | 'OUTBOUND' | null => {
  if (typeof window !== 'undefined' && window.localStorage) {
    const cached = localStorage.getItem('crm_dialer_call_direction');
    if (cached === 'INBOUND' || cached === 'OUTBOUND') {
      return cached;
    }
  }
  return null;
};

const getInitialStartTime = (): string | null => {
  if (typeof window !== 'undefined' && window.localStorage) {
    return localStorage.getItem('crm_dialer_start_time');
  }
  return null;
};

const initialLead = getInitialLead();
const initialLifecycle = getInitialLifecycle();
const initialAgentState = getInitialAgentState();
const initialCallDirection = getInitialCallDirection();
const initialStartTime = getInitialStartTime();
const initialDuration = (initialLifecycle === 'connected' && initialStartTime)
  ? Math.max(0, Math.floor((Date.now() - new Date(initialStartTime).getTime()) / 1000))
  : 0;

export const useDialerStore = create<DialerState>((set, get) => ({
  agentState: initialAgentState,
  callLifecycle: initialLifecycle,
  networkStatus: 'online',
  reconnectCountdown: 15,
  currentLead: initialLead,
  breakReason: null,
  callDuration: initialDuration,
  stateTimestamp: initialStartTime,
  isLoading: false,
  error: null,
  callDirection: initialCallDirection,
  webrtcStatus: 'idle',
  isMuted: false,
  isKeypadOpen: false,
  isReconnecting: false,
  incomingCall: null,
  isDispositionModalOpen: false,
  dispositionSession: null,

  setIncomingCall: (call) => set({ incomingCall: call }),

  rejectInboundCall: () => {
    stopTimer();
    telecmiWebRTC.reject();
    set({ incomingCall: null, callLifecycle: 'idle', callDirection: null, currentLead: null });
  },

  toggleKeypad: (force?: boolean) => {
    set((state) => ({ isKeypadOpen: typeof force === 'boolean' ? force : !state.isKeypadOpen }));
  },

  sendDTMF: (digit: string | number) => {
    telecmiWebRTC.sendDTMF(digit);
  },

  openDispositionModal: () => {
    set({ isDispositionModalOpen: true });
  },

  closeDispositionModal: () => {
    stopTimer();
    set({
      isDispositionModalOpen: false,
      callLifecycle: 'idle',
      agentState: 'IDLE',
      currentLead: null,
      callDirection: null,
      callDuration: 0,
      dispositionSession: null,
      error: null,
    });
    if (typeof localStorage !== 'undefined') {
      localStorage.removeItem('crm_dialer_lifecycle');
      localStorage.removeItem('crm_dialer_current_lead');
      localStorage.removeItem('crm_dialer_call_direction');
      localStorage.removeItem('crm_dialer_start_time');
    }
  },

  initWebRTC: async () => {
    if (!isWebRTCSubscribed) {
      isWebRTCSubscribed = true;

      whatsappRealtime.subscribe((data) => {
        if (!data) return;
        const eventType = data.type || data.event;
        if (eventType === 'call_ended' || eventType === 'inbound_call_ended') {
          console.log('[Dialer] Remote call_ended event received via WebSocket:', data);
          stopTimer();
          telecmiWebRTC.hangup();
          const currentCallLifecycle = get().callLifecycle;
          const finalDuration = typeof data.duration === 'number' && data.duration > 0
            ? Math.max(get().callDuration || 0, data.duration)
            : (get().callDuration || 0);

          let currentLeadObj = get().currentLead;
          if (!currentLeadObj && typeof localStorage !== 'undefined') {
            try {
              const cached = localStorage.getItem('crm_dialer_current_lead');
              if (cached) currentLeadObj = JSON.parse(cached);
            } catch {}
          }

          if (currentLeadObj) {
            const dir = get().callDirection || 'OUTBOUND';
            const callSessionId = data.call_id || data.call_sid || `call-ws-${Date.now()}`;
            const techStatus = currentCallLifecycle === 'connected' ? 'connected' : 'ringing_no_answer';

            set({
              callLifecycle: 'disposition',
              isDispositionModalOpen: true,
              callDuration: finalDuration,
              webrtcStatus: 'ended',
              incomingCall: null,
              agentState: 'ACTIVE_CALLING',
              currentLead: currentLeadObj,
              dispositionSession: {
                call_sid: callSessionId,
                lead: currentLeadObj,
                duration: finalDuration,
                direction: dir,
                technical_status: techStatus,
                startTime: get().stateTimestamp || new Date().toISOString(),
                endTime: new Date().toISOString(),
                submitted: false,
              }
            });
            if (typeof localStorage !== 'undefined') {
              localStorage.setItem('crm_dialer_lifecycle', 'disposition');
              localStorage.setItem('crm_dialer_current_lead', JSON.stringify(currentLeadObj));
            }
          } else {
            set({
              callLifecycle: 'idle',
              incomingCall: null,
              agentState: 'IDLE',
              callDirection: null,
              callDuration: 0,
              webrtcStatus: 'registered',
            });
            if (typeof localStorage !== 'undefined') {
              localStorage.removeItem('crm_dialer_lifecycle');
              localStorage.removeItem('crm_dialer_current_lead');
              localStorage.removeItem('crm_dialer_call_direction');
              localStorage.removeItem('crm_dialer_start_time');
            }
          }
        }
      });

      telecmiWebRTC.subscribe((status, _details) => {
        set({ webrtcStatus: status, isMuted: telecmiWebRTC.getIsMuted() });

        if (status === 'incoming') {
          // If the agent is currently placing an outbound call, this incoming SIP leg is the telephony provider bridge connecting back to the agent softphone!
          const activeDirection = get().callDirection;
          const activeLifecycle = get().callLifecycle;
          const isOutboundCallActive = activeDirection === 'OUTBOUND' && (activeLifecycle === 'initiating' || activeLifecycle === 'ringing' || activeLifecycle === 'connected');
          const isBridgeLegPending = telecmiWebRTC.getIsOutboundPending();

          if (isOutboundCallActive || isBridgeLegPending) {
            console.log('[WebRTC] Incoming status belongs to active outbound bridge leg. Auto-connecting rather than treating as incoming call.');
            telecmiWebRTC.answer().catch(() => {});
            return;
          }

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
          const finalDuration = get().callDuration || 0;
          const currentLeadObj = get().currentLead;
          const dir = get().callDirection || 'OUTBOUND';
          const callId = _details?.call_id || _details?.callId || telecmiWebRTC.getActiveCallNumber() || undefined;

          // Immediately persist call log metrics in database upon disconnected event
          if (currentLeadObj?.id && String(currentLeadObj.id).length === 36) {
            dialerApi.recordCallEnded({
              lead_id: currentLeadObj.id,
              call_sid: typeof callId === 'string' ? callId : undefined,
              duration: finalDuration,
              call_direction: dir,
              status: finalDuration > 0 ? 'Completed' : 'Missed',
            }).catch((err) => {
              console.warn('[Dialer] Record call ended catch:', err);
            });
          }

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
              callDuration: 0,
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

          // Outbound call attempt (connected, unanswered RNR, busy) or answered inbound call -> Open Mandatory Disposition!
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
              title: 'Call Session',
              status: 'Contacted',
            } as any;
          }

          const callSessionId = typeof callId === 'string' && callId.length > 5 ? callId : `call-${Date.now()}`;
          const techStatus = wasConnected ? 'connected' : (wasRinging ? 'ringing_no_answer' : 'failed');

          set({
            callLifecycle: 'disposition',
            isDispositionModalOpen: true,
            currentLead: lead,
            webrtcStatus: 'ended',
            incomingCall: null,
            agentState: 'ACTIVE_CALLING',
            dispositionSession: {
              call_sid: callSessionId,
              lead,
              duration: finalDuration,
              direction: dir,
              technical_status: techStatus,
              startTime: get().stateTimestamp || new Date().toISOString(),
              endTime: new Date().toISOString(),
              submitted: false,
            }
          });
          if (typeof localStorage !== 'undefined') {
            localStorage.setItem('crm_dialer_lifecycle', 'disposition');
            localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
          }
        } else if (status === 'error') {
          stopTimer();
          console.warn('[Dialer] WebRTC error encountered:', _details);
          const isMicError = _details?.type === 'mediaFailed' || String(_details?.message || '').toLowerCase().includes('micro') || String(_details?.message || '').toLowerCase().includes('permission');
          const errMsg = isMicError
            ? 'Microphone access is required to place calls. Please click the permissions icon in your browser address bar and allow Microphone.'
            : (_details?.message || 'Call failed due to WebRTC error.');

          let currentLeadObj = get().currentLead;
          const wasActiveCall = get().callLifecycle === 'connected' || get().callLifecycle === 'ringing';

          if (wasActiveCall && currentLeadObj) {
            const dir = get().callDirection || 'OUTBOUND';
            const callSessionId = `call-err-${Date.now()}`;
            set({
              callLifecycle: 'disposition',
              isDispositionModalOpen: true,
              currentLead: currentLeadObj,
              webrtcStatus: 'ended',
              incomingCall: null,
              agentState: 'ACTIVE_CALLING',
              error: errMsg,
              dispositionSession: {
                call_sid: callSessionId,
                lead: currentLeadObj,
                duration: 0,
                direction: dir,
                technical_status: 'failed',
                startTime: get().stateTimestamp || new Date().toISOString(),
                endTime: new Date().toISOString(),
                submitted: false,
              }
            });
            if (typeof localStorage !== 'undefined') {
              localStorage.setItem('crm_dialer_lifecycle', 'disposition');
              localStorage.setItem('crm_dialer_current_lead', JSON.stringify(currentLeadObj));
            }
          } else {
            set({
              error: errMsg,
              callLifecycle: 'idle',
              isDispositionModalOpen: false,
              incomingCall: null,
              agentState: 'IDLE',
              callDirection: null,
              callDuration: 0,
              webrtcStatus: 'registered',
            });
            if (typeof localStorage !== 'undefined') {
              localStorage.removeItem('crm_dialer_lifecycle');
              localStorage.removeItem('crm_dialer_current_lead');
              localStorage.removeItem('crm_dialer_call_direction');
              localStorage.removeItem('crm_dialer_start_time');
            }
          }
        } else if (status === 'idle') {
          const isBusy = get().callLifecycle === 'ringing' || Boolean(get().incomingCall) || get().callLifecycle === 'connected' || get().callLifecycle === 'disposition' || get().isDispositionModalOpen;
          if (!isBusy && (!get().currentLead || get().callLifecycle === 'idle')) {
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
    telecmiWebRTC.clearOutboundPending();
    stopTimer();
    const currentLeadObj = get().currentLead;
    if (currentLeadObj) {
      const callSessionId = `call-cancel-${Date.now()}`;
      set({
        callLifecycle: 'disposition',
        isDispositionModalOpen: true,
        webrtcStatus: 'ended',
        agentState: 'ACTIVE_CALLING',
        dispositionSession: {
          call_sid: callSessionId,
          lead: currentLeadObj,
          duration: 0,
          direction: 'OUTBOUND',
          technical_status: 'ringing_no_answer',
          startTime: get().stateTimestamp || new Date().toISOString(),
          endTime: new Date().toISOString(),
          submitted: false,
        }
      });
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('crm_dialer_lifecycle', 'disposition');
        localStorage.setItem('crm_dialer_current_lead', JSON.stringify(currentLeadObj));
      }
    } else {
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
    }
  },

  hangupWebRTC: () => {
    telecmiWebRTC.hangup();
    stopTimer();
    const wasConnected = get().callLifecycle === 'connected';
    const finalDuration = get().callDuration || 0;
    const currentLeadObj = get().currentLead;
    const dir = get().callDirection || 'OUTBOUND';
    const callSessionId = `call-${Date.now()}`;

    if (currentLeadObj) {
      set({
        callLifecycle: 'disposition',
        isDispositionModalOpen: true,
        webrtcStatus: 'ended',
        agentState: 'ACTIVE_CALLING',
        dispositionSession: {
          call_sid: callSessionId,
          lead: currentLeadObj,
          duration: finalDuration,
          direction: dir,
          technical_status: wasConnected ? 'connected' : 'ringing_no_answer',
          startTime: get().stateTimestamp || new Date().toISOString(),
          endTime: new Date().toISOString(),
          submitted: false,
        }
      });
      if (typeof localStorage !== 'undefined') {
        localStorage.setItem('crm_dialer_lifecycle', 'disposition');
        localStorage.setItem('crm_dialer_current_lead', JSON.stringify(currentLeadObj));
      }
    } else {
      set({
        callLifecycle: 'idle',
        agentState: 'IDLE',
        callDirection: null,
        callDuration: 0,
        incomingCall: null,
      });
      if (typeof localStorage !== 'undefined') {
        localStorage.removeItem('crm_dialer_lifecycle');
        localStorage.removeItem('crm_dialer_current_lead');
        localStorage.removeItem('crm_dialer_call_direction');
        localStorage.removeItem('crm_dialer_start_time');
      }
    }
  },

  fetchCurrentState: async () => {
    set({ isLoading: true, error: null });
    try {
      let data: any;
      try {
        data = await dialerApi.getCurrentState();
      } catch {
        data = await dialerApi.getState();
      }
      
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
        const cachedLifecycle = localStorage.getItem('crm_dialer_lifecycle');
        if (cachedLifecycle === 'disposition') {
          lifecycle = 'disposition';
        } else if (cachedLifecycle === 'connected' && telecmiWebRTC.getActiveCallNumber()) {
          lifecycle = 'connected';
        } else if (cachedLifecycle === 'initiating' || cachedLifecycle === 'ringing') {
          lifecycle = cachedLifecycle as any;
        } else if (data.state === 'ACTIVE_CALLING' && lead) {
          lifecycle = 'disposition';
        } else {
          lifecycle = 'idle';
        }
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

      if (lifecycle === 'connected' && telecmiWebRTC.getActiveCallNumber()) {
        startTimer(set, elapsed);
      } else {
        stopTimer();
        if (lifecycle !== 'disposition') {
          set({ callDuration: 0 });
        }
      }

      // If call is in disposition, open the disposition modal
      if (lifecycle === 'disposition' && lead) {
        set({
          isDispositionModalOpen: true,
          dispositionSession: get().dispositionSession || {
            call_sid: `call-resume-${Date.now()}`,
            lead,
            duration: elapsed,
            direction: direction || 'OUTBOUND',
            technical_status: 'connected',
            startTime: startTime || new Date().toISOString(),
            endTime: new Date().toISOString(),
            submitted: false,
          }
        });
      }
    } catch (err: any) {
      const errMsg = err.response?.data?.detail || err.message || 'Failed to fetch agent state';
      set({ error: errMsg, isLoading: false });
      throw err;
    }
  },

  startCalling: async (collectivePooling = false, creds?: CallCreds) => {
    if (get().callLifecycle === 'disposition' || get().isDispositionModalOpen) {
      const errMsg = 'Please complete and save the pending call disposition before dialing the next lead.';
      set({ error: errMsg, isDispositionModalOpen: true });
      throw new Error(errMsg);
    }

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
        callDuration: 0,
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
    if (get().callLifecycle === 'disposition' || get().isDispositionModalOpen) {
      const pendingLead = get().currentLead || get().dispositionSession?.lead;
      const pendingName = pendingLead ? `${pendingLead.first_name || ''} ${pendingLead.last_name || ''}`.trim() : 'previous lead';
      const errMsg = `Please complete and save the post-call disposition for ${pendingName} before placing a new call.`;
      set({ error: errMsg, isDispositionModalOpen: true });
      throw new Error(errMsg);
    }

    set({ isLoading: true, error: null });

    // Request microphone permission on user gesture (click event)
    try {
      if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        stream.getTracks().forEach((t) => t.stop());
      }
    } catch (micErr: any) {
      console.warn('[Dialer] Microphone check on user click:', micErr);
      set({
        error: 'Microphone access is required to place calls. Click "Enable Microphone" below or allow access in your browser settings.',
        isLoading: false,
        callLifecycle: 'idle',
      });
      return;
    }

    let lead: any = null;
    try {
      console.log('[Dialer] Placing click-to-call to lead:', leadId);
      lead = await leadApi.getLead(leadId);
    } catch (e) {
      console.warn('[Dialer] Pre-fetch lead info failed:', e);
    }

    const nowStr = new Date().toISOString();
    stopTimer();
    set({
      currentLead: lead,
      agentState: 'ACTIVE_CALLING',
      callLifecycle: 'initiating',
      callDirection: 'OUTBOUND',
      callDuration: 0,
      stateTimestamp: nowStr,
      isLoading: false,
      isKeypadOpen: false,
    });

    const dialPhone = lead?.phone;
    if (dialPhone) {
      telecmiWebRTC.makeCall(dialPhone).catch((e) => console.warn('[WebRTC] Direct call trigger error:', e));
    }

    if (typeof localStorage !== 'undefined' && lead) {
      localStorage.setItem('crm_dialer_current_lead', JSON.stringify(lead));
      localStorage.setItem('crm_dialer_call_direction', 'OUTBOUND');
      localStorage.setItem('crm_dialer_lifecycle', 'initiating');
      localStorage.setItem('crm_dialer_start_time', nowStr);
    }

    try {
      const serverLead = await dialerApi.callLead(leadId, { ...(creds || {}) });
      if (serverLead) {
        set({ currentLead: serverLead });
        if (serverLead.phone && !dialPhone) {
          telecmiWebRTC.makeCall(serverLead.phone).catch((e) => console.warn('[WebRTC] Direct call trigger error:', e));
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
      set({ error: errMsg, isLoading: false, callLifecycle: 'idle', agentState: 'IDLE' });
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
    let lead = get().currentLead || get().dispositionSession?.lead;
    if (!lead && typeof localStorage !== 'undefined') {
      const cachedLead = localStorage.getItem('crm_dialer_current_lead');
      if (cachedLead) {
        try { lead = JSON.parse(cachedLead); } catch {}
      }
    }

    set({ isLoading: true, error: null });
    stopTimer();
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

        const sess = get().dispositionSession;
        await dialerApi.submitDisposition(targetLeadId, {
          status: dispositionData.status,
          remarks: dispositionData.remarks,
          call_sid: dispositionData.call_sid || sess?.call_sid,
          call_duration: dispositionData.call_duration ?? sess?.duration ?? get().callDuration ?? 0,
          call_direction: dispositionData.call_direction || sess?.direction || get().callDirection || 'OUTBOUND',
          technical_status: dispositionData.technical_status || sess?.technical_status,
          follow_up_date: dispositionData.follow_up_date,
          follow_up_time: dispositionData.follow_up_time,
          follow_up_priority: dispositionData.follow_up_priority,
          custom_pipeline_stage_id: dispositionData.custom_pipeline_stage_id,
          dispatch_omnichannel_followup: dispositionData.dispatch_omnichannel_followup,
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
        isDispositionModalOpen: false,
        dispositionSession: null,
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

  requestMicrophonePermission: async (): Promise<boolean> => {
    try {
      if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
        stream.getTracks().forEach((track) => track.stop());
        set({ error: null });
        return true;
      }
      set({ error: 'Audio recording devices are not supported by this browser.' });
      return false;
    } catch (err: any) {
      console.warn('[Dialer] Microphone request rejected:', err);
      if (err.name === 'NotAllowedError' || err.name === 'PermissionDeniedError') {
        set({
          error: 'Microphone access is blocked in your browser settings. Please click the lock icon in your address bar, switch Microphone to "Allow", and reload.',
        });
      } else {
        set({ error: `Microphone access error: ${err.message || 'Permission denied'}` });
      }
      return false;
    }
  },

  clearError: () => {
    set({ error: null });
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
      isDispositionModalOpen: false,
      dispositionSession: null,
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
