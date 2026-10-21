import React, { useEffect, useState, useCallback } from 'react';
import { PhoneCall, Clock, AlertTriangle, ArrowRight, X } from 'lucide-react';
import { api } from '../../services/api';
import { useDialerStore } from '../../store/dialerStore';

interface CallbackLead {
  id: string;
  first_name?: string;
  last_name?: string;
  phone?: string;
  status?: string;
  scheduled_callback_at: string;
}

export const CallbackTakeoverModal: React.FC = () => {
  const [matureCallbacks, setMatureCallbacks] = useState<CallbackLead[]>([]);
  const [isDismissed, setIsDismissed] = useState(false);
  const [isDialing, setIsDialing] = useState(false);
  const { callSpecificLead, currentLead, agentState, incomingCall } = useDialerStore();

  const checkMatureCallbacks = useCallback(async () => {
    try {
      const res = await api.get<CallbackLead[]>('/leads/callbacks/mature');
      if (res.data && res.data.length > 0) {
        setMatureCallbacks(res.data);
        setIsDismissed(false);
      } else {
        setMatureCallbacks([]);
      }
    } catch (e) {
      // Ignore background poll errors
    }
  }, []);

  useEffect(() => {
    // Check on mount and every 20 seconds
    checkMatureCallbacks();
    const interval = setInterval(checkMatureCallbacks, 20000);
    return () => clearInterval(interval);
  }, [checkMatureCallbacks]);

  // If already on a call, receiving an incoming call, no callbacks mature, or dismissed, don't show
  if (matureCallbacks.length === 0 || isDismissed || currentLead || incomingCall || agentState === 'ACTIVE_CALLING') {
    return null;
  }

  const primaryCallback = matureCallbacks[0];
  const callbackDate = new Date(primaryCallback.scheduled_callback_at);

  const handleDialNow = async () => {
    setIsDialing(true);
    try {
      await callSpecificLead(primaryCallback.id);
      setIsDismissed(true);
    } catch (e) {
      console.error('Failed to trigger callback dial:', e);
    } finally {
      setIsDialing(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-[#111a2e] border-2 border-amber-500/80 rounded-2xl shadow-2xl shadow-amber-500/20 overflow-hidden transform animate-in zoom-in-95 duration-200">
        {/* Urgent Header */}
        <div className="bg-gradient-to-r from-amber-950/80 via-amber-900/60 to-red-950/80 border-b border-amber-500/30 px-6 py-4 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-amber-500/20 border border-amber-500/40 flex items-center justify-center text-amber-400 animate-bounce">
              <AlertTriangle className="w-5 h-5" />
            </div>
            <div>
              <span className="text-[10px] font-black tracking-widest uppercase text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/30">
                Floor Screen Takeover · Priority #1
              </span>
              <h2 className="text-base font-bold text-white mt-1">Mature Callback Triggered</h2>
            </div>
          </div>
          <button
            onClick={() => setIsDismissed(true)}
            title="Acknowledge & Snooze 2m"
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-white/5 transition"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Content */}
        <div className="p-6 space-y-4">
          <p className="text-xs text-slate-300 leading-relaxed">
            The scheduled callback for <strong className="text-white font-semibold">{primaryCallback.first_name || ''} {primaryCallback.last_name || 'Lead'}</strong> is now mature and has taken priority over standard queue dials.
          </p>

          <div className="p-4 rounded-xl bg-[#080b14] border border-[#1e293b] space-y-2.5">
            <div className="flex items-center justify-between text-xs">
              <span className="text-slate-400">Scheduled Time</span>
              <span className="font-mono text-amber-400 font-bold flex items-center gap-1.5">
                <Clock className="w-3.5 h-3.5" />
                {callbackDate.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} ({callbackDate.toLocaleDateString()})
              </span>
            </div>
            <div className="flex items-center justify-between text-xs border-t border-[#1e293b] pt-2">
              <span className="text-slate-400">Masked Phone</span>
              <span className="font-mono text-indigo-300 font-semibold">{primaryCallback.phone || '+91 98450 •••••'}</span>
            </div>
            <div className="flex items-center justify-between text-xs border-t border-[#1e293b] pt-2">
              <span className="text-slate-400">Queue Slot</span>
              <span className="text-emerald-400 font-bold bg-emerald-500/10 px-2 py-0.5 rounded border border-emerald-500/20">Slot #1 Locked</span>
            </div>
          </div>

          {/* Action Button */}
          <div className="pt-2 flex flex-col sm:flex-row gap-3">
            <button
              onClick={handleDialNow}
              disabled={isDialing}
              className="flex-1 min-h-[44px] bg-gradient-to-r from-indigo-600 to-indigo-700 hover:from-indigo-500 hover:to-indigo-600 text-white font-bold py-3 px-5 rounded-xl shadow-lg shadow-indigo-600/30 flex items-center justify-center gap-2 cursor-pointer transition transform active:scale-98"
            >
              <PhoneCall className="w-4 h-4" />
              <span>{isDialing ? 'Connecting to Lead...' : 'Connect Priority Call Now'}</span>
              <ArrowRight className="w-4 h-4" />
            </button>
            <button
              onClick={() => setIsDismissed(true)}
              className="min-h-[44px] px-4 py-2.5 rounded-xl border border-[#1e293b] text-slate-400 hover:text-slate-200 hover:bg-[#18233d] text-xs font-semibold cursor-pointer transition"
            >
              Snooze 2m
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
