import React, { useCallback, useEffect, useState } from 'react';
import {
  Gauge, Loader2, X, Check, Trash2, Plus, Power, Pencil, Pause, Play, RefreshCw,
  ListChecks, Timer, AlertTriangle, BarChart3, Building2, PartyPopper, ShieldAlert,
} from 'lucide-react';
import {
  slaApi, SLAPolicy, SLATracker, SLABreach, SLACatalog, SLAReport,
} from '../services/slaApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm';

const fmtDue = (s: string | null) => {
  if (!s) return '—';
  const d = new Date(s); const now = Date.now();
  const diff = Math.round((d.getTime() - now) / 60000);
  const rel = diff > 0 ? `in ${diff < 60 ? diff + 'm' : Math.round(diff / 60) + 'h'}` : `${Math.abs(diff) < 60 ? Math.abs(diff) + 'm' : Math.round(Math.abs(diff) / 60) + 'h'} ago`;
  return `${d.toLocaleString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })} (${rel})`;
};

const StatusChip: React.FC<{ t: SLATracker }> = ({ t }) => {
  const s = t.status;
  const tone = s === 'met' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : s === 'breached' ? 'bg-red-500/10 text-red-400 border-red-500/20'
      : s === 'paused' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
        : 'bg-brand-500/10 text-brand-300 border-brand-500/20';
  return <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{s}</span>;
};

type Tab = 'policies' | 'active' | 'breaches' | 'dashboard';

