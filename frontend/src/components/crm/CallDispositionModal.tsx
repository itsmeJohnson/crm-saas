import React, { useState, useEffect } from 'react';
import {
  PhoneCall,
  Clock,
  User,
  Calendar,
  AlertCircle,
  CheckCircle2,
  X,
  FileText,
  Tag,
  ShieldAlert,
  Loader2,
  Copy,
  Check
} from 'lucide-react';
import { useDialerStore } from '../../store/dialerStore';
import { usePipelineStore } from '../../store/pipelineStore';
import { useAuthStore } from '../../store/authStore';
import { useLeadStore } from '../../store/leadStore';
import { useDashboardStore } from '../../store/dashboardStore';
import { dashboardApi } from '../../services/dashboardApi';

export const DISPOSITION_OPTIONS = [
  // ── 1. Connected Outcomes ──
  { value: 'Picked — Connected', label: 'Picked — Connected', category: 'Connected', badge: 'bg-emerald-500/10 text-emerald-500 border-emerald-500/30' },
  { value: 'Interested', label: 'Interested', category: 'Connected', badge: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/30' },
  { value: 'Not Interested', label: 'Not Interested', category: 'Connected', badge: 'bg-rose-500/10 text-rose-400 border-rose-500/30' },
  { value: 'Follow-up Required', label: 'Follow-up Required', category: 'Connected', badge: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/30' },
  { value: 'Callback Scheduled', label: 'Callback Scheduled', category: 'Connected', badge: 'bg-blue-500/10 text-blue-400 border-blue-500/30' },
  { value: 'Converted / Successful', label: 'Converted / Successful', category: 'Connected', badge: 'bg-purple-500/10 text-purple-400 border-purple-500/30' },
  { value: 'Language Barrier', label: 'Language Barrier', category: 'Connected', badge: 'bg-amber-500/10 text-amber-400 border-amber-500/30' },
  { value: 'Do Not Call', label: 'Do Not Call', category: 'Connected', badge: 'bg-red-500/10 text-red-400 border-red-500/30' },

  // ── 2. Unanswered / Busy Outcomes ──
  { value: 'RNR — Ringing No Response', label: 'RNR — Ringing No Response', category: 'Unanswered', badge: 'bg-amber-500/10 text-amber-500 border-amber-500/30' },
  { value: 'Busy', label: 'Busy', category: 'Unanswered', badge: 'bg-orange-500/10 text-orange-400 border-orange-500/30' },
  { value: 'Switched Off', label: 'Switched Off', category: 'Unanswered', badge: 'bg-slate-500/10 text-slate-400 border-slate-500/30' },
  { value: 'Not Reachable', label: 'Not Reachable', category: 'Unanswered', badge: 'bg-zinc-500/10 text-zinc-400 border-zinc-500/30' },
  { value: 'Call Rejected', label: 'Call Rejected', category: 'Unanswered', badge: 'bg-pink-500/10 text-pink-400 border-pink-500/30' },

  // ── 3. Invalid Number & System Outcomes ──
  { value: 'Wrong Number', label: 'Wrong Number', category: 'Invalid / System', badge: 'bg-yellow-500/10 text-yellow-500 border-yellow-500/30' },
  { value: 'Number Does Not Exist', label: 'Number Does Not Exist', category: 'Invalid / System', badge: 'bg-red-500/10 text-red-500 border-red-500/30' },
  { value: 'Technical Failure', label: 'Technical Failure', category: 'Invalid / System', badge: 'bg-red-500/10 text-red-400 border-red-500/30' },
];

export const CallDispositionModal: React.FC = () => {
  const {
    isDispositionModalOpen,
    dispositionSession,
    closeDispositionModal,
    submitDisposition,
    currentLead: activeLead,
  } = useDialerStore();

  const { user } = useAuthStore();
  const { stages, fetchStages } = usePipelineStore();

  // Selected lead is from session or fallback to current store lead
  const targetLead = dispositionSession?.lead || activeLead;

  // Form states
  const [outcome, setOutcome] = useState<string>('Picked — Connected');
  const [remarks, setRemarks] = useState<string>('');
  const [targetStageId, setTargetStageId] = useState<string>('');
  const [followUpDate, setFollowUpDate] = useState<string>('');
  const [followUpTime, setFollowUpTime] = useState<string>('');
  const [followUpPriority, setFollowUpPriority] = useState<'Low' | 'Medium' | 'High' | 'Urgent'>('Medium');
  const [dispatchOmnichannel, setDispatchOmnichannel] = useState<boolean>(false);

  // Validation & UI states
  const [validationError, setValidationError] = useState<string | null>(null);
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const [showCloseConfirm, setShowCloseConfirm] = useState<boolean>(false);
  const [phoneCopied, setPhoneCopied] = useState<boolean>(false);
  const [activeCategory, setActiveCategory] = useState<'All' | 'Connected' | 'Unanswered' | 'Invalid / System'>('All');

  // Load stages on mount
  useEffect(() => {
    if (stages.length === 0) {
      fetchStages().catch(() => {});
    }
  }, [stages.length, fetchStages]);

  // Pre-seed form values based on call session telemetry
  useEffect(() => {
    if (!isDispositionModalOpen) {
      setShowCloseConfirm(false);
      setValidationError(null);
      return;
    }

    if (dispositionSession) {
      const techStatus = dispositionSession.technical_status;
      if (techStatus === 'failed') {
        setOutcome('Technical Failure');
      } else if (techStatus === 'ringing_no_answer') {
        setOutcome('RNR — Ringing No Response');
      } else if (techStatus === 'busy') {
        setOutcome('Busy');
      } else if (techStatus === 'connected' || dispositionSession.duration > 0) {
        setOutcome('Picked — Connected');
      } else {
        setOutcome('RNR — Ringing No Response');
      }
    }
  }, [isDispositionModalOpen, dispositionSession]);

  // Auto-suggest stage when outcome changes
  useEffect(() => {
    if (!stages || stages.length === 0) return;

    if (outcome === 'Interested') {
      const match = stages.find(s => s.name.toLowerCase().includes('interested') || s.name.toLowerCase().includes('qualified'));
      if (match) setTargetStageId(match.id);
    } else if (outcome === 'Converted / Successful') {
      const match = stages.find(s => s.name.toLowerCase().includes('won') || s.name.toLowerCase().includes('converted'));
      if (match) setTargetStageId(match.id);
    } else if (outcome === 'Not Interested') {
      const match = stages.find(s => s.name.toLowerCase().includes('not interested') || s.name.toLowerCase().includes('lost'));
      if (match) setTargetStageId(match.id);
    }
  }, [outcome, stages]);

  if (!isDispositionModalOpen || !targetLead) {
    return null;
  }

  const isFollowUpRequired = outcome === 'Follow-up Required' || outcome === 'Callback Scheduled';
  const durationSeconds = dispositionSession?.duration || 0;
  const mins = Math.floor(durationSeconds / 60);
  const secs = durationSeconds % 60;
  const durationFormatted = `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;

  const leadName = `${targetLead.first_name || ''} ${targetLead.last_name || 'Prospect'}`.trim() || 'Active Lead';
  const leadPhone = targetLead.phone || 'No phone number';
  const agentDisplayName = user ? `${user.first_name || ''} ${user.last_name || ''}`.trim() || user.email : 'Assigned Agent';
  const direction = dispositionSession?.direction || 'OUTBOUND';
  const technicalStatus = dispositionSession?.technical_status || (durationSeconds > 0 ? 'connected' : 'unanswered');

  const handleCopyPhone = () => {
    if (targetLead.phone) {
      navigator.clipboard?.writeText(targetLead.phone);
      setPhoneCopied(true);
      setTimeout(() => setPhoneCopied(false), 2000);
    }
  };

  const handleSave = async (e: React.FormEvent) => {
    e.preventDefault();
    setValidationError(null);

    // 1. Mandatory Remarks Validation (min 3 chars after trimming, max 1000)
    const trimmedRemarks = remarks.trim();
    if (trimmedRemarks.length < 3) {
      setValidationError('Remarks are mandatory and must contain at least 3 characters.');
      return;
    }
    if (trimmedRemarks.length > 1000) {
      setValidationError('Remarks cannot exceed 1,000 characters.');
      return;
    }

    // 2. Conditional Follow-up Validation
    if (isFollowUpRequired) {
      if (!followUpDate) {
        setValidationError('Please select a valid follow-up date for scheduled callbacks.');
        return;
      }
      if (!followUpTime) {
        setValidationError('Please select a valid follow-up time for scheduled callbacks.');
        return;
      }
      try {
        const scheduledTime = new Date(`${followUpDate}T${followUpTime}`).getTime();
        if (scheduledTime < Date.now() - 60000) {
          setValidationError('Follow-up date and time cannot be in the past.');
          return;
        }
      } catch {
        setValidationError('Invalid date/time format.');
        return;
      }
    }

    setIsSubmitting(true);
    try {
      // Create scheduled follow-up activity if date provided
      if (isFollowUpRequired && targetLead?.id && followUpDate && followUpTime) {
        try {
          const nextAt = new Date(`${followUpDate}T${followUpTime}`).toISOString();
          await dashboardApi.logFollowUp(String(targetLead.id), {
            outcome: outcome,
            follow_up_type: 'call',
            remarks: trimmedRemarks,
            next_follow_up_at: nextAt,
            priority: followUpPriority,
          });
        } catch (fErr) {
          console.warn('[Disposition] Follow-up schedule task sync error:', fErr);
        }
      }

      // Submit disposition payload to backend
      await submitDisposition({
        status: outcome,
        remarks: trimmedRemarks,
        call_sid: dispositionSession?.call_sid,
        call_duration: durationSeconds,
        call_direction: direction,
        technical_status: technicalStatus,
        follow_up_date: isFollowUpRequired ? followUpDate : undefined,
        follow_up_time: isFollowUpRequired ? followUpTime : undefined,
        follow_up_priority: isFollowUpRequired ? followUpPriority : undefined,
        custom_pipeline_stage_id: targetStageId || undefined,
        dispatch_omnichannel_followup: dispatchOmnichannel,
      });

      // Refresh stores
      try {
        useLeadStore.getState().fetchLeads();
        useDashboardStore.getState().fetchSummary();
        useDashboardStore.getState().fetchRecentActivities();
      } catch {}

      // Close modal cleanly
      closeDispositionModal();
    } catch (err: any) {
      console.error('[Disposition] Failed to submit disposition:', err);
      const errDetail = err?.response?.data?.detail;
      const message = typeof errDetail === 'string'
        ? errDetail
        : Array.isArray(errDetail)
        ? errDetail.map((d: any) => d.msg || JSON.stringify(d)).join(', ')
        : (err?.message || 'Failed to save disposition. Please check connection and try again.');
      setValidationError(message);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleForceDismiss = () => {
    setShowCloseConfirm(false);
    closeDispositionModal();
  };

  // Min date for follow-up date input is today
  const todayStr = new Date().toISOString().split('T')[0];

  const filteredOptions = activeCategory === 'All'
    ? DISPOSITION_OPTIONS
    : DISPOSITION_OPTIONS.filter((o) => o.category === activeCategory);

  return (
    <div className="fixed inset-0 z-[150] flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-md animate-in fade-in duration-200">
      <div
        className="w-full max-w-2xl bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-3xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh] animate-in zoom-in-95 duration-200"
        role="dialog"
        aria-modal="true"
        aria-labelledby="disposition-modal-title"
      >
        {/* Modal Header */}
        <div className="px-6 py-5 border-b border-slate-200 dark:border-slate-800 flex items-center justify-between gap-4 bg-white dark:bg-slate-900 shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-2xl bg-indigo-50 border border-indigo-200 dark:bg-indigo-500/10 dark:border-indigo-500/20 flex items-center justify-center text-indigo-600 dark:text-indigo-400 shrink-0 shadow-xs">
              <PhoneCall className="w-5 h-5" />
            </div>
            <div>
              <div className="flex items-center gap-2.5 flex-wrap">
                <h2 id="disposition-modal-title" className="text-base font-bold text-slate-900 dark:text-slate-100">
                  Mandatory Post-Call Disposition
                </h2>
                <span className={`text-[10px] font-bold uppercase tracking-wider px-2.5 py-0.5 rounded-full border ${
                  durationSeconds > 0
                    ? 'bg-emerald-50 border-emerald-200 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-400 dark:border-emerald-500/30'
                    : technicalStatus === 'ringing_no_answer'
                    ? 'bg-amber-50 border-amber-200 text-amber-700 dark:bg-amber-500/10 dark:text-amber-400 dark:border-amber-500/30'
                    : 'bg-slate-100 border-slate-200 text-slate-700 dark:bg-slate-800 dark:text-slate-300 dark:border-slate-700'
                }`}>
                  {durationSeconds > 0 ? `Connected (${durationFormatted})` : technicalStatus === 'ringing_no_answer' ? 'No Answer' : 'Call Ended (00:00)'}
                </span>
              </div>
              <p className="text-xs text-slate-500 dark:text-slate-400 mt-0.5">
                Log the official outcome and agent notes to complete call compliance
              </p>
            </div>
          </div>

          <button
            type="button"
            onClick={() => setShowCloseConfirm(true)}
            className="p-1.5 rounded-xl hover:bg-slate-100 dark:hover:bg-slate-800 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-all cursor-pointer"
            title="Close disposition form"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Dismiss Warning Confirmation Overlay */}
        {showCloseConfirm && (
          <div className="bg-amber-500/10 border-b border-amber-500/30 px-6 py-3.5 flex items-center justify-between gap-4 text-amber-300 text-xs animate-in slide-in-from-top-2 shrink-0">
            <div className="flex items-center gap-2.5">
              <ShieldAlert className="w-5 h-5 text-amber-400 shrink-0" />
              <span>
                <strong>Warning:</strong> Post-call disposition is mandatory. Closing without saving will leave this call un-dispositioned in audit logs.
              </span>
            </div>
            <div className="flex items-center gap-2 shrink-0">
              <button
                type="button"
                onClick={() => setShowCloseConfirm(false)}
                className="px-3 py-1 bg-amber-500/20 hover:bg-amber-500/30 border border-amber-500/40 rounded-lg text-amber-200 font-semibold transition-all cursor-pointer"
              >
                Return to Form
              </button>
              <button
                type="button"
                onClick={handleForceDismiss}
                className="px-3 py-1 bg-rose-600 hover:bg-rose-700 text-white rounded-lg font-semibold transition-all cursor-pointer"
              >
                Force Dismiss
              </button>
            </div>
          </div>
        )}

        {/* Scrollable Form Body */}
        <form onSubmit={handleSave} className="flex-1 overflow-y-auto p-6 space-y-5">
          {/* Validation Error Banner */}
          {validationError && (
            <div className="p-3.5 rounded-2xl bg-rose-500/10 border border-rose-500/30 flex items-start gap-3 text-rose-600 dark:text-rose-400 text-xs animate-in fade-in">
              <AlertCircle className="w-4 h-4 shrink-0 mt-0.5" />
              <div className="flex-1 font-medium">{validationError}</div>
              <button
                type="button"
                onClick={() => setValidationError(null)}
                className="text-rose-400 hover:text-rose-200 p-0.5 cursor-pointer"
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </div>
          )}

          {/* Call Telemetry Card */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 p-4 bg-slate-50 dark:bg-slate-800/50 border border-slate-200 dark:border-slate-800 rounded-2xl text-xs">
            {/* Lead Name & Phone */}
            <div className="col-span-2">
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Prospect / Lead</span>
              <p className="font-bold text-slate-900 dark:text-slate-100 truncate mt-0.5 text-sm">{leadName}</p>
              <div className="flex items-center gap-1.5 mt-0.5">
                <span className="font-mono text-slate-600 dark:text-slate-400 font-semibold">{leadPhone}</span>
                <button
                  type="button"
                  onClick={handleCopyPhone}
                  className="p-1 hover:bg-slate-200 dark:hover:bg-slate-700 rounded text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 transition-all cursor-pointer"
                  title="Copy Phone Number"
                >
                  {phoneCopied ? <Check className="w-3 h-3 text-emerald-500" /> : <Copy className="w-3 h-3" />}
                </button>
              </div>
            </div>

            {/* Agent Name */}
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Calling Agent</span>
              <p className="font-semibold text-slate-800 dark:text-slate-200 truncate mt-0.5 flex items-center gap-1">
                <User className="w-3 h-3 text-indigo-500 shrink-0" />
                {agentDisplayName}
              </p>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 font-medium capitalize">
                {direction === 'INBOUND' ? 'Incoming Call' : 'Outgoing Call'}
              </span>
            </div>

            {/* Connected Duration */}
            <div>
              <span className="text-[10px] font-bold uppercase tracking-wider text-slate-500 dark:text-slate-400">Call Duration</span>
              <p className={`font-mono font-black mt-0.5 flex items-center gap-1 text-sm ${
                durationSeconds > 0 ? 'text-emerald-600 dark:text-emerald-400' : 'text-slate-600 dark:text-slate-400'
              }`}>
                <Clock className="w-3.5 h-3.5 shrink-0" />
                {durationFormatted}
              </p>
              <span className="text-[10px] text-slate-500 dark:text-slate-400 capitalize">
                {durationSeconds > 0 ? 'Connected' : technicalStatus === 'ringing_no_answer' ? 'No Answer' : 'Terminated'}
              </span>
            </div>
          </div>

          {/* Section 1: Mandatory Call Outcome */}
          <div className="space-y-2.5">
            <div className="flex items-center justify-between gap-2">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300">
                1. Call Outcome <span className="text-rose-500">*</span>
              </label>

              {/* Category Filter Pills */}
              <div className="flex items-center gap-1 bg-slate-100 dark:bg-slate-800 p-0.5 rounded-lg text-[11px] font-semibold">
                {(['All', 'Connected', 'Unanswered', 'Invalid / System'] as const).map((cat) => (
                  <button
                    key={cat}
                    type="button"
                    onClick={() => setActiveCategory(cat)}
                    className={`px-2 py-0.5 rounded-md transition-all cursor-pointer ${
                      activeCategory === cat
                        ? 'bg-white dark:bg-slate-700 text-indigo-600 dark:text-indigo-300 shadow-2xs font-bold'
                        : 'text-slate-600 dark:text-slate-400 hover:text-slate-900 dark:hover:text-slate-200'
                    }`}
                  >
                    {cat === 'Invalid / System' ? 'System' : cat}
                  </button>
                ))}
              </div>
            </div>

            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2.5">
              {filteredOptions.map((opt) => {
                const isSelected = outcome === opt.value;
                return (
                  <button
                    key={opt.value}
                    type="button"
                    onClick={() => setOutcome(opt.value)}
                    className={`p-3 rounded-xl border text-left transition-all cursor-pointer flex flex-col justify-between min-h-[64px] ${
                      isSelected
                        ? 'bg-indigo-600 text-white border-indigo-600 shadow-md shadow-indigo-500/25 ring-2 ring-indigo-500/40'
                        : 'bg-white dark:bg-slate-800/90 border-slate-200 dark:border-slate-700 hover:border-indigo-300 dark:hover:border-indigo-500 hover:bg-slate-50 dark:hover:bg-slate-800 text-slate-800 dark:text-slate-200'
                    }`}
                  >
                    <div className="flex items-start justify-between gap-1.5">
                      <span className="text-xs font-bold leading-tight">{opt.label}</span>
                      {isSelected && <Check className="w-3.5 h-3.5 text-white shrink-0 mt-0.5" />}
                    </div>
                    <span className={`text-[10px] font-semibold tracking-wider uppercase mt-2 px-2 py-0.5 rounded-md w-fit ${
                      isSelected ? 'bg-white/20 text-white' : opt.badge
                    }`}>
                      {opt.category}
                    </span>
                  </button>
                );
              })}
            </div>
          </div>

          {/* Section 2: Conditional Follow-Up Scheduling */}
          {isFollowUpRequired && (
            <div className="p-4 bg-indigo-50/50 dark:bg-indigo-950/30 border border-indigo-200 dark:border-indigo-800/50 rounded-2xl space-y-3 animate-in slide-in-from-top-2">
              <div className="flex items-center gap-2 text-indigo-700 dark:text-indigo-300 text-xs font-bold uppercase tracking-wider">
                <Calendar className="w-4 h-4 text-indigo-500" />
                <span>Scheduled Callback Requirements *</span>
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-3 gap-3">
                {/* Date Input */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Callback Date <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="date"
                    min={todayStr}
                    value={followUpDate}
                    onChange={(e) => setFollowUpDate(e.target.value)}
                    required={isFollowUpRequired}
                    className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>

                {/* Time Input */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Callback Time <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="time"
                    value={followUpTime}
                    onChange={(e) => setFollowUpTime(e.target.value)}
                    required={isFollowUpRequired}
                    className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 outline-none"
                  />
                </div>

                {/* Priority Selector */}
                <div>
                  <label className="block text-[11px] font-semibold text-slate-600 dark:text-slate-400 mb-1">
                    Follow-Up Priority
                  </label>
                  <select
                    value={followUpPriority}
                    onChange={(e) => setFollowUpPriority(e.target.value as any)}
                    className="w-full px-3 py-2 bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 outline-none"
                  >
                    <option value="Low">Low</option>
                    <option value="Medium">Medium</option>
                    <option value="High">High</option>
                    <option value="Urgent">Urgent</option>
                  </select>
                </div>
              </div>
            </div>
          )}

          {/* Section 3: Conditional Pipeline Stage Selection */}
          {stages && stages.length > 0 && (
            <div className="space-y-1.5">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <Tag className="w-3.5 h-3.5 text-slate-400" />
                Pipeline Stage Progression (Optional)
              </label>
              <select
                value={targetStageId}
                onChange={(e) => setTargetStageId(e.target.value)}
                className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-xs font-semibold text-slate-900 dark:text-slate-100 focus:ring-2 focus:ring-indigo-500 outline-none"
              >
                <option value="">Keep current pipeline stage</option>
                {stages.map((stage) => (
                  <option key={stage.id} value={stage.id}>
                    {stage.name}
                  </option>
                ))}
              </select>
            </div>
          )}

          {/* Section 4: Mandatory Remarks Textarea */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between">
              <label className="block text-xs font-bold uppercase tracking-wider text-slate-700 dark:text-slate-300 flex items-center gap-1.5">
                <FileText className="w-3.5 h-3.5 text-slate-400" />
                2. Mandatory Call Remarks <span className="text-rose-500">*</span>
              </label>
              <span className={`text-[10px] font-mono font-semibold ${
                remarks.trim().length >= 3 && remarks.trim().length <= 1000
                  ? 'text-emerald-500'
                  : 'text-slate-400'
              }`}>
                {remarks.trim().length} / 1000 characters (min 3)
              </span>
            </div>
            <textarea
              value={remarks}
              onChange={(e) => {
                setRemarks(e.target.value);
                if (validationError && e.target.value.trim().length >= 3) {
                  setValidationError(null);
                }
              }}
              rows={3}
              maxLength={1000}
              required
              placeholder="Enter detailed call conversation remarks, customer requirements, or reason for callback..."
              className="w-full px-3.5 py-2.5 bg-slate-50 dark:bg-slate-800/60 border border-slate-300 dark:border-slate-700 rounded-xl text-xs text-slate-900 dark:text-slate-100 placeholder:text-slate-400 focus:ring-2 focus:ring-indigo-500 outline-none resize-none"
            />
          </div>

          {/* Section 5: Optional Omnichannel Follow-Up Dispatch */}
          <div className="flex items-center gap-2 pt-1 pb-1">
            <input
              type="checkbox"
              id="dispatch-omnichannel"
              checked={dispatchOmnichannel}
              onChange={(e) => setDispatchOmnichannel(e.target.checked)}
              className="w-4 h-4 rounded text-indigo-600 focus:ring-indigo-500 cursor-pointer"
            />
            <label htmlFor="dispatch-omnichannel" className="text-xs text-slate-600 dark:text-slate-400 cursor-pointer select-none">
              Trigger instant omnichannel (WhatsApp/SMS) follow-up dispatch
            </label>
          </div>

          {/* Modal Actions */}
          <div className="pt-2 flex items-center justify-between gap-3 border-t border-slate-200 dark:border-slate-800 shrink-0">
            <button
              type="button"
              onClick={() => setShowCloseConfirm(true)}
              className="px-4 py-2.5 border border-slate-300 dark:border-slate-700 hover:bg-slate-100 dark:hover:bg-slate-800 rounded-xl text-xs font-semibold text-slate-700 dark:text-slate-300 transition-all cursor-pointer"
            >
              Dismiss
            </button>

            <button
              type="submit"
              disabled={isSubmitting || remarks.trim().length < 3 || (isFollowUpRequired && (!followUpDate || !followUpTime))}
              className="flex-1 flex items-center justify-center gap-2 px-6 py-2.5 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-xl text-xs font-bold shadow-lg shadow-emerald-600/20 active:scale-98 transition-all cursor-pointer"
            >
              {isSubmitting ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  <span>Saving Disposition...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="w-4 h-4" />
                  <span>Save & Complete Disposition</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
