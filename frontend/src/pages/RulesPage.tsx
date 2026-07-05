import React, { useCallback, useEffect, useState } from 'react';
import {
  Filter, Plus, Loader2, X, Check, Trash2, Pencil, Copy, Upload, Download, FlaskConical,
  BarChart3, LayoutTemplate, ListChecks, GitBranch, ArrowUp, ArrowDown, Power,
} from 'lucide-react';
import {
  ruleApi, Rule, RuleCatalog, RuleNode, RuleGroup, RuleCondition, RuleTestResult, RuleReport, RuleEvaluationRow,
} from '../services/ruleApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm';

const emptyGroup = (logic: 'and' | 'or' | 'not' = 'and'): RuleGroup => ({ type: 'group', logic, children: [] });
const emptyCond = (field: string): RuleCondition => ({ type: 'condition', field, op: 'eq', value: '', value_type: 'static' });

const OPS_NO_VALUE = ['is_empty', 'is_not_empty', 'is_true', 'is_false'];
const OPS_LIST_VALUE = ['in', 'not_in', 'between', 'date_between', 'time_between'];

/* ── one condition row ── */
const ConditionRow: React.FC<{
  node: RuleCondition; catalog: RuleCatalog; entityType: string;
  onChange: (n: RuleCondition) => void; onRemove: () => void;
}> = ({ node, catalog, entityType, onChange, onRemove }) => {
  const fields = catalog.fields[entityType] || [];
  const allOps = [...catalog.operators.comparison, ...catalog.operators.date, ...catalog.operators.time, ...catalog.operators.boolean];
  const set = (patch: Partial<RuleCondition>) => onChange({ ...node, ...patch });
  const needsValue = !OPS_NO_VALUE.includes(node.op);
  const vt = node.value_type || 'static';
  return (
    <div className="flex flex-wrap items-center gap-2 p-2 rounded-lg bg-slate-950/50 border border-slate-800/70">
      <select value={node.field} onChange={(e) => set({ field: e.target.value })} className={`${F} !w-auto min-w-[9rem]`}>
        {fields.map((f) => <option key={f.field} value={f.field}>{f.field}{f.cross ? ' ↗' : ''}</option>)}
      </select>
      <select value={node.op} onChange={(e) => set({ op: e.target.value })} className={`${F} !w-auto min-w-[8rem]`}>
        {allOps.map((o) => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
      </select>
      {needsValue && (
        <>
          <select value={vt} onChange={(e) => set({ value_type: e.target.value as any })} className={`${F} !w-auto`}>
            {catalog.value_types.map((v) => <option key={v} value={v}>{v}</option>)}
          </select>
          {vt === 'static' && (
            <input value={node.value ?? ''} onChange={(e) => set({ value: e.target.value })}
              placeholder={OPS_LIST_VALUE.includes(node.op) ? 'a,b (comma list)' : 'value'}
              className={`${F} !w-auto min-w-[8rem]`} />
          )}
          {vt === 'field' && (
            <select value={node.value_field || ''} onChange={(e) => set({ value_field: e.target.value })} className={`${F} !w-auto min-w-[9rem]`}>
              <option value="">— field —</option>
              {fields.map((f) => <option key={f.field} value={f.field}>{f.field}</option>)}
            </select>
          )}
          {vt === 'variable' && (
            <select value={node.variable || ''} onChange={(e) => set({ variable: e.target.value })} className={`${F} !w-auto min-w-[9rem]`}>
              <option value="">— variable —</option>
              {catalog.variables.map((v) => <option key={v} value={v}>{v}</option>)}
            </select>
          )}
        </>
      )}
      <button onClick={onRemove} className="ml-auto text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
    </div>
  );
};

/* ── recursive group editor (AND / OR / NOT) ── */
const GroupEditor: React.FC<{
  node: RuleGroup; catalog: RuleCatalog; entityType: string; depth?: number;
  onChange: (n: RuleGroup) => void; onRemove?: () => void;
}> = ({ node, catalog, entityType, depth = 0, onChange, onRemove }) => {
  const fields = catalog.fields[entityType] || [];
  const setChild = (i: number, child: RuleNode) => {
    const children = [...node.children]; children[i] = child; onChange({ ...node, children });
  };
  const removeChild = (i: number) => onChange({ ...node, children: node.children.filter((_, x) => x !== i) });
  const addCond = () => onChange({ ...node, children: [...node.children, emptyCond(fields[0]?.field || 'status')] });
  const addGroup = () => onChange({ ...node, children: [...node.children, emptyGroup('or')] });
  const tone = node.logic === 'or' ? 'border-indigo-500/40' : node.logic === 'not' ? 'border-red-500/40' : 'border-emerald-500/40';
  return (
    <div className={`rounded-xl border ${tone} bg-slate-900/40 p-3 space-y-2`}>
      <div className="flex items-center gap-2">
        <GitBranch className="w-3.5 h-3.5 text-slate-400" />
        <select value={node.logic} onChange={(e) => onChange({ ...node, logic: e.target.value as any })}
          className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1 px-2 rounded-md text-xs font-semibold">
          {catalog.logic.map((l) => <option key={l} value={l}>{l.toUpperCase()}</option>)}
        </select>
        <span className="text-[10px] text-slate-500">{node.logic === 'not' ? 'none of the below match' : `${node.logic === 'or' ? 'any' : 'all'} of the below match`}</span>
        {onRemove && <button onClick={onRemove} className="ml-auto text-slate-600 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>}
      </div>
      <div className="space-y-2 pl-3 border-l border-slate-800/70">
        {node.children.map((c, i) => c.type === 'group'
          ? <GroupEditor key={i} node={c} catalog={catalog} entityType={entityType} depth={depth + 1}
              onChange={(n) => setChild(i, n)} onRemove={() => removeChild(i)} />
          : <ConditionRow key={i} node={c} catalog={catalog} entityType={entityType}
              onChange={(n) => setChild(i, n)} onRemove={() => removeChild(i)} />)}
        {node.children.length === 0 && <p className="text-[11px] text-slate-600 italic py-1">No conditions — always matches.</p>}
      </div>
      <div className="flex items-center gap-2">
        <button onClick={addCond} className="text-[11px] px-2 py-1 rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer flex items-center gap-1"><Plus className="w-3 h-3" /> Condition</button>
        {depth < 4 && <button onClick={addGroup} className="text-[11px] px-2 py-1 rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer flex items-center gap-1"><Plus className="w-3 h-3" /> Group</button>}
      </div>
    </div>
  );
};

type Tab = 'rules' | 'templates' | 'evaluations' | 'reports';

export const RulesPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('rules');
  const [catalog, setCatalog] = useState<RuleCatalog | null>(null);
  const [rules, setRules] = useState<Rule[]>([]);
  const [templates, setTemplates] = useState<Rule[]>([]);
  const [evals, setEvals] = useState<RuleEvaluationRow[]>([]);
  const [report, setReport] = useState<RuleReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  // editor
  const [editing, setEditing] = useState<Rule | null>(null);
  const [draft, setDraft] = useState<any>(null);
  const [saving, setSaving] = useState(false);
  // tester
  const [testFor, setTestFor] = useState<Rule | null>(null);
  const [sample, setSample] = useState('{\n  "status": "New",\n  "value": 60000\n}');
  const [testResult, setTestResult] = useState<RuleTestResult | null>(null);

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cat, rs, tpls] = await Promise.all([
        ruleApi.catalog(), ruleApi.list({ is_template: false }), ruleApi.list({ is_template: true }),
      ]);
      setCatalog(cat); setRules(rs); setTemplates(tpls);
    } catch (e) { setErr(extractErrorMessage(e, 'Something went wrong.')); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (tab === 'reports') ruleApi.report().then(setReport).catch(() => {}); }, [tab]);
  useEffect(() => { if (tab === 'evaluations') ruleApi.evaluations({ limit: 50 }).then(setEvals).catch(() => {}); }, [tab]);

  const newRule = () => {
    const et = catalog?.entity_types[0] || 'lead';
    setEditing({ id: '' } as Rule);
    setDraft({ name: '', description: '', category: '', entity_type: et, priority: 100,
      conflict_strategy: 'highest_priority', is_active: true, definition: emptyGroup('and') });
  };
  const editRule = (r: Rule) => {
    setEditing(r);
    setDraft({ name: r.name, description: r.description || '', category: r.category || '', entity_type: r.entity_type,
      priority: r.priority, conflict_strategy: r.conflict_strategy, is_active: r.is_active,
      definition: r.definition || emptyGroup('and') });
  };
  const save = async () => {
    if (!draft?.name?.trim()) { setErr('Name is required.'); return; }
    setSaving(true); setErr('');
    try {
      if (editing?.id) await ruleApi.update(editing.id, draft);
      else await ruleApi.create(draft);
      setEditing(null); setDraft(null); flash('Saved.'); await load();
    } catch (e) { setErr(extractErrorMessage(e, 'Something went wrong.')); } finally { setSaving(false); }
  };
  const act = async (fn: () => Promise<any>, ok: string) => {
    try { await fn(); flash(ok); await load(); } catch (e) { setErr(extractErrorMessage(e, 'Something went wrong.')); }
  };
  const bumpPriority = (r: Rule, delta: number) => act(() => ruleApi.setPriority(r.id, r.priority + delta), 'Priority updated.');
  const exportRule = async (r: Rule) => {
    const data = await ruleApi.exportOne(r.id);
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const a = document.createElement('a'); a.href = URL.createObjectURL(blob); a.download = `rule-${r.name}.json`; a.click();
  };
  const importRule = () => {
    const inp = document.createElement('input'); inp.type = 'file'; inp.accept = 'application/json';
    inp.onchange = async () => {
      const file = inp.files?.[0]; if (!file) return;
      try { await ruleApi.importOne(JSON.parse(await file.text())); flash('Imported.'); await load(); }
      catch (e) { setErr(extractErrorMessage(e, 'Something went wrong.')); }
    };
    inp.click();
  };
  const runTest = async () => {
    if (!testFor) return;
    setTestResult(null); setErr('');
    try {
      let body: any = {};
      if (sample.trim()) body.sample = JSON.parse(sample);
      setTestResult(await ruleApi.test(testFor.id, body));
    } catch (e) { setErr(extractErrorMessage(e, 'Something went wrong.')); }
  };

  const Tabs = (
    <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
      {([['rules', 'Rules', ListChecks], ['templates', 'Templates', LayoutTemplate],
         ['evaluations', 'Evaluations', FlaskConical], ['reports', 'Reports', BarChart3]] as [Tab, string, any][])
        .map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Filter className="w-6 h-6 text-brand-400" /> Rule Engine</h1>
          <p className="text-sm text-slate-500 mt-1">Reusable AND/OR/NOT condition rules with priority, testing and conflict resolution.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={importRule} className="px-3 py-2 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Upload className="w-3.5 h-3.5" /> Import</button>
          <button onClick={newRule} className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New Rule</button>
        </div>
      </div>

      {Tabs}
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'rules' ? (
        <div className="space-y-2">
          {rules.length === 0 && <p className="text-sm text-slate-500">No rules yet. Create one or start from a template.</p>}
          {rules.map((r) => (
            <div key={r.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex flex-col items-center gap-0.5">
                <button onClick={() => bumpPriority(r, 10)} className="text-slate-500 hover:text-brand-300 cursor-pointer"><ArrowUp className="w-3.5 h-3.5" /></button>
                <span className="text-xs font-bold text-slate-300">P{r.priority}</span>
                <button onClick={() => bumpPriority(r, -10)} className="text-slate-500 hover:text-brand-300 cursor-pointer"><ArrowDown className="w-3.5 h-3.5" /></button>
              </div>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-100 truncate">{r.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400 border border-slate-600/40">{r.entity_type}</span>
                  {r.category && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">{r.category}</span>}
                  {!r.is_active && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-500">inactive</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5 truncate">{r.condition_count} condition(s) · {r.conflict_strategy.replace(/_/g, ' ')} · {r.match_count}/{r.eval_count} matched</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title="Test" onClick={() => { setTestFor(r); setTestResult(null); }} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><FlaskConical className="w-4 h-4" /></button>
                <button title={r.is_active ? 'Deactivate' : 'Activate'} onClick={() => act(() => ruleApi.update(r.id, { is_active: !r.is_active }), 'Updated.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-emerald-300 cursor-pointer"><Power className="w-4 h-4" /></button>
                <button title="Edit" onClick={() => editRule(r)} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                <button title="Clone" onClick={() => act(() => ruleApi.clone(r.id), 'Cloned.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Copy className="w-4 h-4" /></button>
                <button title="Export" onClick={() => exportRule(r)} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Download className="w-4 h-4" /></button>
                <button title="Delete" onClick={() => window.confirm(`Delete rule "${r.name}"?`) && act(() => ruleApi.remove(r.id), 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'templates' ? (
        <div className="space-y-3">
          <button onClick={() => act(() => ruleApi.seedTemplates(), 'Templates seeded.')} className="px-3 py-2 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer">Seed built-in templates</button>
          {templates.length === 0 && <p className="text-sm text-slate-500">No templates. Seed the built-ins to get started.</p>}
          {templates.map((t) => (
            <div key={t.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <span className="text-sm font-semibold text-slate-100">{t.name}</span>
                <p className="text-[11px] text-slate-500 mt-0.5">{t.description}</p>
              </div>
              <button onClick={() => act(() => ruleApi.instantiate(t.id), 'Rule created from template.')} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer shrink-0">Use template</button>
            </div>
          ))}
        </div>
      ) : tab === 'evaluations' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Entity</th>
              <th className="text-left px-4 py-2 font-semibold">Matched</th>
              <th className="text-left px-4 py-2 font-semibold">Mode</th>
              <th className="text-left px-4 py-2 font-semibold">When</th>
            </tr></thead>
            <tbody>
              {evals.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-500">No evaluations recorded yet.</td></tr>}
              {evals.map((e) => (
                <tr key={e.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2 text-slate-300">{e.entity_type}{e.entity_id ? ` · ${e.entity_id.slice(0, 8)}` : ''}</td>
                  <td className="px-4 py-2">{e.matched ? <span className="text-emerald-400">match</span> : <span className="text-slate-500">no match</span>}</td>
                  <td className="px-4 py-2 text-slate-400">{e.is_test ? 'test' : 'live'}</td>
                  <td className="px-4 py-2 text-slate-500">{e.created_at ? new Date(e.created_at).toLocaleString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {report && [['Total rules', report.total], ['Active', report.active], ['Templates', report.templates],
            ['Evaluations', report.evaluations], ['Matches', report.matches], ['Match rate', `${report.match_rate}%`]].map(([k, v]) => (
            <div key={k as string} className="glass-panel border border-slate-800/85 rounded-xl p-4">
              <p className="text-[10px] font-semibold text-slate-500 uppercase">{k}</p>
              <p className="text-xl font-bold text-slate-100 mt-1">{v}</p>
            </div>
          ))}
        </div>
      )}

      {/* Editor modal */}
      {editing && draft && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => { setEditing(null); setDraft(null); }}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{editing.id ? 'Edit rule' : 'New rule'}</h3>
              <button onClick={() => { setEditing(null); setDraft(null); }} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="grid grid-cols-2 gap-3 mb-3">
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Rule name" className={F} />
              <input value={draft.category} onChange={(e) => setDraft({ ...draft, category: e.target.value })} placeholder="Category (optional)" className={F} />
              <select value={draft.entity_type} onChange={(e) => setDraft({ ...draft, entity_type: e.target.value, definition: emptyGroup('and') })} className={F}>
                {catalog.entity_types.map((t) => <option key={t} value={t}>{t}</option>)}
              </select>
              <select value={draft.conflict_strategy} onChange={(e) => setDraft({ ...draft, conflict_strategy: e.target.value })} className={F}>
                {catalog.conflict_strategies.map((s) => <option key={s} value={s}>{s.replace(/_/g, ' ')}</option>)}
              </select>
              <input type="number" value={draft.priority} onChange={(e) => setDraft({ ...draft, priority: parseInt(e.target.value) || 0 })} placeholder="Priority" className={F} />
              <label className="flex items-center gap-2 text-xs text-slate-300 px-1"><input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} /> Active</label>
            </div>
            <textarea value={draft.description} onChange={(e) => setDraft({ ...draft, description: e.target.value })} placeholder="Description (optional)" rows={2} className={`${F} mb-3`} />
            <p className="text-xs font-semibold text-slate-400 mb-2">Expression</p>
            <GroupEditor node={draft.definition} catalog={catalog} entityType={draft.entity_type} onChange={(d) => setDraft({ ...draft, definition: d })} />
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => { setEditing(null); setDraft(null); }} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={save} disabled={saving} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5">
                {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} Save
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Tester modal */}
      {testFor && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setTestFor(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2"><FlaskConical className="w-5 h-5 text-brand-400" /> Test: {testFor.name}</h3>
              <button onClick={() => setTestFor(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <p className="text-xs text-slate-500 mb-1">Sample facts (JSON) for the {testFor.entity_type}:</p>
            <textarea value={sample} onChange={(e) => setSample(e.target.value)} rows={6} className={`${F} font-mono`} />
            <div className="flex items-center justify-end gap-2 mt-3">
              <button onClick={runTest} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer">Run test</button>
            </div>
            {testResult && (
              <div className={`mt-4 p-3 rounded-lg border ${testResult.matched ? 'bg-emerald-500/10 border-emerald-500/30' : 'bg-slate-800/40 border-slate-700/60'}`}>
                <p className={`text-sm font-bold ${testResult.matched ? 'text-emerald-400' : 'text-slate-400'}`}>{testResult.matched ? '✓ Rule matches' : '✗ No match'}</p>
                <pre className="text-[10px] text-slate-400 mt-2 overflow-x-auto">{JSON.stringify(testResult.trace, null, 2)}</pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
