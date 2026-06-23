import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';
import { useDialerStore } from '../../store/dialerStore';
import { leadApi } from '../../services/leadApi';
import { PhoneCall, X, Loader2 } from 'lucide-react';

interface InboundCallEvent {
  event: 'inbound_call';
  call_sid: string;
  lead_id: string;
  lead_name: string;
  company_name?: string;
  phone: string;
  activity_id: string;
}

export const InboundCallPopup: React.FC = () => {
  const { user } = useAuthStore();
  const navigate = useNavigate();
  const { answerInboundCall } = useDialerStore();
  const [activeCall, setActiveCall] = useState<InboundCallEvent | null>(null);
  const [isAnswering, setIsAnswering] = useState(false);

  useEffect(() => {
    if (!user) return;

    // Connect to backend WebSocket endpoint for telephony alerts
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsHost = window.location.host; // Usually localhost (proxied via Nginx)
    const wsUrl = `${wsProtocol}//${wsHost}/api/v1/telephony/ws/${user.id}`;

    let socket: WebSocket;
    let reconnectTimeout: NodeJS.Timeout;

    const connectWS = () => {
      socket = new WebSocket(wsUrl);

      socket.onopen = () => {
        console.log("Connected to CRM telephony alert socket.");
      };

      socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          if (data && data.event === 'inbound_call') {
            setActiveCall(data as InboundCallEvent);
            
            // Optional: Play a calling ring/ping audio notification
            try {
              const audioCtx = new (window.AudioContext || (window as any).webkitAudioContext)();
              const osc = audioCtx.createOscillator();
              const gain = audioCtx.createGain();
              osc.connect(gain);
              gain.connect(audioCtx.destination);
              osc.type = 'sine';
              osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5 note
              gain.gain.setValueAtTime(0.1, audioCtx.currentTime);
              osc.start();
              osc.stop(audioCtx.currentTime + 0.35);
            } catch (e) {
              console.warn("Audio Context block:", e);
            }
          }
        } catch (e) {
          console.error("Failed to parse telephony WebSocket message:", e);
        }
      };

      socket.onclose = () => {
        console.log("Telephony socket closed. Attempting reconnect in 5 seconds...");
        reconnectTimeout = setTimeout(() => {
          connectWS();
        }, 5000);
      };

      socket.onerror = (err) => {
        console.error("Telephony alert socket error:", err);
      };
    };

    connectWS();

    return () => {
      if (socket) socket.close();
      if (reconnectTimeout) clearTimeout(reconnectTimeout);
    };
  }, [user]);

  if (!activeCall) return null;


  const handleAnswerCall = async () => {
    if (isAnswering) return;
    setIsAnswering(true);
    try {
      const lead = await leadApi.getLead(activeCall.lead_id);
      if (lead) {
        await answerInboundCall(lead);
        navigate(`/leads?leadId=${activeCall.lead_id}`);
      }
      setActiveCall(null);
    } catch (e) {
      console.error("Failed to answer inbound call:", e);
      alert("Failed to answer inbound call. Please try again.");
    } finally {
      setIsAnswering(false);
    }
  };

  return (
    <div className="fixed top-20 right-6 z-50 max-w-sm w-full bg-slate-900/90 border border-brand-500/30 rounded-2xl shadow-2xl backdrop-blur-md animate-in fade-in slide-in-from-top-6 duration-300 overflow-hidden">
      <div className="p-4 flex items-start gap-4">
        {/* Call Icon Ringing */}
        <div className="w-10 h-10 rounded-xl bg-blue-500/10 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0 animate-pulse">
          <PhoneCall className="w-5 h-5" />
        </div>

        {/* Text Details */}
        <div className="flex-1 min-w-0">
          <p className="text-[10px] font-bold text-blue-400 uppercase tracking-widest">Incoming Cloud Call</p>
          <h4 className="text-sm font-bold text-slate-100 mt-0.5 truncate">
            {activeCall.lead_name}
          </h4>
          {activeCall.company_name && (
            <p className="text-xs text-slate-400 truncate">{activeCall.company_name}</p>
          )}
          <p className="text-xs text-slate-500 mt-1">{activeCall.phone}</p>
        </div>

        {/* Dismiss Button */}
        <button
          onClick={() => setActiveCall(null)}
          className="p-1 border border-slate-800 hover:border-slate-700 hover:bg-slate-950/40 text-slate-500 hover:text-slate-200 rounded-lg transition-all cursor-pointer shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Action Footer */}
      <div className="px-4 py-2.5 bg-slate-950/60 border-t border-slate-800/80 flex justify-end gap-2">
        <button
          onClick={() => setActiveCall(null)}
          className="px-3 py-1.5 border border-slate-800 hover:border-slate-700 rounded-lg text-[11px] font-semibold text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
        >
          Ignore
        </button>
        <button
          onClick={handleAnswerCall}
          disabled={isAnswering}
          className="px-4 py-1.5 bg-blue-600 hover:bg-blue-500 disabled:bg-blue-800 text-white rounded-lg text-[11px] font-semibold flex items-center gap-1.5 shadow transition-all cursor-pointer"
        >
          {isAnswering ? (
            <>
              <Loader2 className="w-3.5 h-3.5 animate-spin" />
              Answering...
            </>
          ) : (
            <>
              <PhoneCall className="w-3.5 h-3.5" />
              Answer Call
            </>
          )}
        </button>
      </div>
    </div>
  );
};
