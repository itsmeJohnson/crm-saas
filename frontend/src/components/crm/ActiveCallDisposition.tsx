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

  const handleDispositionSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!selectedStatus || !remarks.trim() || (selectedStatus === 'Picked' && !targetStageId)) {
      return;
    }
    try {
      await submitDisposition({
        status: selectedStatus,
        remarks: remarks,
        custom_pipeline_stage_id: selectedStatus === 'Picked' ? targetStageId : undefined
      });

      // Refresh dashboard statistics
      try {
        useDashboardStore.getState().fetchSummary();
        useDashboardStore.getState().fetchRecentActivities();
        useAnalyticsStore.getState().fetchDashboardMetrics();
      } catch (err) {}
    } catch (err) {}
  };

  const dispositionOptions = ['RNR', 'Switch Off', 'Busy', 'Not Exist', 'Out of Service', 'Picked'];
  const isSubmitDisabled = !selectedStatus || !remarks.trim() || (selectedStatus === 'Picked' && !targetStageId) || isLoading;

  return (
    <div className="bg-slate-900 border border-brand-500/20 rounded-2xl shadow-xl overflow-hidden animate-in fade-in slide-in-from-top-4 duration-300">
      {/* Active Call Banner */}
      <div className="bg-gradient-to-r from-blue-950/40 to-indigo-950/40 border-b border-slate-800 p-4 flex items-center justify-between gap-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-blue-500/10 border border-blue-500/20 flex items-center justify-center text-blue-400 shrink-0 animate-pulse">
            <Phone className="w-4.5 h-4.5" />
          </div>
          <div>
            <p className="text-[10px] font-bold text-blue-400 uppercase tracking-widest">Active Inbound Call</p>
            <p className="text-xs text-slate-400 mt-0.5">Logging outcome for {currentLead.first_name || ''} {currentLead.last_name}</p>
          </div>
        </div>
        
        {/* Duration Timer */}
        <div className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-950/60 border border-slate-800 rounded-xl">
          <Clock className="w-3.5 h-3.5 text-blue-400" />
          <span className="font-mono text-sm font-bold text-blue-400 tracking-wider">
            {formatDuration(callDuration)}
          </span>
        </div>
      </div>

      {/* Form Details */}
      <form onSubmit={handleDispositionSubmit} className="p-4 space-y-4">
        {error && (
          <div className="flex items-center gap-2 p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-xs">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <p className="font-medium">{error}</p>
          </div>
        )}

        {/* Status Options */}
        <div className="space-y-1.5">
          <label className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <UserCheck className="w-3.5 h-3.5 text-indigo-400" />
            Select Call Status
          </label>
          <div className="grid grid-cols-3 gap-2">
            {dispositionOptions.map((opt) => (
              <button
                key={opt}
                type="button"
                onClick={() => setSelectedStatus(opt)}
                className={`py-2 px-3 text-xs font-semibold rounded-lg border transition-all duration-150 text-center cursor-pointer ${
                  selectedStatus === opt
                    ? 'bg-blue-600 border-blue-500 text-white shadow-lg shadow-blue-600/25'
                    : 'bg-slate-800/50 border-slate-700/80 text-slate-300 hover:bg-slate-700/80 hover:border-slate-600'
                }`}
              >
                {opt}
              </button>
            ))}
          </div>
        </div>

        {/* Stage selection */}
        {selectedStatus === 'Picked' && (
          <div className="space-y-1.5 p-3 bg-indigo-500/5 border border-indigo-500/10 rounded-xl animate-in fade-in slide-in-from-top-2 duration-200">
            <label htmlFor="timeline-pipeline-stage" className="text-[10px] font-bold text-indigo-400 uppercase tracking-widest block">
              Advance Stage
            </label>
            <select
              id="timeline-pipeline-stage"
              value={targetStageId}
              onChange={(e) => setTargetStageId(e.target.value)}
              className="w-full bg-slate-950 border border-slate-800 text-slate-200 py-1.5 px-2.5 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500/50 text-xs"
            >
              <option value="" disabled>-- Select Stage --</option>
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
          <label htmlFor="call-remarks" className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">
            <FileText className="w-3.5 h-3.5 text-indigo-400" />
            Remarks / Conversation Notes
          </label>
          <textarea
            id="call-remarks"
            rows={3}
            value={remarks}
            onChange={(e) => setRemarks(e.target.value)}
            placeholder="Mandatory notes about the call context..."
            className="w-full bg-slate-950 border border-slate-800 rounded-xl py-2.5 px-3 text-slate-200 placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-blue-500/50 text-xs resize-none"
          />
        </div>

        {/* Submit */}
        <button
          type="submit"
          disabled={isSubmitDisabled}
          className="w-full flex items-center justify-center gap-1.5 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 disabled:cursor-not-allowed text-white font-semibold py-2.5 px-4 rounded-xl shadow-lg transition-all duration-150 transform active:scale-[0.98] text-xs cursor-pointer"
        >
          <CheckCircle className="w-4 h-4" />
          Submit Call Outcome
        </button>
      </form>
    </div>
  );
};
