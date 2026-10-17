import React, { useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useDialerStore } from '../../store/dialerStore';
import { usePipelineStore } from '../../store/pipelineStore';
import { Phone, Clock, UserCheck, FileText, CheckCircle, AlertCircle, Minus, Maximize2, MessageSquare } from 'lucide-react';
import { useDashboardStore } from '../../store/dashboardStore';
import { useAnalyticsStore } from '../../store/analyticsStore';
import { dashboardApi } from '../../services/dashboardApi';
import { OmniChannelChatDrawer } from './OmniChannelChatDrawer';

export const ActiveCallDisposition: React.FC = () => {
  const location = useLocation();
  const isDashboard = location.pathname === '/' || location.pathname === '/dashboard';

  const {
    currentLead,
    callDuration,
    isLoading,
    error,
    callDirection,
    submitDisposition
  } = useDialerStore();

  const { stages, fetchStages } = usePipelineStore();

  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);
  const [remarks, setRemarks] = useState('');
  const [targetStageId, setTargetStageId] = useState('');
  const [isMinimized, setIsMinimized] = useState(isDashboard);
  const [showChatDrawer, setShowChatDrawer] = useState(false);

  // Follow-up scheduling states
  const [followUpDate, setFollowUpDate] = useState('');
  const [followUpTime, setFollowUpTime] = useState('');
  const [followUpPriority, setFollowUpPriority] = useState<'Low' | 'Medium' | 'High' | 'Urgent'>('Medium');

  useEffect(() => {
    if (stages.length === 0) {
      fetchStages().catch(() => {});
    }
  }, [stages.length, fetchStages]);

  // When switching pages or leads, minimize on dashboard to allow inline cockpit usage
  useEffect(() => {
    if (isDashboard) {
      setIsMinimized(true);
    }
  }, [location.pathname, isDashboard]);

  // Reset form inputs when current lead changes
  useEffect(() => {
    setSelectedStatus(null);
    setRemarks('');
    setTargetStageId('');
    setFollowUpDate('');
    setFollowUpTime('');
  }, [currentLead?.id]);

  if (!currentLead) return null;

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const isFollowUpOutcome = selectedStatus === 'Follow-up' || selectedStatus === 'Call Back Later';
  const isStageRequired = selectedStatus === 'Picked' || selectedStatus === 'Interested';
  const isStageAllowed = ['Picked', 'Interested', 'Answered / Resolved', 'Callback Requested'].includes(selectedStatus || '');
  const followUpIncomplete = isFollowUpOutcome && (!followUpDate || !followUpTime);

  const handleDispositionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStatus || !remarks.trim() || (isStageRequired && !targetStageId) || followUpIncomplete) {
      return;
    }
    try {
      if (isFollowUpOutcome && currentLead?.id && followUpDate && followUpTime) {
        try {
          const nextAt = new Date(`${followUpDate}T${followUpTime}`).toISOString();
          await dashboardApi.logFollowUp(currentLead.id, {
            outcome: selectedStatus,
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
        status: selectedStatus,
        remarks: remarks.trim(),
        custom_pipeline_stage_id: isStageAllowed ? (targetStageId || undefined) : undefined
      });

      // Clear local states
      setSelectedStatus(null);
      setRemarks('');
      setTargetStageId('');

      // Refresh dashboard statistics
      try {
        useDashboardStore.getState().fetchSummary();
        useDashboardStore.getState().fetchRecentActivities();
        useAnalyticsStore.getState().fetchDashboardMetrics();
      } catch (err) {}
    } catch (err) {}
  };

  const dispositionOptions = callDirection === 'INBOUND'
    ? ['Answered / Resolved', 'Callback Requested', 'Interested', 'Not Interested', 'Spam / Junk']
    : ['RNR', 'Switch Off', 'Busy', 'Picked', 'Follow-up', 'Call Back Later', 'Not Exist', 'Out of Service'];

  const isSubmitDisabled = !selectedStatus || !remarks.trim() || (isStageRequired && !targetStageId) || followUpIncomplete || isLoading;
  const leadFullName = `${currentLead.first_name || ''} ${currentLead.last_name || 'Active Lead'}`.trim();

  // Floating Minimized Call Bar
  if (isMinimized) {
    return (
      <>
        <div className="fixed bottom-6 right-6 z-50 animate-in slide-in-from-bottom-4 duration-200">
          <div className="bg-slate-900/95 backdrop-blur-md border border-slate-700/80 rounded-2xl shadow-2xl shadow-indigo-950/40 p-3.5 flex items-center gap-3.5 max-w-md">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0 animate-pulse">
              <Phone className="w-5 h-5" />
            </div>
            
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2">
                <span className="w-2 h-2 rounded-full bg-emerald-400 animate-ping shrink-0" />
                <p className="text-xs font-bold text-slate-100 truncate">
                  {leadFullName}
                </p>
              </div>
              <p className="text-[11px] font-mono text-slate-400 truncate mt-0.5">
                {currentLead.phone || 'Phone Connected'} • <span className="text-amber-400 font-bold">{formatDuration(callDuration)}</span>
              </p>
            </div>

            <div className="flex items-center gap-1.5 shrink-0">
              <button
                type="button"
                onClick={() => setShowChatDrawer(true)}
                title="WhatsApp / Collect Docs"
                className="p-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-xl transition-all cursor-pointer"
              >
                <MessageSquare className="w-4 h-4" />
              </button>

              <button
                type="button"
                onClick={() => setIsMinimized(false)}
                className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-xs rounded-xl shadow-md shadow-indigo-600/30 flex items-center gap-1.5 transition-all cursor-pointer"
              >
                <Maximize2 className="w-3.5 h-3.5" />
                <span>Save Disposition</span>
              </button>
            </div>
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
  }

  return (
    <>
      <div className="fixed inset-0 z-50 bg-slate-950/70 backdrop-blur-sm flex items-center justify-center p-4 max-md:items-end max-md:p-0 animate-in fade-in duration-200">
        <div className="w-full max-w-xl bg-slate-900 border border-slate-700/80 rounded-2xl max-md:rounded-b-none max-md:rounded-t-2xl shadow-2xl shadow-indigo-950/50 overflow-hidden animate-in zoom-in-95 max-md:slide-in-from-bottom duration-200">
          
          {/* Mobile Pull Handle */}
          <div className="md:hidden w-12 h-1.5 bg-slate-700/60 rounded-full mx-auto mt-2.5 mb-1" />

          {/* Active Call Header */}
          <div className="bg-gradient-to-r from-slate-850 via-slate-900 to-indigo-950/40 border-b border-slate-800 p-4 sm:p-5 flex items-center justify-between gap-3">
            <div className="flex items-center gap-3.5 min-w-0">
              <div className="w-11 h-11 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
                <Phone className="w-5 h-5 animate-pulse" />
              </div>
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  <span className="px-2 py-0.5 rounded-full text-[10px] font-bold uppercase tracking-wider bg-emerald-500/10 text-emerald-400 border border-emerald-500/30">
                    Live Call Active
                  </span>
                  <span className="text-[11px] text-slate-400 font-medium">
                    • {callDirection === 'INBOUND' ? 'Inbound' : 'Outbound'}
                  </span>
                </div>
                <h3 className="text-base font-bold text-white truncate mt-1">
                  {leadFullName}
                </h3>
                {currentLead.phone && (
                  <p className="text-xs font-mono text-slate-400 mt-0.5">
                    {currentLead.phone}
                  </p>
                )}
              </div>
            </div>
            
            <div className="flex items-center gap-2 shrink-0">
              {/* Duration Timer */}
              <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-800/90 border border-slate-700 rounded-xl">
                <Clock className="w-3.5 h-3.5 text-amber-400" />
                <span className="font-mono text-sm font-bold text-amber-400 tracking-wider">
                  {formatDuration(callDuration)}
                </span>
              </div>

              {/* WhatsApp Button */}
              <button
                type="button"
                onClick={() => setShowChatDrawer(true)}
                title="Open WhatsApp chat & collect documents"
                className="p-2 bg-emerald-500/10 hover:bg-emerald-500/20 text-emerald-400 border border-emerald-500/20 rounded-xl transition-all cursor-pointer"
              >
                <MessageSquare className="w-4 h-4" />
              </button>

              {/* Minimize Modal */}
              <button
                type="button"
                onClick={() => setIsMinimized(true)}
                title="Minimize call to floating widget"
                className="p-2 bg-slate-800 hover:bg-slate-700 text-slate-400 hover:text-slate-200 border border-slate-700 rounded-xl transition-all cursor-pointer"
              >
                <Minus className="w-4 h-4" />
              </button>
            </div>
          </div>

          {/* Form Body */}
          <form onSubmit={handleDispositionSubmit} className="p-5 sm:p-6 space-y-4 max-h-[75vh] overflow-y-auto">
            {error && (
              <div className="flex items-center gap-2.5 p-3.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs">
                <AlertCircle className="w-4 h-4 shrink-0" />
                <p className="font-medium">{error}</p>
              </div>
            )}

            {/* Disposition Status Options */}
            <div className="space-y-2">
              <label className="text-xs font-bold text-slate-200 flex items-center gap-1.5 uppercase tracking-wider">
                <UserCheck className="w-3.5 h-3.5 text-indigo-400" />
                Call Disposition Status <span className="text-rose-400">*</span>
              </label>
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
                {dispositionOptions.map((opt) => (
                  <button
                    key={opt}
                    type="button"
                    onClick={() => setSelectedStatus(opt)}
                    className={`min-h-[44px] py-2.5 px-3 text-xs font-semibold rounded-xl border transition-all duration-150 text-center cursor-pointer flex items-center justify-center ${
                      selectedStatus === opt
                        ? 'bg-indigo-600 border-indigo-400 text-white shadow-lg shadow-indigo-600/30 ring-2 ring-indigo-500/30 scale-[1.02]'
                        : 'bg-slate-800/90 border-slate-700/80 text-slate-200 hover:bg-slate-750 hover:border-slate-500 hover:text-white'
                    }`}
                  >
                    {opt}
                  </button>
                ))}
              </div>
            </div>

            {/* In-place Follow-up Date/Time when selected */}
            {isFollowUpOutcome && (
              <div className="p-4 bg-indigo-950/30 border border-indigo-500/30 rounded-xl space-y-3 animate-in fade-in duration-200">
                <p className="text-xs font-bold text-indigo-300 flex items-center gap-1.5 uppercase tracking-wider">
                  <Clock className="w-3.5 h-3.5 text-indigo-400" />
                  Schedule Follow-Up Callback <span className="text-rose-400">*</span>
                </p>
                <div className="grid grid-cols-1 sm:grid-cols-3 gap-2.5">
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-400 mb-1">Date *</label>
                    <input
                      type="date"
                      value={followUpDate}
                      onChange={(e) => setFollowUpDate(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 text-white rounded-xl py-2 px-3 text-xs focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-400 mb-1">Time *</label>
                    <input
                      type="time"
                      value={followUpTime}
                      onChange={(e) => setFollowUpTime(e.target.value)}
                      className="w-full bg-slate-800 border border-slate-700 text-white rounded-xl py-2 px-3 text-xs focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                  <div>
                    <label className="block text-[10px] font-semibold text-slate-400 mb-1">Priority</label>
                    <select
                      value={followUpPriority}
                      onChange={(e) => setFollowUpPriority(e.target.value as any)}
                      className="w-full bg-slate-800 border border-slate-700 text-white rounded-xl py-2 px-3 text-xs focus:ring-1 focus:ring-indigo-500"
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

            {/* Advance Stage Selection */}
            {isStageAllowed && (
              <div className="space-y-1.5 p-3.5 bg-indigo-950/20 border border-indigo-500/20 rounded-xl animate-in fade-in duration-200">
                <label htmlFor="modal-pipeline-stage" className="text-[10px] font-bold text-indigo-300 uppercase tracking-widest block">
                  {isStageRequired ? 'Advance Pipeline Stage (Required)' : 'Advance Pipeline Stage (Optional)'}
                </label>
                <select
                  id="modal-pipeline-stage"
                  value={targetStageId}
                  onChange={(e) => setTargetStageId(e.target.value)}
                  className="w-full min-h-[42px] bg-slate-800 border border-slate-700 text-slate-100 py-2 px-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-xs"
                >
                  <option value="">-- Keep Current Stage --</option>
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

            {/* Remarks */}
            <div className="space-y-1.5">
              <label htmlFor="modal-call-remarks" className="text-xs font-bold text-slate-200 flex items-center gap-1.5 uppercase tracking-wider">
                <FileText className="w-3.5 h-3.5 text-indigo-400" />
                Call Notes & Remarks <span className="text-rose-400">*</span>
              </label>
              <textarea
                id="modal-call-remarks"
                rows={3}
                value={remarks}
                onChange={(e) => setRemarks(e.target.value)}
                placeholder="Enter call summary, client feedback, or discussion notes..."
                className="w-full bg-slate-800/90 border border-slate-700 rounded-xl py-2.5 px-3 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-xs resize-none"
              />
            </div>

            {/* Save Call Disposition Button */}
            <button
              type="submit"
              disabled={isSubmitDisabled}
              className="w-full min-h-[46px] flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-xl shadow-lg shadow-emerald-950/50 transition-all duration-150 transform active:scale-[0.98] text-xs cursor-pointer"
            >
              <CheckCircle className="w-4 h-4" />
              {isLoading ? 'Saving Disposition...' : 'Save Call Disposition'}
            </button>
          </form>
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
