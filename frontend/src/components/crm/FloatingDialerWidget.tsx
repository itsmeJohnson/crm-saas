import React, { useState, useEffect } from 'react';
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
    agentState,
    callLifecycle,
    currentLead,
    callDuration,
    callDirection,
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
      return (localStorage.getItem('crm_dialer_dock') as 'right' | 'left') || 'right';
    }
    return 'right';
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

  // If there is no active lead and we are idle, don't show the widget
  if (!currentLead && callLifecycle === 'idle' && agentState !== 'ACTIVE_CALLING') {
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
          <div className="bg-gray-950/95 border border-gray-700 shadow-2xl shadow-black/80 rounded-2xl px-3.5 py-2 flex items-center gap-3 backdrop-blur-xl ring-1 ring-white/10 text-white">
            <div className="w-8 h-8 rounded-xl bg-gradient-to-tr from-emerald-600 to-teal-500 text-white flex items-center justify-center shrink-0 shadow-md">
              <PhoneCall className="w-4 h-4 animate-pulse" />
            </div>

            <div className="min-w-0 flex-1 max-w-[150px] sm:max-w-[180px]">
              <div className="flex items-center gap-1.5">
                <span
                  className={`w-2 h-2 rounded-full shrink-0 ${
                    callLifecycle === 'connected' ? 'bg-emerald-400 animate-ping' : 'bg-amber-400 animate-pulse'
                  }`}
                />
                <p className="text-xs font-bold text-white truncate">{leadName}</p>
              </div>
              <p className="text-[11px] font-mono text-emerald-400 font-bold truncate mt-0.5">
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
                      ? 'bg-rose-500/20 border-rose-500/40 text-rose-300'
                      : 'bg-gray-800 border-gray-700 text-gray-300 hover:text-white'
                  }`}
                  title={isMuted ? 'Unmute' : 'Mute'}
                >
                  {isMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                </button>
              )}

              <button
                type="button"
                onClick={toggleDock}
                className="p-1.5 bg-gray-800 hover:bg-gray-700 border border-gray-700 text-gray-300 hover:text-white rounded-lg transition-all cursor-pointer"
                title={dockSide === 'right' ? 'Dock to bottom-left' : 'Dock to bottom-right'}
              >
                <ArrowLeftRight className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={() => setIsMinimized(false)}
                className="p-1.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg shadow-sm transition-all cursor-pointer"
                title="Expand dialer"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>

              <button
                type="button"
                onClick={callLifecycle === 'connected' ? hangupWebRTC : cancelInitiatingCall}
                className="p-1.5 bg-red-600 hover:bg-red-500 text-white rounded-lg shadow-sm transition-all cursor-pointer active:scale-95"
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
        } z-[100] w-full max-w-sm sm:max-w-md animate-in slide-in-from-bottom-4 duration-200 select-none`}
      >
        <div className="bg-gray-950 border border-gray-700 shadow-2xl shadow-black/80 rounded-2xl overflow-hidden backdrop-blur-xl ring-1 ring-white/10 text-white">
          {/* Header Bar */}
          <div className="bg-gradient-to-r from-gray-900 via-gray-950 to-indigo-950/80 border-b border-gray-800/80 px-4 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div
                className={`w-8 h-8 rounded-xl flex items-center justify-center shrink-0 ${
                  callLifecycle === 'connected'
                    ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                    : callLifecycle === 'disposition'
                    ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                    : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
                }`}
              >
                {callLifecycle === 'connected' ? (
                  <PhoneCall className="w-4 h-4 animate-pulse" />
                ) : callLifecycle === 'disposition' ? (
                  <UserCheck className="w-4 h-4" />
                ) : (
                  <Loader2 className="w-4 h-4 animate-spin" />
                )}
              </div>

              <div className="min-w-0">
                <div className="flex items-center gap-1.5">
                  <span
                    className={`px-1.5 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider ${
                      callLifecycle === 'connected'
                        ? 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30'
                        : callLifecycle === 'disposition'
                        ? 'bg-indigo-500/20 text-indigo-300 border border-indigo-500/30'
                        : 'bg-amber-500/20 text-amber-300 border border-amber-500/30'
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
                  <span className="text-[11px] text-gray-400 font-medium">
                    • {callDirection === 'INBOUND' ? 'Inbound' : 'Outbound'}
                  </span>
                </div>
                <h4 className="text-sm font-bold text-white truncate mt-0.5">{leadName}</h4>
              </div>
            </div>

            {/* Right Controls */}
            <div className="flex items-center gap-1.5 shrink-0">
              {networkStatus === 'unstable' ? (
                <span className="flex items-center gap-1 text-[10px] font-bold text-amber-400 bg-amber-500/10 px-2 py-0.5 rounded-full border border-amber-500/30 animate-pulse">
                  <WifiOff className="w-3 h-3" />
                  {reconnectCountdown}s
                </span>
              ) : (
                <span className="flex items-center gap-1 text-[10px] font-semibold text-gray-400" title="WebRTC Connected">
                  <Wifi className="w-3.5 h-3.5 text-emerald-400" />
                </span>
              )}

              {/* Dock Side Switcher (Dock Left / Dock Right to avoid covering open drawers) */}
              <button
                type="button"
                onClick={toggleDock}
                title={dockSide === 'right' ? 'Dock dialer to bottom-left' : 'Dock dialer to bottom-right'}
                className="p-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border border-gray-700/80 rounded-lg transition-all cursor-pointer"
              >
                <ArrowLeftRight className="w-3.5 h-3.5" />
              </button>

              {/* Minimize button (disabled during mandatory wrap-up form) */}
              {callLifecycle !== 'disposition' && (
                <button
                  type="button"
                  onClick={() => setIsMinimized(true)}
                  title="Minimize dialer"
                  className="p-1.5 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white border border-gray-700/80 rounded-lg transition-all cursor-pointer"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Network Warning Banner */}
          {networkStatus === 'unstable' && (
            <div className="bg-amber-500/20 border-b border-amber-500/30 px-3.5 py-2 flex items-center justify-between text-amber-300 text-xs animate-in slide-in-from-top-1">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 animate-pulse" />
                <span className="font-semibold text-xs">Network unstable. Reconnecting...</span>
              </div>
              <span className="font-mono text-xs font-bold text-amber-400">{reconnectCountdown}s</span>
            </div>
          )}

          {/* ── STATE A: INITIATING / RINGING ── */}
          {(callLifecycle === 'initiating' || callLifecycle === 'ringing') && (
            <div className="p-6 text-center space-y-4">
              <div className="relative mx-auto w-24 h-24 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20 animate-ping" />
                <div className="absolute inset-2 rounded-full border-2 border-emerald-500/40 animate-pulse" />
                <div className="w-16 h-16 rounded-full bg-gradient-to-tr from-emerald-600/30 to-teal-500/30 border border-emerald-500/60 flex items-center justify-center text-emerald-400 shadow-xl shadow-emerald-500/20">
                  <Radio className="w-7 h-7 animate-pulse text-emerald-300" />
                </div>
              </div>

              <div>
                <p className="text-base font-bold text-white tracking-wide">{leadName}</p>
                <div className="mt-1">
                  <span className="text-xs font-mono font-bold text-emerald-300 bg-emerald-950/70 border border-emerald-500/30 px-3 py-1 rounded-full inline-block shadow-inner">
                    {leadPhone}
                  </span>
                </div>
                <p className="text-xs font-semibold text-emerald-400 mt-2.5 flex items-center justify-center gap-2">
                  <Loader2 className="w-4 h-4 animate-spin text-emerald-400" />
                  {callLifecycle === 'ringing' ? 'Customer phone is ringing...' : 'Connecting softphone bridge...'}
                </p>
              </div>

              {error && (
                <div className="bg-red-500/15 border border-red-500/30 text-red-300 text-xs px-3 py-2 rounded-xl">
                  {error}
                </div>
              )}

              <div className="pt-2">
                <button
                  type="button"
                  onClick={cancelInitiatingCall}
                  className="w-full flex items-center justify-center gap-2 py-3 px-4 bg-red-600 hover:bg-red-500 active:scale-98 text-white rounded-xl text-xs font-bold shadow-lg shadow-red-600/30 transition-all cursor-pointer"
                >
                  <PhoneOff className="w-4 h-4" />
                  Cancel Call
                </button>
              </div>
            </div>
          )}

          {/* ── STATE B: CONNECTED / ACTIVE ── */}
          {callLifecycle === 'connected' && (
            <div className="p-4 space-y-4">
              {/* Call Timer Display */}
              <div className="text-center py-3 bg-gray-900/90 border border-gray-800 rounded-xl">
                <p className="text-[10px] font-bold text-gray-400 uppercase tracking-widest">Active Call Duration</p>
                <div className="flex items-center justify-center gap-2 mt-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                  <p className="font-mono text-3xl font-black text-emerald-400 tracking-wider">
                    {formatDuration(callDuration)}
                  </p>
                </div>
                <p className="text-xs font-mono text-gray-300 mt-1 font-semibold">{leadPhone}</p>
              </div>

              {/* Call Control Buttons */}
              <div className="grid grid-cols-4 gap-2">
                {/* Mute Button */}
                <button
                  type="button"
                  onClick={toggleMute}
                  className={`flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl border text-[11px] font-semibold transition-all cursor-pointer ${
                    isMuted
                      ? 'bg-rose-500/20 border-rose-500/40 text-rose-300 shadow-lg shadow-rose-950/30'
                      : 'bg-gray-900 border-gray-700 text-gray-300 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  {isMuted ? <MicOff className="w-4 h-4 text-rose-400" /> : <Mic className="w-4 h-4 text-gray-300" />}
                  <span>{isMuted ? 'Muted' : 'Mute'}</span>
                </button>

                {/* Keypad DTMF Toggle */}
                <button
                  type="button"
                  onClick={() => toggleKeypad()}
                  className={`flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl border text-[11px] font-semibold transition-all cursor-pointer ${
                    isKeypadOpen
                      ? 'bg-indigo-600/30 border-indigo-500/50 text-indigo-300'
                      : 'bg-gray-900 border-gray-700 text-gray-300 hover:bg-gray-800 hover:text-white'
                  }`}
                >
                  <Grid className="w-4 h-4" />
                  <span>Keypad</span>
                </button>

                {/* Omnichannel Chat Trigger */}
                <button
                  type="button"
                  onClick={() => setShowChatDrawer(true)}
                  className="flex flex-col items-center justify-center gap-1 py-2.5 px-2 bg-gray-900 hover:bg-gray-800 border border-gray-700 text-emerald-400 hover:text-emerald-300 rounded-xl text-[11px] font-semibold transition-all cursor-pointer"
                  title="WhatsApp & SMS Chat"
                >
                  <MessageSquare className="w-4 h-4" />
                  <span>Chat</span>
                </button>

                {/* Hang Up Button */}
                <button
                  type="button"
                  onClick={hangupWebRTC}
                  className="flex flex-col items-center justify-center gap-1 py-2.5 px-2 bg-red-600 hover:bg-red-500 text-white rounded-xl text-[11px] font-bold shadow-lg shadow-red-600/30 transition-all cursor-pointer active:scale-95"
                  title="End Call & Open Wrap-Up Form"
                >
                  <PhoneOff className="w-4 h-4" />
                  <span>End</span>
                </button>
              </div>

              {/* Interactive DTMF Keypad Drawer */}
              {isKeypadOpen && (
                <div className="pt-2 border-t border-gray-800 animate-in fade-in duration-150">
                  <div className="flex items-center justify-between mb-2">
                    <span className="text-[10px] font-bold text-gray-400 uppercase tracking-wider">
                      DTMF Keypad (IVR)
                    </span>
                    <button
                      type="button"
                      onClick={() => toggleKeypad(false)}
                      className="text-gray-400 hover:text-gray-200 text-xs cursor-pointer"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5">
                    {['1', '2', '3', '4', '5', '6', '7', '8', '9', '*', '0', '#'].map((digit) => (
                      <button
                        key={digit}
                        type="button"
                        onClick={() => sendDTMF(digit)}
                        className="py-2 bg-gray-900 hover:bg-gray-800 active:bg-indigo-600 active:text-white border border-gray-800 text-gray-200 font-bold text-sm rounded-lg transition-colors cursor-pointer"
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
            <div className="p-4 space-y-3.5 max-h-[75vh] overflow-y-auto">
              <div className="flex items-start justify-between gap-2 pb-2 border-b border-gray-800/80">
                <div>
                  <h3 className="text-xs font-bold text-white flex items-center gap-1.5">
                    <UserCheck className="w-4 h-4 text-indigo-400" />
                    Call Disposition & Wrap-Up
                  </h3>
                  <p className="text-[11px] text-gray-400 mt-0.5">
                    Call ended ({formatDuration(callDuration)}). Log the outcome to complete.
                  </p>
                </div>
                <span className="text-[10px] bg-rose-500/20 text-rose-300 border border-rose-500/40 px-2 py-0.5 rounded-full font-bold">
                  Mandatory
                </span>
              </div>

              {error && (
                <div className="p-2.5 bg-rose-500/15 border border-rose-500/30 rounded-xl text-rose-300 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <span>{error}</span>
                </div>
              )}

              <form onSubmit={handleFormSubmit} className="space-y-3">
                {/* 1. Call Status */}
                <div>
                  <label className="block text-[11px] font-bold text-gray-300 mb-1">
                    Call Status <span className="text-rose-400">*</span>
                  </label>
                  <select
                    value={callStatus}
                    onChange={(e) => setCallStatus(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-hidden focus:ring-2 focus:ring-brand-500/30 cursor-pointer"
                  >
                    <option value="Picked">Answered (Connected)</option>
                    <option value="Busy">Busy</option>
                    <option value="RNR">No Answer / Ringing Not Responded</option>
                    <option value="Not Exist">Wrong Number / Does Not Exist</option>
                    <option value="Switch Off">Switched Off / Out of Coverage</option>
                  </select>
                </div>

                {/* 2. Disposition Category */}
                <div>
                  <label className="block text-[11px] font-bold text-gray-300 mb-1">
                    Disposition Outcome <span className="text-rose-400">*</span>
                  </label>
                  <select
                    value={dispositionCategory}
                    onChange={(e) => setDispositionCategory(e.target.value)}
                    className="w-full bg-gray-900 border border-gray-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-hidden focus:ring-2 focus:ring-brand-500/30 cursor-pointer"
                  >
                    <option value="Interested">Interested / Qualified</option>
                    <option value="Not Interested">Not Interested</option>
                    <option value="Callback Requested">Callback Requested</option>
                    <option value="Follow-up Scheduled">Follow-up Scheduled</option>
                  </select>
                </div>

                {/* 3. Conditional Follow-up / Callback Fields */}
                {isFollowUp && (
                  <div className="p-3 bg-indigo-950/30 border border-indigo-500/30 rounded-xl space-y-2.5 animate-in fade-in duration-200">
                    <div className="flex items-center gap-1.5 text-indigo-300 text-xs font-bold">
                      <Calendar className="w-3.5 h-3.5" />
                      <span>Schedule Follow-Up Details</span>
                    </div>

                    <div className="grid grid-cols-2 gap-2">
                      <div>
                        <label className="block text-[10px] font-bold text-gray-400 mb-0.5">Date *</label>
                        <input
                          type="date"
                          value={followUpDate}
                          min={new Date().toISOString().split('T')[0]}
                          onChange={(e) => setFollowUpDate(e.target.value)}
                          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-xs text-white focus:ring-1 focus:ring-indigo-500"
                          required
                        />
                      </div>
                      <div>
                        <label className="block text-[10px] font-bold text-gray-400 mb-0.5">Time *</label>
                        <input
                          type="time"
                          value={followUpTime}
                          onChange={(e) => setFollowUpTime(e.target.value)}
                          className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-xs text-white focus:ring-1 focus:ring-indigo-500"
                          required
                        />
                      </div>
                    </div>

                    <div>
                      <label className="block text-[10px] font-bold text-gray-400 mb-0.5">Priority</label>
                      <select
                        value={followUpPriority}
                        onChange={(e) => setFollowUpPriority(e.target.value as any)}
                        className="w-full bg-gray-900 border border-gray-700 rounded-lg px-2 py-1.5 text-xs text-white"
                      >
                        <option value="Low">Low Priority</option>
                        <option value="Medium">Medium Priority</option>
                        <option value="High">High Priority</option>
                        <option value="Urgent">Urgent Priority</option>
                      </select>
                    </div>
                  </div>
                )}

                {/* 4. Advance Pipeline Stage (Optional) */}
                {stages.length > 0 && (
                  <div>
                    <label className="block text-[11px] font-bold text-gray-300 mb-1">
                      Update Pipeline Stage (Optional)
                    </label>
                    <select
                      value={targetStageId}
                      onChange={(e) => setTargetStageId(e.target.value)}
                      className="w-full bg-gray-900 border border-gray-700/80 rounded-xl px-3 py-2 text-xs text-white focus:outline-hidden focus:ring-2 focus:ring-brand-500/30 cursor-pointer"
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
                  <label className="block text-[11px] font-bold text-gray-300 mb-1">
                    Call Summary & Notes <span className="text-rose-400">*</span>
                  </label>
                  <textarea
                    rows={2}
                    value={remarks}
                    onChange={(e) => setRemarks(e.target.value)}
                    placeholder="Enter call notes, customer reaction, next steps..."
                    required
                    className="w-full bg-gray-900 border border-gray-700/80 rounded-xl px-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-hidden focus:ring-2 focus:ring-brand-500/30"
                  />
                </div>

                {/* Submit Button */}
                <button
                  type="submit"
                  disabled={isLoading || !remarks.trim() || followUpIncomplete}
                  className="w-full py-2.5 px-4 bg-gradient-to-r from-brand-600 to-indigo-600 hover:from-brand-500 hover:to-indigo-500 disabled:opacity-50 text-white rounded-xl text-xs font-bold shadow-lg shadow-brand-500/25 transition-all flex items-center justify-center gap-2 cursor-pointer active:scale-98"
                >
                  {isLoading ? (
                    <>
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                      <span>Saving Disposition...</span>
                    </>
                  ) : (
                    <>
                      <CheckCircle className="w-3.5 h-3.5" />
                      <span>Save & Complete Call</span>
                    </>
                  )}
                </button>
              </form>
            </div>
          )}
        </div>
      </div>
    </>
  );
};
