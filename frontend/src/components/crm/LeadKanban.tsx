import React, { useMemo, useState } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { useMetadataStore } from '../../store/metadataStore';
import { LeadResponse } from '../../services/leadApi';
import { DollarSign, GripVertical } from 'lucide-react';
import { formatMoney } from '../../utils/currency';

interface LeadKanbanProps {
  onCardClick?: (lead: LeadResponse) => void;
}

const fmtValue = (v: number | null) =>
  v === null || v === undefined ? null : formatMoney(v);

export const LeadKanban: React.FC<LeadKanbanProps> = ({ onCardClick }) => {
  const { leads, updateLead, fetchLeads } = useLeadStore();
  const { pipelines, selectedPipelineId, selectPipeline } = useMetadataStore();

  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overStageId, setOverStageId] = useState<string | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);

  const selected = useMemo(
    () => pipelines.find((p) => p.id === selectedPipelineId) || pipelines[0] || null,
    [pipelines, selectedPipelineId],
  );
  const stages = useMemo(
    () => (selected ? [...selected.stages].sort((a, b) => a.order_position - b.order_position) : []),
    [selected],
  );

  const stageIds = useMemo(() => new Set(stages.map((s) => s.id)), [stages]);

  // Group the currently loaded leads by stage. Leads whose stage belongs to a
  // different pipeline are not shown on this board.
  const grouped = useMemo(() => {
    const map = new Map<string, LeadResponse[]>();
    stages.forEach((s) => map.set(s.id, []));
    for (const lead of leads) {
      if (lead.stage_id && stageIds.has(lead.stage_id)) {
        map.get(lead.stage_id)!.push(lead);
      }
    }
    return map;
  }, [leads, stages, stageIds]);

  const handleDrop = async (stageId: string) => {
    const id = draggingId;
    setDraggingId(null);
    setOverStageId(null);
    if (!id) return;
    const lead = leads.find((l) => l.id === id);
    if (!lead || lead.stage_id === stageId) return;
    setMoveError(null);
    try {
      await updateLead(id, { stage_id: stageId });
      await fetchLeads();
    } catch (e: any) {
      setMoveError(e.message || 'Failed to move lead');
    }
  };

  if (!selected) {
    return <div className="py-12 text-center text-slate-500 text-sm">No pipelines configured. Create one in Settings → Pipelines.</div>;
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <label className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Pipeline</label>
        <select
          value={selected.id}
          onChange={(e) => selectPipeline(e.target.value)}
          className="px-3.5 py-2 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50"
        >
          {pipelines.map((p) => (
            <option key={p.id} value={p.id}>{p.name}{p.is_default ? ' (default)' : ''}</option>
          ))}
        </select>
        {moveError && <span className="text-xs text-red-400">{moveError}</span>}
      </div>

      <div className="flex gap-4 overflow-x-auto pb-4">
        {stages.map((stage) => {
          const items = grouped.get(stage.id) || [];
          const colValue = items.reduce((sum, l) => sum + (l.value || 0), 0);
          return (
            <div
              key={stage.id}
              onDragOver={(e) => { e.preventDefault(); setOverStageId(stage.id); }}
              onDragLeave={() => setOverStageId((cur) => (cur === stage.id ? null : cur))}
              onDrop={() => handleDrop(stage.id)}
              className={`w-72 shrink-0 flex flex-col rounded-2xl border transition-colors ${
                overStageId === stage.id ? 'border-brand-500/60 bg-brand-500/5' : 'border-slate-800 bg-slate-900/40'
              }`}
            >
              <div className="p-3 border-b border-slate-800/80 flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: stage.color || '#4F46E5' }} />
                  <span className="text-sm font-semibold text-slate-200">{stage.name}</span>
                  <span className="text-[11px] text-slate-500 bg-slate-800/60 px-1.5 py-0.5 rounded-full">{items.length}</span>
                </div>
                {fmtValue(colValue) && <span className="text-[11px] text-emerald-400 font-medium">{fmtValue(colValue)}</span>}
              </div>

              <div className="p-2.5 space-y-2.5 flex-1 min-h-[120px] max-h-[65vh] overflow-y-auto">
                {items.map((lead) => (
                  <div
                    key={lead.id}
                    draggable
                    onDragStart={() => setDraggingId(lead.id)}
                    onDragEnd={() => { setDraggingId(null); setOverStageId(null); }}
                    onClick={() => onCardClick?.(lead)}
                    className={`group p-3 bg-slate-950/60 border border-slate-800 rounded-xl cursor-pointer hover:border-slate-700 transition-all ${
                      draggingId === lead.id ? 'opacity-40' : ''
                    }`}
                  >
                    <div className="flex items-start gap-2">
                      <GripVertical className="w-3.5 h-3.5 text-slate-600 mt-0.5 shrink-0" />
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-semibold text-slate-200 truncate">{lead.title}</p>
                        <p className="text-xs text-slate-500 truncate mt-0.5">
                          {`${lead.first_name || ''} ${lead.last_name}`.trim()}
                          {lead.company_name ? ` · ${lead.company_name}` : ''}
                        </p>
                        <div className="flex items-center gap-2 mt-1.5">
                          {fmtValue(lead.value) && (
                            <span className="inline-flex items-center gap-0.5 text-[11px] text-emerald-400">
                              <DollarSign className="w-3 h-3" />{fmtValue(lead.value)}
                            </span>
                          )}
                          <span className={`text-[10px] px-1.5 py-0.5 rounded-full ${
                            lead.priority === 'Urgent' ? 'bg-red-500/10 text-red-400'
                            : lead.priority === 'High' ? 'bg-amber-500/10 text-amber-400'
                            : 'bg-slate-800 text-slate-400'
                          }`}>{lead.priority}</span>
                        </div>
                      </div>
                    </div>
                  </div>
                ))}
                {items.length === 0 && (
                  <div className="py-8 text-center text-[11px] text-slate-600 select-none">Drop leads here</div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
};
