import React, { useEffect, useMemo, useState } from 'react';
import { useMetadataStore } from '../../store/metadataStore';
import { pipelineApi, PipelineStage, Pipeline } from '../../services/pipelineApi';
import {
  ArrowUp, ArrowDown, Trash2, Plus, Edit2, Check, X, ShieldAlert, BadgeHelp,
  CheckCircle2, GitBranch,
} from 'lucide-react';

export const PipelineSettings: React.FC = () => {
  const {
    pipelines,
    selectedPipelineId,
    isLoading,
    error: storeError,
    fetchBootstrap,
    refresh,
    selectPipeline,
  } = useMetadataStore();

  const selected: Pipeline | null = useMemo(
    () => pipelines.find((p) => p.id === selectedPipelineId) || pipelines[0] || null,
    [pipelines, selectedPipelineId],
  );
  const stages = useMemo(
    () => (selected ? [...selected.stages].sort((a, b) => a.order_position - b.order_position) : []),
    [selected],
  );

  // Pipeline-level state
  const [newPipelineName, setNewPipelineName] = useState('');
  const [editingPipelineId, setEditingPipelineId] = useState<string | null>(null);
  const [editingPipelineName, setEditingPipelineName] = useState('');
  const [pipelineToDelete, setPipelineToDelete] = useState<Pipeline | null>(null);
  const [reassignPipelineId, setReassignPipelineId] = useState('');

  // Stage-level state
  const [newStageName, setNewStageName] = useState('');
  const [newStageDefault, setNewStageDefault] = useState(false);
  const [editingStageId, setEditingStageId] = useState<string | null>(null);
  const [editingName, setEditingName] = useState('');
  const [stageToDelete, setStageToDelete] = useState<PipelineStage | null>(null);
  const [fallbackId, setFallbackId] = useState('');
  const [deletionError, setDeletionError] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    fetchBootstrap();
  }, [fetchBootstrap]);

  const run = async (fn: () => Promise<any>, fallbackMsg: string) => {
    setActionError(null);
    try {
      await fn();
      await refresh();
    } catch (err: any) {
      setActionError(err.response?.data?.detail || err.message || fallbackMsg);
      throw err;
    }
  };

  // ── Pipeline handlers ──
  const handleCreatePipeline = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPipelineName.trim()) return;
    try {
      const created = await pipelineApi.createPipelineEntity({
        name: newPipelineName.trim(),
        is_default: pipelines.length === 0,
      });
      setNewPipelineName('');
      await refresh();
      selectPipeline(created.id);
    } catch (err: any) {
      setActionError(err.response?.data?.detail || err.message || 'Failed to create pipeline');
    }
  };

  const handleSavePipelineName = async (id: string) => {
    if (!editingPipelineName.trim()) return;
    await run(() => pipelineApi.updatePipelineEntity(id, { name: editingPipelineName.trim() }), 'Failed to rename pipeline');
    setEditingPipelineId(null);
  };

  const handleSetDefaultPipeline = async (id: string) => {
    await run(() => pipelineApi.updatePipelineEntity(id, { is_default: true }), 'Failed to set default pipeline');
  };

  const handleDeletePipelineClick = async (p: Pipeline) => {
    setActionError(null);
    setDeletionError(null);
    try {
      await pipelineApi.deletePipelineEntity(p.id);
      await refresh();
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || '';
      // Blocked because leads still reference this pipeline — ask for a reassignment target.
      if (/lead|reassign|reference/i.test(detail)) {
        setPipelineToDelete(p);
        const firstOther = pipelines.find((pl) => pl.id !== p.id);
        setReassignPipelineId(firstOther ? firstOther.id : '');
      } else {
        setActionError(detail || 'Failed to delete pipeline');
      }
    }
  };

  const handleConfirmDeletePipeline = async () => {
    if (!pipelineToDelete || !reassignPipelineId) return;
    setDeletionError(null);
    try {
      await pipelineApi.deletePipelineEntity(pipelineToDelete.id, reassignPipelineId);
      setPipelineToDelete(null);
      setReassignPipelineId('');
      await refresh();
    } catch (err: any) {
      setDeletionError(err.response?.data?.detail || err.message || 'Failed to delete pipeline');
    }
  };

  // ── Stage handlers (scoped to the selected pipeline) ──
  const handleCreateStage = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newStageName.trim() || !selected) return;
    try {
      await run(
        () => pipelineApi.createStage({
          pipeline_id: selected.id,
          name: newStageName.trim(),
          is_system_default: newStageDefault,
          order_position: (stages[stages.length - 1]?.order_position || 0) + 1,
        }),
        'Failed to create stage',
      );
      setNewStageName('');
      setNewStageDefault(false);
    } catch { /* surfaced via actionError */ }
  };

  const handleSaveEdit = async (stageId: string) => {
    if (!editingName.trim()) return;
    await run(() => pipelineApi.updateStage(stageId, { name: editingName.trim() }), 'Failed to rename stage');
    setEditingStageId(null);
  };

  const handleSetDefault = async (stageId: string) => {
    await run(() => pipelineApi.updateStage(stageId, { is_system_default: true }), 'Failed to set default stage');
  };

  const swap = async (index: number, dir: -1 | 1) => {
    const target = stages[index];
    const sibling = stages[index + dir];
    if (!target || !sibling) return;
    await run(
      () => pipelineApi.reorderStages([
        { stage_id: target.id, new_position: sibling.order_position },
        { stage_id: sibling.id, new_position: target.order_position },
      ]),
      'Failed to reorder stages',
    );
  };

  const handleDeleteStageClick = async (stage: PipelineStage) => {
    setActionError(null);
    setDeletionError(null);
    try {
      await pipelineApi.deleteStage(stage.id);
      await refresh();
    } catch (err: any) {
      const detail = err.response?.data?.detail || err.message || '';
      if (/contain|lead|reassign/i.test(detail)) {
        setStageToDelete(stage);
        const firstAvailable = stages.find((s) => s.id !== stage.id);
        setFallbackId(firstAvailable ? firstAvailable.id : '');
      } else {
        setActionError(detail || 'Failed to delete stage');
      }
    }
  };

  const handleConfirmDeleteStage = async () => {
    if (!stageToDelete || !fallbackId) return;
    setDeletionError(null);
    try {
      await pipelineApi.deleteStage(stageToDelete.id, fallbackId);
      setStageToDelete(null);
      setFallbackId('');
      await refresh();
    } catch (err: any) {
      setDeletionError(err.response?.data?.detail || err.message || 'Failed to delete stage');
    }
  };

  // Inputs share one dark-first style; the app's slate-var inversion themes them for light mode.
  const inputCls =
    'px-3.5 py-2 text-sm bg-slate-900 border border-slate-700 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-100';

  return (
    <div className="w-full max-w-4xl mx-auto space-y-8 p-6 bg-slate-900 rounded-xl shadow-md border border-slate-800/80">

      {/* Header */}
      <div>
        <h2 className="text-xl font-semibold text-slate-100">Pipelines &amp; Stages</h2>
        <p className="mt-1 text-sm text-slate-400">
          Create multiple pipelines (e.g. Sales, Admissions, Support) and manage the stages within each. New leads default to the selected pipeline's default stage.
        </p>
      </div>

      {(storeError || actionError) && (
        <div className="p-4 bg-rose-950/20 text-rose-400 rounded-lg flex items-start gap-2.5 border border-rose-900/30 text-sm">
          <ShieldAlert className="w-4 h-4 mt-0.5 shrink-0" />
          <div>{actionError || storeError}</div>
        </div>
      )}

      {/* Pipeline selector + create */}
      <div className="bg-slate-950/30 p-4 rounded-xl border border-slate-800/60 space-y-4">
        <h3 className="text-sm font-medium text-slate-300 flex items-center gap-2">
          <GitBranch className="w-4 h-4" /> Pipelines
        </h3>
        <div className="flex flex-wrap gap-2">
          {pipelines.map((p) => (
            <div
              key={p.id}
              className={`group flex items-center gap-2 pl-3 pr-2 py-1.5 rounded-lg border text-sm cursor-pointer transition ${
                selected?.id === p.id
                  ? 'bg-indigo-600 border-indigo-600 text-white'
                  : 'bg-slate-900 border-slate-700 text-slate-300 hover:border-indigo-400'
              }`}
              onClick={() => selectPipeline(p.id)}
            >
              {editingPipelineId === p.id ? (
                <>
                  <input
                    value={editingPipelineName}
                    onChange={(e) => setEditingPipelineName(e.target.value)}
                    onClick={(e) => e.stopPropagation()}
                    className="px-2 py-0.5 text-sm rounded bg-slate-900 text-slate-100 border border-slate-700 focus:outline-none"
                    autoFocus
                  />
                  <button onClick={(e) => { e.stopPropagation(); handleSavePipelineName(p.id); }} className="p-0.5"><Check className="w-3.5 h-3.5" /></button>
                  <button onClick={(e) => { e.stopPropagation(); setEditingPipelineId(null); }} className="p-0.5"><X className="w-3.5 h-3.5" /></button>
                </>
              ) : (
                <>
                  <span className="font-medium">{p.name}</span>
                  {p.is_default && (
                    <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${selected?.id === p.id ? 'bg-white/20' : 'bg-emerald-950/40 text-emerald-400'}`}>
                      default
                    </span>
                  )}
                  <button
                    onClick={(e) => { e.stopPropagation(); setEditingPipelineId(p.id); setEditingPipelineName(p.name); }}
                    className="p-0.5 opacity-0 group-hover:opacity-100 transition"
                    title="Rename pipeline"
                  >
                    <Edit2 className="w-3 h-3" />
                  </button>
                  {!p.is_default && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleSetDefaultPipeline(p.id); }}
                      className="p-0.5 opacity-0 group-hover:opacity-100 transition"
                      title="Make default pipeline"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                  {pipelines.length > 1 && (
                    <button
                      onClick={(e) => { e.stopPropagation(); handleDeletePipelineClick(p); }}
                      className="p-0.5 opacity-0 group-hover:opacity-100 transition"
                      title="Delete pipeline"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  )}
                </>
              )}
            </div>
          ))}
        </div>
        <form onSubmit={handleCreatePipeline} className="flex items-center gap-2">
          <input
            type="text"
            placeholder="New pipeline name (e.g. Admissions)"
            value={newPipelineName}
            onChange={(e) => setNewPipelineName(e.target.value)}
            className={`flex-1 max-w-sm ${inputCls}`}
          />
          <button
            type="submit"
            disabled={!newPipelineName.trim()}
            className="inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition disabled:opacity-50"
          >
            <Plus className="w-4 h-4" /> New Pipeline
          </button>
        </form>
      </div>

      {/* Stage management for selected pipeline */}
      {selected && (
        <>
          <form onSubmit={handleCreateStage} className="bg-slate-950/30 p-4 rounded-xl border border-slate-800/60 space-y-4">
            <h3 className="text-sm font-medium text-slate-300">
              Add stage to <span className="text-indigo-400">{selected.name}</span>
            </h3>
            <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
              <input
                type="text"
                placeholder="e.g. Qualified, Proposal, Negotiating"
                value={newStageName}
                onChange={(e) => setNewStageName(e.target.value)}
                disabled={isLoading}
                className={`w-full max-w-md ${inputCls}`}
              />
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="is_default"
                  checked={newStageDefault}
                  onChange={(e) => setNewStageDefault(e.target.checked)}
                  className="w-4 h-4 rounded text-indigo-600 border-slate-700 focus:ring-indigo-500"
                />
                <label htmlFor="is_default" className="text-sm text-slate-400 select-none">
                  Set as default stage
                </label>
              </div>
              <button
                type="submit"
                disabled={!newStageName.trim()}
                className="sm:ml-auto inline-flex items-center gap-1.5 px-4 py-2 text-sm font-medium text-white bg-indigo-600 hover:bg-indigo-700 rounded-lg shadow-sm transition disabled:opacity-50"
              >
                <Plus className="w-4 h-4" /> Add Stage
              </button>
            </div>
          </form>

          <div className="border border-slate-800 rounded-xl overflow-hidden">
            {stages.length === 0 ? (
              <div className="py-12 text-center text-slate-400 text-sm">No stages in this pipeline yet.</div>
            ) : (
              <div className="divide-y divide-slate-800 bg-slate-900">
                {stages.map((stage, index) => (
                  <div key={stage.id} className="flex items-center justify-between p-4 hover:bg-slate-950/20 transition">
                    <div className="flex items-center gap-4 flex-1">
                      <span className="text-xs font-semibold text-slate-400 bg-slate-800 w-6 h-6 rounded-full flex items-center justify-center">
                        {index + 1}
                      </span>
                      {editingStageId === stage.id ? (
                        <div className="flex items-center gap-2">
                          <input
                            type="text"
                            value={editingName}
                            onChange={(e) => setEditingName(e.target.value)}
                            className="px-2.5 py-1 text-sm bg-slate-900 border border-slate-700 rounded focus:outline-none focus:ring-1 focus:ring-indigo-500 text-slate-100"
                            autoFocus
                          />
                          <button onClick={() => handleSaveEdit(stage.id)} className="p-1 text-emerald-400 hover:bg-emerald-950/30 rounded transition"><Check className="w-4 h-4" /></button>
                          <button onClick={() => setEditingStageId(null)} className="p-1 text-slate-400 hover:bg-slate-800 rounded transition"><X className="w-4 h-4" /></button>
                        </div>
                      ) : (
                        <div className="flex items-center gap-2 group">
                          <span className="font-medium text-slate-200">{stage.name}</span>
                          <button onClick={() => { setEditingStageId(stage.id); setEditingName(stage.name); }} className="p-1 opacity-0 group-hover:opacity-100 text-slate-400 hover:text-slate-300 transition"><Edit2 className="w-3.5 h-3.5" /></button>
                        </div>
                      )}
                      {stage.is_system_default ? (
                        <span className="inline-flex items-center gap-1 text-[11px] font-medium text-emerald-400 bg-emerald-950/30 px-2.5 py-0.5 rounded-full border border-emerald-900/30">
                          <CheckCircle2 className="w-3 h-3" /> Default Stage
                        </span>
                      ) : (
                        <button onClick={() => handleSetDefault(stage.id)} className="text-[11px] font-medium text-slate-400 hover:text-indigo-400 bg-slate-800/40 hover:bg-indigo-950/30 px-2.5 py-0.5 rounded-full border border-slate-700/60 transition">
                          Make Default
                        </button>
                      )}
                    </div>
                    <div className="flex items-center gap-2.5">
                      <div className="flex items-center border border-slate-800 rounded-lg overflow-hidden shrink-0">
                        <button type="button" onClick={() => swap(index, -1)} disabled={index === 0} className="p-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-30 text-slate-400 border-r border-slate-800 transition"><ArrowUp className="w-4 h-4" /></button>
                        <button type="button" onClick={() => swap(index, 1)} disabled={index === stages.length - 1} className="p-1.5 bg-slate-900 hover:bg-slate-800 disabled:opacity-30 text-slate-400 transition"><ArrowDown className="w-4 h-4" /></button>
                      </div>
                      <button type="button" onClick={() => handleDeleteStageClick(stage)} disabled={stage.is_system_default} className="p-2 text-slate-400 hover:text-rose-400 hover:bg-rose-950/20 disabled:opacity-20 rounded-lg transition" title={stage.is_system_default ? 'Cannot delete default stage' : 'Delete stage'}>
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </>
      )}

      {/* Stage deletion fallback modal */}
      {stageToDelete && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md bg-slate-900 rounded-xl shadow-xl border border-slate-800 overflow-hidden">
            <div className="p-5 space-y-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-amber-950/30 text-amber-400 rounded-full border border-amber-900/30"><BadgeHelp className="w-6 h-6" /></div>
                <div>
                  <h3 className="text-base font-semibold text-slate-100">Move Leads Before Deleting</h3>
                  <p className="mt-1 text-sm text-slate-400">
                    The stage <span className="font-semibold text-slate-300">"{stageToDelete.name}"</span> currently has active leads. Select a fallback stage to move them to.
                  </p>
                </div>
              </div>
              {deletionError && <div className="p-3 bg-rose-950/20 text-rose-400 rounded-lg text-xs border border-rose-900/30">{deletionError}</div>}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Fallback Stage</label>
                <select value={fallbackId} onChange={(e) => setFallbackId(e.target.value)} className="w-full px-3 py-2 text-sm bg-slate-900 border border-slate-700 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-100">
                  {stages.filter((s) => s.id !== stageToDelete.id).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
            </div>
            <div className="bg-slate-950/40 p-4 border-t border-slate-800 flex justify-end gap-3">
              <button type="button" onClick={() => { setStageToDelete(null); setFallbackId(''); setDeletionError(null); }} className="px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 rounded-lg border border-slate-700 transition">Cancel</button>
              <button type="button" onClick={handleConfirmDeleteStage} disabled={!fallbackId} className="px-4 py-2 text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition disabled:opacity-50">Reassign &amp; Delete</button>
            </div>
          </div>
        </div>
      )}

      {/* Pipeline deletion reassignment modal */}
      {pipelineToDelete && (
        <div className="fixed inset-0 bg-slate-900/60 backdrop-blur-sm flex items-center justify-center p-4 z-50">
          <div className="w-full max-w-md bg-slate-900 rounded-xl shadow-xl border border-slate-800 overflow-hidden">
            <div className="p-5 space-y-4">
              <div className="flex items-start gap-3">
                <div className="p-2 bg-amber-950/30 text-amber-400 rounded-full border border-amber-900/30"><BadgeHelp className="w-6 h-6" /></div>
                <div>
                  <h3 className="text-base font-semibold text-slate-100">Move Leads Before Deleting</h3>
                  <p className="mt-1 text-sm text-slate-400">
                    The pipeline <span className="font-semibold text-slate-300">"{pipelineToDelete.name}"</span> has active leads. Select a pipeline to reassign them to.
                  </p>
                </div>
              </div>
              {deletionError && <div className="p-3 bg-rose-950/20 text-rose-400 rounded-lg text-xs border border-rose-900/30">{deletionError}</div>}
              <div className="space-y-2">
                <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Reassign To Pipeline</label>
                <select value={reassignPipelineId} onChange={(e) => setReassignPipelineId(e.target.value)} className="w-full px-3 py-2 text-sm bg-slate-900 border border-slate-700 rounded-lg shadow-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 focus:border-indigo-500 text-slate-100">
                  {pipelines.filter((p) => p.id !== pipelineToDelete.id).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
                </select>
              </div>
            </div>
            <div className="bg-slate-950/40 p-4 border-t border-slate-800 flex justify-end gap-3">
              <button type="button" onClick={() => { setPipelineToDelete(null); setReassignPipelineId(''); setDeletionError(null); }} className="px-4 py-2 text-xs font-medium text-slate-300 hover:bg-slate-800 rounded-lg border border-slate-700 transition">Cancel</button>
              <button type="button" onClick={handleConfirmDeletePipeline} disabled={!reassignPipelineId} className="px-4 py-2 text-xs font-medium text-white bg-rose-600 hover:bg-rose-700 rounded-lg shadow-sm transition disabled:opacity-50">Reassign &amp; Delete</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
