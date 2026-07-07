import React, { useCallback, useEffect, useState } from 'react';
import {
  Workflow as WorkflowIcon, Plus, Loader2, X, Check, Trash2, Pencil, Play, Copy, Upload, Download,
  History as HistoryIcon, BarChart3, LayoutTemplate, GitBranch, Clock, ShieldCheck, RefreshCw, Repeat,
  Flag, Zap, Rocket, Power, ChevronRight, RotateCcw,
} from 'lucide-react';
import {
  workflowApi, Workflow, WorkflowCatalog, WorkflowNode, WorkflowVersion, Execution, WorkflowReport,
} from '../services/workflowApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
const uid = () => Math.random().toString(36).slice(2, 8);
const nodeIcon = (t: string) => t === 'trigger' ? <Zap className="w-3.5 h-3.5 text-amber-400" />
  : t === 'branch' ? <GitBranch className="w-3.5 h-3.5 text-indigo-300" />
    : t === 'delay' ? <Clock className="w-3.5 h-3.5 text-slate-400" />
      : t === 'approval' ? <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" />
        : t === 'loop' ? <Repeat className="w-3.5 h-3.5 text-brand-300" />
          : t === 'end' ? <Flag className="w-3.5 h-3.5 text-red-400" />
            : <Rocket className="w-3.5 h-3.5 text-brand-400" />;

const StatusChip: React.FC<{ s: string }> = ({ s }) => {
  const tone = s === 'published' || s === 'completed' || s === 'success' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : s === 'draft' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
      : s === 'failed' ? 'bg-red-500/10 text-red-400 border-red-500/20'
        : 'bg-slate-700/40 text-slate-400 border-slate-600/40';
  return <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{s}</span>;
};

/* Build engine edges from the linear node list (branch false → end). */
const buildGraph = (trigger: any, steps: WorkflowNode[]) => {
  const end = steps.find((n) => n.type === 'end') || { id: 'end', type: 'end', config: {} };
  const chain = [trigger, ...steps.filter((n) => n.type !== 'end'), end];
  const edges: any[] = [];
  for (let i = 0; i < chain.length - 1; i++) {
    const cur = chain[i], nxt = chain[i + 1];
    if (cur.type === 'branch') {
      edges.push({ from: cur.id, to: nxt.id, branch: 'true' });
      edges.push({ from: cur.id, to: end.id, branch: 'false' });
    } else if (cur.id !== end.id) {
      edges.push({ from: cur.id, to: nxt.id });
    }
  }
  return { nodes: chain, edges };
};

