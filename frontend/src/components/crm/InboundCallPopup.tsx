import React, { useEffect, useState, useRef } from 'react';
import { whatsappRealtime } from '../../services/whatsappRealtime';
import { useAuthStore } from '../../store/authStore';
import { useDialerStore } from '../../store/dialerStore';
import { leadApi } from '../../services/leadApi';
import { PhoneCall, PhoneIncoming, X, Loader2, PhoneOff, Building2, Tag, Layers } from 'lucide-react';

interface InboundCallEvent {
  event: 'inbound_call';
  call_sid: string;
  lead_id?: string;
  lead_name?: string;
  company_name?: string;
  phone: string;
  stage_name?: string;
  source?: string;
  activity_id?: string;
}

export const InboundCallPopup: React.FC = () => {
  const user = useAuthStore((s) => s.user);
  const incomingCall = useDialerStore((s) => s.incomingCall);
  const answerInboundCall = useDialerStore((s) => s.answerInboundCall);
  const rejectInboundCall = useDialerStore((s) => s.rejectInboundCall);
  const initWebRTC = useDialerStore((s) => s.initWebRTC);
  const callLifecycle = useDialerStore((s) => s.callLifecycle);
  const callDirection = useDialerStore((s) => s.callDirection);
  const currentLead = useDialerStore((s) => s.currentLead);

  const [activeSocketCall, setActiveSocketCall] = useState<InboundCallEvent | null>(null);
  const [isAnswering, setIsAnswering] = useState(false);
  const audioIntervalRef = useRef<any>(null);

  // Initialize WebRTC client so inbound SIP calls can ring anytime
  useEffect(() => {
    if (!user) return;
    initWebRTC().catch((err) => {
      console.warn('[WebRTC] Background softphone init warning:', err);
    });
  }, [user, initWebRTC]);

  const webrtcStatus = useDialerStore((s) => s.webrtcStatus);

  // When call connects, transitions to disposition, or an outbound call is active, clear ringing popup immediately
  useEffect(() => {
    if (callLifecycle === 'connected' || callLifecycle === 'disposition' || callDirection === 'OUTBOUND') {
      setActiveSocketCall(null);
    }
  }, [callLifecycle, callDirection]);

  // When softphone reports call has ended, clear ringing popup
  useEffect(() => {
    if (webrtcStatus === 'ended' && !incomingCall) {
      setActiveSocketCall(null);
    }
  }, [webrtcStatus, incomingCall]);

  // Auto-dismiss ringing popup after telecom ring timeout (40 seconds)
  useEffect(() => {
    if (!activeSocketCall) return;
    const timeout = setTimeout(() => {
      setActiveSocketCall(null);
    }, 40000);
    return () => clearTimeout(timeout);
  }, [activeSocketCall]);

  // Unified caller details - preserves identified lead information across softphone & websocket events
  const currentIncoming = (incomingCall || activeSocketCall) ? {
    phone: incomingCall?.from || activeSocketCall?.phone || '',
    lead_name: (
      incomingCall?.lead?.first_name
        ? `${incomingCall.lead.first_name} ${incomingCall.lead.last_name || ''}`.trim()
        : (activeSocketCall?.lead_name && activeSocketCall.lead_name !== 'Unknown Caller'
            ? activeSocketCall.lead_name
            : (incomingCall?.name && incomingCall.name !== 'Customer' ? incomingCall.name : (activeSocketCall?.lead_name || incomingCall?.name || 'Customer')))
    ),
    company_name: incomingCall?.lead?.company || incomingCall?.lead?.company_name || activeSocketCall?.company_name || '',
    stage_name: incomingCall?.lead?.stage?.name || incomingCall?.lead?.status || activeSocketCall?.stage_name || 'New Lead',
    source: incomingCall?.lead?.source || activeSocketCall?.source || 'Inbound Call',
    lead_id: incomingCall?.lead?.id || activeSocketCall?.lead_id,
    call_sid: incomingCall?.call_id || activeSocketCall?.call_sid || '',
  } : null;

  const normalizedPhone = (currentIncoming?.phone || '').replace(/\D/g, '').slice(-10);

  // Ringtone / Chime during inbound ringing (keyed on normalizedPhone to prevent stuttering/flicker)
  useEffect(() => {
    if (!normalizedPhone) {
      if (audioIntervalRef.current) {
        clearInterval(audioIntervalRef.current);
        audioIntervalRef.current = null;
      }
      return;
    }

    const playChime = () => {
      try {
        const AudioContextClass = window.AudioContext || (window as any).webkitAudioContext;
        if (!AudioContextClass) return;
        const audioCtx = new AudioContextClass();
        const osc1 = audioCtx.createOscillator();
        const osc2 = audioCtx.createOscillator();
        const gain = audioCtx.createGain();

        osc1.type = 'sine';
        osc1.frequency.setValueAtTime(523.25, audioCtx.currentTime); // C5
        osc2.type = 'sine';
        osc2.frequency.setValueAtTime(659.25, audioCtx.currentTime); // E5

        gain.gain.setValueAtTime(0.08, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.001, audioCtx.currentTime + 0.45);

        osc1.connect(gain);
        osc2.connect(gain);
        gain.connect(audioCtx.destination);

        osc1.start();
        osc2.start();
        osc1.stop(audioCtx.currentTime + 0.5);
        osc2.stop(audioCtx.currentTime + 0.5);
      } catch (e) {
        // Audio autoplay policy
      }
    };

    playChime();
    audioIntervalRef.current = setInterval(playChime, 2500);

    return () => {
      if (audioIntervalRef.current) {
        clearInterval(audioIntervalRef.current);
        audioIntervalRef.current = null;
      }
    };
  }, [normalizedPhone]);

  // Subscribe to real-time socket events for telephony
  useEffect(() => {
    if (!user) return;

    whatsappRealtime.connect(user.id);
    const unsubscribe = whatsappRealtime.subscribe((data) => {
      try {
        if (data && data.event === 'inbound_call') {
          // If the agent is currently placing an outbound call, ignore this event to prevent outgoing calls from ringing as incoming
          const dialer = useDialerStore.getState();
          const activeOutboundDigits = (dialer.currentLead?.phone || '').replace(/\D/g, '').slice(-10);
          const incomingDigits = (data.phone || '').replace(/\D/g, '').slice(-10);

          if (
            dialer.callDirection === 'OUTBOUND' &&
            dialer.callLifecycle !== 'idle'
          ) {
            console.log('[InboundCallPopup] Suppressed inbound popup: active outbound call in progress to', activeOutboundDigits);
            return;
          }

          if (activeOutboundDigits && incomingDigits && activeOutboundDigits === incomingDigits) {
            console.log('[InboundCallPopup] Suppressed inbound popup: matches current lead phone', incomingDigits);
            return;
          }

          setActiveSocketCall((prev) => {
            // Deduplicate: if already showing for this call, do not replace object reference
            if (prev && (prev.call_sid === data.call_sid || (prev.phone && data.phone && prev.phone === data.phone))) {
              return prev;
            }
            return data as InboundCallEvent;
          });
        } else if (data && (data.event === 'inbound_call_ended' || data.event === 'inbound_call_cancelled')) {
          setActiveSocketCall(null);
          useDialerStore.getState().setIncomingCall(null);
        }
      } catch (e) {
        console.error('Failed to handle telephony socket message:', e);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [user?.id]);

  if (!user || !currentIncoming) return null;

  // Suppress inbound popup if the agent is already engaged in an outbound call
  if (callDirection === 'OUTBOUND') {
    return null;
  }
  const activeOutboundDigits = (currentLead?.phone || '').replace(/\D/g, '').slice(-10);
  if (activeOutboundDigits && normalizedPhone && activeOutboundDigits === normalizedPhone) {
    return null;
  }

  const handleAnswerCall = async () => {
    if (isAnswering) return;
    setIsAnswering(true);
    try {
      // 1. Unlock browser audio element immediately within user click gesture
      const audio = document.getElementById('telecmi_audio_tag') as HTMLAudioElement;
      if (audio) {
        audio.play().catch(() => {});
      }

      let lead = incomingCall?.lead;
      if (!lead && currentIncoming.lead_id) {
        try {
          lead = await leadApi.getLead(currentIncoming.lead_id);
        } catch {}
      }

      setActiveSocketCall(null);
      await answerInboundCall(lead);
    } catch (e) {
      console.error('Failed to answer inbound call:', e);
      alert('Failed to answer inbound call. Please try again.');
    } finally {
      setIsAnswering(false);
    }
  };

  const handleDeclineCall = () => {
    setActiveSocketCall(null);
    rejectInboundCall();
  };

  return (
    <div
      key={normalizedPhone || 'inbound-call-card'}
      className="fixed top-20 right-6 z-50 max-w-sm w-full bg-slate-900/95 border-2 border-emerald-500/50 rounded-2xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-4 duration-200 overflow-hidden ring-4 ring-emerald-500/10"
    >
      <div className="p-4 flex items-start gap-3.5">
        {/* Steady Elegant Ringing Icon */}
        <div className="w-11 h-11 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0 shadow-md">
          <PhoneIncoming className="w-5 h-5 text-emerald-300 animate-pulse" />
        </div>

        {/* Caller Details with Lead Name, Stage, Company, Source */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400" />
            <p className="text-[10px] font-bold text-emerald-400 uppercase tracking-widest">
              Incoming Call · Live
            </p>
          </div>
          <h4 className="text-sm font-bold text-slate-100 mt-1 truncate">
            {currentIncoming.lead_name}
          </h4>
          
          <p className="text-xs font-mono font-medium text-slate-300 mt-0.5">
            {currentIncoming.phone}
          </p>

          <div className="flex flex-wrap items-center gap-1.5 mt-2">
            <span className="inline-flex items-center gap-1 text-[10px] font-semibold text-indigo-300 bg-indigo-500/10 px-2 py-0.5 rounded-full border border-indigo-500/30">
              <Layers className="w-3 h-3 text-indigo-400" />
              {currentIncoming.stage_name}
            </span>

            {currentIncoming.company_name ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-slate-300 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700 truncate max-w-[130px]">
                <Building2 className="w-3 h-3 text-slate-400 shrink-0" />
                {currentIncoming.company_name}
              </span>
            ) : null}

            {currentIncoming.source ? (
              <span className="inline-flex items-center gap-1 text-[10px] font-medium text-slate-400 bg-slate-800/80 px-1.5 py-0.5 rounded border border-slate-700/60">
                <Tag className="w-2.5 h-2.5 text-slate-400" />
                {currentIncoming.source}
              </span>
            ) : null}
          </div>
        </div>

        {/* Dismiss Button */}
        <button
          onClick={handleDeclineCall}
          title="Decline"
          className="p-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded-lg transition-all cursor-pointer shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Action Buttons: Prominent Green Accept & Red Decline */}
      <div className="px-4 py-3 bg-slate-950/80 border-t border-slate-800/80 flex items-center justify-between gap-3">
        <button
          onClick={handleDeclineCall}
          className="flex-1 flex items-center justify-center gap-1.5 px-3 py-2 border border-red-500/30 hover:border-red-500/50 bg-red-500/10 hover:bg-red-500/20 text-red-300 rounded-xl text-xs font-semibold transition-all cursor-pointer"
        >
          <PhoneOff className="w-3.5 h-3.5" />
          Decline
        </button>
        <button
          onClick={handleAnswerCall}
          disabled={isAnswering}
          className="flex-1 flex items-center justify-center gap-1.5 px-4 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:bg-emerald-800 text-white rounded-xl text-xs font-semibold shadow-lg shadow-emerald-900/30 transition-all cursor-pointer"
        >
          {isAnswering ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Connecting...
            </>
          ) : (
            <>
              <PhoneCall className="w-3.5 h-3.5" />
              Accept Call
            </>
          )}
        </button>
      </div>
    </div>
  );
};
