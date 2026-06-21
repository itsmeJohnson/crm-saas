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
  LogOut
} from 'lucide-react';
import { useDialerStore } from '../../store/dialerStore';
import { usePipelineStore } from '../../store/pipelineStore';
import { MaskedField } from '../common/MaskedField';

export const DialerConsole: React.FC = () => {
  const {
    agentState,
    currentLead,
    breakReason,
    callDuration,
    isLoading,
    error,
    fetchCurrentState,
    startCalling,
    submitDisposition,
    goOnBreak,
    endBreak
  } = useDialerStore();

  const { stages, fetchStages } = usePipelineStore();

  // Local state for break countdown (15 minutes = 900 seconds)
  const [breakTimeRemaining, setBreakTimeRemaining] = useState(900);
  // Local state for disposition form
  const [selectedStatus, setSelectedStatus] = useState<string | null>(null);
  const [remarks, setRemarks] = useState('');
  const [targetStageId, setTargetStageId] = useState('');
  const [collectivePooling, setCollectivePooling] = useState(false);
  const [showBreakMenu, setShowBreakMenu] = useState(false);

  // Fetch initial dialer and pipeline stage details on mount
  useEffect(() => {
    fetchCurrentState().catch(() => {});
    fetchStages().catch(() => {});
  }, [fetchCurrentState, fetchStages]);

  // Interval for break countdown
  useEffect(() => {
    let interval: any = null;
    if (agentState === 'BREAK') {
      setBreakTimeRemaining(900);
      interval = setInterval(() => {
        setBreakTimeRemaining((prev) => (prev > 0 ? prev - 1 : 0));
      }, 1000);
    } else {
      setBreakTimeRemaining(900);
      if (interval) clearInterval(interval);
    }
    return () => {
      if (interval) clearInterval(interval);
    };
  }, [agentState]);

  // Reset form inputs when current lead changes
  useEffect(() => {
    if (!currentLead) {
      setSelectedStatus(null);
      setRemarks('');
      setTargetStageId('');
    }
  }, [currentLead]);

  const formatDuration = (seconds: number): string => {
    const mins = Math.floor(seconds / 60);
    const secs = seconds % 60;
    return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
  };

  const handleStartDialing = async () => {
    try {
      await startCalling(collectivePooling);
    } catch (err) {}
  };

  const handleRequestBreak = async (reason: string) => {
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
    if (!selectedStatus || !remarks || (selectedStatus === 'Picked' && !targetStageId)) {
      return;
    }
    try {
      await submitDisposition({
        status: selectedStatus,
        remarks: remarks,
        custom_pipeline_stage_id: selectedStatus === 'Picked' ? targetStageId : undefined
      });
    } catch (err) {}
  };

  const breakOptions = ['Lunch', 'Tea', 'Meeting', 'General'];
  const dispositionOptions = ['RNR', 'Switch Off', 'Busy', 'Not Exist', 'Out of Service', 'Picked'];

  const isSubmitDisabled = !selectedStatus || !remarks.trim() || (selectedStatus === 'Picked' && !targetStageId) || isLoading;

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
              </div>
            )}
          </div>
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
                {selectedStatus === 'Picked' && (
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

                {/* Call Remarks Textarea */}
                <div className="space-y-2">
                  <label htmlFor="remarks" className="text-sm font-semibold text-slate-300 flex items-center gap-1.5">
                    <FileText className="w-4 h-4 text-indigo-400" />
                    Call Notes & Remarks
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