/* ── Node config editor ── */
const NodeCard: React.FC<{ node: WorkflowNode; users: any[]; actions: string[]; onChange: (c: any) => void; onRemove: () => void }> =
  ({ node, users, actions, onChange, onRemove }) => {
    const c = node.config || {};
    const set = (patch: any) => onChange({ ...c, ...patch });
    return (
      <div className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/40">
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-semibold text-slate-200 flex items-center gap-1.5 capitalize">{nodeIcon(node.type)} {node.type}</span>
          <button onClick={onRemove} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
        </div>
        {node.type === 'action' && (
          <div className="space-y-2">
            <select value={c.action || actions[0]} onChange={(e) => set({ action: e.target.value })} className={F}>
              {actions.map((a) => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
            </select>
            {(c.action === 'assign_lead' || c.action === 'assign_task' || c.action === 'create_task' || c.action === 'create_notification' || c.action === 'schedule_meeting') && (
              <select value={c.user_id || ''} onChange={(e) => set({ user_id: e.target.value })} className={F}>
                <option value="">— assignee: lead owner —</option>
                {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
              </select>
            )}
            {c.action === 'update_status' && <input value={c.value || ''} onChange={(e) => set({ value: e.target.value })} placeholder="New status" className={F} />}
            {(c.action === 'create_task' || c.action === 'create_notification' || c.action === 'schedule_meeting' || c.action === 'send_email') && (
              <input value={c.title || ''} onChange={(e) => set({ title: e.target.value })} placeholder="Title / subject" className={F} />
            )}
            {(c.action === 'create_notification' || c.action === 'send_email' || c.action === 'send_sms' || c.action === 'send_whatsapp' || c.action === 'create_task') && (
              <textarea value={c.message || ''} onChange={(e) => set({ message: e.target.value })} rows={2} placeholder="Message" className={F} />
            )}
            {c.action === 'webhook' && <input value={c.url || ''} onChange={(e) => set({ url: e.target.value })} placeholder="https://webhook.url" className={F} />}
          </div>
        )}
        {node.type === 'branch' && (
          <div className="grid grid-cols-3 gap-2">
            <input value={c.conditions?.[0]?.field || ''} onChange={(e) => set({ conditions: [{ field: e.target.value, op: c.conditions?.[0]?.op || 'eq', value: c.conditions?.[0]?.value || '' }] })} placeholder="field" className={F} />
            <select value={c.conditions?.[0]?.op || 'eq'} onChange={(e) => set({ conditions: [{ ...(c.conditions?.[0] || {}), op: e.target.value }] })} className={F}>
              {['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'contains'].map((o) => <option key={o} value={o}>{o}</option>)}
            </select>
            <input value={c.conditions?.[0]?.value ?? ''} onChange={(e) => set({ conditions: [{ ...(c.conditions?.[0] || {}), value: e.target.value }] })} placeholder="value" className={F} />
            <p className="col-span-3 text-[10px] text-slate-500">If true → continue; if false → end.</p>
          </div>
        )}
        {node.type === 'delay' && <input type="number" value={c.minutes || ''} onChange={(e) => set({ minutes: Number(e.target.value) })} placeholder="Delay minutes" className={F} />}
        {node.type === 'loop' && <input type="number" value={c.iterations || 1} onChange={(e) => set({ iterations: Number(e.target.value) })} placeholder="Iterations" className={F} />}
        {node.type === 'approval' && (
          <div className="space-y-2">
            <input value={c.title || ''} onChange={(e) => set({ title: e.target.value })} placeholder="Approval title" className={F} />
            <input value={c.request_type || 'generic'} onChange={(e) => set({ request_type: e.target.value })} placeholder="request type (discount/generic…)" className={F} />
          </div>
        )}
        {node.type === 'end' && <p className="text-[11px] text-slate-500">Workflow ends here.</p>}
      </div>
    );
  };

/* ── Designer ── */
const Designer: React.FC<{ initial?: Workflow | null; catalog: WorkflowCatalog; users: any[]; onClose: () => void; onSaved: () => void }> =
  ({ initial, catalog, users, onClose, onSaved }) => {
    const triggerNode = initial?.graph?.nodes.find((n) => n.type === 'trigger');
    const [meta, setMeta] = useState<any>({
      name: initial?.name || '', description: initial?.description || '', category: initial?.category || 'General',
      trigger_event: initial?.trigger_event || catalog.triggers[0]?.event,
    });
    const [conditions, setConditions] = useState<any[]>(triggerNode?.config?.conditions || []);
    const [steps, setSteps] = useState<WorkflowNode[]>(
      (initial?.graph?.nodes || []).filter((n) => n.type !== 'trigger'));
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const addNode = (type: string) => setSteps((s) => [...s.filter((n) => n.type !== 'end'), { id: uid(), type, config: type === 'action' ? { action: catalog.actions[0] } : {} }, ...(s.some((n) => n.type === 'end') ? s.filter((n) => n.type === 'end') : [])]);
    const updateNode = (id: string, config: any) => setSteps((s) => s.map((n) => n.id === id ? { ...n, config } : n));
    const removeNode = (id: string) => setSteps((s) => s.filter((n) => n.id !== id));

    const save = async () => {
      if (!meta.name.trim()) { setError('Name is required'); return; }
      setBusy(true); setError(null);
      try {
        const trigger = { id: triggerNode?.id || 't1', type: 'trigger', config: { conditions } };
        const graph = buildGraph(trigger, steps);
        const payload = { name: meta.name, description: meta.description || undefined, category: meta.category, trigger_event: meta.trigger_event, graph };
        if (initial) await workflowApi.update(initial.id, payload);
        else await workflowApi.create(payload);
        onSaved();
      } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
    };

    return (
      <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
        <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-2xl bg-slate-900 max-h-[92vh] overflow-y-auto">
          <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><WorkflowIcon className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} workflow</h3>
            <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
          </div>
          <div className="p-4 space-y-3">
            {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
            <div className="grid grid-cols-2 gap-2">
              <input value={meta.name} onChange={(e) => setMeta({ ...meta, name: e.target.value })} placeholder="Workflow name" className={F} />
              <select value={meta.category} onChange={(e) => setMeta({ ...meta, category: e.target.value })} className={F}>
                {catalog.categories.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
            </div>
            <input value={meta.description} onChange={(e) => setMeta({ ...meta, description: e.target.value })} placeholder="Description" className={F} />

            {/* Visual flow */}
            <div className="border border-slate-800/60 rounded-xl p-3 bg-slate-950/30 space-y-0">
              {/* Trigger */}
              <div className="p-3 rounded-xl border border-amber-500/30 bg-amber-500/5">
                <div className="flex items-center gap-2 mb-2"><Zap className="w-3.5 h-3.5 text-amber-400" /><span className="text-xs font-semibold text-slate-200">When</span>
                  <select value={meta.trigger_event} onChange={(e) => setMeta({ ...meta, trigger_event: e.target.value })} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1 px-1.5 rounded-md text-xs">
                    {catalog.triggers.map((t) => <option key={t.event} value={t.event}>{t.event.replace(/_/g, ' ')}</option>)}
                  </select>
                </div>
                <div className="flex items-center gap-2">
                  <input value={conditions[0]?.field || ''} onChange={(e) => setConditions([{ field: e.target.value, op: conditions[0]?.op || 'eq', value: conditions[0]?.value || '' }])} placeholder="condition field (optional)" className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1 px-2 rounded-md text-xs" />
                  {conditions[0]?.field && (
                    <>
                      <select value={conditions[0]?.op || 'eq'} onChange={(e) => setConditions([{ ...conditions[0], op: e.target.value }])} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1 px-1.5 rounded-md text-xs">
                        {['eq', 'neq', 'gt', 'gte', 'lt', 'lte', 'contains'].map((o) => <option key={o} value={o}>{o}</option>)}
                      </select>
                      <input value={conditions[0]?.value ?? ''} onChange={(e) => setConditions([{ ...conditions[0], value: e.target.value }])} placeholder="value" className="w-24 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1 px-2 rounded-md text-xs" />
                    </>
                  )}
                </div>
              </div>
              {steps.filter((n) => n.type !== 'end').map((n) => (
                <div key={n.id}>
                  <div className="flex justify-center py-1"><ChevronRight className="w-4 h-4 text-slate-600 rotate-90" /></div>
                  <NodeCard node={n} users={users} actions={catalog.actions} onChange={(c) => updateNode(n.id, c)} onRemove={() => removeNode(n.id)} />
                </div>
              ))}
              <div className="flex justify-center py-1"><ChevronRight className="w-4 h-4 text-slate-600 rotate-90" /></div>
              <div className="p-2 rounded-xl border border-red-500/20 bg-red-500/5 text-center text-[11px] text-red-400/80 flex items-center justify-center gap-1"><Flag className="w-3.5 h-3.5" /> End</div>
            </div>
            <div className="flex gap-1.5 flex-wrap">
              {[['action', Rocket], ['branch', GitBranch], ['delay', Clock], ['approval', ShieldCheck], ['loop', Repeat]].map(([t, Icon]: any) => (
                <button key={t} onClick={() => addNode(t)} className="inline-flex items-center gap-1 text-[11px] text-slate-300 border border-slate-800 rounded-lg px-2 py-1 cursor-pointer hover:border-slate-700 capitalize"><Icon className="w-3 h-3" /> + {t}</button>
              ))}
            </div>
            <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save draft' : 'Create draft'}
            </button>
          </div>
        </div>
      </div>
    );
  };

/* ── Page ── */
export const WorkflowsPage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager';

  const [tab, setTab] = useState<'workflows' | 'templates' | 'executions' | 'reports'>('workflows');
  const [catalog, setCatalog] = useState<WorkflowCatalog | null>(null);
  const [items, setItems] = useState<Workflow[]>([]);
  const [templates, setTemplates] = useState<Workflow[]>([]);
  const [executions, setExecutions] = useState<Execution[]>([]);
  const [report, setReport] = useState<WorkflowReport | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [designer, setDesigner] = useState<Workflow | null | 'new'>(null);
  const [versionsOf, setVersionsOf] = useState<{ wf: Workflow; rows: WorkflowVersion[] } | null>(null);
  const [logOf, setLogOf] = useState<Execution | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { workflowApi.catalog().then(setCatalog).catch(() => {}); userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {}); }, []);

  const loadTab = useCallback(() => {
    setError(null);
    if (tab === 'workflows') workflowApi.list({ is_template: false }).then(setItems).catch((e) => setError(extractErrorMessage(e, 'Failed')));
    if (tab === 'templates') workflowApi.list({ is_template: true }).then(setTemplates).catch(() => {});
    if (tab === 'executions') workflowApi.executions({ limit: 50 }).then((r) => setExecutions(r.items)).catch(() => {});
    if (tab === 'reports') workflowApi.report().then(setReport).catch(() => {});
  }, [tab]);
  useEffect(() => { loadTab(); }, [loadTab]);

  const act = async (fn: () => Promise<any>, msg?: string) => {
    try { const r = await fn(); if (msg) window.alert(typeof r === 'object' && r?.created != null ? `${r.created} created.` : msg); loadTab(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Action failed')); }
  };
  const doExport = async (w: Workflow) => {
    const data = await workflowApi.exportOne(w.id);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob); const a = document.createElement('a'); a.href = url; a.download = `${w.name}.workflow.json`; a.click(); URL.revokeObjectURL(url);
  };
  const doImport = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    const reader = new FileReader();
    reader.onload = async () => {
      try { await workflowApi.importOne(JSON.parse(String(reader.result))); loadTab(); }
      catch (err: any) { setError(extractErrorMessage(err, 'Import failed')); }
    };
    reader.readAsText(file); e.target.value = '';
  };
  const test = async (w: Workflow) => {
    try { const ex = await workflowApi.test(w.id); setLogOf(await workflowApi.executionLogs(ex.id)); }
    catch (e: any) { setError(extractErrorMessage(e, 'Test failed')); }
  };
  const openVersions = async (w: Workflow) => setVersionsOf({ wf: w, rows: await workflowApi.versions(w.id) });

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><WorkflowIcon className="w-5 h-5 text-brand-400" /> Workflow Engine</h1>
        {isManager && tab === 'workflows' && (
          <div className="flex items-center gap-2">
            <label className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 cursor-pointer px-2.5 py-1.5 border border-slate-800 rounded-lg"><Upload className="w-3.5 h-3.5" /> Import<input type="file" accept=".json" onChange={doImport} className="hidden" /></label>
            <button onClick={() => setDesigner('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New workflow</button>
          </div>
        )}
      </div>

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      <div className="flex gap-1 border-b border-slate-800/60 flex-wrap">
        {([['workflows', 'Workflows', WorkflowIcon], ['templates', 'Templates', LayoutTemplate], ['executions', 'Execution History', HistoryIcon], ['reports', 'Reports', BarChart3]] as const).map(([key, lbl, Icon]) => (
          <button key={key} onClick={() => setTab(key)} className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
            <Icon className="w-3.5 h-3.5" /> {lbl}
          </button>
        ))}
      </div>

      {tab === 'workflows' && (
        <div className="space-y-2">
          {items.map((w) => (
            <div key={w.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30">
              <div className="flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <p className="text-sm text-slate-200 font-medium flex items-center gap-2">{w.name}
                    <StatusChip s={w.status} /> {!w.is_enabled && <span className="text-[10px] text-slate-500">disabled</span>}
                    <span className="text-[10px] text-slate-600">v{w.version}</span>
                  </p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{w.category} · on {w.trigger_event.replace(/_/g, ' ')} · {w.node_count} node(s)</p>
                </div>
                {isManager && (
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => test(w)} title="Test run" className="p-1.5 text-slate-500 hover:text-brand-300 cursor-pointer"><Play className="w-4 h-4" /></button>
                    {w.status === 'draft'
                      ? <button onClick={() => act(() => workflowApi.publish(w.id), 'Published')} title="Publish" className="p-1.5 text-emerald-400/80 hover:text-emerald-400 cursor-pointer"><Rocket className="w-4 h-4" /></button>
                      : <button onClick={() => act(() => workflowApi.setEnabled(w.id, !w.is_enabled))} title={w.is_enabled ? 'Disable' : 'Enable'} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Power className={`w-4 h-4 ${w.is_enabled ? 'text-emerald-400/70' : ''}`} /></button>}
                    <button onClick={() => openVersions(w)} title="Versions" className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><HistoryIcon className="w-4 h-4" /></button>
                    <button onClick={() => act(() => workflowApi.clone(w.id), 'Cloned')} title="Clone" className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Copy className="w-4 h-4" /></button>
                    <button onClick={() => doExport(w)} title="Export" className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Download className="w-4 h-4" /></button>
                    <button onClick={() => setDesigner(w)} title="Edit" className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                    <button onClick={() => { if (window.confirm('Delete workflow?')) act(() => workflowApi.remove(w.id)); }} title="Delete" className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                  </div>
                )}
              </div>
            </div>
          ))}
          {!items.length && <p className="text-xs text-slate-500 py-8 text-center">No workflows yet. Create one or start from a template.</p>}
        </div>
      )}

      {tab === 'templates' && (
        <div className="space-y-3">
          {isManager && <button onClick={() => act(() => workflowApi.seedTemplates(), 'seeded')} className="inline-flex items-center gap-1.5 border border-slate-800 text-slate-300 text-xs py-1.5 px-3 rounded-lg cursor-pointer"><LayoutTemplate className="w-3.5 h-3.5" /> Load built-in templates</button>}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
            {templates.map((t) => (
              <div key={t.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
                <div>
                  <p className="text-sm text-slate-200 font-medium">{t.name}</p>
                  <p className="text-[11px] text-slate-500 mt-0.5">{t.category} · {t.trigger_event.replace(/_/g, ' ')} · {t.node_count} node(s)</p>
                </div>
                {isManager && <button onClick={() => act(() => workflowApi.instantiate(t.id), 'Created from template')} className="text-xs text-brand-400 cursor-pointer inline-flex items-center gap-1 shrink-0"><Plus className="w-3.5 h-3.5" /> Use</button>}
              </div>
            ))}
            {!templates.length && <p className="text-xs text-slate-500 py-6 text-center col-span-full">No templates — load the built-ins.</p>}
          </div>
        </div>
      )}

      {tab === 'executions' && (
        <div className="space-y-2">
          {executions.map((ex) => (
            <div key={ex.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
              <div className="min-w-0">
                <p className="text-sm text-slate-200 truncate">{ex.workflow_name} <span className="text-slate-500 text-[11px]">· {ex.trigger_event.replace(/_/g, ' ')}{ex.is_test ? ' · test' : ''}</span></p>
                <p className="text-[11px] text-slate-500">{ex.steps_run} step(s){ex.rolled_back ? ' · rolled back' : ''}{ex.started_at ? ` · ${new Date(ex.started_at).toLocaleString()}` : ''}</p>
              </div>
              <div className="flex items-center gap-2 shrink-0">
                <StatusChip s={ex.status} />
                <button onClick={async () => setLogOf(await workflowApi.executionLogs(ex.id))} className="text-xs text-brand-400 cursor-pointer">Logs</button>
                {isManager && !ex.is_test && !ex.rolled_back && ex.steps_run > 0 && (
                  <button onClick={() => act(() => workflowApi.rollbackExecution(ex.id), 'Rolled back')} title="Roll back" className="text-slate-500 hover:text-amber-400 cursor-pointer"><RotateCcw className="w-3.5 h-3.5" /></button>
                )}
              </div>
            </div>
          ))}
          {!executions.length && <p className="text-xs text-slate-500 py-8 text-center">No executions yet.</p>}
        </div>
      )}

      {tab === 'reports' && report && (
        <div className="space-y-3">
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
            {[
              { label: 'Workflows', value: report.total_workflows }, { label: 'Published', value: report.published },
              { label: 'Enabled', value: report.enabled }, { label: 'Total runs', value: report.total_runs },
              { label: 'Completed', value: report.completed }, { label: 'Failed', value: report.failed },
              { label: 'Success rate', value: `${report.success_rate}%` },
            ].map((s) => (
              <div key={s.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{s.label}</p>
                <p className="text-lg font-bold text-slate-100 mt-0.5">{s.value}</p>
              </div>
            ))}
          </div>
          <div className="space-y-1.5">
            <p className="text-xs font-semibold text-slate-400">Most active workflows</p>
            {report.top_workflows.map((t) => (
              <div key={t.workflow_id} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
                <span className="text-slate-300">{t.name}</span><span className="text-slate-500">{t.runs} run(s)</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {designer && catalog && <Designer initial={designer === 'new' ? null : designer} catalog={catalog} users={users} onClose={() => setDesigner(null)} onSaved={() => { setDesigner(null); loadTab(); }} />}

      {versionsOf && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={() => setVersionsOf(null)}>
          <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-semibold text-slate-200">Versions · {versionsOf.wf.name}</h3><button onClick={() => setVersionsOf(null)} className="text-slate-500 cursor-pointer"><X className="w-4 h-4" /></button></div>
            <ul className="space-y-1.5">
              {versionsOf.rows.map((v) => (
                <li key={v.id} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
                  <span className="text-slate-300">v{v.version} <span className="text-slate-600">· {v.published_by_name}{v.published_at ? ` · ${new Date(v.published_at).toLocaleDateString()}` : ''}</span></span>
                  <button onClick={() => act(() => workflowApi.rollback(versionsOf.wf.id, v.version).then(() => setVersionsOf(null)), 'Rolled back')} className="text-brand-400 cursor-pointer inline-flex items-center gap-1"><RefreshCw className="w-3 h-3" /> Restore</button>
                </li>
              ))}
              {!versionsOf.rows.length && <li className="text-xs text-slate-500">No published versions yet.</li>}
            </ul>
          </div>
        </div>
      )}

      {logOf && (
        <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4" onClick={() => setLogOf(null)}>
          <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-lg bg-slate-900 p-4 max-h-[85vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">{logOf.workflow_name} <StatusChip s={logOf.status} />{logOf.is_test && <span className="text-[10px] text-slate-500">test run</span>}</h3><button onClick={() => setLogOf(null)} className="text-slate-500 cursor-pointer"><X className="w-4 h-4" /></button></div>
            <ol className="space-y-1.5">
              {(logOf.steps || []).map((s) => (
                <li key={s.seq} className="flex items-start gap-2 text-xs p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                  <span className="shrink-0">{nodeIcon(s.node_type)}</span>
                  <div className="min-w-0">
                    <p className="text-slate-200 capitalize">{s.node_type}{s.action_type ? ` · ${s.action_type.replace(/_/g, ' ')}` : ''} <StatusChip s={s.status} /></p>
                    {s.detail && <p className="text-[11px] text-slate-500">{s.detail}</p>}
                  </div>
                </li>
              ))}
              {!(logOf.steps || []).length && <li className="text-xs text-slate-500">No steps recorded.</li>}
            </ol>
          </div>
        </div>
      )}
    </div>
  );
};
