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
  const { user } = useAuthStore();
  const { incomingCall, answerInboundCall, rejectInboundCall, initWebRTC } = useDialerStore();
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

  // Unified caller details
  const currentIncoming = incomingCall ? {
    phone: incomingCall.from,
    lead_name: incomingCall.lead?.first_name ? `${incomingCall.lead.first_name} ${incomingCall.lead.last_name || ''}`.trim() : (incomingCall.name || 'Unknown Caller'),
    company_name: incomingCall.lead?.company || incomingCall.lead?.company_name || '',
    stage_name: incomingCall.lead?.stage?.name || incomingCall.lead?.status || 'New Lead',
    source: incomingCall.lead?.source || 'Inbound Call',
    lead_id: incomingCall.lead?.id,
    call_sid: incomingCall.call_id,
  } : (activeSocketCall ? {
    phone: activeSocketCall.phone,
    lead_name: activeSocketCall.lead_name || 'Unknown Caller',
    company_name: activeSocketCall.company_name || '',
    stage_name: activeSocketCall.stage_name || 'New Lead',
    source: activeSocketCall.source || 'Inbound Call',
    lead_id: activeSocketCall.lead_id,
    call_sid: activeSocketCall.call_sid,
  } : null);

  // Ringtone / Chime during inbound ringing
  useEffect(() => {
    if (!currentIncoming) {
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
  }, [currentIncoming?.phone, currentIncoming?.call_sid]);

  // Subscribe to real-time socket events for telephony
  useEffect(() => {
    if (!user) return;

    whatsappRealtime.connect(user.id);
    const unsubscribe = whatsappRealtime.subscribe((data) => {
      try {
        if (data && data.event === 'inbound_call') {
          setActiveSocketCall(data as InboundCallEvent);
        }
      } catch (e) {
        console.error('Failed to handle telephony socket message:', e);
      }
    });

    return () => {
      unsubscribe();
    };
  }, [user]);

  if (!user || !currentIncoming) return null;

  const handleAnswerCall = async () => {
    if (isAnswering) return;
    setIsAnswering(true);
    try {
      let lead = incomingCall?.lead;
      if (!lead && currentIncoming.lead_id) {
        try {
          lead = await leadApi.getLead(currentIncoming.lead_id);
        } catch {}
      }

      await answerInboundCall(lead);
      setActiveSocketCall(null);
      // Automatically minimizes popup into the active floating dialer widget
    } catch (e) {
      console.error('Failed to answer inbound call:', e);
      alert('Failed to answer inbound call. Please try again.');
    } finally {
      setIsAnswering(false);
    }
  };

  const handleDeclineCall = () => {
    rejectInboundCall();
    setActiveSocketCall(null);
  };

  return (
    <div className="fixed top-20 right-6 z-50 max-w-sm w-full bg-slate-900/95 border-2 border-emerald-500/50 rounded-2xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-6 duration-300 overflow-hidden ring-4 ring-emerald-500/10">
      <div className="p-4 flex items-start gap-3.5">
        {/* Pulsing Inbound Ringing Icon */}
        <div className="w-11 h-11 rounded-xl bg-emerald-500/20 border border-emerald-500/40 flex items-center justify-center text-emerald-400 shrink-0 animate-bounce">
          <PhoneIncoming className="w-5 h-5 text-emerald-300 animate-pulse" />
        </div>

        {/* Caller Details with Lead Name, Stage, Company, Source */}
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping" />
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
