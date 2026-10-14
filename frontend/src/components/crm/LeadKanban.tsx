import React, { useMemo, useState, useEffect } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { useMetadataStore } from '../../store/metadataStore';
import { useUserStore } from '../../store/userStore';
import { LeadResponse } from '../../services/leadApi';
import { emailApi } from '../../services/emailApi';
import { Mail, Phone, Loader2, RefreshCw, MessageCircle, Plus, CheckCircle2, XCircle } from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { StageEmailDialog } from './StageEmailDialog';
import { configForStage } from '../../utils/stageAutomation';

interface LeadKanbanProps {
  onCardClick?: (lead: LeadResponse) => void;
  onChatClick?: (lead: LeadResponse, channel?: 'whatsapp' | 'sms') => void;
  onCallClick?: (leadId: string) => void;
  onAddDeal?: (stageId?: string) => void;
}

const num = (v: number | string | null | undefined): number => {
  const n = typeof v === 'string' ? parseFloat(v) : v;
  return Number.isFinite(n as number) ? (n as number) : 0;
};

const fmtValue = (v: number | string | null | undefined): string | null => {
  const n = num(v);
  return n ? formatMoney(n) : null;
};

interface PendingMove {
  lead: LeadResponse;
  toStage: { id: string; name: string };
  fromStageName?: string;
}

