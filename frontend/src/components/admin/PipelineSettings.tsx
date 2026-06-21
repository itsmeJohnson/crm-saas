import React, { useEffect, useState } from 'react';
import { usePipelineStore } from '../../store/pipelineStore';
import { ArrowUp, ArrowDown, Trash2, Plus, Edit2, Check, X, ShieldAlert, BadgeHelp, CheckCircle2 } from 'lucide-react';
import { PipelineStage } from '../../services/pipelineApi';

export const PipelineSettings: React.FC = () => {
  const {
    stages,
    isLoading,
    error: storeError,
    fetchStages,
    createStage,
    updateStage,
    reorderStages,
    deleteStage,
  } = usePipelineStore();

  const [newStageName, setNewStageName] = useState('');
  const [newStageDefault, setNewStageDefault] = useState(false);
  const [editingStageId, setEditingStageId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  
  // States for handling deletion fallback when leads are present
  const [stageToDelete, setStageToDelete] = useState<PipelineStage | null>(null);
  const [fallbackId, setFallbackId] = useState('');
  const [deletionError, setDeletionError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    fetchStages();
  }, [fetchStages]);

  const handleCreateStage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStageName.trim()) return;

    setActionError(null);
    try {
      await createStage({
        name: newStageName.trim(),
        is_system_default: newStageDefault,
      });
      setNewStageName('');
      setNewStageDefault(false);
    } catch (err: any) {
      setActionError(err.message || 'Failed to create stage');
    }
  };

  const handleStartEdit = (stage: PipelineStage) => {
    setEditingStageId(stage.id);
    setEditingName(stage.name);
  };

  const handleCancelEdit = () => {
    setEditingStageId(null);
    setEditingName('');
  };

  const handleSaveEdit = async (stageId: string) => {
    if (!editingName.trim()) return;
    setActionError(null);
    try {
      await updateStage(stageId, { name: editingName.trim() });
      setEditingStageId(null);
    } catch (err: any) {
      setActionError(err.message || 'Failed to update stage name');
    }
  };

  const handleSetDefault = async (stageId: string) => {
    setActionError(null);
    try {
      await updateStage(stageId, { is_system_default: true });
    } catch (err: any) {
      setActionError(err.message || 'Failed to set default stage');
    }
  };

  const handleMoveUp = async (index: number) => {
    if (index === 0) return;
    setActionError(null);
    const target = stages[index];
    const sibling = stages[index - 1];

    const orders = [
      { stage_id: target.id, new_position: sibling.order_position },
      { stage_id: sibling.id, new_position: target.order_position },
    ];

    try {
      await reorderStages(orders);
    } catch (err: any) {
      setActionError(err.message || 'Failed to reorder stages');
    }
  };

  const handleMoveDown = async (index: number) => {
    if (index === stages.length - 1) return;
    setActionError(null);
    const target = stages[index];
    const sibling = stages[index + 1];

    const orders = [
      { stage_id: target.id, new_position: sibling.order_position },
      { stage_id: sibling.id, new_position: target.order_position },
    ];

    try {
      await reorderStages(orders);
    } catch (err: any) {
      setActionError(err.message || 'Failed to reorder stages');
    }
  };

  const handleDeleteClick = async (stage: PipelineStage) => {
    setActionError(null);
    setDeletionError(null);
    try {
      // Try to delete stage without fallback first
      await deleteStage(stage.id);
    } catch (err: any) {
      // If error indicates leads are linked, open fallback prompt modal
      if (err.message && err.message.includes('contains') && err.message.includes('lead')) {
        setStageToDelete(stage);
        // Default fallback to first available stage that isn't the one being deleted
        const firstAvailableFallback = stages.find(s => s.id !== stage.id);
        setFallbackId(firstAvailableFallback ? firstAvailableFallback.id : '');
      } else {
        setActionError(err.message || 'Failed to delete stage');
      }
    }
  };

  const handleConfirmDeleteWithFallback = async () => {
    if (!stageToDelete || !fallbackId) return;
    setDeletionError(null);
    try {
      await deleteStage(stageToDelete.id, fallbackId);
      setStageToDelete(null);
      setFallbackId('');
    } catch (err: any) {
      setDeletionError(err.message || 'Failed to complete stage deletion');
    }
  };

  return (
    <div className="w-full max-w-4xl mx-auto space-y-8 p-6 bg-white dark:bg-slate-900 rounded-xl shadow-md border border-slate-200/60 dark:border-slate-800/80">
      
      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-slate-800 dark:text-slate-100">Pipeline Stages</h2>
        <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
          Manage and reorder lead progression stages. New leads default to the designated system default stage.
        </p>
      </div>

      {/* Errors */}
      {(storeError || actionError) && (
        <div className="p-4 bg-rose-50 dark:bg-rose-950/20 text-rose-600 dark:text-rose-400 rounded-lg flex items-start gap-2.5 border border-rose-200/50 dark:border-rose-900/30 text-sm">
          <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />
          <div>{actionError || storeError}</div>
        </div>
      )}

      {/* Add Stage Form */}
      <form onSubmit={handleCreateStage} className="bg-slate-50 dark:bg-slate-950/30 p-4 rounded-xl border border-slate-150 dark:border-slate-800/60 space-y-4">
        <h3 className="text-sm font-medium text-slate-700 dark:text-slate-300">Create New Pipeline Stage</h3>
        <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
          <input
            type="text"
            placeholder="e.g. Qualified, Proposal, Negotiating"
            value={newStageName}
            onChange={(e) => setNewStageName(e.target.value)}
            disabled={isLoading}
            className="w-full max-w-md px-3.5 py-2 text-sm bg-white dark:bg-slate-900 border border-slate-250 dark:border-slate-700 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-800 dark:text-slate-100"
          />
          <div className="flex items-center gap-2">
            <input
              type="checkbox"
              id="is_default"
              checked={newStageDefault}
              onChange={(e) => setNewStageDefault(e.target.checked)}
              disabled={isLoading}
              className="w-4 h-4 rounded text-indigo-600 border-slate-300 focus:ring-indigo-500"
            />
            <label htmlFor="is_default" className="text-sm text-slate-600 dark:text-slate-400 select-none">
              Set as default stage
            </label>
          </div>
          <button
            type="submit"
            disabled={isLoading || !newStageName.trim()}
            className="sm:ml-auto inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition disabled:opacity-50"
          >
            <Plus className="w-4 h-4" />
            Add Stage
          </button>
        </div>
      </form>

      {/* Stages List */}
      <div className="border border-slate-200/80 dark:border-slate-800 rounded-xl overflow-hidden">
        {isLoading && stages.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-sm">Loading stages...</div>
        ) : stages.length === 0 ? (
          <div className="py-12 text-center text-slate-400 text-sm">No pipeline stages configured.</div>
        ) : (
          <div className="divide-y divide-slate-200/80 dark:divide-slate-800 bg-white dark:bg-slate-900">
            {stages.map((stage, index) => (
              <div key={stage.id} className="flex items-center justify-between p-4 hover:bg-slate-50/50 dark:hover:bg-slate-950/20 transition">
                
                {/* Left side: Position and Name */}
                <div className="flex items-center gap-4 flex-1">
                  <span className="text-xs font-semibold text-slate-400 dark:text-slate-600 bg-slate-100 dark:bg-slate-800 w-6 h-6 rounded-full flex items-center justify-center">
                    {index + 1}
                  </span>

                  {editingStageId === stage.id ? (
                    <div className="flex items-center gap-2">
                      <input
                        type="text"
                        value={editingName}
                        onChange={(e) => setEditingName(e.target.value)}
                        className="px-2.5 py-1 text-sm bg-white dark:bg-slate-900 border border-slate-350 dark:border-slate-700 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500 text-slate-800 dark:text-slate-100"
                        autoFocus
                      />
                      <button
                        onClick={() => handleSaveEdit(stage.id)}
                        className="p-1 text-emerald-600 hover:bg-emerald-50 dark:hover:bg-emerald-950/30 rounded transition"
                      >
                        <Check className="w-4 h-4" />
                      </button>
                      <button
                        onClick={handleCancelEdit}
                        className="p-1 text-slate-400 hover:bg-slate-100 dark:hover:bg-slate-800 rounded transition"
                      >
                        <X className="w-4 h-4" />
                      </button>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2 group">
                      <span className="font-medium text-slate-800 dark:text-slate-200">{stage.name}</span>
                      <button
                        onClick={() => handleStartEdit(stage)}
                        className="p-1 opacity-0 group-hover:opacity-100 text-slate-400 hover:text-slate-600 dark:hover:text-slate-300 transition"
                      >
                        <Edit2 className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  )}

                  {/* System Default Badge */}
                  {stage.is_system_default ? (
                    <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400 bg-emerald-50 dark:bg-emerald-950/30 px-2.5 py-0.5 rounded-full border border-emerald-150 dark:border-emerald-900/30">
                      <CheckCircle2 className="w-3 h-3" />
                      Default Stage
                    </span>
                  ) : (
                    <button
                      onClick={() => handleSetDefault(stage.id)}
                      className="text-[11px] font-medium text-slate-500 hover:text-indigo-600 bg-slate-50 hover:bg-indigo-50 dark:bg-slate-800/40 dark:hover:bg-indigo-950/30 px-2.5 py-0.5 rounded-full border border-slate-200 dark:border-slate-700/60 transition"
                    >
                      Make Default
                    </button>
                  )}
                </div>

                {/* Right side: Reordering & Actions */}
                <div className="flex items-center gap-2.5">
                  
                  {/* Position Switchers */}
                  <div className="flex items-center border border-slate-200 dark:border-slate-800 rounded-lg overflow-hidden shrink-0">
                    <button
                      type="button"
                      onClick={() => handleMoveUp(index)}
                      disabled={index === 0}
                      className="p-1.5 bg-white hover:bg-slate-550 dark:bg-slate-900 dark:hover:bg-slate-800 disabled:opacity-30 text-slate-600 dark:text-slate-400 border-r border-slate-200 dark:border-slate-800 transition"
                    >
                      <ArrowUp className="w-4 h-4" />
                    </button>
                    <button
                      type="button"
                      onClick={() => handleMoveDown(index)}
                      disabled={index === stages.length - 1}
                      className="p-1.5 bg-white hover:bg-slate-550 dark:bg-slate-900 dark:hover:bg-slate-800 disabled:opacity-30 text-slate-600 dark:text-slate-400 transition"
                    >
                      <ArrowDown className="w-4 h-4" />
                    </button>
                  </div>

                  {/* Delete Button */}
                  <button
                    type="button"
                    onClick={() => handleDeleteClick(stage)}
                    disabled={stage.is_system_default}
                    className="p-2 text-slate-400 hover:text-rose-600 hover:bg-rose-50 dark:hover:bg-rose-950/20 disabled:opacity-20 rounded-lg transition"
                    title={stage.is_system_default ? 'Cannot delete default stage' : 'Delete stage'}
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                </div>

              </div>
            ))}
          </div>
        )}
      </div>

      {/* Fallback Selection Modal (rendered if deletion failed because leads exist) */}
      {stageToDelete && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md bg-white dark:bg-slate-900 rounded-xl shadow-xl border border-slate-250 dark:border-slate-800 overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-5 space-y-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-amber-50 dark:bg-amber-950/30 text-amber-600 dark:text-amber-400 rounded-full border border-amber-100 dark:border-amber-900/30">
                  <BadgeHelp className="w-6 h-6" />
                </div>
                <div>
                  <h3 className="text-base font-semibold text-slate-800 dark:text-slate-100">Move Leads Before Deleting</h3>
                  <p className="mt-1 text-sm text-slate-500 dark:text-slate-400">
                    The stage <span className="font-semibold text-slate-700 dark:text-slate-300">"{stageToDelete.name}"</span> currently has active leads. Please select a fallback stage to move these leads to.
                  </p>
                </div>
              </div>

              {deletionError && (
                <div className="p-3 bg-rose-50 dark:bg-rose-950/20 text-rose-600 dark:text-rose-400 rounded-lg text-xs border border-rose-200/50 dark:border-rose-900/30">
                  {deletionError}
                </div>
              )}

              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-500 dark:text-slate-400 uppercase tracking-wider">Fallback Stage</label>
                <select
                  value={fallbackId}
                  onChange={(e) => setFallbackId(e.target.value)}
                  className="w-full px-3 py-2 text-sm bg-white dark:bg-slate-900 border border-slate-300 dark:border-slate-700 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-800 dark:text-slate-100"
                >
                  {stages
                    .filter((s) => s.id !== stageToDelete.id)
                    .map((s) => (
                      <option key={s.id} value={s.id}>
                        {s.name}
                      </option>
                    ))}
                </select>
              </div>
            </div>

            <div className="bg-slate-50 dark:bg-slate-950/40 p-4 border-t border-slate-200 dark:border-slate-800 flex justify-end gap-3">
              <button
                type="button"
                onClick={() => {
                  setStageToDelete(null);
                  setFallbackId('');
                  setDeletionError(null);
                }}
                className="px-4 py-2 text-xs font-medium text-slate-700 hover:bg-slate-100 dark:text-slate-300 dark:hover:bg-slate-800 rounded-lg border border-slate-250 dark:border-slate-700 transition"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDeleteWithFallback}
                disabled={!fallbackId}
                className="px-4 py-2 text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition disabled:opacity-50"
              >
                Reassign & Delete
              </button>
            </div>
          </div>
        </div>
      )}

    </div>
  );
};
