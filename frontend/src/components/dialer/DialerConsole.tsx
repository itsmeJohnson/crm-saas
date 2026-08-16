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
  Settings
} from 'lucide-react';
import { useDialerStore } from '../../store/dialerStore';
import { usePipelineStore } from '../../store/pipelineStore';
import { useAuthStore } from '../../store/authStore';
import { MaskedField } from '../common/MaskedField';
import { useDashboardStore } from '../../store/dashboardStore';
import { useAnalyticsStore } from '../../store/analyticsStore';
import { dashboardApi } from '../../services/dashboardApi';

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
    endBreak
  } = useDialerStore();

  const { stages, fetchStages } = usePipelineStore();
  // Integrated click-to-call is a paid feature; without it the cockpit runs in
  // manual mode (fetch lead → agent calls on own phone → log disposition).
  const callingEnabled = useAuthStore((s) => s.features.includes('OUTBOUND_CALLING'));

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
  const [collectivePooling, setCollectivePooling] = useState(false);
  const [showBreakMenu, setShowBreakMenu] = useState(false);

  const [knowlarityApiKey, setKnowlarityApiKey] = useState(() => 
    typeof localStorage !== 'undefined' ? (localStorage.getItem('crm_knowlarity_api_key') || '') : ''
  );
  const [knowlaritySrn, setKnowlaritySrn] = useState(() => 
    typeof localStorage !== 'undefined' ? (localStorage.getItem('crm_knowlarity_srn') || '') : ''
  );
  const [agentPhoneNumber, setAgentPhoneNumber] = useState(() =>
    typeof localStorage !== 'undefined' ? (localStorage.getItem('crm_agent_phone_number') || '') : ''
  );
  // Telephony provider + MyOperator (OBD) credentials.
  const ls = (k: string) => (typeof localStorage !== 'undefined' ? localStorage.getItem(k) || '' : '');
  const [provider, setProvider] = useState(() => ls('crm_telephony_provider') || 'knowlarity');
  const [myopXApiKey, setMyopXApiKey] = useState(() => ls('crm_myop_x_api_key'));
  const [myopSecretKey, setMyopSecretKey] = useState(() => ls('crm_myop_secret_key'));
  const [myopCompanyId, setMyopCompanyId] = useState(() => ls('crm_myop_company_id'));
  const [myopPublicIvrId, setMyopPublicIvrId] = useState(() => ls('crm_myop_public_ivr_id'));
  const [myopType, setMyopType] = useState(() => ls('crm_myop_type') || '1');
  const [autoDial, setAutoDial] = useState(() => {
    if (typeof localStorage !== 'undefined') {
      const saved = localStorage.getItem('crm_auto_dial');
      return saved !== null ? saved === 'true' : true;
    }
    return true;
  });
  const [showSettings, setShowSettings] = useState(false);
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

  useEffect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_knowlarity_api_key', knowlarityApiKey);
    }
  }, [knowlarityApiKey]);

  useEffect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_knowlarity_srn', knowlaritySrn);
    }
  }, [knowlaritySrn]);

  useEffect(() => {
    if (typeof localStorage !== 'undefined') {
      localStorage.setItem('crm_agent_phone_number', agentPhoneNumber);
    }
  }, [agentPhoneNumber]);

  useEffect(() => {
    if (typeof localStorage === 'undefined') return;
    localStorage.setItem('crm_telephony_provider', provider);
    localStorage.setItem('crm_myop_x_api_key', myopXApiKey);
    localStorage.setItem('crm_myop_secret_key', myopSecretKey);
    localStorage.setItem('crm_myop_company_id', myopCompanyId);
    localStorage.setItem('crm_myop_public_ivr_id', myopPublicIvrId);
    localStorage.setItem('crm_myop_type', myopType);
  }, [provider, myopXApiKey, myopSecretKey, myopCompanyId, myopPublicIvrId, myopType]);

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
  }, [fetchCurrentState, fetchStages]);

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

  // Provider-aware credential assembly for click-to-call.
  const credsConfigured =
    provider === 'myoperator'
      ? Boolean(myopXApiKey && myopSecretKey && myopCompanyId && myopPublicIvrId)
      : Boolean(knowlarityApiKey && agentPhoneNumber);

  const buildCreds = () => ({
    provider,
    agent_phone_number: agentPhoneNumber || undefined,
    knowlarity_api_key: knowlarityApiKey || undefined,
    knowlarity_srn: knowlaritySrn || undefined,
    myop_x_api_key: myopXApiKey || undefined,
    myop_secret_key: myopSecretKey || undefined,
    myop_company_id: myopCompanyId || undefined,
    myop_public_ivr_id: myopPublicIvrId || undefined,
    myop_type: myopType || '1',
  });

  const handleStartDialing = async () => {
    setNextCallCountdown(null);
    try {
      // Credentials are org-level (Settings → Communication → Calling) and applied
      // server-side. Agents never send them.
      await startCalling(collectivePooling);
    } catch (err) {}
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
    const isStageRequired = selectedStatus === 'Picked' || selectedStatus === 'Interested';
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
      } else {
        await submitDisposition({
          status: selectedStatus,
          remarks: remarks,
          custom_pipeline_stage_id: isStageAllowed ? (targetStageId || undefined) : undefined
        });
      }

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
    } catch (err) {}
  };

  const breakOptions = ['Lunch', 'Tea', 'Meeting', 'General'];
  const dispositionOptions = callDirection === 'INBOUND'
    ? ['Answered / Resolved', 'Callback Requested', 'Interested', 'Not Interested', 'Spam / Junk']
    : ['RNR', 'Switch Off', 'Busy', 'Not Exist', 'Out of Service', 'Picked', 'Follow-up', 'Call Back Later'];

  // Outcomes that imply a next touch — the cockpit schedules the follow-up in place.
  const isFollowUpOutcome = selectedStatus === 'Follow-up' || selectedStatus === 'Call Back Later';
  const isStageRequired = selectedStatus === 'Picked' || selectedStatus === 'Interested';
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
          <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 shadow-xl space-y-6">
            <div className="flex items-center justify-between border-b border-slate-800 pb-4">
              <h2 className="text-lg font-semibold text-slate-100 flex items-center gap-2">
                <Clock className="w-5 h-5 text-indigo-400" />
                Agent Console
              </h2>
              <span className={`px-3 py-1 rounded-full text-xs font-semibold tracking-wider ${
                agentState === 'IDLE' ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' :
                agentState === 'ACTIVE_CALLING' ? 'bg-amber-500/10 text-amber-400 border border-amber-500/20' :
                'bg-blue-500/10 text-blue-400 border border-blue-500/20'
              }`}>
                {agentState}
              </span>
            </div>

            {/* Layout based on Agent State */}
            {agentState === 'IDLE' && (
              <div className="space-y-6 py-4">
                {/* Power-dialer countdown to the next auto-dialed call */}
                {nextCallCountdown !== null && (
                  <div className="flex items-center justify-between bg-amber-500/10 border border-amber-500/20 text-amber-400 p-4 rounded-xl animate-fade-in">
                    <span className="text-sm font-semibold flex items-center gap-2">
                      <Phone className="w-4 h-4 animate-pulse" />
                      Power dialer: next call in {nextCallCountdown}s
                    </span>
                    <button
                      type="button"
                      onClick={() => setNextCallCountdown(null)}
                      className="text-xs font-semibold text-slate-300 hover:text-white bg-slate-800/80 hover:bg-slate-700 border border-slate-700/60 px-3 py-1.5 rounded-lg transition-colors cursor-pointer"
                    >
                      Stop
                    </button>
                  </div>
                )}
                <div className="space-y-3">
                  <div className="flex items-center gap-3 bg-slate-800/40 p-4 rounded-xl border border-slate-800/60">
                    <input
                      id="collective-pooling"
                      type="checkbox"
                      checked={collectivePooling}
                      onChange={(e) => setCollectivePooling(e.target.checked)}
                      className="w-4 h-4 text-indigo-600 bg-slate-800 border-slate-700 rounded focus:ring-indigo-500"
                    />
                    <label htmlFor="collective-pooling" className="text-sm text-slate-300 font-medium cursor-pointer select-none">
                      Enable Collective Pooling (fetch from TL pool)
                    </label>
                  </div>

                  <div className="flex items-center gap-3 bg-slate-800/40 p-4 rounded-xl border border-slate-800/60">
                    <input
                      id="auto-dial"
                      type="checkbox"
                      checked={autoDial}
                      onChange={(e) => setAutoDial(e.target.checked)}
                      className="w-4 h-4 text-indigo-600 bg-slate-800 border-slate-700 rounded focus:ring-indigo-500"
                    />
                    <label htmlFor="auto-dial" className="text-sm text-slate-300 font-medium cursor-pointer select-none flex-1">
                      Power Dialer (auto-dial next lead)
                    </label>
                    {autoDial && (
                      <select
                        aria-label="Power dialer delay"
                        value={powerDelay}
                        onChange={(e) => setPowerDelay(parseInt(e.target.value, 10))}
                        className="bg-slate-800 border border-slate-700 text-slate-300 text-xs py-1.5 px-2 rounded-lg focus:outline-none"
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
                  className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-indigo-600 to-violet-600 hover:from-indigo-500 hover:to-violet-500 text-white font-medium py-3.5 px-4 rounded-xl shadow-lg shadow-indigo-500/20 transition-all duration-200 transform active:scale-[0.98] disabled:opacity-50"
                >
                  <Play className="w-5 h-5" />
                  Start Dialing Session
                </button>

                <div className="relative border-t border-slate-800/60 pt-4">
                  <button
                    onClick={() => setShowBreakMenu(!showBreakMenu)}
                    disabled={isLoading}
                    className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium py-2.5 px-4 rounded-xl transition-all duration-200 border border-slate-700/50"
                  >
                    <Coffee className="w-4 h-4 text-slate-400" />
                    Request Break
                  </button>

                  {showBreakMenu && (
                    <div className="absolute left-0 right-0 mt-2 bg-slate-800 border border-slate-700 rounded-xl shadow-xl overflow-hidden z-20 animate-fade-in">
                      {breakOptions.map((opt) => (
                        <button
                          key={opt}
                          onClick={() => handleRequestBreak(opt)}
                          className="w-full text-left px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700 transition-colors duration-150"
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
                <div className="inline-flex items-center justify-center p-4 bg-blue-500/10 border border-blue-500/20 rounded-full text-blue-400 mb-2">
                  <Coffee className="w-10 h-10" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-100">{breakReason} Break</h3>
                  <p className="text-sm text-slate-400 mt-1">Break countdown remaining</p>
                </div>

                <div className="text-4xl font-mono font-bold text-indigo-400 bg-slate-950/80 border border-slate-800/80 rounded-2xl py-4 max-w-[200px] mx-auto tracking-wider">
                  {formatDuration(breakTimeRemaining)}
                </div>

                <button
                  onClick={handleEndBreak}
                  disabled={isLoading}
                  className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-200 font-medium py-3 px-4 rounded-xl transition-all duration-200 border border-slate-700"
                >
                  <LogOut className="w-4 h-4" />
                  End Break
                </button>
              </div>
            )}

            {agentState === 'ACTIVE_CALLING' && (
              <div className="space-y-6 py-4 text-center">
                <div className="inline-flex items-center justify-center p-4 bg-amber-500/10 border border-amber-500/20 rounded-full text-amber-400 mb-2 animate-pulse">
                  <Phone className="w-10 h-10" />
                </div>
                <div>
                  <h3 className="text-xl font-bold text-slate-100">Live Call Active</h3>
                  <p className="text-sm text-slate-400 mt-1">Do not close this panel during call</p>
                </div>

                <div className="text-4xl font-mono font-bold text-amber-400 bg-slate-950/80 border border-slate-800/80 rounded-2xl py-4 max-w-[200px] mx-auto tracking-wider">
                  {formatDuration(callDuration)}
                </div>

                {/* Queue Break option during active call */}
                <div className="relative border-t border-slate-800/60 pt-4 mt-4">
                  {pendingBreakReason ? (
                    <div className="flex items-center justify-between bg-blue-500/10 border border-blue-500/20 text-blue-400 p-3 rounded-xl">
                      <span className="text-sm font-medium flex items-center gap-1.5">
                        <Coffee className="w-4 h-4" />
                        Pending Break: {pendingBreakReason}
                      </span>
                      <button
                        type="button"
                        onClick={() => setPendingBreakReason(null)}
                        className="text-xs text-slate-400 hover:text-slate-200 transition-colors underline cursor-pointer"
                      >
                        Cancel
                      </button>
                    </div>
                  ) : (
                    <>
                      <button
                        type="button"
                        onClick={() => setShowActiveBreakMenu(!showActiveBreakMenu)}
                        className="w-full flex items-center justify-center gap-2 bg-slate-800 hover:bg-slate-700 text-slate-300 font-medium py-2.5 px-4 rounded-xl transition-all duration-200 border border-slate-700/50 cursor-pointer"
                      >
                        <Coffee className="w-4 h-4 text-slate-400" />
                        Take Break After Call
                      </button>

                      {showActiveBreakMenu && (
                        <div className="absolute left-0 right-0 mt-2 bg-slate-800 border border-slate-700 rounded-xl shadow-xl overflow-hidden z-20 animate-fade-in">
                          {breakOptions.map((opt) => (
                            <button
                              key={opt}
                              type="button"
                              onClick={() => {
                                setPendingBreakReason(opt);
                                setShowActiveBreakMenu(false);
                              }}
                              className="w-full text-left px-4 py-2.5 text-sm text-slate-300 hover:bg-slate-700 transition-colors duration-150 cursor-pointer"
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

          {/* Telephony credentials are configured once, org-wide, by an admin in
              Settings → Communication → Calling — never per agent. Nothing to
              set here; the backend applies the org config automatically. */}
        </div>

        {/* RIGHT CONTEXT PANEL (Cols 6-12) */}
        <div className="md:col-span-7">
          {agentState !== 'ACTIVE_CALLING' ? (
            <div className="bg-slate-900/40 border border-slate-800/60 rounded-2xl p-12 text-center shadow-lg border-dashed">
              <Phone className="w-12 h-12 text-slate-600 mx-auto mb-4" />
              <h3 className="text-slate-300 font-semibold text-lg">No Active Session</h3>
              <p className="text-slate-500 text-sm mt-1 max-w-sm mx-auto">
                Ready your headpieces, configure collective settings, and click "Start Dialing Session" on the left to push your next assigned lead.
              </p>
            </div>
          ) : (
            <div className="bg-slate-900 border border-slate-800 rounded-2xl shadow-xl overflow-hidden animate-fade-in">
              {/* Lead Details Banner */}
              <div className="bg-gradient-to-r from-indigo-950/40 to-violet-950/40 border-b border-slate-800 p-6">
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <span className="text-xs font-semibold text-indigo-400 uppercase tracking-wider">Active Lead Context</span>
                    <h3 className="text-2xl font-bold text-slate-100 mt-1">
                      {currentLead?.first_name} {currentLead?.last_name}
                    </h3>
                    <p className="text-sm text-slate-400 mt-1 flex items-center gap-1.5">
                      <Building className="w-4 h-4 text-slate-500" />
                      {currentLead?.title} {currentLead?.company_name && `at ${currentLead?.company_name}`}
                    </p>
                  </div>
                  
                  {/* Phone Row displaying premium MaskedField */}
                  <div className="bg-slate-950/80 border border-slate-800 px-4 py-2.5 rounded-xl flex items-center gap-2">
                    <MaskedField value={currentLead?.phone || null} />
                  </div>
                </div>
              </div>

              {/* Disposition Form */}
              <form onSubmit={handleDispositionSubmit} className="p-6 space-y-6">
                {/* Disposition Status Grid */}
                <div className="space-y-3">
                  <label className="text-sm font-semibold text-slate-300 flex items-center gap-1.5">
                    <UserCheck className="w-4 h-4 text-indigo-400" />
                    Call Disposition Status
                  </label>
                  <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                    {dispositionOptions.map((opt) => (
                      <button
                        key={opt}
                        type="button"
                        onClick={() => setSelectedStatus(opt)}
                        className={`py-3 px-4 text-sm font-medium rounded-xl border transition-all duration-150 text-center ${
                          selectedStatus === opt
                            ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-600/20'
                            : 'bg-slate-800/60 border-slate-700/80 text-slate-300 hover:bg-slate-700/80 hover:border-slate-600'
                        }`}
                      >
                        {opt}
                      </button>
                    ))}
                  </div>
                </div>

                {/* Smooth expansion for Picked Dynamic Pipeline Selector */}
                {['Picked', 'Interested', 'Answered / Resolved', 'Callback Requested'].includes(selectedStatus || '') && (
                  <div className="space-y-2 p-4 bg-indigo-500/5 border border-indigo-500/10 rounded-xl animate-slide-down">
                    <label htmlFor="pipeline-stage" className="text-xs font-semibold text-indigo-400 uppercase tracking-wider block">
                      Advance Lead to Pipeline Stage
                    </label>
                    <select
                      id="pipeline-stage"
                      value={targetStageId}
                      onChange={(e) => setTargetStageId(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2.5 px-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
                    >
                      <option value="" disabled>-- Select Pipeline Stage --</option>
                      {stages
                        .filter((s) => s.name !== 'Fresh Leads') // typically advance out of fresh
                        .map((stage) => (
                          <option key={stage.id} value={stage.id}>
                            {stage.name}
                          </option>
                        ))}
                    </select>
                  </div>
                )}

                {/* Follow-up scheduler — shown for Follow-up / Call Back Later (Phase 1) */}
                {isFollowUpOutcome && (
                  <div className="space-y-4 p-4 bg-brand-500/5 border border-brand-500/15 rounded-xl animate-slide-down">
                    <p className="text-xs font-bold text-brand-300 uppercase tracking-wider">Schedule Next Follow-up</p>
                    <div className="grid grid-cols-2 gap-3">
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-400">Follow-up Date <span className="text-red-400">*</span></label>
                        <input type="date" value={followUpDate} onChange={(e) => setFollowUpDate(e.target.value)}
                          className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                      </div>
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-400">Follow-up Time <span className="text-red-400">*</span></label>
                        <input type="time" value={followUpTime} onChange={(e) => setFollowUpTime(e.target.value)}
                          className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
                      </div>
                    </div>
                    <div className="flex items-center justify-between">
                      <label className="text-[11px] font-semibold text-slate-400">Set a reminder</label>
                      <button type="button" onClick={() => setReminderEnabled((v) => !v)}
                        className={`w-10 h-5 rounded-full transition-colors cursor-pointer ${reminderEnabled ? 'bg-emerald-500/70' : 'bg-slate-700'}`}>
                        <span className={`block w-4 h-4 bg-white rounded-full transition-transform mt-0.5 ${reminderEnabled ? 'translate-x-5' : 'translate-x-0.5'}`} />
                      </button>
                    </div>
                    {reminderEnabled && (
                      <div className="space-y-1">
                        <label className="text-[11px] font-semibold text-slate-400">Remind me before</label>
                        <div className="grid grid-cols-4 gap-2">
                          {[{ l: '15 Min', v: 15 }, { l: '30 Min', v: 30 }, { l: '1 Hour', v: 60 }, { l: '1 Day', v: 1440 }].map((o) => (
                            <button key={o.v} type="button" onClick={() => setReminderBefore(o.v)}
                              className={`py-2 text-xs font-medium rounded-lg border ${reminderBefore === o.v ? 'bg-brand-600 border-brand-500 text-white' : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:bg-slate-700/60'}`}>
                              {o.l}
                            </button>
                          ))}
                        </div>
                      </div>
                    )}
                    <div className="space-y-1">
                      <label className="text-[11px] font-semibold text-slate-400">Priority</label>
                      <div className="grid grid-cols-4 gap-2">
                        {['Low', 'Medium', 'High', 'Critical'].map((p) => (
                          <button key={p} type="button" onClick={() => setFollowUpPriority(p)}
                            className={`py-2 text-xs font-medium rounded-lg border ${followUpPriority === p ? 'bg-brand-600 border-brand-500 text-white' : 'bg-slate-800/60 border-slate-700 text-slate-300 hover:bg-slate-700/60'}`}>
                            {p}
                          </button>
                        ))}
                      </div>
                    </div>
                  </div>
                )}

                {/* Call Remarks Textarea */}
                <div className="space-y-2">
                  <label htmlFor="remarks" className="text-sm font-semibold text-slate-300 flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    {isFollowUpOutcome ? 'Remarks' : 'Call Notes & Remarks'} <span className="text-red-400">*</span>
                  </label>
                  <textarea
                    id="remarks"
                    rows={4}
                    value={remarks}
                    onChange={(e) => setRemarks(e.target.value)}
                    placeholder="Enter mandatory call notes describing the outcome, next steps, or specific discussion details..."
                    className="w-full bg-slate-800/80 border border-slate-700/80 rounded-xl py-3 px-4 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm transition-all"
                  />
                </div>

                {/* Form submit button */}
                <div className="border-t border-slate-800/80 pt-6">
                  <button
                    type="submit"
                    disabled={isSubmitDisabled}
                    className="w-full flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 text-white font-semibold py-3.5 px-4 rounded-xl shadow-lg shadow-emerald-600/10 transition-all duration-150 disabled:opacity-40 disabled:cursor-not-allowed transform active:scale-[0.98]"
                  >
                    <CheckCircle className="w-5 h-5" />
                    Submit Disposition Outcome
                  </button>
                </div>
              </form>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