export const SLAPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('policies');
  const [catalog, setCatalog] = useState<SLACatalog | null>(null);
  const [policies, setPolicies] = useState<SLAPolicy[]>([]);
  const [trackers, setTrackers] = useState<SLATracker[]>([]);
  const [breaches, setBreaches] = useState<SLABreach[]>([]);
  const [report, setReport] = useState<SLAReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [draft, setDraft] = useState<any>(null);

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };
  const fail = (e: any) => setErr(extractErrorMessage(e, 'Something went wrong.'));

  const load = useCallback(async () => {
    setLoading(true);
    try { const [c, p] = await Promise.all([slaApi.catalog(), slaApi.listPolicies()]); setCatalog(c); setPolicies(p); }
    catch (e) { fail(e); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (tab === 'active') slaApi.trackers({ limit: 100 }).then(setTrackers).catch(() => {});
    if (tab === 'breaches') slaApi.breaches({ limit: 100 }).then(setBreaches).catch(() => {});
    if (tab === 'dashboard') slaApi.report().then(setReport).catch(() => {});
  }, [tab]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); } catch (e) { fail(e); } };

  const newPolicy = () => setDraft({
    name: '', entity_type: 'lead', response_hours: 4, resolution_hours: 24, priority_field: 'priority',
    priorities: [], business_hours_only: false, skip_holidays: false, on_breach: 'notify_manager',
    escalate_to_role: '', conditions: '', is_active: true,
  });
  const editPolicy = (p: SLAPolicy) => setDraft({ ...p, priorities: p.priorities || [], escalate_to_role: p.escalate_to_role || '', conditions: p.conditions ? JSON.stringify(p.conditions, null, 2) : '' });

  const save = async () => {
    if (!draft?.name?.trim()) { setErr('Name is required.'); return; }
    try {
      const payload: any = { ...draft };
      payload.conditions = draft.conditions?.trim() ? JSON.parse(draft.conditions) : null;
      payload.priorities = (draft.priorities || []).filter((t: any) => t.level?.trim());
      payload.escalate_to_role = draft.escalate_to_role?.trim() || null;
      if (draft.id) await slaApi.updatePolicy(draft.id, payload);
      else await slaApi.createPolicy(payload);
      setDraft(null); flash('Policy saved.'); await load();
    } catch (e) { fail(e); }
  };
  const addTier = () => setDraft({ ...draft, priorities: [...draft.priorities, { level: '', response_hours: null, resolution_hours: null }] });
  const setTier = (i: number, patch: any) => {
    const priorities = [...draft.priorities]; priorities[i] = { ...priorities[i], ...patch }; setDraft({ ...draft, priorities });
  };

  const Tabs = (
    <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
      {([['policies', 'Policies', ListChecks], ['active', 'Active SLAs', Timer], ['breaches', 'Breaches', AlertTriangle], ['dashboard', 'Dashboard', BarChart3]] as [Tab, string, any][])
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
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Gauge className="w-6 h-6 text-brand-400" /> SLA Management</h1>
          <p className="text-sm text-slate-500 mt-1">Response & resolution targets by priority — business-hours & holiday aware, with pause/resume, breach escalation and compliance reporting.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => act(async () => { const r = await slaApi.scan(); flash(`Scan flagged ${r.breaches} breach(es).`); if (tab === 'active') slaApi.trackers({ limit: 100 }).then(setTrackers); }, '')} className="px-3 py-2 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><RefreshCw className="w-3.5 h-3.5" /> Scan now</button>
          <button onClick={newPolicy} className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New policy</button>
        </div>
      </div>

      {Tabs}
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'policies' ? (
        <div className="space-y-2">
          {policies.length === 0 && <p className="text-sm text-slate-500">No SLA policies yet.</p>}
          {policies.map((p) => (
            <div key={p.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-100 truncate">{p.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400 border border-slate-600/40">{p.entity_type}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">resp {p.response_hours ?? '—'}h · res {p.resolution_hours ?? '—'}h</span>
                  {p.priorities && p.priorities.length > 0 && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">{p.priorities.length} tiers</span>}
                  {p.business_hours_only && <span title="Business hours only"><Building2 className="w-3.5 h-3.5 text-slate-500" /></span>}
                  {p.skip_holidays && <span title="Skips holidays"><PartyPopper className="w-3.5 h-3.5 text-slate-500" /></span>}
                  {!p.is_active && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-500">inactive</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">on breach: {p.on_breach.replace(/_/g, ' ')}{p.escalate_to_role ? ` → ${p.escalate_to_role}` : ''} · {p.breach_count} breaches</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title={p.is_active ? 'Disable' : 'Enable'} onClick={() => act(async () => { await slaApi.enablePolicy(p.id, !p.is_active); await load(); }, 'Updated.')} className={`p-1.5 rounded-md hover:bg-slate-800 cursor-pointer ${p.is_active ? 'text-emerald-400' : 'text-slate-500'}`}><Power className="w-4 h-4" /></button>
                <button title="Edit" onClick={() => editPolicy(p)} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                <button title="Delete" onClick={() => window.confirm(`Delete "${p.name}"?`) && act(async () => { await slaApi.removePolicy(p.id); await load(); }, 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'active' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Entity</th>
              <th className="text-left px-4 py-2 font-semibold">Priority</th>
              <th className="text-left px-4 py-2 font-semibold">Status</th>
              <th className="text-left px-4 py-2 font-semibold">Response due</th>
              <th className="text-left px-4 py-2 font-semibold">Resolution due</th>
              <th className="px-4 py-2"></th>
            </tr></thead>
            <tbody>
              {trackers.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">No active SLA trackers.</td></tr>}
              {trackers.map((t) => (
                <tr key={t.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2 text-slate-300">{t.entity_type} · {t.entity_id.slice(0, 8)}</td>
                  <td className="px-4 py-2 text-slate-400">{t.priority_level || '—'}</td>
                  <td className="px-4 py-2"><StatusChip t={t} /></td>
                  <td className={`px-4 py-2 ${t.response_breached ? 'text-red-400' : t.first_response_at ? 'text-emerald-400' : 'text-slate-400'}`}>{t.first_response_at ? 'responded' : fmtDue(t.response_due_at)}</td>
                  <td className={`px-4 py-2 ${t.resolution_breached ? 'text-red-400' : t.resolved_at ? 'text-emerald-400' : 'text-slate-400'}`}>{t.resolved_at ? 'resolved' : fmtDue(t.resolution_due_at)}</td>
                  <td className="px-4 py-2 text-right">
                    {t.status === 'running' && <button title="Pause" onClick={() => act(async () => { await slaApi.pause(t.id); slaApi.trackers({ limit: 100 }).then(setTrackers); }, 'Paused.')} className="text-amber-400 hover:text-amber-300 cursor-pointer inline-flex"><Pause className="w-4 h-4" /></button>}
                    {t.status === 'paused' && <button title="Resume" onClick={() => act(async () => { await slaApi.resume(t.id); slaApi.trackers({ limit: 100 }).then(setTrackers); }, 'Resumed.')} className="text-brand-400 hover:text-brand-300 cursor-pointer inline-flex"><Play className="w-4 h-4" /></button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : tab === 'breaches' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Entity</th>
              <th className="text-left px-4 py-2 font-semibold">Metric</th>
              <th className="text-left px-4 py-2 font-semibold">Elapsed</th>
              <th className="text-left px-4 py-2 font-semibold">When</th>
            </tr></thead>
            <tbody>
              {breaches.length === 0 && <tr><td colSpan={4} className="px-4 py-6 text-center text-slate-500">No breaches. 🎉</td></tr>}
              {breaches.map((b) => (
                <tr key={b.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2 text-slate-300">{b.entity_type} · {b.entity_id.slice(0, 8)}</td>
                  <td className="px-4 py-2"><span className="text-red-400 flex items-center gap-1"><ShieldAlert className="w-3.5 h-3.5" /> {b.metric.replace(/_/g, ' ')}</span></td>
                  <td className="px-4 py-2 text-slate-400">{b.hours_elapsed}h</td>
                  <td className="px-4 py-2 text-slate-500">{b.breached_at ? new Date(b.breached_at).toLocaleString() : ''}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {report && [['Compliance', `${report.compliance_rate}%`], ['Policies', report.policies], ['Met', report.met],
              ['Breached', report.breached], ['Open breaches', report.open_breaches], ['Avg response', `${report.avg_response_hours}h`]].map(([k, v]) => (
              <div key={k as string} className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-[10px] font-semibold text-slate-500 uppercase">{k}</p>
                <p className="text-xl font-bold text-slate-100 mt-1">{v}</p>
              </div>
            ))}
          </div>
          {report && (
            <div className="glass-panel border border-slate-800/85 rounded-xl p-4">
              <p className="text-xs font-semibold text-slate-300 mb-2">Trackers by status</p>
              {Object.keys(report.by_status).length === 0 ? <p className="text-xs text-slate-500">No trackers yet.</p> :
                Object.entries(report.by_status).map(([s, n]) => <div key={s} className="flex justify-between text-xs py-0.5"><span className="text-slate-400">{s}</span><span className="text-slate-300">{n}</span></div>)}
            </div>
          )}
        </div>
      )}

      {/* Policy editor */}
      {draft && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{draft.id ? 'Edit SLA policy' : 'New SLA policy'}</h3>
              <button onClick={() => setDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Policy name" className={F} />
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-[11px] text-slate-500">Response hours</label><input type="number" value={draft.response_hours ?? ''} onChange={(e) => setDraft({ ...draft, response_hours: e.target.value === '' ? null : parseFloat(e.target.value) })} className={F} /></div>
                <div><label className="text-[11px] text-slate-500">Resolution hours</label><input type="number" value={draft.resolution_hours ?? ''} onChange={(e) => setDraft({ ...draft, resolution_hours: e.target.value === '' ? null : parseFloat(e.target.value) })} className={F} /></div>
              </div>
              <div>
                <div className="flex items-center justify-between">
                  <label className="text-[11px] text-slate-500">Priority tiers (override the defaults per priority)</label>
                  <button onClick={addTier} className="text-[11px] px-2 py-0.5 rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer">+ tier</button>
                </div>
                {draft.priorities.map((t: any, i: number) => (
                  <div key={i} className="grid grid-cols-[1fr_1fr_1fr_auto] gap-2 mt-1 items-center">
                    <input value={t.level} onChange={(e) => setTier(i, { level: e.target.value })} placeholder="High" className={F} />
                    <input type="number" value={t.response_hours ?? ''} onChange={(e) => setTier(i, { response_hours: e.target.value === '' ? null : parseFloat(e.target.value) })} placeholder="resp h" className={F} />
                    <input type="number" value={t.resolution_hours ?? ''} onChange={(e) => setTier(i, { resolution_hours: e.target.value === '' ? null : parseFloat(e.target.value) })} placeholder="res h" className={F} />
                    <button onClick={() => setDraft({ ...draft, priorities: draft.priorities.filter((_: any, x: number) => x !== i) })} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-4 h-4" /></button>
                  </div>
                ))}
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-[11px] text-slate-500">On breach</label>
                  <select value={draft.on_breach} onChange={(e) => setDraft({ ...draft, on_breach: e.target.value })} className={F}>
                    {catalog.breach_actions.map((a) => <option key={a} value={a}>{a.replace(/_/g, ' ')}</option>)}
                  </select></div>
                <div><label className="text-[11px] text-slate-500">Escalate to role (optional)</label><input value={draft.escalate_to_role} onChange={(e) => setDraft({ ...draft, escalate_to_role: e.target.value })} placeholder="Manager" className={F} /></div>
              </div>
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={draft.business_hours_only} onChange={(e) => setDraft({ ...draft, business_hours_only: e.target.checked })} /> Business hours only</label>
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={draft.skip_holidays} onChange={(e) => setDraft({ ...draft, skip_holidays: e.target.checked })} /> Skip holidays</label>
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
