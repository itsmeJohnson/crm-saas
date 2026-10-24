import React, { useEffect, useState } from 'react';
import { 
  Phone, 
  Coffee, 
  Play, 
  CheckCircle, 
  AlertCircle, 
  Clock, 
  Building, 
  FileText,
  UserCheck,
  LogOut,
  MessageCircle,
  History,
  Sparkles,
  ChevronDown,
  ChevronUp,
  PhoneOff,
  Mic,
  MicOff,
  Headphones
} from 'lucide-react';
import { useDialerStore } from '../../store/dialerStore';
import { usePipelineStore } from '../../store/pipelineStore';
import { MaskedField } from '../common/MaskedField';
import { useDashboardStore } from '../../store/dashboardStore';
import { useAnalyticsStore } from '../../store/analyticsStore';
import { dashboardApi } from '../../services/dashboardApi';
import { OmniChannelChatDrawer } from '../crm/OmniChannelChatDrawer';
import { leadApi, LeadTimelineEvent } from '../../services/leadApi';
import { dialerApi } from '../../services/dialerApi';
import { useUserStore } from '../../store/userStore';

export const DialerConsole: React.FC = () => {
  const {
    agentState,
    currentLead,
    breakReason,
    callDuration,
    stateTimestamp,
    isLoading,
    error,
    callDirection,
    fetchCurrentState,
    startCalling,
    submitDisposition,
    goOnBreak,
    endBreak,
    webrtcStatus,
    isMuted,
    initWebRTC,
    toggleMute,
    hangupWebRTC
  } = useDialerStore();

  const { stages, fetchStages } = usePipelineStore();

  // Local state for break countdown (15 minutes = 900 seconds)
  const [breakTimeRemaining, setBreakTimeRemaining] = useState(900);
  // Local state for disposition form
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);
  const [remarks, setRemarks] = useState('');
  const [targetStageId, setTargetStageId] = useState('');
  // Follow-up scheduling (shown when outcome needs a next touch — Phase 1)
  const [followUpDate, setFollowUpDate] = useState('');
  const [followUpTime, setFollowUpTime] = useState('');
  const [reminderEnabled, setReminderEnabled] = useState(true);
  const [reminderBefore, setReminderBefore] = useState(30); // minutes
  const [followUpPriority, setFollowUpPriority] = useState('Medium');
  const [collectivePooling, setCollectivePooling] = useState(() => {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('crm_collective_pooling');
      return saved !== null ? saved === 'true' : false;
    }
    return false;
  });
  const [showBreakMenu, setShowBreakMenu] = useState(false);
  const [showChatDrawer, setShowChatDrawer] = useState(false);

  const [autoDial, setAutoDial] = useState(() => {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('crm_auto_dial');
      return saved !== null ? saved === 'true' : true;
    }
    return true;
  });
  // Power dialer: seconds until the next auto-dial fires (null = no pending call)
  const [nextCallCountdown, setNextCallCountdown] = useState<number | null>(null);
  const [powerDelay, setPowerDelay] = useState(() => {
    if (typeof localStorage !== 'undefined') {
      const saved = parseInt(localStorage.getItem('crm_power_dialer_delay') || '', 10);
      if (!isNaN(saved) && saved > 0) return saved;
    }
    return 5;
  });
  const [pendingBreakReason, setPendingBreakReason] = useState<string | null>(null);
  const [showActiveBreakMenu, setShowActiveBreakMenu] = useState(false);

  // Lead Timeline & Conversation History state
  const { users, fetchUsers } = useUserStore();
  const [timelineEvents, setTimelineEvents] = useState<LeadTimelineEvent[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);
  const [historyFilterDays, setHistoryFilterDays] = useState<7 | 30 | 'all'>(7);
  const [showAllHistory, setShowAllHistory] = useState(false);

  useEffect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_collective_pooling', String(collectivePooling));
    }
  }, [collectivePooling]);

  useEffect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_auto_dial', String(autoDial));
    }
  }, [autoDial]);

  useEffect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_power_dialer_delay', String(powerDelay));
    }
  }, [powerDelay]);

  // Power-dialer countdown: tick down each second, fire the next call at zero.
  useEffect(() => {
    if (nextCallCountdown === null) return;
    if (nextCallCountdown <= 0) {
      setNextCallCountdown(null);
      if (useDialerStore.getState().agentState === 'IDLE') {
        handleStartDialing();
      }
      return;
    }
    const timer = setTimeout(() => {
      setNextCallCountdown((c) => (c === null ? null : c - 1));
    }, 1000);
    return () => clearTimeout(timer);
  }, [nextCallCountdown]);

  // Fetch initial dialer and pipeline stage details on mount
  useEffect(() => {
    fetchCurrentState().catch(() => {});
    fetchStages().catch(() => {});
    initWebRTC().catch(() => {});
  }, [fetchCurrentState, fetchStages, initWebRTC]);

  // Interval for break countdown
  useEffect(() => {
    let interval: any = null;
    if (agentState === 'BREAK') {
      const updateBreakTime = () => {
        if (stateTimestamp) {
          const elapsed = Math.floor((Date.now() - new Date(stateTimestamp).getTime()) / 1000);
          setBreakTimeRemaining(Math.max(0, 900 - elapsed));
        } else {
          setBreakTimeRemaining(900);
        }
      };
      
      updateBreakTime();
      interval = setInterval(updateBreakTime, 1000);
    } else {
      setBreakTimeRemaining(900);
      if (interval) clearInterval(interval);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [agentState, stateTimestamp]);

  // Fetch users list for resolving agent names
  useEffect(() => {
    if (users.length === 0) fetchUsers();
  }, []);

  // Fetch timeline whenever current lead changes
  useEffect(() => {
    if (!currentLead?.id) {
      setTimelineEvents([]);
      return;
    }
    let isMounted = true;
    setTimelineLoading(true);
    leadApi.getTimeline(currentLead.id)
      .then((data) => {
        if (isMounted) setTimelineEvents(data);
      })
      .catch((err) => {
        console.warn('Could not fetch lead timeline in dialer console:', err);
      })
      .finally(() => {
        if (isMounted) setTimelineLoading(false);
      });

    return () => {
      isMounted = false;
    };
  }, [currentLead?.id]);

  // Reset form inputs when current lead changes
  useEffect(() => {
    if (!currentLead) {
      setSelectedStatus(null);
      setRemarks('');
      setTargetStageId('');
      setPendingBreakReason(null);
      setShowActiveBreakMenu(false);
    }
  }, [currentLead]);

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const resolveActorName = (actorId: string | null) => {
    if (!actorId) return null;
    const u = users.find((x) => x.id === actorId);
    return u ? (`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email) : null;
  };

  const formatEventTime = (iso?: string) => {
    if (!iso) return '';
    const d = new Date(iso);
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
    
    const timeStr = d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
    if (diffDays === 0) return `Today at ${timeStr}`;
    if (diffDays === 1) return `Yesterday at ${timeStr}`;
    if (diffDays < 7) return `${diffDays}d ago at ${timeStr}`;
    return `${d.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' })} at ${timeStr}`;
  };

  const callHistoryEvents = timelineEvents.filter(
    (ev) => ev.type === 'activity' && (ev.title.toLowerCase().includes('call') || (ev.event_metadata as any)?.activity_type === 'Call')
  );

  const totalCallTouches = callHistoryEvents.length;
  const isFreshLead = totalCallTouches === 0 && (currentLead?.status === 'New' || !currentLead?.status);
  const latestPriorCall = callHistoryEvents[0];

  const filteredHistoryEvents = timelineEvents.filter((ev) => {
    if (historyFilterDays === 'all') return true;
    const cutoff = Date.now() - historyFilterDays * 24 * 60 * 60 * 1000;
    return new Date(ev.timestamp).getTime() >= cutoff;
  });

  const visibleHistoryEvents = showAllHistory
    ? filteredHistoryEvents
    : filteredHistoryEvents.slice(0, 3);



  const handleToggleCollectivePooling = (checked: boolean) => {
    setCollectivePooling(checked);
    try {
      localStorage.setItem('crm_collective_pooling', String(checked));
    } catch {}
    dialerApi.updateState({
      state: agentState,
      metadata: { collective_pooling: checked }
    }).catch(() => {});
  };

  const handleStartDialing = async () => {
    setNextCallCountdown(null);
    try {
      // Credentials are org-level (Settings → Communication → Calling) and applied
      // server-side. Agents never send them.
      await startCalling(collectivePooling);
    } catch (err: any) {
      console.warn('[Power Dialer] Auto-dial sequence handled:', err?.message || err);
    }
  };

  const handleRequestBreak = async (reason: string) => {
    setNextCallCountdown(null);
    try {
      await goOnBreak(reason);
      setShowBreakMenu(false);
    } catch (err) {}
  };

  const handleEndBreak = async () => {
    try {
      await endBreak();
    } catch (err) {}
  };

  const handleDispositionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const isStageRequired = (selectedStatus === 'Picked' || selectedStatus === 'Interested') && stages.length > 0;
    const isStageAllowed = ['Picked', 'Interested', 'Answered / Resolved', 'Callback Requested'].includes(selectedStatus || '');
    const followUp = selectedStatus === 'Follow-up' || selectedStatus === 'Call Back Later';
    if (!selectedStatus || !remarks.trim() || (isStageRequired && !targetStageId) || (followUp && (!followUpDate || !followUpTime))) {
      return;
    }
    const breakReasonToApply = pendingBreakReason;
    try {
      if (followUp && currentLead?.id) {
        // Schedule the next follow-up in place: creates task + reminder + timeline
        // + activity + calendar + notifies employee/manager (backend orchestration).
        const nextAt = new Date(`${followUpDate}T${followUpTime}`).toISOString();
        // Backend priority vocabulary is Low|Medium|High|Urgent; "Critical" maps to Urgent.
        const priority = followUpPriority === 'Critical' ? 'Urgent' : followUpPriority;
        await dashboardApi.logFollowUp(currentLead.id, {
          outcome: selectedStatus,
          follow_up_type: 'call',
          remarks,
          next_follow_up_at: nextAt,
          priority,
          reminder_minutes_before: reminderEnabled ? reminderBefore : null,
        });
        // reset follow-up fields
        setFollowUpDate(''); setFollowUpTime(''); setReminderEnabled(true);
        setReminderBefore(30); setFollowUpPriority('Medium');
      }

      // Always submit call disposition outcome to backend
      await submitDisposition({
        status: selectedStatus,
        remarks: remarks,
        custom_pipeline_stage_id: isStageAllowed ? (targetStageId || undefined) : undefined
      });

      // Clear disposition form fields for the next call
      setSelectedStatus(null);
      setRemarks('');
      setTargetStageId('');

      // Refresh dashboard data instantly on submission
      try {
        useDashboardStore.getState().fetchSummary();
        useDashboardStore.getState().fetchRecentActivities();
        useAnalyticsStore.getState().fetchDashboardMetrics();
      } catch (dashErr) {}

      if (breakReasonToApply) {
        setPendingBreakReason(null);
        await goOnBreak(breakReasonToApply);
      } else if (autoDial) {
        // Power dialer: visible countdown to the next call instead of an instant redial
        setNextCallCountdown(powerDelay);
      }
    } catch (err: any) {
      console.error('Failed to submit disposition:', err);
    }
  };

  const breakOptions = ['Lunch', 'Tea', 'Meeting', 'General'];
  const dispositionOptions = callDirection === 'INBOUND'
    ? ['Answered / Resolved', 'Callback Requested', 'Interested', 'Not Interested', 'Spam / Junk']
    : ['RNR', 'Switch Off', 'Busy', 'Not Exist', 'Out of Service', 'Picked', 'Interested', 'Follow-up', 'Call Back Later'];

  // Outcomes that imply a next touch — the cockpit schedules the follow-up in place.
  const isFollowUpOutcome = selectedStatus === 'Follow-up' || selectedStatus === 'Call Back Later';
  const isStageRequired = (selectedStatus === 'Picked' || selectedStatus === 'Interested') && stages.length > 0;
  const followUpIncomplete = isFollowUpOutcome && (!followUpDate || !followUpTime);
  const isSubmitDisabled = !selectedStatus || !remarks.trim() || (isStageRequired && !targetStageId) || followUpIncomplete || isLoading;

  return (
    <div className="max-w-6xl mx-auto p-6 space-y-6">
      {/* Error alert banner */}
      {error && (
        <div className="flex items-center gap-3 p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl animate-fade-in">
          <AlertCircle className="w-5 h-5 flex-shrink-0" />
          <p className="text-sm font-medium">{error}</p>
        </div>
      )}

      {/* Main Split-Pane Workspace */}
      <div className="grid grid-cols-1 md:grid-cols-12 gap-6 items-start">
         {/* LEFT CONTROL PANEL (Cols 1-5) */}
        <div className="md:col-span-5 space-y-6">
          <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-6 shadow-sm space-y-6">
            <div className="flex items-center justify-between border-b border-slate-200 dark:border-slate-800 pb-4">
              <h2 className="text-lg font-bold text-slate-900 dark:text-slate-100 flex items-center gap-2">
                <Clock className="w-5 h-5 text-indigo-600 dark:text-indigo-400" />
                Agent Console
              </h2>
              <span className={`px-3 py-1 rounded-full text-xs font-semibold tracking-wider border ${
                agentState === 'IDLE' ? 'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700' :
                agentState === 'ACTIVE_CALLING' ? 'bg-indigo-50 dark:bg-indigo-950/60 text-indigo-700 dark:text-indigo-300 border-indigo-200 dark:border-indigo-800' :
                'bg-slate-100 dark:bg-slate-800 text-slate-700 dark:text-slate-300 border-slate-200 dark:border-slate-700'
              }`}>
                {agentState}
              </span>
            </div>

            {/* Layout based on Agent State */}
            {agentState === 'IDLE' && (
              <div className="space-y-6 py-4">
                {/* Power-dialer countdown to the next auto-dialed call */}
                {nextCallCountdown !== null && (
                  <div className="flex items-center justify-between bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 p-4 rounded-xl animate-fade-in">
                    <span className="text-sm font-semibold flex items-center gap-2">
                      <Phone className="w-4 h-4 animate-pulse text-indigo-600" />
                      Power dialer: next call in {nextCallCountdown}s
                    </span>
                    <button
                      type="button"
                      onClick={() => setNextCallCountdown(null)}
                      className="text-xs font-semibold text-slate-700 dark:text-slate-200 hover:text-slate-900 bg-white dark:bg-slate-800 hover:bg-slate-50 border border-slate-200 dark:border-slate-700 px-3 py-1.5 rounded-lg shadow-xs transition-colors cursor-pointer"
                    >
                      Stop
                    </button>
                  </div>
                )}
                <div className="space-y-3">
                  <div className="flex items-center gap-3 bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl border border-slate-200 dark:border-slate-700">
                    <input
                      id="collective-pooling"
                      type="checkbox"
                      checked={collectivePooling}
                      onChange={(e) => handleToggleCollectivePooling(e.target.checked)}
                      className="w-4 h-4 text-indigo-600 bg-white border-slate-300 rounded focus:ring-indigo-500"
                    />
                    <label htmlFor="collective-pooling" className="text-sm text-slate-800 dark:text-slate-200 font-medium cursor-pointer select-none">
                      Enable Collective Pooling (fetch from TL pool)
                    </label>
                  </div>

                  <div className="flex items-center gap-3 bg-slate-50 dark:bg-slate-800/50 p-4 rounded-xl border border-slate-200 dark:border-slate-700">
                    <input
                      id="auto-dial"
                      type="checkbox"
                      checked={autoDial}
                      onChange={(e) => setAutoDial(e.target.checked)}
                      className="w-4 h-4 text-indigo-600 bg-white border-slate-300 rounded focus:ring-indigo-500"
                    />
                    <label htmlFor="auto-dial" className="text-sm text-slate-800 dark:text-slate-200 font-medium cursor-pointer select-none flex-1">
                      Power Dialer (auto-dial next lead)
                    </label>
                    {autoDial && (
                      <select
                        aria-label="Power dialer delay"
                        value={powerDelay}
                        onChange={(e) => setPowerDelay(parseInt(e.target.value, 10))}
                        className="bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-800 dark:text-slate-200 text-xs py-1.5 px-2 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value={3}>3s gap</option>
                        <option value={5}>5s gap</option>
                        <option value={10}>10s gap</option>
                        <option value={15}>15s gap</option>
                      </select>
                    )}
                  </div>
                </div>

                <button
                  onClick={handleStartDialing}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold py-3 px-4 rounded-xl shadow-xs transition-all duration-150 transform active:scale-[0.98] disabled:opacity-50 cursor-pointer"
                >
                  <Play className="w-5 h-5" />
                  Start Dialing Session
                </button>

                <div className="relative border-t border-slate-200 dark:border-slate-800 pt-4">
                  <button
                    onClick={() => setShowBreakMenu(!showBreakMenu)}
                    disabled={isLoading}
                    className="w-full flex items-center justify-center gap-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold py-2.5 px-4 rounded-xl transition-all duration-150 border border-slate-200 dark:border-slate-700 shadow-xs cursor-pointer"
                  >
                    <Coffee className="w-4 h-4 text-slate-500" />
                    Request Break
                  </button>

                  {showBreakMenu && (
                    <div className="absolute left-0 right-0 mt-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg overflow-hidden z-20 animate-fade-in">
                      {breakOptions.map((opt) => (
                        <button
                          key={opt}
                          onClick={() => handleRequestBreak(opt)}
                          className="w-full text-left px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors duration-150 cursor-pointer"
                        >
                          {opt} Break
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </div>
            )}

            {agentState === 'BREAK' && (
              <div className="space-y-6 py-4 text-center">
                <div className="inline-flex items-center justify-center p-4 bg-indigo-50 border border-indigo-200 rounded-full text-indigo-600 mb-2">
                  <Coffee className="w-10 h-10" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-100">{breakReason} Break</h3>
                  <p className="text-sm text-slate-400 mt-1">Break countdown remaining</p>
                </div>

                <div className="text-4xl font-mono font-bold text-slate-100 bg-slate-950 border border-slate-800 rounded-2xl py-4 max-w-[200px] mx-auto tracking-wider shadow-xs">
                  {formatDuration(breakTimeRemaining)}
                </div>

                <button
                  onClick={handleEndBreak}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 bg-slate-900 hover:bg-slate-950 text-slate-200 font-semibold py-3 px-4 rounded-xl transition-all duration-150 border border-slate-800 shadow-xs cursor-pointer"
                >
                  <LogOut className="w-4 h-4 text-slate-400" />
                  End Break
                </button>
              </div>
            )}

            {agentState === 'ACTIVE_CALLING' && (
              <div className="space-y-6 py-4 text-center">
                <div className="inline-flex items-center justify-center p-4 bg-indigo-50 border border-indigo-200 rounded-full text-indigo-600 mb-2 animate-pulse">
                  <Phone className="w-10 h-10" />
                </div>
                <div>
                  <div className="flex items-center justify-center gap-2 mb-1.5">
                    <span className="px-2.5 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider border bg-indigo-50 text-indigo-700 border-indigo-200">
                      {callDirection === 'INBOUND' ? 'Inbound Customer Call' : 'Outbound Dial'}
                    </span>
                  </div>
                  <h3 className="text-xl font-bold text-slate-100">Live Call Active</h3>
                  <p className="text-xs text-slate-400 mt-1">Do not close this panel during call</p>
                </div>

                <div className="text-4xl font-mono font-bold text-slate-100 bg-slate-950 border border-slate-800 rounded-2xl py-4 max-w-[200px] mx-auto tracking-wider shadow-xs">
                  {formatDuration(callDuration)}
                </div>

                {/* Embedded WebRTC In-Browser Audio Controls */}
                <div className="p-3.5 bg-slate-950 border border-slate-800 rounded-xl space-y-3">
                  <div className="flex items-center justify-between text-xs">
                    <span className="flex items-center gap-1.5 text-slate-300 font-semibold">
                      <Headphones className="w-3.5 h-3.5 text-indigo-600" />
                      Browser Softphone
                    </span>
                    <span className={`px-2 py-0.5 rounded-full font-semibold uppercase text-[10px] tracking-wider border ${
                      webrtcStatus === 'connected' ? 'bg-emerald-50 dark:bg-emerald-950/40 text-emerald-700 dark:text-emerald-300 border-emerald-200 dark:border-emerald-800 animate-pulse' :
                      webrtcStatus === 'ringing' ? 'bg-indigo-50 text-indigo-700 border-indigo-200 animate-pulse' :
                      webrtcStatus === 'calling' ? 'bg-indigo-50 text-indigo-700 border-indigo-200' :
                      'bg-slate-100 text-slate-600 border-slate-200'
                    }`}>
                      {webrtcStatus === 'connected' ? 'Audio Live' :
                       webrtcStatus === 'ringing' ? 'Ringing Remote' :
                       webrtcStatus === 'calling' ? 'Connecting...' :
                       webrtcStatus === 'ended' ? 'Call Ended' : 'Ready'}
                    </span>
                  </div>

                  <div className="flex items-center justify-center gap-3 pt-1">
                    <button
                      type="button"
                      onClick={toggleMute}
                      className={`flex items-center gap-1.5 px-3 py-2 rounded-lg text-xs font-semibold transition-colors cursor-pointer border ${
                        isMuted
                          ? 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800'
                          : 'bg-white dark:bg-slate-800 text-slate-700 dark:text-slate-200 border-slate-200 dark:border-slate-700 hover:bg-slate-50 shadow-xs'
                      }`}
                    >
                      {isMuted ? <MicOff className="w-4 h-4 text-rose-600" /> : <Mic className="w-4 h-4 text-slate-600 dark:text-slate-300" />}
                      {isMuted ? 'Unmute Mic' : 'Mute Mic'}
                    </button>

                    <button
                      type="button"
                      onClick={hangupWebRTC}
                      className="flex items-center gap-1.5 px-3.5 py-2 rounded-lg text-xs font-semibold bg-rose-600 hover:bg-rose-700 active:bg-rose-800 text-white transition-colors cursor-pointer shadow-xs"
                    >
                      <PhoneOff className="w-4 h-4" />
                      Hang Up
                    </button>
                  </div>
                </div>

                {/* Queue Break option during active call */}
                <div className="relative border-t border-slate-200 dark:border-slate-800 pt-4 mt-4">
                  {pendingBreakReason ? (
                    <div className="flex items-center justify-between bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300 p-3 rounded-xl">
                      <span className="text-sm font-medium flex items-center gap-1.5">
                        <Coffee className="w-4 h-4 text-indigo-600" />
                        Pending Break: {pendingBreakReason}
                      </span>
                      <button
                        type="button"
                        onClick={() => setPendingBreakReason(null)}
                        className="text-xs text-slate-500 hover:text-slate-800 dark:hover:text-slate-200 transition-colors underline cursor-pointer"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => setShowActiveBreakMenu(!showActiveBreakMenu)}
                        className="w-full flex items-center justify-center gap-2 bg-white dark:bg-slate-800 hover:bg-slate-50 dark:hover:bg-slate-700 text-slate-700 dark:text-slate-200 font-semibold py-2.5 px-4 rounded-xl transition-all duration-150 border border-slate-200 dark:border-slate-700 shadow-xs cursor-pointer"
                      >
                        <Coffee className="w-4 h-4 text-slate-500" />
                        Take Break After Call
                      </button>

                      {showActiveBreakMenu && (
                        <div className="absolute left-0 right-0 mt-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl shadow-lg overflow-hidden z-20 animate-fade-in">
                          {breakOptions.map((opt) => (
                            <button
                              key={opt}
                              type="button"
                              onClick={() => {
                                setPendingBreakReason(opt);
                                setShowActiveBreakMenu(false);
                              }}
                              className="w-full text-left px-4 py-2.5 text-sm text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 transition-colors duration-150 cursor-pointer"
                            >
                              {opt} Break
                            </button>
                          ))}
                        </div>
                      )}
                    </>
                  )}
                </div>
              </div>
            )}
          </div>
        </div>

        {/* RIGHT CONTEXT PANEL (Cols 6-12) */}
        <div className="md:col-span-7">
          {agentState !== 'ACTIVE_CALLING' ? (
            <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-2xl p-12 text-center shadow-xs">
              <div className="w-14 h-14 rounded-2xl bg-indigo-50 dark:bg-indigo-950/40 border border-indigo-200 dark:border-indigo-800 text-indigo-600 dark:text-indigo-400 flex items-center justify-center mx-auto mb-4">
                <Phone className="w-6 h-6" />
              </div>
              <h3 className="text-slate-900 dark:text-slate-100 font-bold text-lg">No Active Session</h3>
              <p className="text-slate-500 dark:text-slate-400 text-sm mt-1 max-w-sm mx-auto">
                Ready your headpieces, configure collective settings, and click "Start Dialing Session" on the left to push your next assigned lead.
              </p>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-sm overflow-hidden animate-fade-in">
              {/* Lead Details Banner */}
              <div className="bg-slate-950/60 border-b border-slate-800 p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <div className="flex items-center gap-2 mb-1">
                      <span className="text-xs font-bold text-indigo-600 uppercase tracking-wider">Active Lead Context</span>
                      {isFreshLead ? (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-emerald-50 text-emerald-700 border border-emerald-200">
                          <Sparkles className="w-3 h-3" />
                          Fresh Lead • 1st Call
                        </span>
                      ) : (
                        <span className="inline-flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[10px] font-bold bg-indigo-50 text-indigo-700 border border-indigo-200">
                          <History className="w-3 h-3" />
                          Follow-Up Call • Attempt #{totalCallTouches + 1}
                        </span>
                      )}
                    </div>
                    <h3 className="text-2xl font-bold text-slate-100 mt-1">
                      {currentLead?.first_name || currentLead?.last_name
                        ? `${currentLead?.first_name || ''} ${currentLead?.last_name || ''}`.trim()
                        : 'Active Call Connected'}
                    </h3>
                    <p className="text-sm text-slate-400 mt-1 flex items-center gap-1.5">
                      <Building className="w-4 h-4 text-slate-400" />
                      {currentLead?.title || currentLead?.company_name
                        ? `${currentLead?.title || ''} ${currentLead?.company_name ? `at ${currentLead?.company_name}` : ''}`.trim()
                        : 'In-progress call session'}
                    </p>
                  </div>
                  
                  {/* Phone & WhatsApp / Document collection trigger */}
                  <div className="flex items-center gap-2">
                    <div className="bg-slate-900 border border-slate-800 px-3.5 py-2 rounded-xl flex items-center gap-2 text-slate-100 font-mono text-xs shadow-xs">
                      <MaskedField value={currentLead?.phone || null} />
                    </div>
                    {currentLead?.phone && (
                      <button
                        type="button"
                        onClick={() => setShowChatDrawer(true)}
                        className="flex items-center gap-1.5 bg-indigo-600 hover:bg-indigo-700 text-white px-3.5 py-2 rounded-xl text-xs font-semibold shadow-xs transition cursor-pointer"
                        title="Open WhatsApp chat & collect documents"
                      >
                        <MessageCircle className="w-4 h-4" />
                        <span className="hidden sm:inline">WhatsApp &amp; Docs</span>
                      </button>
                    )}
                  </div>
                </div>
              </div>

              {/* Previous Conversations & Lead History Section */}
              <div className="border-b border-slate-800 bg-slate-900 p-6 space-y-4">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <History className="w-4 h-4 text-indigo-600" />
                    <h4 className="text-sm font-bold text-slate-100 uppercase tracking-wider">
                      Previous Conversations &amp; Customer History
                    </h4>
                    <span className="text-[11px] font-semibold px-2 py-0.5 rounded-full bg-slate-950 text-slate-300 border border-slate-800">
                      {timelineEvents.length} {timelineEvents.length === 1 ? 'interaction' : 'interactions'}
                    </span>
                  </div>

                  {/* Filter range buttons (7 days, 30 days, all) */}
                  <div className="flex items-center gap-1 bg-slate-950 p-1 rounded-lg border border-slate-800">
                    <button
                      type="button"
                      onClick={() => setHistoryFilterDays(7)}
                      className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer ${
                        historyFilterDays === 7
                          ? 'bg-indigo-600 text-white shadow-xs'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Last 7 Days
                    </button>
                    <button
                      type="button"
                      onClick={() => setHistoryFilterDays(30)}
                      className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer ${
                        historyFilterDays === 30
                          ? 'bg-indigo-600 text-white shadow-xs'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      Last 30 Days
                    </button>
                    <button
                      type="button"
                      onClick={() => setHistoryFilterDays('all')}
                      className={`px-2.5 py-1 text-xs font-semibold rounded-md transition-colors cursor-pointer ${
                        historyFilterDays === 'all'
                          ? 'bg-indigo-600 text-white shadow-xs'
                          : 'text-slate-400 hover:text-slate-200'
                      }`}
                    >
                      All History
                    </button>
                  </div>
                </div>

                {/* Status Guidance Banner */}
                {isFreshLead ? (
                  <div className="bg-emerald-50 dark:bg-emerald-950/30 border border-emerald-200 dark:border-emerald-800/40 rounded-xl p-3.5 flex items-start gap-3">
                    <Sparkles className="w-5 h-5 text-emerald-600 dark:text-emerald-400 flex-shrink-0 mt-0.5" />
                    <div>
                      <p className="text-xs font-bold text-emerald-800 dark:text-emerald-300">Fresh Lead • First-Time Call</p>
                      <p className="text-xs text-emerald-700/80 dark:text-emerald-300/80 mt-0.5">
                        This customer has not been contacted before. Introduce the company, verify their interest, and record their response below.
                      </p>
                    </div>
                  </div>
                ) : (
                  <div className="bg-indigo-50/60 dark:bg-indigo-950/30 border border-indigo-200/80 dark:border-indigo-800/40 rounded-xl p-3.5 flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="inline-flex items-center gap-1 text-xs font-bold px-2 py-0.5 rounded bg-indigo-100 dark:bg-indigo-900/50 text-indigo-700 dark:text-indigo-300 border border-indigo-200 dark:border-indigo-700">
                        Follow-Up Call • Attempt #{totalCallTouches + 1}
                      </span>
                      {latestPriorCall && (
                        <span className="text-xs text-slate-700 dark:text-slate-300">
                          Last called {formatEventTime(latestPriorCall.timestamp)}
                          {resolveActorName(latestPriorCall.actor_user_id) && ` by ${resolveActorName(latestPriorCall.actor_user_id)}`}
                        </span>
                      )}
                    </div>
                    {latestPriorCall?.description && (
                      <span className="text-xs text-indigo-700 dark:text-indigo-300 italic truncate max-w-md">
                        "{latestPriorCall.description.split('\n')[0]}"
                      </span>
                    )}
                  </div>
                )}

                {/* Timeline Feed */}
                {timelineLoading ? (
                  <div className="py-6 text-center text-xs text-slate-500">Loading conversation history...</div>
                ) : filteredHistoryEvents.length === 0 ? (
                  <div className="bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-700 rounded-xl p-4 text-center">
                    <p className="text-xs text-slate-500 dark:text-slate-400">
                      No interactions recorded in the selected period ({historyFilterDays === 'all' ? 'all time' : `past ${historyFilterDays} days`}).
                    </p>
                    {historyFilterDays !== 'all' && timelineEvents.length > 0 && (
                      <button
                        type="button"
                        onClick={() => setHistoryFilterDays('all')}
                        className="mt-2 text-xs font-semibold text-indigo-600 hover:text-indigo-700 underline cursor-pointer"
                      >
                        View all {timelineEvents.length} older interactions
                      </button>
                    )}
                  </div>
                ) : (
                  <div className="space-y-2.5">
                    {visibleHistoryEvents.map((ev) => (
                      <div
                        key={ev.id}
                        className="bg-slate-950/60 border border-slate-800 rounded-xl p-3 hover:border-slate-700 transition-colors"
                      >
                        <div className="flex items-start justify-between gap-2 mb-1.5">
                          <div className="flex items-center gap-2">
                            {ev.type === 'activity' ? (
                              <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-indigo-50 text-indigo-700 border border-indigo-200">
                                <Phone className="w-3 h-3" /> Call
                              </span>
                            ) : ev.type === 'whatsapp' ? (
                              <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 border border-emerald-200">
                                <MessageCircle className="w-3 h-3" /> WhatsApp
                              </span>
                            ) : ev.type === 'note' ? (
                              <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-950 text-slate-300 border border-slate-800">
                                <FileText className="w-3 h-3" /> Note
                              </span>
                            ) : (
                              <span className="inline-flex items-center gap-1 text-[11px] font-semibold px-2 py-0.5 rounded bg-slate-950 text-slate-300 border border-slate-800">
                                <Clock className="w-3 h-3" /> {ev.title}
                              </span>
                            )}
                            <span className="text-xs font-semibold text-slate-100">
                              {ev.title}
                            </span>
                          </div>

                          <div className="flex items-center gap-2 text-[11px] text-slate-400">
                            {resolveActorName(ev.actor_user_id) && (
                              <span className="bg-slate-900 border border-slate-800 px-2 py-0.5 rounded text-slate-300 font-medium">
                                Agent: {resolveActorName(ev.actor_user_id)}
                              </span>
                            )}
                            <span>{formatEventTime(ev.timestamp)}</span>
                          </div>
                        </div>

                        {ev.description && (
                          <div className="text-xs text-slate-200 bg-slate-900 rounded-lg p-2.5 border border-slate-800 whitespace-pre-line mt-1">
                            {ev.description}
                          </div>
                        )}
                      </div>
                    ))}

                    {/* Show More / Show Less Button */}
                    {filteredHistoryEvents.length > 3 && (
                      <button
                        type="button"
                        onClick={() => setShowAllHistory(!showAllHistory)}
                        className="w-full flex items-center justify-center gap-1.5 py-2 px-3 text-xs font-semibold text-indigo-600 hover:text-indigo-700 bg-white dark:bg-slate-800 hover:bg-slate-50 border border-slate-200 dark:border-slate-700 rounded-lg transition-colors cursor-pointer shadow-xs"
                      >
                        {showAllHistory ? (
                          <>
                            <ChevronUp className="w-3.5 h-3.5" />
                            Show Less History
                          </>
                        ) : (
                          <>
                            <ChevronDown className="w-3.5 h-3.5" />
                            Show More Previous History ({filteredHistoryEvents.length - 3} older interactions)
                          </>
                        )}
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Disposition Form */}
              <form onSubmit={handleDispositionSubmit} className="p-6 space-y-6">
                {/* Disposition Status Grid */}
                <div className="space-y-3">
                  <label className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                    <UserCheck className="w-4 h-4 text-indigo-600" />
                    Call Disposition Status
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {dispositionOptions.map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => {
                          setSelectedStatus(opt);
                          if ((opt === 'Picked' || opt === 'Interested') && !targetStageId && stages.length > 0) {
                            const eligible = stages.find((s) => s.name !== 'Fresh Leads') || stages[0];
                            if (eligible) setTargetStageId(eligible.id);
                          }
                        }}
                        className={`py-2.5 px-3.5 text-xs font-semibold rounded-xl border transition-all duration-150 text-center cursor-pointer ${
                          selectedStatus === opt
                            ? 'bg-indigo-600 border-indigo-600 text-white shadow-xs'
                            : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-200 hover:bg-slate-50 dark:hover:bg-slate-700 shadow-xs'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Smooth expansion for Picked Dynamic Pipeline Selector */}
                {['Picked', 'Interested', 'Answered / Resolved', 'Callback Requested'].includes(selectedStatus || '') && (
                  <div className="space-y-2 p-4 bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-800/40 rounded-xl animate-slide-down">
                    <label htmlFor="pipeline-stage" className="text-xs font-bold text-indigo-700 dark:text-indigo-300 uppercase tracking-wider block">
                      Advance Lead to Pipeline Stage
                    </label>
                    <select
                      id="pipeline-stage"
                      value={targetStageId}
                      onChange={(e) => setTargetStageId(e.target.value)}
                      className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-100 py-2.5 px-3 rounded-lg focus:outline-hidden focus:ring-2 focus:ring-indigo-500 text-sm cursor-pointer shadow-xs"
                    >
                      <option value="" disabled>-- Select Pipeline Stage --</option>
                      {stages
                        .filter((s) => s.name !== 'Fresh Leads')
                        .map((stage) => (
                          <option key={stage.id} value={stage.id}>
                            {stage.name}
                          </option>
                        ))}
                    </select>
                  </div>
                )}

                {/* Follow-up scheduler */}
                {isFollowUpOutcome && (
                  <div className="space-y-4 p-4 bg-indigo-50/50 dark:bg-indigo-950/20 border border-indigo-200 dark:border-indigo-800/40 rounded-xl animate-slide-down">
                    <p className="text-xs font-bold text-indigo-700 dark:text-indigo-300 uppercase tracking-wider">Schedule Next Follow-up</p>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">Follow-up Date <span className="text-rose-500">*</span></label>
                        <input type="date" value={followUpDate} onChange={(e) => setFollowUpDate(e.target.value)}
                          className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-100 py-2 px-3 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500" />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">Follow-up Time <span className="text-rose-500">*</span></label>
                        <input type="time" value={followUpTime} onChange={(e) => setFollowUpTime(e.target.value)}
                          className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-slate-900 dark:text-slate-100 py-2 px-3 rounded-lg text-sm focus:outline-hidden focus:ring-2 focus:ring-indigo-500" />
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <label className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">Set a reminder</label>
                      <button type="button" onClick={() => setReminderEnabled((v) => !v)}
                        className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${reminderEnabled ? 'bg-indigo-600' : 'bg-slate-300 dark:bg-slate-700'}`}>
                        <span className={`block w-4 h-4 bg-white rounded-full transition-transform mt-0.5 ${reminderEnabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
                      </button>
                    </div>
                    {reminderEnabled && (
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">Remind me before</label>
                        <div className="grid grid-cols-4 gap-2">
                          {[{ l: '15 Min', v: 15 }, { l: '30 Min', v: 30 }, { l: '1 Hour', v: 60 }, { l: '1 Day', v: 1440 }].map((o) => (
                            <button key={o.v} type="button" onClick={() => setReminderBefore(o.v)}
                              className={`py-2 text-xs font-semibold rounded-lg border transition cursor-pointer ${reminderBefore === o.v ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50'}`}>
                              {o.l}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-slate-700 dark:text-slate-300">Priority</label>
                      <div className="grid grid-cols-4 gap-2">
                        {['Low', 'Medium', 'High', 'Critical'].map((p) => (
                          <button key={p} type="button" onClick={() => setFollowUpPriority(p)}
                            className={`py-2 text-xs font-semibold rounded-lg border transition cursor-pointer ${followUpPriority === p ? 'bg-indigo-600 border-indigo-600 text-white' : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50'}`}>
                            {p}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Call Remarks Textarea */}
                <div className="space-y-2">
                  <label htmlFor="remarks" className="text-sm font-bold text-slate-900 dark:text-slate-100 flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-indigo-600" />
                    {isFollowUpOutcome ? 'Remarks' : 'Call Notes & Remarks'} <span className="text-rose-500">*</span>
                  </label>
                  <textarea
                    id="remarks"
                    rows={4}
                    value={remarks}
                    onChange={(e) => setRemarks(e.target.value)}
                    placeholder="Enter mandatory call notes describing the outcome, next steps, or specific discussion details..."
                    className="w-full bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 rounded-xl py-3 px-4 text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-hidden focus:ring-2 focus:ring-indigo-500 text-sm transition-all shadow-xs"
                  />
                </div>

                {/* Form submit button */}
                <div className="border-t border-slate-200 dark:border-slate-800 pt-6">
                  <button
                    type="submit"
                    disabled={isSubmitDisabled}
                    className="w-full flex items-center justify-center gap-2 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white font-semibold py-3 px-4 rounded-xl shadow-xs transition-all duration-150 disabled:bg-slate-100 disabled:text-slate-400 disabled:border disabled:border-slate-200 disabled:shadow-none disabled:cursor-not-allowed transform active:scale-[0.98] cursor-pointer"
                  >
                    <CheckCircle className="w-5 h-5" />
                    {isLoading ? 'Saving Disposition...' : 'Save Call Disposition'}
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>

      {/* WhatsApp & Document Collection Drawer */}
      <OmniChannelChatDrawer
        lead={currentLead}
        isOpen={showChatDrawer}
        onClose={() => setShowChatDrawer(false)}
        initialChannel="whatsapp"
      />
    </div>
  );
};
