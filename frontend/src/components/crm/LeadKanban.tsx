import React, { useMemo, useState, useEffect } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { useMetadataStore } from '../../store/metadataStore';
import { useUserStore } from '../../store/userStore';
import { LeadResponse } from '../../services/leadApi';
import { emailApi } from '../../services/emailApi';
import { GripVertical, Mail, Phone, Loader2, RefreshCw } from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { StageEmailDialog } from './StageEmailDialog';
import { configForStage } from '../../utils/stageAutomation';

interface LeadKanbanProps {
  onCardClick?: (lead: LeadResponse) => void;
}

// Coerce values that may arrive as strings (Decimal) so column totals never NaN.
const num = (v: number | string | null | undefined) => {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return Number.isFinite(n as number) ? (n as number) : 0;
};
const fmtValue = (v: number | string | null | undefined) => {
  const n = num(v);
  return n ? formatMoney(n) : null;
};

interface PendingMove { lead: LeadResponse; toStage: { id: string; name: string }; fromStageName?: string; }

export const LeadKanban: React.FC<LeadKanbanProps> = ({ onCardClick }) => {
  const { leads, updateLead, fetchLeads } = useLeadStore();
  const { pipelines, selectedPipelineId, selectPipeline, fetchBootstrap, loaded, isLoading } = useMetadataStore();
  const { users } = useUserStore();

  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overStageId, setOverStageId] = useState<string | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingMove | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  useEffect(() => {
    fetchBootstrap(true);
  }, []);

  const selected = useMemo(
    () => pipelines.find((p) => p.id === selectedPipelineId) || pipelines[0] || null,
    [pipelines, selectedPipelineId],
  );
  const stages = useMemo(
    () => (selected ? [...selected.stages].sort((a, b) => a.order_position - b.order_position) : []),
    [selected],
  );
  const stageIds = useMemo(() => new Set(stages.map((s) => s.id)), [stages]);
  const stageName = (id?: string | null) => stages.find((s) => s.id === id)?.name;

  const grouped = useMemo(() => {
    const map = new Map<string, LeadResponse[]>();
    stages.forEach((s) => map.set(s.id, []));
    for (const lead of leads) {
      if (lead.stage_id && stageIds.has(lead.stage_id)) {
        map.get(lead.stage_id)!.push(lead);
      } else if (stages.length > 0) {
        // Fallback matching: match by stage name (e.g. "Contacted", "Fresh Leads", "Followup", "Dropped")
        const stageNameLower = (lead.stage?.name || lead.status || '').toLowerCase().trim();
        const matched = stages.find((s) => s.name.toLowerCase().trim() === stageNameLower);
        if (matched) {
          map.get(matched.id)!.push(lead);
        } else {
          // If no match, place in first stage so deal card is visible and draggable
          map.get(stages[0].id)!.push(lead);
        }
      }
    }
    return map;
  }, [leads, stages, stageIds]);

  // On drop, check if the destination stage triggers an automated client email.
  const handleDrop = async (stageId: string) => {
    const id = draggingId;
    setDraggingId(null);
    setOverStageId(null);
    if (!id) return;
    const lead = leads.find((l) => l.id === id);
    const stage = stages.find((s) => s.id === stageId);
    if (!lead || !stage || lead.stage_id === stageId) return;

    setMoveError(null);
    const stageCfg = configForStage(stage.name);

    if (stageCfg?.sendsEmail) {
      // Open dialog to allow reviewing/customizing email before send
      setPending({ lead, toStage: { id: stage.id, name: stage.name }, fromStageName: stageName(lead.stage_id) });
    } else {
      // Immediate clean move
      try {
        await updateLead(lead.id, { stage_id: stage.id });
        setToast(`Moved "${lead.title}" to "${stage.name}".`);
        setTimeout(() => setToast(null), 3500);
        await fetchLeads();
      } catch (err: any) {
        setMoveError(err.message || 'Failed to update stage');
      }
    }
  };

  const confirmMove = async (opts: { withEmail: boolean; to?: string; subject?: string; body?: string }) => {
    if (!pending) return;
    const { lead, toStage } = pending;
    await updateLead(lead.id, { stage_id: toStage.id });
    if (opts.withEmail && opts.subject && opts.body) {
      await emailApi.send({ subject: opts.subject, body: opts.body, to: opts.to, lead_id: lead.id });
    }
    setPending(null);
    setToast(opts.withEmail ? `Moved to "${toStage.name}" and emailed the client.` : `Moved to "${toStage.name}".`);
    setTimeout(() => setToast(null), 3500);
    await fetchLeads();
  };

  if (isLoading || (!loaded && pipelines.length === 0)) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-brand-400" />
        <span className="text-sm font-medium">Loading Staging Pipelines & Deals...</span>
      </div>
    );
  }

  if (!selected) {
    return (
      <div className="py-16 text-center space-y-4">
        <p className="text-slate-400 text-sm">No sales pipeline active yet.</p>
        <button
          onClick={() => fetchBootstrap(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-semibold bg-brand-500 hover:bg-brand-600 text-white shadow-lg shadow-brand-500/25 transition-all cursor-pointer"
        >
          <RefreshCw className="w-4 h-4" /> Load Staging Pipeline
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Kanban Pipeline Control Bar */}
      <div className="bg-slate-900 border border-slate-700/80 rounded-2xl p-3.5 px-4 shadow-sm flex items-center justify-between flex-wrap gap-3">
        <div className="flex items-center gap-3 flex-wrap">
          <div className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-slate-400">
            <span className="w-2 h-2 rounded-full bg-brand-500" />
            <span>Staging Pipeline</span>
          </div>

          <div className="relative">
            <select
              value={selected.id}
              onChange={(e) => selectPipeline(e.target.value)}
              className="px-3.5 py-1.5 rounded-xl text-sm font-semibold bg-slate-950 border border-slate-700/80 text-slate-100 focus:outline-none focus:border-brand-500 focus:ring-2 focus:ring-brand-500/20 shadow-2xs cursor-pointer"
            >
              {pipelines.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}{p.is_default ? ' (Default)' : ''}
                </option>
              ))}
            </select>
          </div>

          <div className="flex items-center gap-2">
            <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-slate-800 text-slate-200 border border-slate-700/80 shadow-2xs">
              {stages.length} Stages
            </span>
            <span className="text-xs font-semibold px-2.5 py-1 rounded-lg bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shadow-2xs">
              {leads.length} Total Deals
            </span>
          </div>
          {moveError && <span className="text-xs text-rose-500 font-medium">{moveError}</span>}
        </div>

        <div className="inline-flex items-center gap-1.5 text-xs font-medium text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-3 py-1.5 rounded-xl shadow-2xs">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Drag cards between stages to advance deals & trigger auto-actions</span>
        </div>
      </div>

      {/* Columns List */}
      <div className="flex gap-4 overflow-x-auto pb-4 pt-1">
        {stages.map((stage) => {
          const items = grouped.get(stage.id) || [];
          const colValue = items.reduce((sum, l) => sum + num(l.value), 0);
          const over = overStageId === stage.id;
          return (
            <div
              key={stage.id}
              onDragOver={(e) => { e.preventDefault(); setOverStageId(stage.id); }}
              onDragLeave={() => setOverStageId((cur) => (cur === stage.id ? null : cur))}
              onDrop={() => handleDrop(stage.id)}
              className={`w-80 shrink-0 flex flex-col rounded-2xl border transition-all duration-200 ${
                over
                  ? 'border-brand-500 bg-brand-500/10 shadow-lg ring-2 ring-brand-500/20'
                  : 'border-slate-700/80 bg-slate-950/60 shadow-xs'
              }`}
            >
              {/* Column Header */}
              <div className="p-3.5 border-b border-slate-800/80 flex items-center justify-between">
                <div className="flex items-center gap-2.5 min-w-0">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0 ring-4"
                    style={{
                      backgroundColor: stage.color || '#4F46E5',
                      boxShadow: `0 0 10px ${(stage.color || '#4F46E5')}50`
                    }}
                  />
                  <span className="text-sm font-bold text-slate-100 truncate">
                    {stage.name}
                  </span>
                  <span className="text-xs font-bold text-slate-200 bg-slate-800 px-2 py-0.5 rounded-full border border-slate-700 shadow-2xs shrink-0">
                    {items.length}
                  </span>
                </div>
                {fmtValue(colValue) && (
                  <span className="text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-lg shrink-0 shadow-2xs">
                    {fmtValue(colValue)}
                  </span>
                )}
              </div>

              {/* Cards Container */}
              <div className="p-3 space-y-3 flex-1 min-h-[160px] max-h-[calc(100vh-320px)] overflow-y-auto">
                {items.map((lead) => {
                  const name = `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || lead.title;
                  const initials = name
                    .split(' ')
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((w) => w[0]?.toUpperCase())
                    .join('') || 'LD';

                  return (
                    <div
                      key={lead.id}
                      draggable
                      onDragStart={() => setDraggingId(lead.id)}
                      onDragEnd={() => { setDraggingId(null); setOverStageId(null); }}
                      onClick={() => onCardClick?.(lead)}
                      className={`group relative bg-slate-900 border border-slate-700/80 rounded-xl p-3.5 shadow-sm hover:shadow-md hover:border-brand-500/60 transition-all duration-200 cursor-grab active:cursor-grabbing select-none overflow-hidden ${
                        draggingId === lead.id ? 'opacity-30 scale-95' : ''
                      }`}
                    >
                      {/* Stage Color Left Accent Bar */}
                      <div
                        className="absolute left-0 top-2.5 bottom-2.5 w-1 rounded-r"
                        style={{ backgroundColor: stage.color || '#4F46E5' }}
                      />

                      {/* Header row: Avatar + Name + Grip */}
                      <div className="flex items-start gap-2.5 pl-1.5">
                        <div className="w-8 h-8 rounded-lg bg-gradient-to-tr from-brand-600 to-indigo-600 text-white font-bold text-xs flex items-center justify-center shrink-0 shadow-xs">
                          {initials}
                        </div>
                        <div className="min-w-0 flex-1">
                          <p className="text-sm font-bold text-slate-100 group-hover:text-brand-400 transition-colors truncate leading-tight">
                            {name}
                          </p>
                          {lead.title && lead.title !== name && (
                            <p className="text-xs text-slate-400 truncate mt-0.5">
                              {lead.title}
                            </p>
                          )}
                        </div>
                        <GripVertical className="w-4 h-4 text-slate-500 group-hover:text-slate-300 transition-colors shrink-0 mt-0.5" />
                      </div>

                      {/* Middle row: Deal Value + Priority */}
                      <div className="flex items-center gap-2 mt-3 pt-2.5 border-t border-slate-800/80 pl-1.5 flex-wrap justify-between">
                        <div>
                          {fmtValue(lead.value) ? (
                            <span className="inline-flex items-center gap-0.5 text-xs font-bold text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2 py-0.5 rounded-md shadow-2xs">
                              {fmtValue(lead.value)}
                            </span>
                          ) : (
                            <span className="text-[11px] text-slate-400 font-medium">No value set</span>
                          )}
                        </div>

                        <div className="flex items-center gap-1.5">
                          <span
                            className={`text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded-md border shadow-2xs ${
                              lead.priority === 'Urgent'
                                ? 'bg-rose-500/10 text-rose-400 border-rose-500/20'
                                : lead.priority === 'High'
                                ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                                : lead.priority === 'Low'
                                ? 'bg-slate-500/10 text-slate-400 border-slate-500/20'
                                : 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                            }`}
                          >
                            {lead.priority || 'Medium'}
                          </span>
                        </div>
                      </div>

                      {/* Footer row: channels & owner */}
                      <div className="flex items-center justify-between mt-2 pt-2 border-t border-slate-800/60 pl-1.5 text-[11px] text-slate-400">
                        {(() => {
                          const assignedUser = users.find((u) => u.id === lead.assigned_user_id);
                          const ownerName = assignedUser
                            ? `${assignedUser.first_name || ''} ${assignedUser.last_name || ''}`.trim() || assignedUser.email
                            : (lead.source || 'Direct');
                          return (
                            <span className="truncate max-w-[140px] font-medium text-slate-300">
                              {ownerName}
                            </span>
                          );
                        })()}
                        <div className="flex items-center gap-2">
                          {lead.email && <Mail className="w-3.5 h-3.5 text-slate-400 hover:text-brand-500 transition-colors" />}
                          {lead.phone && <Phone className="w-3.5 h-3.5 text-slate-400 hover:text-emerald-500 transition-colors" />}
                        </div>
                      </div>
                    </div>
                  );
                })}

                {items.length === 0 && (
                  <div className="border-2 border-dashed border-slate-800 rounded-xl py-12 flex flex-col items-center justify-center gap-2 text-slate-400 text-xs text-center px-4">
                    <span>Drop leads here to advance</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {pending && (
        <StageEmailDialog
          lead={pending.lead}
          toStageName={pending.toStage.name}
          fromStageName={pending.fromStageName}
          onCancel={() => setPending(null)}
          onConfirm={confirmMove}
        />
      )}

      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl text-sm font-medium shadow-lg bg-slate-800 text-slate-100 border border-slate-700">
          {toast}
        </div>
      )}
    </div>
  );
};
