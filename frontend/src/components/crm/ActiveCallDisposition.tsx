import React, { useEffect, useState } from 'react';
import { useDialerStore } from '../../store/dialerStore';
import { usePipelineStore } from '../../store/pipelineStore';
import { Phone, Clock, UserCheck, FileText, CheckCircle, AlertCircle } from 'lucide-react';
import { useDashboardStore } from '../../store/dashboardStore';
import { useAnalyticsStore } from '../../store/analyticsStore';

export const ActiveCallDisposition: React.FC = () => {
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

  useEffect(() => {
    if (stages.length === 0) {
      fetchStages().catch(() => {});
    }
  }, [stages.length, fetchStages]);

  // Reset form inputs when current lead changes
  useEffect(() => {
    setSelectedStatus(null);
    setRemarks('');
    setTargetStageId('');
  }, [currentLead]);

  if (!currentLead) return null;

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const isStageRequired = selectedStatus === 'Picked' || selectedStatus === 'Interested';
  const isStageAllowed = ['Picked', 'Interested', 'Answered / Resolved', 'Callback Requested'].includes(selectedStatus || '');

  const handleDispositionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStatus || !remarks.trim() || (isStageRequired && !targetStageId)) {
      return;
    }
    try {
      await submitDisposition({
        status: selectedStatus,
        remarks: remarks,
        custom_pipeline_stage_id: isStageAllowed ? (targetStageId || undefined) : undefined
      });

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
    : ['RNR', 'Switch Off', 'Busy', 'Not Exist', 'Out of Service', 'Picked'];

  const isSubmitDisabled = !selectedStatus || !remarks.trim() || (isStageRequired && !targetStageId) || isLoading;

  return (
    <div className="fixed inset-0 z-50 bg-black/85 backdrop-blur-md flex items-center justify-center p-4 max-md:items-end max-md:p-0 animate-in fade-in duration-200">
      <div className="w-full max-w-lg bg-[#111a2e] border border-[#1e293b] rounded-2xl max-md:rounded-b-none max-md:rounded-t-2xl shadow-2xl shadow-indigo-950/50 overflow-hidden animate-in zoom-in-95 max-md:slide-in-from-bottom duration-200">
        {/* Mobile Pull Handle */}
        <div className="md:hidden w-12 h-1.5 bg-slate-700/60 rounded-full mx-auto mt-2.5 mb-1" />

        {/* Active Call Banner */}
        <div className="bg-gradient-to-r from-indigo-950/80 to-[#111a2e] border-b border-[#1e293b] p-4 flex items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 shrink-0 animate-pulse">
              <Phone className="w-5 h-5" />
            </div>
            <div>
              <p className="text-[10px] font-black text-indigo-400 uppercase tracking-widest">
                Active {callDirection === 'INBOUND' ? 'Inbound' : 'Outbound'} Call · Mandatory Disposition
              </p>
              <p className="text-xs font-semibold text-slate-200 mt-0.5">
                Outcome for {currentLead.first_name || ''} {currentLead.last_name || 'Lead'}
              </p>
            </div>
          </div>
          
          {/* Duration Timer */}
          <div className="flex items-center gap-1.5 px-3 py-1.5 bg-[#080b14] border border-[#1e293b] rounded-xl">
            <Clock className="w-3.5 h-3.5 text-indigo-400" />
            <span className="font-mono text-sm font-bold text-indigo-400 tracking-wider">
              {formatDuration(callDuration)}
            </span>
          </div>
        </div>

        {/* Form Details */}
        <form onSubmit={handleDispositionSubmit} className="p-5 space-y-4 max-h-[75vh] overflow-y-auto">
          {error && (
            <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs">
              <AlertCircle className="w-4 h-4 shrink-0" />
              <p className="font-medium">{error}</p>
            </div>
          )}

          {/* Status Options */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
              <UserCheck className="w-3.5 h-3.5 text-indigo-400" />
              Call Disposition Outcome <span className="text-rose-400">*</span>
            </label>
            <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
              {dispositionOptions.map((opt) => (
                <button
                  key={opt}
                  type="button"
                  onClick={() => setSelectedStatus(opt)}
                  className={`min-h-[44px] py-2.5 px-3 text-xs font-semibold rounded-xl border transition-all duration-150 text-center cursor-pointer flex items-center justify-center ${
                    selectedStatus === opt
                      ? 'bg-indigo-600 border-indigo-500 text-white shadow-lg shadow-indigo-600/30'
                      : 'bg-[#080b14] border-[#1e293b] text-slate-300 hover:bg-[#18233d] hover:border-slate-600'
                  }`}
                >
                  {opt}
                </button>
              ))}
            </div>
          </div>

          {/* Stage selection */}
          {isStageAllowed && (
            <div className="space-y-1.5 p-3.5 bg-indigo-500/10 border border-indigo-500/20 rounded-xl animate-in fade-in slide-in-from-top-2 duration-200">
              <label htmlFor="timeline-pipeline-stage" className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest block">
                {isStageRequired ? 'Advance Pipeline Stage (Required)' : 'Advance Pipeline Stage (Optional)'}
              </label>
              <select
                id="timeline-pipeline-stage"
                value={targetStageId}
                onChange={(e) => setTargetStageId(e.target.value)}
                className="w-full min-h-[44px] bg-[#080b14] border border-[#1e293b] text-slate-200 py-2 px-3 rounded-xl focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-xs"
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
            <label htmlFor="call-remarks" className="text-xs font-bold text-slate-300 flex items-center gap-1.5 uppercase tracking-wider">
              <FileText className="w-3.5 h-3.5 text-indigo-400" />
              Conversation Notes / Remarks <span className="text-rose-400">*</span>
            </label>
            <textarea
              id="call-remarks"
              rows={3}
              value={remarks}
              onChange={(e) => setRemarks(e.target.value)}
              placeholder="Mandatory outcome notes before floor unlocks..."
              className="w-full bg-[#080b14] border border-[#1e293b] rounded-xl py-2.5 px-3 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-xs resize-none"
            />
          </div>

          {/* Submit */}
          <button
            type="submit"
            disabled={isSubmitDisabled}
            className="w-full min-h-[44px] flex items-center justify-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-bold py-3 px-4 rounded-xl shadow-lg shadow-emerald-950/50 transition-all duration-150 transform active:scale-[0.98] text-xs cursor-pointer"
          >
            <CheckCircle className="w-4 h-4" />
            {isLoading ? 'Saving Outcome & Dispatching Omnichannel...' : 'Submit Call Outcome & Unlock Console'}
          </button>
        </form>
      </div>
    </div>
  );
};
