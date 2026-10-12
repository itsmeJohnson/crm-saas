import React, { useMemo, useState, useEffect } from 'react';
import { useLeadStore } from '../../store/leadStore';
import { useMetadataStore } from '../../store/metadataStore';
import { useUserStore } from '../../store/userStore';
import { LeadResponse } from '../../services/leadApi';
import { emailApi } from '../../services/emailApi';
import { Mail, Phone, Loader2, RefreshCw, MessageCircle } from 'lucide-react';
import { formatMoney } from '../../utils/currency';
import { StageEmailDialog } from './StageEmailDialog';
import { configForStage } from '../../utils/stageAutomation';

interface LeadKanbanProps {
  onCardClick?: (lead: LeadResponse) => void;
  onChatClick?: (lead: LeadResponse, channel?: 'whatsapp' | 'sms') => void;
  onCallClick?: (leadId: string) => void;
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

export const LeadKanban: React.FC<LeadKanbanProps> = ({ onCardClick, onChatClick, onCallClick }) => {
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
    <div className="space-y-3">
      {/* Kanban Pipeline Low-Profile Control Bar */}
      <div className="flex items-center justify-between flex-wrap gap-2.5 px-0.5 pb-0.5">
        <div className="flex items-center gap-2 flex-wrap">
          <div className="flex items-center gap-1.5 text-xs text-slate-400">
            <span className="font-medium">Pipeline:</span>
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

          <span className="text-xs text-slate-500 font-medium">·</span>
          <span className="text-xs text-slate-400 font-medium">
            {stages.length} stages
          </span>
          <span className="text-xs text-slate-500 font-medium">·</span>
          <span className="text-xs text-slate-400 font-medium">
            {leads.length} deals
          </span>
          {moveError && <span className="text-xs text-rose-500 font-medium">{moveError}</span>}
        </div>

        <div className="hidden sm:inline-flex items-center gap-1.5 text-xs text-slate-400">
          <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
          <span>Drag cards to advance stage</span>
        </div>
      </div>

      {/* Columns List */}
      <div className="flex gap-3.5 overflow-x-auto pb-4 pt-1 items-start">
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
              className={`w-72 shrink-0 flex flex-col rounded-xl border transition-all duration-150 ${
                over
                  ? 'border-brand-500 bg-brand-500/10 shadow-md ring-2 ring-brand-500/20'
                  : 'border-slate-800/80 bg-slate-950/40 shadow-2xs'
              }`}
            >
              {/* Column Header */}
              <div className="p-2.5 px-3 border-b border-slate-800/80 flex items-center justify-between bg-slate-900/60 rounded-t-xl">
                <div className="flex items-center gap-2 min-w-0">
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: stage.color || '#4F46E5' }}
                  />
                  <span className="text-xs font-bold text-slate-200 tracking-wide uppercase truncate">
                    {stage.name}
                  </span>
                  <span className="text-[11px] font-semibold text-slate-400 bg-slate-800/80 px-1.5 py-0.2 rounded border border-slate-700/60 shrink-0">
                    {items.length}
                  </span>
                </div>
                {fmtValue(colValue) && (
                  <span className="text-xs font-semibold text-emerald-400 shrink-0 font-mono">
                    {fmtValue(colValue)}
                  </span>
                )}
              </div>

              {/* Cards Container */}
              <div className="p-2.5 space-y-2.5 flex-1 min-h-[160px] max-h-[calc(100vh-270px)] overflow-y-auto">
                {items.map((lead) => {
                  const contactPerson = `${lead.first_name || ''} ${lead.last_name || ''}`.trim();
                  const name = lead.title || contactPerson || 'Untitled Deal';
                  const initials = (contactPerson || lead.title || 'LD')
                    .split(' ')
                    .filter(Boolean)
                    .slice(0, 2)
                    .map((w) => w[0]?.toUpperCase())
                    .join('') || 'LD';

                  const assignedUser = users.find((u) => u.id === lead.assigned_user_id);
                  const ownerName = assignedUser
                    ? `${assignedUser.first_name || ''} ${assignedUser.last_name || ''}`.trim() || assignedUser.email
                    : (lead.source || 'Unassigned');

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
                        style={{ backgroundColor: stage.color || '#4F46E5' }}
                      />

                      {/* Header Row: Title & Quick Actions */}
                      <div className="flex items-start justify-between gap-1.5 pl-1.5">
                        <div className="min-w-0 flex-1">
                          <p className="text-xs font-bold text-slate-100 group-hover:text-brand-400 transition-colors truncate">
                            {name}
                          </p>
                          {(lead.company_name || (contactPerson && contactPerson !== name)) && (
                            <p className="text-[11px] text-slate-400 truncate mt-0.5">
                              {lead.company_name || contactPerson}
                            </p>
                          )}
                        </div>

                        {/* Quick action icons */}
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

                      {/* Bottom Row: Deal Value, Priority, and Owner Avatar */}
                      <div className="flex items-center justify-between gap-2 mt-2.5 pt-2 border-t border-slate-800/70 pl-1.5">
                        <div className="flex items-center gap-2">
                          {fmtValue(lead.value) ? (
                            <span className="text-xs font-semibold text-emerald-400 font-mono">
                              {fmtValue(lead.value)}
                            </span>
                          ) : (
                            <span className="text-[10px] text-slate-500 font-medium">—</span>
                          )}

                          {/* Linear-style priority indicator */}
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

                        {/* Owner Initials Avatar */}
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

                {items.length === 0 && (
                  <div className="border border-dashed border-slate-800/80 rounded-xl py-10 flex flex-col items-center justify-center gap-1.5 text-slate-500 text-xs text-center px-3">
                    <span>Drop deals here</span>
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
