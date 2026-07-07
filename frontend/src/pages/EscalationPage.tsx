import React, { useCallback, useEffect, useState } from 'react';
import {
  TrendingUp, Loader2, X, Check, Trash2, Plus, Power, Pencil, RefreshCw, ArrowUp,
  ListChecks, History as HistoryIcon, BarChart3,
} from 'lucide-react';
import {
  escalationApi, EscalationRule, EscalationEvent, EscalationCatalog, EscalationReport,
} from '../services/escalationApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm';

type Tab = 'rules' | 'events' | 'dashboard';

export const EscalationPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('rules');
  const [catalog, setCatalog] = useState<EscalationCatalog | null>(null);
  const [rules, setRules] = useState<EscalationRule[]>([]);
  const [events, setEvents] = useState<EscalationEvent[]>([]);
  const [report, setReport] = useState<EscalationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [draft, setDraft] = useState<any>(null);

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };
  const fail = (e: any) => setErr(extractErrorMessage(e, 'Something went wrong.'));

  const load = useCallback(async () => {
    setLoading(true);
    try { const [c, r] = await Promise.all([escalationApi.catalog(), escalationApi.listRules()]); setCatalog(c); setRules(r); }
    catch (e) { fail(e); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (tab === 'events') escalationApi.events({ limit: 50 }).then(setEvents).catch(() => {});
    if (tab === 'dashboard') escalationApi.report().then(setReport).catch(() => {});
  }, [tab]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); } catch (e) { fail(e); } };

  const newRule = () => setDraft({
    name: '', entity_type: 'lead', trigger_condition: 'no_activity',
    levels: [{ after_hours: 24, escalate_to: 'manager', value: '', notify: true }],
    business_hours_only: false, conditions: '', is_active: true,
  });
  const editRule = (r: EscalationRule) => setDraft({ ...r, levels: r.levels.map((l) => ({ ...l, value: l.value || '' })), conditions: r.conditions ? JSON.stringify(r.conditions, null, 2) : '' });

  const save = async () => {
    if (!draft?.name?.trim()) { setErr('Name is required.'); return; }
    if (!draft.levels.length) { setErr('Add at least one escalation level.'); return; }
    try {
      const payload: any = { ...draft };
      payload.conditions = draft.conditions?.trim() ? JSON.parse(draft.conditions) : null;
      payload.levels = draft.levels.map((l: any) => ({ after_hours: Number(l.after_hours), escalate_to: l.escalate_to, value: l.value || null, notify: l.notify !== false }));
      if (draft.id) await escalationApi.updateRule(draft.id, payload);
      else await escalationApi.createRule(payload);
      setDraft(null); flash('Rule saved.'); await load();
    } catch (e) { fail(e); }
  };
  const setLevel = (i: number, patch: any) => { const levels = [...draft.levels]; levels[i] = { ...levels[i], ...patch }; setDraft({ ...draft, levels }); };
  const addLevel = () => setDraft({ ...draft, levels: [...draft.levels, { after_hours: 48, escalate_to: 'department_head', value: '', notify: true }] });

  const Tabs = (
    <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
      {([['rules', 'Rules', ListChecks], ['events', 'Events', HistoryIcon], ['dashboard', 'Dashboard', BarChart3]] as [Tab, string, any][])
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
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><TrendingUp className="w-6 h-6 text-brand-400" /> Escalation Engine</h1>
          <p className="text-sm text-slate-500 mt-1">Multi-level, time-based escalation across leads, tasks, calls, tickets and approvals — to managers, department heads or roles.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => act(async () => { const r = await escalationApi.scan(); flash(`Scan fired ${r.escalations} escalation(s).`); }, '')} className="px-3 py-2 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><RefreshCw className="w-3.5 h-3.5" /> Scan now</button>
          <button onClick={newRule} className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New rule</button>
        </div>
      </div>

      {Tabs}
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'rules' ? (
        <div className="space-y-2">
          {rules.length === 0 && <p className="text-sm text-slate-500">No escalation rules yet.</p>}
          {rules.map((r) => (
            <div key={r.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-100 truncate">{r.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400 border border-slate-600/40">{r.entity_type}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">{r.trigger_condition.replace(/_/g, ' ')}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">{r.levels.length} level{r.levels.length !== 1 ? 's' : ''}</span>
                  {!r.is_active && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-500">paused</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">{r.levels.map((l, i) => `L${i + 1}: ${l.after_hours}h→${l.escalate_to.replace(/_/g, ' ')}`).join(' · ')} · {r.escalation_count} fired</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title={r.is_active ? 'Pause' : 'Resume'} onClick={() => act(async () => { await escalationApi.enableRule(r.id, !r.is_active); await load(); }, 'Updated.')} className={`p-1.5 rounded-md hover:bg-slate-800 cursor-pointer ${r.is_active ? 'text-emerald-400' : 'text-slate-500'}`}><Power className="w-4 h-4" /></button>
                <button title="Edit" onClick={() => editRule(r)} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                <button title="Delete" onClick={() => window.confirm(`Delete "${r.name}"?`) && act(async () => { await escalationApi.removeRule(r.id); await load(); }, 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'events' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Entity</th>
              <th className="text-left px-4 py-2 font-semibold">Level</th>
              <th className="text-left px-4 py-2 font-semibold">Escalated to</th>
              <th className="text-left px-4 py-2 font-semibold">Reason</th>
              <th className="text-left px-4 py-2 font-semibold">When</th>
            </tr></thead>
            <tbody>
              {events.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">No escalations recorded yet.</td></tr>}
              {events.map((e) => (
                <tr key={e.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2 text-slate-300">{e.entity_type} · {e.entity_id.slice(0, 8)}</td>
                  <td className="px-4 py-2"><span className="text-brand-300 flex items-center gap-1"><ArrowUp className="w-3.5 h-3.5" /> L{e.level}</span></td>
                  <td className="px-4 py-2 text-slate-400">{e.escalate_to?.replace(/_/g, ' ')}</td>
                  <td className="px-4 py-2 text-slate-500 truncate max-w-[18rem]">{e.reason}</td>
                  <td className="px-4 py-2 text-slate-500">{e.escalated_at ? new Date(e.escalated_at).toLocaleString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {report && [['Rules', report.rules], ['Active', report.active], ['Escalations', report.escalations]].map(([k, v]) => (
              <div key={k as string} className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-[10px] font-semibold text-slate-500 uppercase">{k}</p>
                <p className="text-xl font-bold text-slate-100 mt-1">{v}</p>
              </div>
            ))}
          </div>
          {report && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-300 mb-2">By entity</p>
                {Object.keys(report.by_entity).length === 0 ? <p className="text-xs text-slate-500">None.</p> :
                  Object.entries(report.by_entity).map(([e, n]) => <div key={e} className="flex justify-between text-xs py-0.5"><span className="text-slate-400">{e}</span><span className="text-slate-300">{n}</span></div>)}
              </div>
              <div className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-300 mb-2">By level</p>
                {Object.keys(report.by_level).length === 0 ? <p className="text-xs text-slate-500">None.</p> :
                  Object.entries(report.by_level).map(([l, n]) => <div key={l} className="flex justify-between text-xs py-0.5"><span className="text-slate-400">Level {l}</span><span className="text-slate-300">{n}</span></div>)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Rule editor */}
      {draft && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{draft.id ? 'Edit escalation rule' : 'New escalation rule'}</h3>
              <button onClick={() => setDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Rule name" className={F} />
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-[11px] text-slate-500">Entity type</label>
                  <select value={draft.entity_type} onChange={(e) => setDraft({ ...draft, entity_type: e.target.value })} className={F}>
                    {catalog.entity_types.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select></div>
                <div><label className="text-[11px] text-slate-500">Trigger condition</label>
                  <select value={draft.trigger_condition} onChange={(e) => setDraft({ ...draft, trigger_condition: e.target.value })} className={F}>
                    {catalog.trigger_conditions.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                  </select></div>
              </div>
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-[11px] text-slate-500">Escalation levels (fire in order as time passes)</label>
                  <button onClick={addLevel} className="text-[11px] px-2 py-0.5 rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer">+ level</button>
                </div>
                {draft.levels.map((l: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 mt-1 p-2 rounded-lg bg-slate-950/50 border border-slate-800/70">
                    <span className="text-[10px] font-bold text-brand-300 w-6">L{i + 1}</span>
                    <input type="number" value={l.after_hours} onChange={(e) => setLevel(i, { after_hours: e.target.value })} placeholder="after h" className={`${F} !w-20`} />
                    <span className="text-[10px] text-slate-500">h →</span>
                    <select value={l.escalate_to} onChange={(e) => setLevel(i, { escalate_to: e.target.value })} className={`${F} !w-auto`}>
                      {catalog.escalate_targets.map((t) => <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>)}
                    </select>
                    {['role', 'user'].includes(l.escalate_to) && <input value={l.value} onChange={(e) => setLevel(i, { value: e.target.value })} placeholder={l.escalate_to === 'role' ? 'role' : 'user id'} className={`${F} !w-auto flex-1`} />}
                    <button onClick={() => setDraft({ ...draft, levels: draft.levels.filter((_: any, x: number) => x !== i) })} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-4 h-4" /></button>
                  </div>
                ))}
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={draft.business_hours_only} onChange={(e) => setDraft({ ...draft, business_hours_only: e.target.checked })} /> Business hours only</label>
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={draft.is_active} onChange={(e) => setDraft({ ...draft, is_active: e.target.checked })} /> Active</label>
              </div>
              <textarea value={draft.conditions} onChange={(e) => setDraft({ ...draft, conditions: e.target.value })} placeholder="Applies-to conditions (Rule-Engine JSON, optional)" rows={2} className={`${F} font-mono`} />
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setDraft(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={save} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