export const LeadKanban: React.FC<LeadKanbanProps> = ({
  onCardClick,
  onChatClick,
  onCallClick,
  onAddDeal,
}) => {
  const {
    leads,
    kanbanBoard,
    loadingStageId,
    loadMoreStageCards,
    moveKanbanCard,
    fetchKanbanBoard,
    updateLead,
    fetchLeads,
  } = useLeadStore();
  const { pipelines, selectedPipelineId, selectPipeline, fetchBootstrap, loaded, isLoading } = useMetadataStore();
  const { users } = useUserStore();

  const [draggingId, setDraggingId] = useState<string | null>(null);
  const [overStageId, setOverStageId] = useState<string | null>(null);
  const [moveError, setMoveError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingMove | null>(null);
  const [toast, setToast] = useState<string | null>(null);

  // Modals for Loss Reason and Won Confirmation
  const [lossModalLead, setLossModalLead] = useState<{ lead: LeadResponse; stageId: string; stageName: string } | null>(null);
  const [lossReason, setLossReason] = useState('Price / Budget too high');
  const [lossNote, setLossNote] = useState('');

  const [wonModalLead, setWonModalLead] = useState<{ lead: LeadResponse; stageId: string; stageName: string } | null>(null);

  useEffect(() => {
    fetchBootstrap(true);
    fetchKanbanBoard(selectedPipelineId || undefined);
  }, [selectedPipelineId]);

  const selected = useMemo(
    () => pipelines.find((p) => p.id === selectedPipelineId) || pipelines[0] || null,
    [pipelines, selectedPipelineId],
  );

  const stages = useMemo(() => {
    if (!selected) return [];
    return [...selected.stages].sort((a, b) => a.order_position - b.order_position);
  }, [selected]);

  const stageName = (id?: string | null) => stages.find((s) => s.id === id)?.name;

  // Find a lead from kanbanBoard cards or fallback leads
  const findLeadCard = (id: string): LeadResponse | undefined => {
    if (kanbanBoard) {
      for (const st of kanbanBoard.stages) {
        const found = st.cards.find((c) => c.id === id);
        if (found) return found;
      }
    }
    return leads.find((l) => l.id === id);
  };

  const handleDrop = async (stageId: string) => {
    const id = draggingId;
    setDraggingId(null);
    setOverStageId(null);
    if (!id) return;
    const lead = findLeadCard(id);
    const stage = stages.find((s) => s.id === stageId);
    if (!lead || !stage || lead.stage_id === stageId) return;

    setMoveError(null);
    const targetStageLower = stage.name.toLowerCase();

    // 1. Check if dropped into 'Dropped' or 'Lost' -> Capture Loss Reason
    if (targetStageLower.includes('drop') || targetStageLower.includes('lost')) {
      setLossModalLead({ lead, stageId: stage.id, stageName: stage.name });
      return;
    }

    // 2. Check if dropped into 'Converted' or 'Won' -> Confirm Won Deal
    if (targetStageLower.includes('convert') || targetStageLower.includes('won')) {
      setWonModalLead({ lead, stageId: stage.id, stageName: stage.name });
      return;
    }

    // 3. Automated Stage Email Trigger
    const stageCfg = configForStage(stage.name);
    if (stageCfg?.sendsEmail) {
      setPending({ lead, toStage: { id: stage.id, name: stage.name }, fromStageName: stageName(lead.stage_id) });
      return;
    }

    // 4. High-performance optimistic stage transition
    try {
      await moveKanbanCard(lead.id, stage.id);
      setToast(`Moved "${lead.title}" to ${stage.name}.`);
      setTimeout(() => setToast(null), 3000);
    } catch (err: any) {
      setMoveError(err.message || 'Failed to update stage');
    }
  };

  const handleConfirmLoss = async () => {
    if (!lossModalLead) return;
    const { lead, stageId } = lossModalLead;
    try {
      await updateLead(lead.id, {
        stage_id: stageId,
        status: 'Lost',
        custom_fields: {
          ...(lead.custom_fields || {}),
          loss_reason: lossReason,
          loss_note: lossNote,
          dropped_at: new Date().toISOString(),
        },
      });
      setToast(`Deal marked as Dropped: ${lossReason}`);
      setTimeout(() => setToast(null), 3500);
      setLossModalLead(null);
      setLossReason('Price / Budget too high');
      setLossNote('');
      await fetchLeads();
    } catch (err: any) {
      setMoveError(err.message || 'Failed to drop deal');
    }
  };

  const handleConfirmWon = async () => {
    if (!wonModalLead) return;
    const { lead, stageId } = wonModalLead;
    try {
      await updateLead(lead.id, {
        stage_id: stageId,
        status: 'Converted',
        custom_fields: {
          ...(lead.custom_fields || {}),
          converted_at: new Date().toISOString(),
        },
      });
      setToast(`🎉 Deal WON: "${lead.title}" converted successfully!`);
      setTimeout(() => setToast(null), 4000);
      setWonModalLead(null);
      await fetchLeads();
    } catch (err: any) {
      setMoveError(err.message || 'Failed to mark deal as won');
    }
  };

  const confirmMove = async (opts: { withEmail: boolean; to?: string; subject?: string; body?: string }) => {
    if (!pending) return;
    const { lead, toStage } = pending;
    try {
      await updateLead(lead.id, { stage_id: toStage.id });
      if (opts.withEmail && opts.subject && opts.body) {
        await emailApi.send({ subject: opts.subject, body: opts.body, to: opts.to, lead_id: lead.id });
      }
      setPending(null);
      setToast(opts.withEmail ? `Moved to ${toStage.name} and emailed client.` : `Moved to ${toStage.name}.`);
      setTimeout(() => setToast(null), 3000);
      await fetchLeads();
    } catch (err: any) {
      setMoveError(err.message || 'Failed to move deal');
    }
  };

  if (isLoading || (!loaded && pipelines.length === 0)) {
    return (
      <div className="py-20 flex flex-col items-center justify-center gap-3 text-slate-400">
        <Loader2 className="w-8 h-8 animate-spin text-brand-400" />
        <span className="text-sm font-medium">Loading Sales Pipeline & Deals...</span>
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
          <RefreshCw className="w-4 h-4" /> Load Pipeline
        </button>
      </div>
    );
  }

  // Stage semantic color mapping
  const getStageColor = (name: string, fallback?: string): string => {
    const n = name.toLowerCase();
    if (n.includes('fresh') || n.includes('new')) return '#3B82F6'; // Blue
    if (n.includes('contact')) return '#F59E0B'; // Amber
    if (n.includes('follow') || n.includes('qualif')) return '#6366F1'; // Indigo
    if (n.includes('won') || n.includes('convert')) return '#10B981'; // Emerald
    if (n.includes('drop') || n.includes('lost')) return '#EF4444'; // Rose
    return fallback || '#6366F1';
  };

  const getEmptyStateText = (name: string): string => {
    const n = name.toLowerCase();
    if (n.includes('fresh')) return 'No fresh leads · Add a deal';
    if (n.includes('contact')) return 'No leads in contacted stage';
    if (n.includes('follow')) return 'No follow-ups pending';
    if (n.includes('convert') || n.includes('won')) return 'No converted deals yet · Drag won deals here';
    if (n.includes('drop') || n.includes('lost')) return 'No dropped deals';
    return 'Drop deals here';
  };

  return (
    <div className="space-y-2.5">
      {/* Low-profile pipeline metadata bar */}
      <div className="flex items-center justify-between flex-wrap gap-2 px-0.5">
        <div className="flex items-center gap-2.5 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="font-semibold text-slate-300">Pipeline:</span>
            <select
              value={selected.id}
              onChange={(e) => selectPipeline(e.target.value)}
              className="px-2.5 py-1 rounded-lg text-xs font-semibold bg-slate-900 border border-slate-700/80 text-slate-100 focus:outline-none focus:border-brand-500 shadow-2xs cursor-pointer"
            >
              {pipelines.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.name}{p.is_default ? ' (Default)' : ''}
                </option>
              ))}
            </select>
          </div>

          <span className="text-xs text-slate-500">·</span>
          <span className="text-xs text-slate-400 font-medium">
            {stages.length} stages
          </span>
          <span className="text-xs text-slate-500">·</span>
          <span className="text-xs text-slate-400 font-medium">
            {kanbanBoard ? `${kanbanBoard.total_deals_count} total deals` : `${leads.filter((l) => !l.is_archived).length} total deals`}
          </span>

          {moveError && <span className="text-xs text-rose-500 font-semibold">{moveError}</span>}
        </div>

        <div className="hidden sm:inline-flex items-center gap-1.5 text-xs text-slate-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Drag deals across stages to advance opportunity</span>
        </div>
      </div>

      {/* Kanban Columns List */}
      <div className="flex gap-3 overflow-x-auto pb-4 pt-0.5 items-start">
        {stages.map((stage) => {
          const serverStage = kanbanBoard?.stages?.find((s) => s.stage_id === stage.id);
          const items = serverStage ? serverStage.cards : [];
          const colValue = serverStage ? serverStage.total_value : 0;
          const totalCount = serverStage ? serverStage.total_count : items.length;
          const hasMore = serverStage ? serverStage.has_more : false;
          const stageColor = getStageColor(stage.name, stage.color);
          const over = overStageId === stage.id;

          return (
            <div
              key={stage.id}
              onDragOver={(e) => { e.preventDefault(); setOverStageId(stage.id); }}
              onDragLeave={() => setOverStageId((cur) => (cur === stage.id ? null : cur))}
              onDrop={() => handleDrop(stage.id)}
              className={`w-72 shrink-0 flex flex-col rounded-xl border transition-all duration-150 ${
                over
                  ? 'border-brand-500 bg-brand-500/10 shadow-md ring-2 ring-brand-500/20'
                  : 'border-slate-800/90 bg-slate-950/40 shadow-2xs'
              }`}
            >
              {/* Column Header */}
              <div className="p-2.5 px-3 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/70 rounded-t-xl">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="w-2.5 h-2.5 rounded-full shrink-0"
                    style={{ backgroundColor: stageColor }}
                  />
                  <span className="text-xs font-bold text-slate-200 tracking-wide uppercase truncate">
                    {stage.name}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400 bg-slate-800/90 px-1.5 py-0.2 rounded border border-slate-700/70 shrink-0">
                    {totalCount}
                  </span>
                </div>

                <div className="flex items-center gap-1.5">
                  {colValue > 0 && (
                    <span className="text-xs font-bold text-emerald-400 shrink-0 font-mono">
                      {formatMoney(colValue)}
                    </span>
                  )}
                  {onAddDeal && (
                    <button
                      type="button"
                      onClick={() => onAddDeal(stage.id)}
                      className="p-1 text-slate-400 hover:text-brand-400 hover:bg-slate-800 rounded transition-colors"
                      title={`Add deal to ${stage.name}`}
                    >
                      <Plus className="w-3.5 h-3.5" />
                    </button>
                  )}
                </div>
              </div>

              {/* Cards Container */}
              <div className="p-2.5 space-y-2.5 flex-1 min-h-[180px] max-h-[calc(100vh-270px)] overflow-y-auto">
                {items.map((lead) => {
                  const contactPerson = [lead.first_name, lead.last_name].filter(Boolean).join(' ').trim();
                  const name = lead.title || contactPerson || 'Untitled Deal';

                  const assignedUser = users.find((u) => u.id === lead.assigned_user_id);
                  const ownerName = assignedUser
                    ? `${assignedUser.first_name || ''} ${assignedUser.last_name || ''}`.trim() || assignedUser.email
                    : (lead.source || 'Unassigned');

                  const initials = (contactPerson || lead.title || 'LD')
                    .split(' ')
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((w) => w[0]?.toUpperCase())
                    .join('') || 'LD';

                  // Deal age & overdue logic
                  const leadCreated = new Date(lead.created_at);
                  const daysOld = !Number.isNaN(leadCreated.getTime())
                    ? Math.max(0, Math.floor((Date.now() - leadCreated.getTime()) / (1000 * 60 * 60 * 24)))
                    : 0;
                  const isOverdue = daysOld >= 7 && !stage.name.toLowerCase().includes('won') && !stage.name.toLowerCase().includes('drop');

                  return (
                    <div
                      key={lead.id}
                      draggable
                      onDragStart={() => setDraggingId(lead.id)}
                      onDragEnd={() => { setDraggingId(null); setOverStageId(null); }}
                      onClick={() => onCardClick?.(lead)}
                      className={`group relative bg-slate-900/90 hover:bg-slate-900 border border-slate-800/90 hover:border-slate-700 rounded-xl p-3 shadow-2xs hover:shadow-md transition-all duration-150 cursor-grab active:cursor-grabbing select-none overflow-hidden ${
                        draggingId === lead.id ? 'opacity-30 scale-95' : ''
                      }`}
                    >
                      {/* Left accent bar matching stage color */}
                      <div
                        className="absolute left-0 top-2 bottom-2 w-1 rounded-r"
                        style={{ backgroundColor: stageColor }}
                      />

                      {/* Header Row: Title & Quick Actions */}
                      <div className="flex items-start justify-between gap-1.5 pl-1.5">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-slate-100 group-hover:text-brand-400 transition-colors truncate">
                            {name}
                          </p>
                          {(lead.company_name || contactPerson) && (
                            <p className="text-[11px] text-slate-400 truncate mt-0.5 flex items-center gap-1">
                              <span>{lead.company_name || contactPerson}</span>
                              {lead.company_name && contactPerson && contactPerson !== name && (
                                <>
                                  <span className="text-slate-600">·</span>
                                  <span className="text-slate-500 truncate">{contactPerson}</span>
                                </>
                              )}
                            </p>
                          )}
                        </div>

                        {/* Hover Quick Action Icons (Telecalling, WhatsApp, Email) */}
                        <div className="flex items-center gap-0.5 shrink-0 opacity-70 group-hover:opacity-100 transition-opacity">
                          {lead.phone && (
                            <button
                              type="button"
                              onClick={(e) => {
                                e.stopPropagation();
                                if (onCallClick) onCallClick(lead.id);
                                else window.location.href = `tel:${lead.phone}`;
                              }}
                              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer"
                              title={`Call ${lead.phone}`}
                            >
                              <Phone className="w-3.5 h-3.5" />
                            </button>
                          )}
                          <button
                            type="button"
                            onClick={(e) => {
                              e.stopPropagation();
                              onChatClick?.(lead, 'whatsapp');
                            }}
                            className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-emerald-400 transition-colors cursor-pointer"
                            title="Open WhatsApp / SMS & Documents"
                          >
                            <MessageCircle className="w-3.5 h-3.5" />
                          </button>
                          {lead.email && (
                            <a
                              href={`mailto:${lead.email}`}
                              onClick={(e) => e.stopPropagation()}
                              className="p-1 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-400 transition-colors cursor-pointer"
                              title={`Email ${lead.email}`}
                            >
                              <Mail className="w-3.5 h-3.5" />
                            </a>
                          )}
                        </div>
                      </div>

                      {/* Middle row: Deal Value & Priority */}
                      <div className="flex items-center justify-between gap-2 mt-2 pt-2 border-t border-slate-800/70 pl-1.5">
                        <div className="flex items-center gap-2">
                          {fmtValue(lead.value) ? (
                            <span className="text-xs font-bold text-emerald-400 font-mono">
                              {fmtValue(lead.value)}
                            </span>
                          ) : (
                            <span className="text-[10px] text-slate-500 font-medium">—</span>
                          )}

                          <div className="flex items-center gap-1 text-[10px] font-medium text-slate-400">
                            <span
                              className={`w-1.5 h-1.5 rounded-full ${
                                lead.priority === 'Urgent'
                                  ? 'bg-rose-500'
                                  : lead.priority === 'High'
                                  ? 'bg-amber-500'
                                  : lead.priority === 'Low'
                                  ? 'bg-slate-500'
                                  : 'bg-blue-500'
                              }`}
                            />
                            <span>{lead.priority || 'Med'}</span>
                          </div>
                        </div>

                        {/* Stale / Overdue badge */}
                        {isOverdue && (
                          <span className="text-[9px] font-semibold text-amber-400 bg-amber-500/10 px-1 py-0.2 rounded border border-amber-500/20">
                            Stale {daysOld}d
                          </span>
                        )}
                      </div>

                      {/* Footer Row: Age & Owner Avatar */}
                      <div className="flex items-center justify-between mt-2 pt-1.5 border-t border-slate-800/50 pl-1.5 text-[10px] text-slate-400">
                        <span>{daysOld === 0 ? 'Today' : `${daysOld}d in pipeline`}</span>

                        <div
                          className="w-5 h-5 rounded-full bg-slate-800 border border-slate-700/80 text-[10px] font-bold text-slate-300 flex items-center justify-center shrink-0"
                          title={`Assigned to: ${ownerName}`}
                        >
                          {initials}
                        </div>
                      </div>
                    </div>
                  );
                })}

                {/* Incremental loading for million-lead scale */}
                {hasMore && (
                  <button
                    type="button"
                    onClick={() => loadMoreStageCards(stage.id)}
                    disabled={loadingStageId === stage.id}
                    className="w-full py-2 px-3 mt-1 text-xs font-semibold text-brand-300 hover:text-brand-200 bg-slate-900/90 hover:bg-slate-800 border border-slate-800 hover:border-slate-700 rounded-xl flex items-center justify-center gap-1.5 transition-all cursor-pointer shadow-xs disabled:opacity-50"
                  >
                    {loadingStageId === stage.id ? (
                      <>
                        <Loader2 className="w-3.5 h-3.5 animate-spin text-brand-400" />
                        <span>Loading cards…</span>
                      </>
                    ) : (
                      <>
                        <span>Load more (+10 deals)</span>
                      </>
                    )}
                  </button>
                )}

                {/* Helpful empty state */}
                {items.length === 0 && (
                  <div className="border border-dashed border-slate-800/80 rounded-xl py-12 flex flex-col items-center justify-center gap-1.5 text-slate-500 text-xs text-center px-3">
                    <span>{getEmptyStateText(stage.name)}</span>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>

      {/* Loss Reason Modal (Enterprise Drop Reason Capture) */}
      {lossModalLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl animate-in fade-in duration-150 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-rose-500/15 border border-rose-500/30 flex items-center justify-center text-rose-400">
                  <XCircle className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100">Drop Deal Reason</h3>
                  <p className="text-xs text-slate-400">"{lossModalLead.lead.title}"</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setLossModalLead(null)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                  Select Primary Reason for Dropping:
                </label>
                <select
                  value={lossReason}
                  onChange={(e) => setLossReason(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700/80 rounded-xl text-xs text-slate-100 focus:outline-none focus:border-rose-500"
                >
                  <option value="Price / Budget too high">Price / Budget too high</option>
                  <option value="Competitor chosen">Competitor chosen</option>
                  <option value="Unresponsive / Ghosted">Unresponsive / Ghosted</option>
                  <option value="Timing / Project cancelled">Timing / Project cancelled</option>
                  <option value="Feature / Capability gap">Feature / Capability gap</option>
                  <option value="Disqualified / Poor lead fit">Disqualified / Poor lead fit</option>
                  <option value="Other">Other</option>
                </select>
              </div>

              <div>
                <label className="text-xs font-semibold text-slate-300 block mb-1.5">
                  Optional Feedback / Closing Notes:
                </label>
                <textarea
                  value={lossNote}
                  onChange={(e) => setLossNote(e.target.value)}
                  placeholder="Provide context for sales intelligence and reporting..."
                  rows={2}
                  className="w-full px-3 py-2 bg-slate-950 border border-slate-700/80 rounded-xl text-xs text-slate-100 placeholder-slate-500 focus:outline-none focus:border-rose-500 resize-none"
                />
              </div>
            </div>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setLossModalLead(null)}
                className="px-3 py-1.5 text-xs font-semibold text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmLoss}
                className="px-4 py-1.5 bg-rose-600 hover:bg-rose-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-rose-600/20"
              >
                Confirm Dropped
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Won Deal Confirmation Modal */}
      {wonModalLead && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/70 backdrop-blur-xs">
          <div className="w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl p-5 shadow-2xl animate-in fade-in duration-150 space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div className="flex items-center gap-2.5">
                <div className="w-8 h-8 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
                  <CheckCircle2 className="w-5 h-5" />
                </div>
                <div>
                  <h3 className="text-sm font-bold text-slate-100">Congratulations! Mark Deal as Won</h3>
                  <p className="text-xs text-slate-400">"{wonModalLead.lead.title}"</p>
                </div>
              </div>
              <button
                type="button"
                onClick={() => setWonModalLead(null)}
                className="text-slate-400 hover:text-slate-200"
              >
                ✕
              </button>
            </div>

            <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-center justify-between">
              <div>
                <p className="text-[11px] font-semibold text-emerald-300">Deal Revenue</p>
                <p className="text-base font-bold text-emerald-400 font-mono">
                  {fmtValue(wonModalLead.lead.value) || 'No value recorded'}
                </p>
              </div>
              <span className="text-xs font-bold px-2 py-0.5 rounded bg-emerald-500/20 text-emerald-300">
                100% Win
              </span>
            </div>

            <p className="text-xs text-slate-400 leading-relaxed">
              Moving this deal to Converted will update sales analytics, record this closed deal in revenue forecasts, and trigger automated client welcome sequences.
            </p>

            <div className="flex items-center justify-end gap-2.5 pt-2 border-t border-slate-800">
              <button
                type="button"
                onClick={() => setWonModalLead(null)}
                className="px-3 py-1.5 text-xs font-semibold text-slate-400 hover:text-slate-200"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmWon}
                className="px-4 py-1.5 bg-emerald-600 hover:bg-emerald-500 text-white rounded-xl text-xs font-semibold shadow-md shadow-emerald-600/20"
              >
                Confirm Won Deal
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Stage Email Automation Dialog */}
      {pending && (
        <StageEmailDialog
          lead={pending.lead}
          toStageName={pending.toStage.name}
          fromStageName={pending.fromStageName}
          onCancel={() => setPending(null)}
          onConfirm={confirmMove}
        />
      )}

      {/* Operation Toast Notification */}
      {toast && (
        <div className="fixed bottom-6 left-1/2 -translate-x-1/2 z-50 px-4 py-2.5 rounded-xl text-xs font-semibold shadow-xl bg-slate-800 text-slate-100 border border-slate-700 animate-in fade-in slide-in-from-bottom-2">
          {toast}
        </div>
      )}
    </div>
  );
};
