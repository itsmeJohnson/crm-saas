import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { useDialerStore } from '../../store/dialerStore';
import { usePipelineStore } from '../../store/pipelineStore';
import { dashboardApi } from '../../services/dashboardApi';
import { useDashboardStore } from '../../store/dashboardStore';
import { useAnalyticsStore } from '../../store/analyticsStore';
import { useLeadStore } from '../../store/leadStore';
import { OmniChannelChatDrawer } from './OmniChannelChatDrawer';
import {
  PhoneCall,
  PhoneOff,
  Mic,
  MicOff,
  Grid,
  UserCheck,
  CheckCircle,
  AlertCircle,
  Minus,
  Maximize2,
  MessageSquare,
  Wifi,
  WifiOff,
  Loader2,
  Calendar,
  X,
  Radio,
  ArrowLeftRight,
} from 'lucide-react';

export const FloatingDialerWidget: React.FC = () => {
  const {
    callLifecycle,
    currentLead,
    callDuration,
    callDirection,
    incomingCall,
    isMuted,
    isKeypadOpen,
    networkStatus,
    reconnectCountdown,
    isLoading,
    error,
    toggleMute,
    toggleKeypad,
    sendDTMF,
    hangupWebRTC,
    cancelInitiatingCall,
    submitDisposition,
  } = useDialerStore();

  const { stages, fetchStages } = usePipelineStore();

  const [isMinimized, setIsMinimized] = useState(false);
  const [showChatDrawer, setShowChatDrawer] = useState(false);
  const [dockSide, setDockSide] = useState<'right' | 'left'>(() => {
    if (typeof localStorage !== 'undefined') {
      return (localStorage.getItem('crm_dialer_dock') as 'right' | 'left') || 'left';
    }
    return 'left';
  });

  const toggleDock = () => {
    const nextSide = dockSide === 'right' ? 'left' : 'right';
    setDockSide(nextSide);
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_dialer_dock', nextSide);
    }
  };

  // Disposition form fields
  const [callStatus, setCallStatus] = useState<string>('Answered');
  const [dispositionCategory, setDispositionCategory] = useState<string>('Interested');
  const [remarks, setRemarks] = useState('');
  const [targetStageId, setTargetStageId] = useState('');
  const [followUpDate, setFollowUpDate] = useState('');
  const [followUpTime, setFollowUpTime] = useState('');
  const [followUpPriority, setFollowUpPriority] = useState<'Low' | 'Medium' | 'High' | 'Urgent'>('Medium');

  useEffect(() => {
    if (stages.length === 0) {
      fetchStages().catch(() => {});
    }
  }, [stages.length, fetchStages]);

  // When a new call starts, reset local disposition form
  useEffect(() => {
    if (callLifecycle === 'initiating' || callLifecycle === 'ringing' || callLifecycle === 'connected') {
      setRemarks('');
      setTargetStageId('');
      setFollowUpDate('');
      setFollowUpTime('');
      setCallStatus('Picked');
      setDispositionCategory('Interested');
    }
  }, [currentLead?.id, callLifecycle]);

  const location = useLocation();
  const isEmbeddedCockpitPage =
    location.pathname === '/' ||
    location.pathname === '/workspace' ||
    location.pathname.startsWith('/calling') ||
    location.pathname.startsWith('/dialer');

  // If on a page with an embedded full dialer console (Cockpit Dashboard or Calling page),
  // do not duplicate with the floating dialer widget!
  if (isEmbeddedCockpitPage) {
    return null;
  }

  // ── INBOUND RINGING IS MANAGED EXCLUSIVELY BY InboundCallPopup ──
  // If an incoming call is ringing or un-answered, do NOT show the floating dialer widget.
  // Floating dialer will appear only after the agent answers (connected or wrap-up/disposition).
  if (incomingCall || (callDirection === 'INBOUND' && callLifecycle !== 'connected' && callLifecycle !== 'disposition')) {
    return null;
  }

  // If we are in idle state, do not render the widget
  if (callLifecycle === 'idle') {
    return null;
  }

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const isFollowUp = dispositionCategory === 'Callback Requested' || dispositionCategory === 'Follow-up Scheduled';
  const followUpIncomplete = isFollowUp && (!followUpDate || !followUpTime);

  const handleFormSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!remarks.trim() || followUpIncomplete) return;

    try {
      if (isFollowUp && currentLead?.id && followUpDate && followUpTime) {
        try {
          const nextAt = new Date(`${followUpDate}T${followUpTime}`).toISOString();
          await dashboardApi.logFollowUp(String(currentLead.id), {
            outcome: `${callStatus} - ${dispositionCategory}`,
            follow_up_type: 'call',
            remarks: remarks.trim(),
            next_follow_up_at: nextAt,
            priority: followUpPriority,
            reminder_minutes_before: 30,
          });
        } catch (fErr) {
          console.warn('Follow-up schedule error:', fErr);
        }
      }

      await submitDisposition({
        status: callStatus,
        disposition_category: dispositionCategory,
        remarks: remarks.trim(),
        custom_pipeline_stage_id: targetStageId || undefined,
        follow_up_date: followUpDate || undefined,
        follow_up_time: followUpTime || undefined,
        follow_up_priority: followUpPriority,
      });

      try {
        useLeadStore.getState().fetchLeads();
        useLeadStore.getState().fetchKanbanBoard();
        useDashboardStore.getState().fetchSummary();
        useDashboardStore.getState().fetchRecentActivities();
        useAnalyticsStore.getState().fetchDashboardMetrics();
      } catch {}
    } catch {}
  };

  const leadName = `${currentLead?.first_name || ''} ${currentLead?.last_name || 'Prospect'}`.trim() || 'Active Lead';
  const leadPhone = currentLead?.phone || '';

  // ── 1. MINIMIZED FLOATING PILL ──
  if (isMinimized && callLifecycle !== 'disposition') {
    return (
      <>
        {showChatDrawer && currentLead && (
          <OmniChannelChatDrawer
            lead={currentLead}
            initialChannel="whatsapp"
            isOpen={showChatDrawer}
            onClose={() => setShowChatDrawer(false)}
          />
        )}
        <div
          className={`fixed bottom-6 ${
            dockSide === 'left' ? 'left-6' : 'right-6'
          } z-[100] animate-in fade-in slide-in-from-bottom-2 duration-200 select-none`}
        >
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xl shadow-slate-900/10 rounded-2xl px-3.5 py-2.5 flex items-center gap-3 ring-1 ring-slate-900/5 text-slate-900 dark:text-slate-100">
            <div className="w-8 h-8 rounded-xl bg-emerald-50 dark:bg-emerald-950/60 border border-emerald-200 dark:border-emerald-800/60 text-emerald-600 dark:text-emerald-400 flex items-center justify-center shrink-0 shadow-xs">
              <PhoneCall className="w-4 h-4 animate-pulse" />
            </div>

            <div className="min-w-0 flex-1 max-w-[150px] sm:max-w-[180px]">
              <div className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    callLifecycle === 'connected' ? 'bg-emerald-500 animate-ping' : 'bg-amber-500 animate-pulse'
                  }`}
                />
                <p className="text-xs font-bold text-slate-900 dark:text-slate-100 truncate">{leadName}</p>
              </div>
              <p className="text-[11px] font-mono text-emerald-600 dark:text-emerald-400 font-bold truncate mt-0.5">
                {callLifecycle === 'connected' ? formatDuration(callDuration) : 'Initiating...'}
              </p>
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              {callLifecycle === 'connected' && (
                <button
                  type="button"
                  onClick={toggleMute}
                  className={`p-1.5 rounded-lg border transition-all cursor-pointer ${
                    isMuted
                      ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-400'
                      : 'bg-slate-50 dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white'
                  }`}
                  title={isMuted ? 'Unmute' : 'Mute'}
                >
                  {isMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                </button>
              )}

              <button
                type="button"
                onClick={toggleDock}
                className="p-1.5 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 text-slate-600 dark:text-slate-300 hover:text-slate-900 dark:hover:text-white rounded-lg transition-all cursor-pointer"
                title={dockSide === 'right' ? 'Dock to bottom-left' : 'Dock to bottom-right'}
              >
                <ArrowLeftRight className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={() => setIsMinimized(false)}
                className="p-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg shadow-xs transition-all cursor-pointer"
                title="Expand dialer"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={callLifecycle === 'connected' ? hangupWebRTC : cancelInitiatingCall}
                className="p-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-lg shadow-xs transition-all cursor-pointer active:scale-95"
                title={callLifecycle === 'connected' ? 'Hang Up' : 'Cancel'}
              >
                <PhoneOff className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

  // ── 2. FULL FLOATING CARD COMPONENT ──
  return (
    <>
      {showChatDrawer && currentLead && (
        <OmniChannelChatDrawer
          lead={currentLead}
          initialChannel="whatsapp"
          isOpen={showChatDrawer}
          onClose={() => setShowChatDrawer(false)}
        />
      )}

      <div
        className={`fixed bottom-6 ${
          dockSide === 'left' ? 'left-6' : 'right-6'
        } z-[100] w-[350px] max-w-[calc(100vw-2rem)] animate-in slide-in-from-bottom-4 duration-200 select-none`}
      >
        <div className="bg-slate-900 border border-slate-800 shadow-xl shadow-slate-900/10 rounded-2xl overflow-hidden ring-1 ring-slate-800/50 text-slate-100">
          {/* Header Bar */}
          <div className="bg-slate-950 border-b border-slate-800 px-3.5 py-2.5 flex items-center justify-between gap-2.5">
            <div className="flex items-center gap-2 min-w-0">
              <div
                className={`w-7 h-7 rounded-lg flex items-center justify-center shrink-0 ${
                  callLifecycle === 'connected'
                    ? 'bg-emerald-50 text-emerald-600 border border-emerald-200'
                    : callLifecycle === 'disposition'
                    ? 'bg-indigo-50 text-indigo-600 border border-indigo-200'
                    : 'bg-indigo-50 text-indigo-600 border border-indigo-200'
                }`}
              >
                {callLifecycle === 'connected' ? (
                  <PhoneCall className="w-3.5 h-3.5 animate-pulse" />
                ) : callLifecycle === 'disposition' ? (
                  <UserCheck className="w-3.5 h-3.5" />
                ) : (
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                )}
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`px-1.5 py-0.2 rounded text-[9px] font-bold uppercase tracking-wider ${
                      callLifecycle === 'connected'
                        ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                        : 'bg-indigo-50 text-indigo-700 border border-indigo-200'
                    }`}
                  >
                    {callLifecycle === 'initiating'
                      ? 'Initiating...'
                      : callLifecycle === 'ringing'
                      ? 'Ringing...'
                      : callLifecycle === 'connected'
                      ? 'Live Active'
                      : 'Wrap-Up'}
                  </span>
                  <span className="text-[10px] text-slate-400 font-medium">
                    • {callDirection === 'INBOUND' ? 'Inbound' : 'Outbound'}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-slate-100 truncate mt-0.5">{leadName}</h4>
              </div>
            </div>

            {/* Right Controls */}
            <div className="flex items-center gap-1.5 shrink-0">
              {networkStatus === 'unstable' ? (
                <span className="flex items-center gap-1 text-[10px] font-bold text-amber-700 bg-amber-50 px-2 py-0.5 rounded-full border border-amber-200 animate-pulse">
                  <WifiOff className="w-3 h-3" />
                  {reconnectCountdown}s
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[10px] font-semibold text-slate-400" title="WebRTC Connected">
                  <Wifi className="w-3.5 h-3.5 text-emerald-600" />
                </span>
              )}

              {/* Dock Side Switcher */}
              <button
                type="button"
                onClick={toggleDock}
                title={dockSide === 'right' ? 'Dock dialer to bottom-left' : 'Dock dialer to bottom-right'}
                className="p-1 bg-slate-900 hover:bg-slate-950 text-slate-300 hover:text-slate-100 border border-slate-800 rounded-lg transition-all cursor-pointer"
              >
                <ArrowLeftRight className="w-3.5 h-3.5" />
              </button>

              {/* Minimize button (disabled during mandatory wrap-up form) */}
              {callLifecycle !== 'disposition' && (
                <button
                  type="button"
                  onClick={() => setIsMinimized(true)}
                  title="Minimize dialer"
                  className="p-1 bg-slate-900 hover:bg-slate-950 text-slate-300 hover:text-slate-100 border border-slate-800 rounded-lg transition-all cursor-pointer"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Network Warning Banner */}
          {networkStatus === 'unstable' && (
            <div className="bg-amber-50 dark:bg-amber-500/20 border-b border-amber-200 dark:border-amber-500/30 px-3.5 py-1.5 flex items-center justify-between text-amber-800 dark:text-amber-300 text-xs animate-in slide-in-from-top-1">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-3.5 h-3.5 text-amber-600 dark:text-amber-400 shrink-0 animate-pulse" />
                <span className="font-semibold text-[11px]">Network unstable. Reconnecting...</span>
              </div>
              <span className="font-mono text-xs font-bold text-amber-700 dark:text-amber-400">{reconnectCountdown}s</span>
            </div>
          )}

          {/* ── STATE A: INITIATING / RINGING ── */}
          {(callLifecycle === 'initiating' || callLifecycle === 'ringing') && (
            <div className="p-5 text-center space-y-3.5">
              <div className="relative mx-auto w-20 h-20 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20 animate-ping" />
                <div className="absolute inset-2 rounded-full border-2 border-emerald-500/30 animate-pulse" />
                <div className="w-14 h-14 rounded-full bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 flex items-center justify-center text-emerald-600 dark:text-emerald-400 shadow-md">
                  <Radio className="w-6 h-6 animate-pulse text-emerald-600 dark:text-emerald-300" />
                </div>
              </div>

              <div>
                <p className="text-sm font-bold text-slate-900 dark:text-slate-100 tracking-wide">{leadName}</p>
                <div className="mt-1">
                  <span className="text-xs font-mono font-bold text-slate-700 dark:text-slate-300 bg-slate-100 dark:bg-slate-800 border border-slate-200 dark:border-slate-700 px-2.5 py-0.5 rounded-full inline-block">
                    {leadPhone}
                  </span>
                </div>
                <p className="text-xs font-semibold text-emerald-600 dark:text-emerald-400 mt-2 flex items-center justify-center gap-1.5">
                  <Loader2 className="w-3.5 h-3.5 animate-spin text-emerald-600 dark:text-emerald-400" />
                  {callLifecycle === 'ringing' ? 'Customer phone is ringing...' : 'Connecting bridge...'}
                </p>
              </div>

              {error && (
                <div className="bg-rose-50 dark:bg-rose-950/40 border border-rose-200 dark:border-rose-800 text-rose-700 dark:text-rose-300 text-xs px-3 py-1.5 rounded-lg">
                  {error}
                </div>
              )}

              <div className="pt-1">
                <button
                  type="button"
                  onClick={cancelInitiatingCall}
                  className="w-full flex items-center justify-center gap-2 py-2 px-4 bg-rose-600 hover:bg-rose-700 active:scale-98 text-white rounded-xl text-xs font-semibold shadow-xs transition-all cursor-pointer"
                >
                  <PhoneOff className="w-3.5 h-3.5" />
                  Cancel Call
                </button>
              </div>
            </div>
          )}

          {/* ── STATE B: CONNECTED / ACTIVE ── */}
          {callLifecycle === 'connected' && (
            <div className="p-3.5 space-y-3">
              {/* Call Timer Display */}
              <div className="text-center py-2.5 bg-slate-50 dark:bg-slate-800/70 border border-slate-200 dark:border-slate-700 rounded-xl">
                <p className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-widest">Active Call Duration</p>
                <div className="flex items-center justify-center gap-2 mt-0.5">
                  <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
                  <p className="font-mono text-2xl font-black text-emerald-600 dark:text-emerald-400 tracking-wider">
                    {formatDuration(callDuration)}
                  </p>
                </div>
                <p className="text-xs font-mono text-slate-600 dark:text-slate-300 mt-0.5 font-semibold">{leadPhone}</p>
              </div>

              {/* Call Control Buttons */}
              <div className="grid grid-cols-4 gap-1.5">
                {/* Mute Button */}
                <button
                  type="button"
                  onClick={toggleMute}
                  className={`flex flex-col items-center justify-center gap-1 py-2 px-1.5 rounded-xl border text-[11px] font-semibold transition-all cursor-pointer ${
                    isMuted
                      ? 'bg-rose-50 dark:bg-rose-950/40 border-rose-200 dark:border-rose-800 text-rose-600 dark:text-rose-300 shadow-xs'
                      : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                  }`}
                >
                  {isMuted ? <MicOff className="w-4 h-4 text-rose-600" /> : <Mic className="w-4 h-4 text-slate-600 dark:text-slate-300" />}
                  <span>{isMuted ? 'Muted' : 'Mute'}</span>
                </button>

                {/* Keypad DTMF Toggle */}
                <button
                  type="button"
                  onClick={() => toggleKeypad()}
                  className={`flex flex-col items-center justify-center gap-1 py-2 px-1.5 rounded-xl border text-[11px] font-semibold transition-all cursor-pointer ${
                    isKeypadOpen
                      ? 'bg-indigo-50 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300'
                      : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
                  }`}
                >
                  <Grid className="w-4 h-4" />
                  <span>Keypad</span>
                </button>

                {/* Omnichannel Chat Trigger */}
                <button
                  type="button"
                  onClick={() => setShowChatDrawer(true)}
                  className="flex flex-col items-center justify-center gap-1 py-2 px-1.5 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 border border-slate-200 dark:border-slate-700 text-emerald-600 dark:text-emerald-400 rounded-xl text-[11px] font-semibold transition-all cursor-pointer"
                  title="WhatsApp & SMS Chat"
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>Chat</span>
                </button>

                {/* Hang Up Button */}
                <button
                  type="button"
                  onClick={hangupWebRTC}
                  className="flex flex-col items-center justify-center gap-1 py-2 px-1.5 bg-rose-600 hover:bg-rose-700 text-white rounded-xl text-[11px] font-bold shadow-xs transition-all cursor-pointer active:scale-95"
                  title="End Call & Open Wrap-Up Form"
                >
                  <PhoneOff className="w-4 h-4" />
                  <span>End</span>
                </button>
              </div>

              {/* Interactive DTMF Keypad Drawer */}
              {isKeypadOpen && (
                <div className="pt-2 border-t border-slate-200 dark:border-slate-800 animate-in fade-in duration-150">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-[10px] font-bold text-slate-500 dark:text-slate-400 uppercase tracking-wider">
                      DTMF Keypad (IVR)
                    </span>
                    <button
                      type="button"
                      onClick={() => toggleKeypad(false)}
                      className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 text-xs cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-1">
                    {['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'].map((digit) => (
                      <button
                        key={digit}
                        type="button"
                        onClick={() => sendDTMF(digit)}
                        className="py-1.5 bg-slate-50 dark:bg-slate-800 hover:bg-slate-100 dark:hover:bg-slate-700 active:bg-indigo-600 active:text-white border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 font-bold text-xs rounded-lg transition-colors cursor-pointer"
                      >
                        {digit}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── STATE C: MANDATORY CALL DISPOSITION & WRAP-UP FORM ── */}
          {callLifecycle === 'disposition' && (
            <div className="p-3.5 space-y-2.5 max-h-[70vh] overflow-y-auto">
              <div className="flex items-start justify-between gap-2 pb-2 border-b border-slate-800">
                <div>
                  <h3 className="text-xs font-bold text-slate-100 flex items-center gap-1.5">
                    <UserCheck className="w-3.5 h-3.5 text-indigo-600" />
                    Call Disposition & Wrap-Up
                  </h3>
                  <p className="text-[10px] text-slate-400 mt-0.5">
                    Call ended ({formatDuration(callDuration)}). Log outcome to complete.
                  </p>
                </div>
                <span className="text-[10px] bg-slate-950 text-slate-300 border border-slate-800 px-2 py-0.5 rounded-md font-semibold">
                  Required
                </span>
              </div>

              {error && (
                <div className="p-2 bg-rose-50 border border-rose-200 rounded-lg text-rose-700 text-xs flex items-center gap-1.5">
                  <AlertCircle className="w-3.5 h-3.5 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleFormSubmit} className="space-y-2.5">
                {/* 1 & 2. Call Status & Disposition Outcome in a compact 2-column grid */}
                <div className="grid grid-cols-2 gap-2">
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                      Call Status <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={callStatus}
                      onChange={(e) => setCallStatus(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 cursor-pointer"
                    >
                      <option value="Picked">Answered</option>
                      <option value="Busy">Busy</option>
                      <option value="RNR">No Answer</option>
                      <option value="Not Exist">Wrong No.</option>
                      <option value="Switch Off">Switched Off</option>
                    </select>
                  </div>

                  <div>
                    <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                      Outcome <span className="text-rose-500">*</span>
                    </label>
                    <select
                      value={dispositionCategory}
                      onChange={(e) => setDispositionCategory(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 cursor-pointer"
                    >
                      <option value="Interested">Interested</option>
                      <option value="Not Interested">Not Interested</option>
                      <option value="Callback Requested">Callback</option>
                      <option value="Follow-up Scheduled">Follow-up</option>
                    </select>
                  </div>
                </div>

                {/* 3. Conditional Follow-up / Callback Fields */}
                {isFollowUp && (
                  <div className="p-2.5 bg-indigo-50/70 border border-indigo-200 rounded-xl space-y-2 animate-in fade-in duration-200">
                    <div className="flex items-center gap-1.5 text-indigo-700 text-xs font-bold">
                      <Calendar className="w-3.5 h-3.5" />
                      <span>Schedule Follow-Up</span>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-bold text-slate-400 mb-0.5">Date *</label>
                        <input
                          type="date"
                          value={followUpDate}
                          min={new Date().toISOString().split('T')[0]}
                          onChange={(e) => setFollowUpDate(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-100 focus:ring-1 focus:ring-indigo-500"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-slate-400 mb-0.5">Time *</label>
                        <input
                          type="time"
                          value={followUpTime}
                          onChange={(e) => setFollowUpTime(e.target.value)}
                          className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-100 focus:ring-1 focus:ring-indigo-500"
                          required
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] font-bold text-slate-400 mb-0.5">Priority</label>
                      <select
                        value={followUpPriority}
                        onChange={(e) => setFollowUpPriority(e.target.value as any)}
                        className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2 py-1 text-xs text-slate-100"
                      >
                        <option value="Low">Low</option>
                        <option value="Medium">Medium</option>
                        <option value="High">High</option>
                        <option value="Urgent">Urgent</option>
                      </select>
                    </div>
                  </div>
                )}

                {/* 4. Advance Pipeline Stage (Optional) */}
                {stages.length > 0 && (
                  <div>
                    <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                      Update Pipeline Stage (Optional)
                    </label>
                    <select
                      value={targetStageId}
                      onChange={(e) => setTargetStageId(e.target.value)}
                      className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 cursor-pointer"
                    >
                      <option value="">Keep Current Stage</option>
                      {stages.map((st) => (
                        <option key={st.id} value={st.id}>
                          Move to: {st.name}
                        </option>
                      ))}
                    </select>
                  </div>
                )}

                {/* 5. Call Summary Notes */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-300 mb-1">
                    Call Summary & Notes <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    rows={2}
                    value={remarks}
                    onChange={(e) => setRemarks(e.target.value)}
                    placeholder="Enter call notes or outcome..."
                    required
                    className="w-full bg-slate-900 border border-slate-800 rounded-lg px-2.5 py-1.5 text-xs text-slate-100 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500"
                  />
                </div>

                {/* Submit and Skip Buttons */}
                {(() => {
                  const isSubmitDisabled = isLoading || !remarks.trim() || followUpIncomplete;
                  return (
                    <div className="flex items-center gap-2 pt-1">
                      <button
                        type="submit"
                        disabled={isSubmitDisabled}
                        className={`flex-1 py-2.5 px-4 rounded-xl text-xs font-semibold transition-all flex items-center justify-center gap-2 ${
                          isSubmitDisabled
                            ? 'bg-slate-950 text-slate-400 border border-slate-800 cursor-not-allowed shadow-none'
                            : 'bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white shadow-xs cursor-pointer active:scale-98'
                        }`}
                      >
                        {isLoading ? (
                          <>
                            <Loader2 className="w-3.5 h-3.5 animate-spin" />
                            <span>Saving...</span>
                          </>
                        ) : (
                          <>
                            <CheckCircle className="w-3.5 h-3.5" />
                            <span>Save & Complete Call</span>
                          </>
                        )}
                      </button>
                      <button
                        type="button"
                        onClick={() => {
                          useDialerStore.getState().resetStore();
                        }}
                        className="py-2.5 px-3 bg-slate-900 hover:bg-slate-800 text-slate-300 hover:text-white rounded-xl text-xs font-medium border border-slate-800 transition-colors cursor-pointer"
                        title="Skip disposition logging and return to idle"
                      >
                        Skip
                      </button>
                    </div>
                  );
                })()}
              </form>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
