import React, { useState, useEffect } from 'react';
import { useDialerStore } from '../../store/dialerStore';
import { usePipelineStore } from '../../store/pipelineStore';
import { dashboardApi } from '../../services/dashboardApi';
import { useDashboardStore } from '../../store/dashboardStore';
import { useAnalyticsStore } from '../../store/analyticsStore';
import { OmniChannelChatDrawer } from './OmniChannelChatDrawer';
import {
  Phone,
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
      setCallStatus(callDirection === 'INBOUND' ? 'Answered' : 'Answered');
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
        useDashboardStore.getState().fetchSummary();
        useDashboardStore.getState().fetchRecentActivities();
        useAnalyticsStore.getState().fetchDashboardMetrics();
      } catch {}
    } catch {}
  };

  const leadName = `${currentLead?.first_name || ''} ${currentLead?.last_name || 'Prospect'}`.trim() || 'Active Lead';
  const leadPhone = currentLead?.phone || '';

  // ── 1. MINIMIZED FLOATING PILL (Allows seamless CRM navigation) ──
  if (isMinimized && callLifecycle !== 'disposition') {
    return (
      <>
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-3 duration-200">
          <div className="bg-slate-900/95 backdrop-blur-md border border-slate-700/80 rounded-2xl shadow-2xl shadow-indigo-950/40 p-3 flex items-center gap-3 max-w-sm">
            <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 ${
              callLifecycle === 'connected'
                ? 'bg-emerald-500/15 border border-emerald-500/30 text-emerald-400'
                : 'bg-amber-500/15 border border-amber-500/30 text-amber-400 animate-pulse'
            }`}>
              <Phone className="w-4 h-4" />
            </div>

            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-1.5">
                <span className={`w-2 h-2 rounded-full ${callLifecycle === 'connected' ? 'bg-emerald-400 animate-ping' : 'bg-amber-400 animate-pulse'}`} />
                <p className="text-xs font-bold text-slate-100 truncate">{leadName}</p>
              </div>
              <p className="text-[11px] font-mono text-slate-400 truncate mt-0.5">
                {leadPhone} • <span className="text-emerald-400 font-bold">{formatDuration(callDuration)}</span>
              </p>
            </div>

            <div className="flex items-center gap-1 shrink-0">
              {callLifecycle === 'connected' && (
                <button
                  type="button"
                  onClick={toggleMute}
                  className={`p-2 rounded-xl border transition-all ${
                    isMuted
                      ? 'bg-rose-500/20 border-rose-500/40 text-rose-300'
                      : 'bg-slate-800 border-slate-700 text-slate-300 hover:text-white'
                  }`}
                  title={isMuted ? 'Unmute' : 'Mute'}
                >
                  {isMuted ? <MicOff className="w-3.5 h-3.5" /> : <Mic className="w-3.5 h-3.5" />}
                </button>
              )}

              <button
                type="button"
                onClick={() => setIsMinimized(false)}
                className="p-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl shadow-md transition-all cursor-pointer"
                title="Expand dialer"
              >
                <Maximize2 className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </div>
      </>
    );
  }

  // ── 2. FULL FLOATING CARD COMPONENT (Bottom-Right Overlay) ──
  return (
    <>
      <div className="fixed bottom-6 right-6 z-50 w-full max-w-sm sm:max-w-md animate-in slide-in-from-bottom-4 duration-200">
        <div className="bg-slate-900 border border-slate-700/90 rounded-2xl shadow-2xl shadow-slate-950/70 overflow-hidden backdrop-blur-xl ring-1 ring-slate-700/50">
          
          {/* Header Bar */}
          <div className="bg-gradient-to-r from-slate-900 via-slate-850 to-indigo-950/40 border-b border-slate-800 px-4 py-3 flex items-center justify-between gap-3">
            <div className="flex items-center gap-2.5 min-w-0">
              <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                callLifecycle === 'connected'
                  ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
                  : callLifecycle === 'disposition'
                  ? 'bg-indigo-500/20 text-indigo-400 border border-indigo-500/30'
                  : 'bg-amber-500/20 text-amber-400 border border-amber-500/30'
              }`}>
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
                  <span className={`px-1.5 py-0.5 rounded text-[9px] font-bold uppercase tracking-wider ${
                    callLifecycle === 'connected'
                      ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
                      : callLifecycle === 'disposition'
                      ? 'bg-indigo-500/10 text-indigo-400 border border-indigo-500/20'
                      : 'bg-amber-500/10 text-amber-400 border border-amber-500/20'
                  }`}>
                    {callLifecycle === 'initiating'
                      ? 'Initiating...'
                      : callLifecycle === 'ringing'
                      ? 'Ringing...'
                      : callLifecycle === 'connected'
                      ? 'Live Active'
                      : 'Wrap-Up'}
                  </span>
                  <span className="text-[10px] text-slate-400">
                    • {callDirection === 'INBOUND' ? 'Inbound' : 'Outbound'}
                  </span>
                </div>
                <h4 className="text-xs font-bold text-white truncate mt-0.5">{leadName}</h4>
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
                <span className="flex items-center gap-1 text-[10px] font-semibold text-slate-400" title="WebRTC Connected">
                  <Wifi className="w-3 h-3 text-emerald-400" />
                </span>
              )}

              {/* Minimize button (disabled during mandatory wrap-up form) */}
              {callLifecycle !== 'disposition' && (
                <button
                  type="button"
                  onClick={() => setIsMinimized(true)}
                  title="Minimize dialer"
                  className="p-1.5 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700/80 rounded-lg transition-all cursor-pointer"
                >
                  <Minus className="w-3.5 h-3.5" />
                </button>
              )}
            </div>
          </div>

          {/* Network Warning Banner */}
          {networkStatus === 'unstable' && (
            <div className="bg-amber-500/15 border-b border-amber-500/30 px-3.5 py-2 flex items-center justify-between text-amber-300 text-xs animate-in slide-in-from-top-1">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-amber-400 shrink-0 animate-pulse" />
                <span className="font-semibold text-[11px]">Network unstable. Reconnecting...</span>
              </div>
              <span className="font-mono text-xs font-bold text-amber-400">{reconnectCountdown}s</span>
            </div>
          )}

          {/* ── STATE A: INITIATING / RINGING ── */}
          {(callLifecycle === 'initiating' || callLifecycle === 'ringing') && (
            <div className="p-5 text-center space-y-4">
              <div className="relative mx-auto w-20 h-20 flex items-center justify-center">
                <div className="absolute inset-0 rounded-full border-2 border-emerald-500/20 animate-ping" />
                <div className="absolute inset-2 rounded-full border-2 border-emerald-500/40 animate-pulse" />
                <div className="w-14 h-14 rounded-full bg-emerald-500/20 border border-emerald-500/50 flex items-center justify-center text-emerald-400 shadow-lg shadow-emerald-500/20">
                  <Radio className="w-6 h-6 animate-pulse" />
                </div>
              </div>

              <div>
                <p className="text-sm font-bold text-white">{leadName}</p>
                <p className="text-xs font-mono text-slate-400 mt-0.5">{leadPhone}</p>
                <p className="text-[11px] font-medium text-emerald-400 mt-2 flex items-center justify-center gap-1.5">
                  <Loader2 className="w-3.5 h-3.5 animate-spin" />
                  {callLifecycle === 'ringing' ? 'Customer phone is ringing...' : 'Connecting softphone bridge...'}
                </p>
              </div>

              <div className="pt-2">
                <button
                  type="button"
                  onClick={cancelInitiatingCall}
                  className="w-full flex items-center justify-center gap-2 py-2.5 px-4 bg-rose-600/20 hover:bg-rose-600/30 border border-rose-500/40 text-rose-300 hover:text-white rounded-xl text-xs font-bold shadow-md transition-all cursor-pointer"
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
              <div className="text-center py-2 bg-slate-950/60 border border-slate-800/80 rounded-xl">
                <p className="text-[10px] font-bold text-slate-400 uppercase tracking-widest">Call Duration</p>
                <div className="flex items-center justify-center gap-2 mt-1">
                  <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 animate-pulse" />
                  <p className="font-mono text-2xl font-black text-emerald-400 tracking-wider">
                    {formatDuration(callDuration)}
                  </p>
                </div>
                <p className="text-xs font-mono text-slate-400 mt-1">{leadPhone}</p>
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
                      : 'bg-slate-800/90 border-slate-700/80 text-slate-300 hover:bg-slate-750 hover:text-white'
                  }`}
                >
                  {isMuted ? <MicOff className="w-4 h-4 text-rose-400" /> : <Mic className="w-4 h-4 text-slate-300" />}
                  <span>{isMuted ? 'Muted' : 'Mute'}</span>
                </button>

                {/* Keypad DTMF Toggle */}
                <button
                  type="button"
                  onClick={() => toggleKeypad()}
                  className={`flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl border text-[11px] font-semibold transition-all cursor-pointer ${
                    isKeypadOpen
                      ? 'bg-indigo-600/30 border-indigo-500/50 text-indigo-300'
                      : 'bg-slate-800/90 border-slate-700/80 text-slate-300 hover:bg-slate-750 hover:text-white'
                  }`}
                >
                  <Grid className="w-4 h-4 text-slate-300" />
                  <span>Keypad</span>
                </button>

                {/* WhatsApp Chat Button */}
                <button
                  type="button"
                  onClick={() => setShowChatDrawer(true)}
                  className="flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl border bg-slate-800/90 border-slate-700/80 text-slate-300 hover:bg-emerald-500/10 hover:border-emerald-500/30 hover:text-emerald-300 text-[11px] font-semibold transition-all cursor-pointer"
                >
                  <MessageSquare className="w-4 h-4 text-emerald-400" />
                  <span>WhatsApp</span>
                </button>

                {/* Hang Up Button */}
                <button
                  type="button"
                  onClick={hangupWebRTC}
                  className="flex flex-col items-center justify-center gap-1 py-2.5 px-2 rounded-xl bg-rose-600 hover:bg-rose-500 text-white text-[11px] font-bold shadow-lg shadow-rose-950/50 transition-all cursor-pointer"
                >
                  <PhoneOff className="w-4 h-4" />
                  <span>Hang Up</span>
                </button>
              </div>

              {/* In-Call DTMF Dialpad Drawer */}
              {isKeypadOpen && (
                <div className="p-3 bg-slate-950/80 border border-slate-800 rounded-xl space-y-2 animate-in fade-in zoom-in-95 duration-150">
                  <div className="flex items-center justify-between text-xs text-slate-400 px-1">
                    <span className="font-semibold uppercase tracking-wider text-[10px]">DTMF Keypad</span>
                    <button
                      type="button"
                      onClick={() => toggleKeypad(false)}
                      className="p-1 hover:text-white rounded"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                  <div className="grid grid-cols-3 gap-1.5">
                    {[
                      { key: '1', sub: '' },
                      { key: '2', sub: 'ABC' },
                      { key: '3', sub: 'DEF' },
                      { key: '4', sub: 'GHI' },
                      { key: '5', sub: 'JKL' },
                      { key: '6', sub: 'MNO' },
                      { key: '7', sub: 'PQRS' },
                      { key: '8', sub: 'TUV' },
                      { key: '9', sub: 'WXYZ' },
                      { key: '*', sub: '' },
                      { key: '0', sub: '+' },
                      { key: '#', sub: '' },
                    ].map((btn) => (
                      <button
                        key={btn.key}
                        type="button"
                        onClick={() => sendDTMF(btn.key)}
                        className="py-2.5 bg-slate-800/90 hover:bg-indigo-600 hover:text-white border border-slate-700/80 active:scale-95 text-slate-200 rounded-xl font-bold transition-all flex flex-col items-center justify-center cursor-pointer"
                      >
                        <span className="text-sm leading-none">{btn.key}</span>
                        {btn.sub && <span className="text-[8px] text-slate-400 font-normal mt-0.5">{btn.sub}</span>}
                      </button>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}

          {/* ── STATE C: POST-CALL WRAP-UP & DISPOSITION FORM ── */}
          {callLifecycle === 'disposition' && (
            <form onSubmit={handleFormSubmit} className="p-4 sm:p-5 space-y-3.5 max-h-[75vh] overflow-y-auto">
              <div className="flex items-center justify-between pb-2 border-b border-slate-800">
                <div>
                  <h5 className="text-xs font-bold text-white uppercase tracking-wider flex items-center gap-1.5">
                    <CheckCircle className="w-3.5 h-3.5 text-emerald-400" />
                    Call Summary & Wrap-Up
                  </h5>
                  <p className="text-[11px] text-slate-400 mt-0.5">
                    Duration: <span className="font-mono text-emerald-400 font-bold">{formatDuration(callDuration)}</span> • {callDirection}
                  </p>
                </div>
                <span className="text-[10px] font-semibold text-rose-400 bg-rose-500/10 px-2 py-0.5 rounded border border-rose-500/20">
                  Required
                </span>
              </div>

              {error && (
                <div className="flex items-center gap-2 p-2.5 bg-rose-500/10 border border-rose-500/20 text-rose-300 rounded-xl text-xs">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  <p>{error}</p>
                </div>
              )}

              {/* Call Status Dropdown */}
              <div>
                <label className="block text-[11px] font-bold text-slate-300 mb-1 uppercase tracking-wider">
                  Call Status <span className="text-rose-400">*</span>
                </label>
                <select
                  value={callStatus}
                  onChange={(e) => setCallStatus(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-xl py-2 px-3 text-xs focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="Answered">Answered</option>
                  <option value="Busy">Busy</option>
                  <option value="No Answer">No Answer</option>
                  <option value="Wrong Number">Wrong Number</option>
                  <option value="Switched Off">Switched Off</option>
                </select>
              </div>

              {/* Disposition Category Dropdown */}
              <div>
                <label className="block text-[11px] font-bold text-slate-300 mb-1 uppercase tracking-wider">
                  Disposition Category <span className="text-rose-400">*</span>
                </label>
                <select
                  value={dispositionCategory}
                  onChange={(e) => setDispositionCategory(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-xl py-2 px-3 text-xs focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="Interested">Interested</option>
                  <option value="Not Interested">Not Interested</option>
                  <option value="Callback Requested">Callback Requested</option>
                  <option value="Follow-up Scheduled">Follow-up Scheduled</option>
                </select>
              </div>

              {/* Conditional Follow-up Date/Time Picker */}
              {isFollowUp && (
                <div className="p-3 bg-indigo-950/30 border border-indigo-500/30 rounded-xl space-y-2.5 animate-in fade-in duration-200">
                  <p className="text-[11px] font-bold text-indigo-300 flex items-center gap-1.5 uppercase tracking-wider">
                    <Calendar className="w-3.5 h-3.5 text-indigo-400" />
                    Schedule Callback / Follow-Up <span className="text-rose-400">*</span>
                  </p>
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">Date *</label>
                      <input
                        type="date"
                        value={followUpDate}
                        onChange={(e) => setFollowUpDate(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg py-1.5 px-2.5 text-xs focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>
                    <div>
                      <label className="block text-[10px] text-slate-400 mb-1">Time *</label>
                      <input
                        type="time"
                        value={followUpTime}
                        onChange={(e) => setFollowUpTime(e.target.value)}
                        className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg py-1.5 px-2.5 text-xs focus:ring-1 focus:ring-indigo-500"
                      />
                    </div>
                  </div>
                  <div>
                    <label className="block text-[10px] text-slate-400 mb-1">Priority</label>
                    <select
                      value={followUpPriority}
                      onChange={(e) => setFollowUpPriority(e.target.value as any)}
                      className="w-full bg-slate-800 border border-slate-700 text-white rounded-lg py-1.5 px-2.5 text-xs focus:ring-1 focus:ring-indigo-500"
                    >
                      <option value="Low">Low</option>
                      <option value="Medium">Medium</option>
                      <option value="High">High</option>
                      <option value="Urgent">Urgent</option>
                    </select>
                  </div>
                </div>
              )}

              {/* Advance Stage Selection (Optional) */}
              <div>
                <label className="block text-[11px] font-bold text-slate-300 mb-1 uppercase tracking-wider">
                  Advance Stage (Optional)
                </label>
                <select
                  value={targetStageId}
                  onChange={(e) => setTargetStageId(e.target.value)}
                  className="w-full bg-slate-800 border border-slate-700 text-slate-100 rounded-xl py-2 px-3 text-xs focus:ring-1 focus:ring-indigo-500"
                >
                  <option value="">-- Keep Current Stage --</option>
                  {stages.map((stage) => (
                    <option key={stage.id} value={stage.id}>
                      {stage.name}
                    </option>
                  ))}
                </select>
              </div>

              {/* Notes & Remarks */}
              <div>
                <label className="block text-[11px] font-bold text-slate-300 mb-1 uppercase tracking-wider">
                  Call Notes & Remarks <span className="text-rose-400">*</span>
                </label>
                <textarea
                  rows={2}
                  value={remarks}
                  onChange={(e) => setRemarks(e.target.value)}
                  placeholder="Summarize client feedback, action items, or discussion..."
                  className="w-full bg-slate-800 border border-slate-700 text-slate-100 placeholder-slate-500 rounded-xl py-2 px-3 text-xs focus:ring-1 focus:ring-indigo-500 resize-none"
                />
              </div>

              {/* Submit Disposition */}
              <button
                type="submit"
                disabled={!remarks.trim() || followUpIncomplete || isLoading}
                className="w-full py-2.5 px-4 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold rounded-xl shadow-lg shadow-emerald-950/40 text-xs flex items-center justify-center gap-1.5 transition-all cursor-pointer"
              >
                <CheckCircle className="w-4 h-4" />
                {isLoading ? 'Saving Disposition...' : 'Submit Disposition & Complete'}
              </button>
            </form>
          )}
        </div>
      </div>

      <OmniChannelChatDrawer
        lead={currentLead}
        isOpen={showChatDrawer}
        onClose={() => setShowChatDrawer(false)}
        initialChannel="whatsapp"
      />
    </>
  );
};
