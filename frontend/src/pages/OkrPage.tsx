import React, { useCallback, useEffect, useState } from 'react';
import {
  Target, Loader2, Plus, X, Check, Pencil, Trash2, ChevronRight, ChevronDown, MessageSquare,
  LayoutDashboard, ListChecks, GitBranch, TrendingUp, AlertTriangle, RefreshCw,
} from 'lucide-react';
import { okrApi as api, OkrMeta, OkrDashboard, Objective, ObjectiveNode, OkrReview, KeyResult } from '../services/okrApi';
import { teamApi } from '../services/teamApi';
import { departmentApi } from '../services/departmentApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';

const LABEL: Record<string, { tone: string; label: string }> = {
  achieved: { tone: 'text-emerald-400', label: 'Achieved' },
  on_track: { tone: 'text-sky-400', label: 'On track' },
  at_risk: { tone: 'text-amber-400', label: 'At risk' },
  missed: { tone: 'text-red-400', label: 'Missed' },
  draft: { tone: 'text-slate-500', label: 'Draft' },
  cancelled: { tone: 'text-slate-500', label: 'Cancelled' },
};
const bar = (_p: number, label: string) =>
  label === 'achieved' ? 'bg-emerald-500/70' : label === 'at_risk' ? 'bg-amber-500/70' : label === 'missed' ? 'bg-red-500/70' : 'bg-sky-500/70';
const fmtVal = (v: number, unit: string) =>
  unit === 'currency' ? `₹${Math.round(v).toLocaleString()}` : unit === 'percent' ? `${v}%` : v.toLocaleString();

export const OkrPage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'objectives' | 'alignment'>('dashboard');
  const [meta, setMeta] = useState<OkrMeta | null>(null);
  const [dash, setDash] = useState<OkrDashboard | null>(null);
  const [rows, setRows] = useState<Objective[]>([]);
  const [tree, setTree] = useState<ObjectiveNode[]>([]);
  const [level, setLevel] = useState('');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [edit, setEdit] = useState<any | null>(null);
  const [detail, setDetail] = useState<Objective | null>(null);
  const [teams, setTeams] = useState<any[]>([]);
  const [depts, setDepts] = useState<any[]>([]);
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };

  useEffect(() => {
    teamApi.list({}).then((t: any) => setTeams(t.items || t)).catch(() => {});
    departmentApi.list({}).then((d: any) => setDepts(d.items || d)).catch(() => {});
  }, []);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (!meta) setMeta(await api.meta());
      if (tab === 'dashboard') setDash(await api.dashboard());
      else if (tab === 'objectives') setRows(await api.list(level ? { level } : {}));
      else setTree(await api.tree());
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load OKRs.')); } finally { setLoading(false); }
  }, [tab, level, meta]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await load(); } catch (e) { setErr(extractErrorMessage(e, 'Failed')); } };

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Target className="w-6 h-6 text-brand-400" /> Goals & OKRs</h1>
          <p className="text-sm text-slate-500 mt-1">Company, department, team and individual objectives with key-result tracking, reviews and feedback.</p>
        </div>
        <button onClick={() => setEdit({ level: 'company', cycle_type: 'quarterly', key_results: [] })} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5 w-fit"><Plus className="w-3.5 h-3.5" /> New objective</button>
      </div>

      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['objectives', 'Objectives', ListChecks], ['alignment', 'Alignment', GitBranch]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Objectives</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.total}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Achieved</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.achieved}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">On track</p><p className="text-xl font-bold text-sky-400 mt-1">{dash.on_track}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">At risk</p><p className="text-xl font-bold text-amber-400 mt-1">{dash.at_risk}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><TrendingUp className="w-3 h-3" /> Avg progress</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.avg_progress}%</p></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">By level</p>
              {Object.keys(dash.by_level).length === 0 ? <p className="text-xs text-slate-500">No objectives yet.</p> :
                Object.entries(dash.by_level).map(([lv, n]) => (
                  <div key={lv} className="flex items-center justify-between py-1 text-sm"><span className="text-slate-300 capitalize">{lv}</span><span className="text-slate-100 font-semibold">{n}</span></div>
                ))}
            </div>
            <div className={card}>
              <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 flex items-center gap-1.5"><AlertTriangle className="w-3.5 h-3.5 text-amber-400" /> At risk</p>
              {dash.at_risk_objectives.length === 0 ? <p className="text-xs text-slate-500">Nothing at risk. 🎉</p> :
                dash.at_risk_objectives.map((o) => (
                  <button key={o.id} onClick={() => setDetail(o)} className="w-full text-left py-1.5 border-b border-slate-800/50 last:border-0 cursor-pointer">
                    <p className="text-sm text-slate-200 truncate">{o.title}</p>
                    <p className="text-[11px] text-slate-500">{o.cycle_label} · {o.progress}% · <span className="capitalize">{o.level}</span></p>
                  </button>
                ))}
            </div>
          </div>
        </div>
      ) : tab === 'objectives' ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <select value={level} onChange={(e) => setLevel(e.target.value)} className={`${F} !w-44`}>
              <option value="">All levels</option>
              {meta?.levels.map((l) => <option key={l} value={l}>{l}</option>)}
            </select>
            <button onClick={() => act(() => api.scan(), 'Scan complete.')} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><RefreshCw className="w-3.5 h-3.5" /> Scan</button>
          </div>
          {rows.length === 0 && <p className="text-sm text-slate-500">No objectives — create one to get started.</p>}
          {rows.map((o) => <ObjectiveCard key={o.id} o={o} onOpen={() => setDetail(o)} onDelete={() => window.confirm(`Delete "${o.title}"?`) && act(() => api.remove(o.id), 'Deleted.')} />)}
        </div>
      ) : tab === 'alignment' ? (
        <div className="space-y-2">
          {tree.length === 0 && <p className="text-sm text-slate-500">No objectives yet.</p>}
          {tree.map((n) => <TreeNode key={n.id} node={n} depth={0} onOpen={setDetail} />)}
        </div>
      ) : null}

      {edit && meta && <ObjectiveModal draft={edit} meta={meta} teams={teams} depts={depts} onClose={() => setEdit(null)} onSaved={async () => { setEdit(null); flash('Saved.'); await load(); }} setErr={setErr} />}
      {detail && <DetailModal id={detail.id} onClose={() => setDetail(null)} onChanged={load} setErr={setErr} />}
    </div>
  );
};

const ObjectiveCard: React.FC<{ o: Objective; onOpen: () => void; onDelete: () => void }> = ({ o, onOpen, onDelete }) => {
  const st = LABEL[o.status_label] || LABEL.on_track;
  return (
    <div className="glass-panel border border-slate-800/85 rounded-xl p-4">
      <div className="flex items-center gap-3">
        <button onClick={onOpen} className="flex-1 min-w-0 text-left cursor-pointer">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-100 truncate">{o.title}</span>
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-700/40 text-slate-400 border border-slate-600/40 capitalize">{o.level}</span>
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-brand-500/10 text-brand-300">{o.cycle_label}</span>
            <span className={`text-[10px] font-semibold ${st.tone}`}>{st.label}</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">{o.owner_name ? `Owner ${o.owner_name} · ` : ''}{o.key_results.length} key result{o.key_results.length === 1 ? '' : 's'} · {o.progress}%</p>
        </button>
        <div className="w-28 shrink-0">
          <div className="h-2 bg-slate-800/60 rounded"><div className={`h-2 rounded ${bar(o.progress, o.status_label)}`} style={{ width: `${Math.min(100, o.progress)}%` }} /></div>
        </div>
        <button title="Delete" onClick={onDelete} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer shrink-0"><Trash2 className="w-4 h-4" /></button>
      </div>
    </div>
  );
};

const TreeNode: React.FC<{ node: ObjectiveNode; depth: number; onOpen: (o: Objective) => void }> = ({ node, depth, onOpen }) => {
  const [open, setOpen] = useState(true);
  const st = LABEL[node.status_label] || LABEL.on_track;
  return (
    <div style={{ marginLeft: depth * 20 }}>
      <div className="glass-panel border border-slate-800/85 rounded-xl p-3 flex items-center gap-2">
        {node.children.length > 0 ? (
          <button onClick={() => setOpen(!open)} className="text-slate-500 hover:text-slate-300 cursor-pointer">{open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}</button>
        ) : <span className="w-4" />}
        <button onClick={() => onOpen(node)} className="flex-1 min-w-0 text-left cursor-pointer">
          <span className="text-sm text-slate-200 truncate">{node.title}</span>
          <span className="text-[10px] text-slate-500 ml-2 capitalize">{node.level} · {node.cycle_label}</span>
        </button>
        <span className={`text-xs font-semibold ${st.tone}`}>{node.progress}%</span>
      </div>
      {open && node.children.map((c) => <div key={c.id} className="mt-2"><TreeNode node={c} depth={depth + 1} onOpen={onOpen} /></div>)}
    </div>
  );
};

const ObjectiveModal: React.FC<{ draft: any; meta: OkrMeta; teams: any[]; depts: any[]; onClose: () => void; onSaved: () => void; setErr: (s: string) => void }> = ({ draft, meta, teams, depts, onClose, onSaved, setErr }) => {
  const [f, setF] = useState<any>(draft);
  const [busy, setBusy] = useState(false);
  const set = (patch: any) => setF({ ...f, ...patch });
  const setKr = (i: number, patch: any) => set({ key_results: f.key_results.map((k: any, j: number) => (j === i ? { ...k, ...patch } : k)) });
  const save = async () => {
    if (!f.title?.trim()) { setErr('Title is required'); return; }
    setBusy(true); setErr('');
    const payload = {
      title: f.title, description: f.description || undefined, level: f.level,
      department_id: f.department_id || undefined, team_id: f.team_id || undefined, user_id: f.user_id || undefined,
      cycle_type: f.cycle_type, cycle_year: f.cycle_year ? Number(f.cycle_year) : undefined,
      cycle_quarter: f.cycle_quarter ? Number(f.cycle_quarter) : undefined,
      start_date: f.cycle_type === 'custom' ? f.start_date : undefined,
      end_date: f.cycle_type === 'custom' ? f.end_date : undefined,
      key_results: (f.key_results || []).filter((k: any) => k.title?.trim()).map((k: any) => ({
        title: k.title, kind: k.kind || 'manual', metric: k.kind === 'metric' ? k.metric : undefined,
        unit: k.unit || 'count', start_value: Number(k.start_value) || 0, target_value: Number(k.target_value) || 0,
        current_value: k.current_value === '' || k.current_value == null ? undefined : Number(k.current_value),
        weight: Number(k.weight) || 1,
      })),
    };
    try { await api.create(payload); onSaved(); }
    catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Target className="w-4 h-4 text-brand-400" /> New objective</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-2">
          <input value={f.title || ''} onChange={(e) => set({ title: e.target.value })} placeholder="Objective title" className={F} />
          <input value={f.description || ''} onChange={(e) => set({ description: e.target.value })} placeholder="Description (optional)" className={F} />
          <div className="grid grid-cols-3 gap-2">
            <label className="text-[11px] text-slate-400">Level<select value={f.level} onChange={(e) => set({ level: e.target.value })} className={F}>{meta.levels.map((l) => <option key={l} value={l}>{l}</option>)}</select></label>
            <label className="text-[11px] text-slate-400">Cycle<select value={f.cycle_type} onChange={(e) => set({ cycle_type: e.target.value })} className={F}>{meta.cycle_types.map((c) => <option key={c} value={c}>{c}</option>)}</select></label>
            {f.cycle_type === 'quarterly' ? (
              <label className="text-[11px] text-slate-400">Quarter<select value={f.cycle_quarter || ''} onChange={(e) => set({ cycle_quarter: e.target.value })} className={F}><option value="">Current</option>{[1, 2, 3, 4].map((q) => <option key={q} value={q}>Q{q}</option>)}</select></label>
            ) : (
              <label className="text-[11px] text-slate-400">Year<input type="number" value={f.cycle_year || new Date().getFullYear()} onChange={(e) => set({ cycle_year: e.target.value })} className={F} /></label>
            )}
          </div>
          {f.cycle_type === 'custom' && (
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[11px] text-slate-400">Start<input type="date" value={f.start_date || ''} onChange={(e) => set({ start_date: e.target.value })} className={F} /></label>
              <label className="text-[11px] text-slate-400">End<input type="date" value={f.end_date || ''} onChange={(e) => set({ end_date: e.target.value })} className={F} /></label>
            </div>
          )}
          {f.level === 'department' && (
            <label className="text-[11px] text-slate-400">Department<select value={f.department_id || ''} onChange={(e) => set({ department_id: e.target.value })} className={F}><option value="">Select department…</option>{depts.map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}</select></label>
          )}
          {f.level === 'team' && (
            <label className="text-[11px] text-slate-400">Team<select value={f.team_id || ''} onChange={(e) => set({ team_id: e.target.value })} className={F}><option value="">Select team…</option>{teams.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}</select></label>
          )}

          <div className="pt-1">
            <div className="flex items-center justify-between mb-1">
              <p className="text-[11px] font-semibold text-slate-400 uppercase">Key results</p>
              <button onClick={() => set({ key_results: [...(f.key_results || []), { title: '', kind: 'manual', target_value: '', weight: 1 }] })} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1"><Plus className="w-3 h-3" /> Add KR</button>
            </div>
            {(f.key_results || []).map((k: any, i: number) => (
              <div key={i} className="border border-slate-800/70 rounded-lg p-2 mb-2 space-y-1.5">
                <div className="flex items-center gap-1.5">
                  <input value={k.title} onChange={(e) => setKr(i, { title: e.target.value })} placeholder="Key result" className={F} />
                  <button onClick={() => set({ key_results: f.key_results.filter((_: any, j: number) => j !== i) })} className="text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
                <div className="grid grid-cols-4 gap-1.5">
                  <select value={k.kind} onChange={(e) => setKr(i, { kind: e.target.value })} className={F}>{meta.kr_kinds.map((x) => <option key={x} value={x}>{x}</option>)}</select>
                  {k.kind === 'metric' ? (
                    <select value={k.metric || ''} onChange={(e) => setKr(i, { metric: e.target.value })} className={F}><option value="">metric…</option>{meta.metrics.map((m) => <option key={m} value={m}>{m}</option>)}</select>
                  ) : (
                    <select value={k.unit || 'count'} onChange={(e) => setKr(i, { unit: e.target.value })} className={F}>{meta.units.map((u) => <option key={u} value={u}>{u}</option>)}</select>
                  )}
                  <input type="number" value={k.target_value} onChange={(e) => setKr(i, { target_value: e.target.value })} placeholder="Target" className={F} />
                  <input type="number" value={k.weight} onChange={(e) => setKr(i, { weight: e.target.value })} placeholder="Weight" className={F} />
                </div>
              </div>
            ))}
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 font-medium py-2 rounded-lg text-sm cursor-pointer mt-2">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Create objective</button>
        </div>
      </div>
    </div>
  );
};

const DetailModal: React.FC<{ id: string; onClose: () => void; onChanged: () => void; setErr: (s: string) => void }> = ({ id, onClose, onChanged, setErr }) => {
  const [o, setO] = useState<(Objective & { reviews: OkrReview[] }) | null>(null);
  const [checkin, setCheckin] = useState<{ kr: KeyResult; value: string; comment: string } | null>(null);
  const [review, setReview] = useState({ review_type: 'review', rating: '', comment: '' });
  const [busy, setBusy] = useState(false);
  const reload = useCallback(async () => {
    try { setO(await api.get(id)); } catch (e) { setErr(extractErrorMessage(e, 'Failed to load objective.')); }
  }, [id, setErr]);
  useEffect(() => { reload(); }, [reload]);

  const doCheckin = async () => {
    if (!checkin) return;
    setBusy(true);
    try {
      await api.checkin(checkin.kr.id, { value: Number(checkin.value) || 0, comment: checkin.comment || undefined });
      setCheckin(null); await reload(); onChanged();
    } catch (e) { setErr(extractErrorMessage(e, 'Check-in failed')); } finally { setBusy(false); }
  };
  const doReview = async () => {
    if (!review.comment.trim()) { setErr('A comment is required.'); return; }
    setBusy(true);
    try {
      await api.addReview(id, { review_type: review.review_type, rating: review.rating ? Number(review.rating) : undefined, comment: review.comment });
      setReview({ review_type: 'review', rating: '', comment: '' }); await reload();
    } catch (e) { setErr(extractErrorMessage(e, 'Review failed')); } finally { setBusy(false); }
  };

  const st = o ? (LABEL[o.status_label] || LABEL.on_track) : null;
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        {!o ? <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div> : (
          <>
            <div className="flex items-center justify-between mb-1">
              <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Target className="w-4 h-4 text-brand-400" /> {o.title}</h3>
              <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
            </div>
            <p className="text-[11px] text-slate-500 mb-3 capitalize">{o.level} · {o.cycle_label} · {o.owner_name ? `Owner ${o.owner_name} · ` : ''}<span className={st!.tone}>{st!.label}</span> · {o.progress}%</p>
            <div className="h-2 bg-slate-800/60 rounded mb-4"><div className={`h-2 rounded ${bar(o.progress, o.status_label)}`} style={{ width: `${Math.min(100, o.progress)}%` }} /></div>

            <p className="text-[11px] font-semibold text-slate-400 uppercase mb-1.5">Key results</p>
            {o.key_results.length === 0 && <p className="text-xs text-slate-500 mb-2">No key results.</p>}
            {o.key_results.map((k) => (
              <div key={k.id} className="border border-slate-800/70 rounded-lg p-2.5 mb-2">
                <div className="flex items-center gap-2">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm text-slate-200 truncate">{k.title} {k.kind === 'metric' && <span className="text-[10px] text-brand-300">({k.metric})</span>}</p>
                    <p className="text-[11px] text-slate-500">{fmtVal(k.current_value, k.unit)} / {fmtVal(k.target_value, k.unit)} · weight {k.weight} · {k.progress}%</p>
                  </div>
                  {k.kind === 'manual' && <button onClick={() => setCheckin({ kr: k, value: String(k.current_value), comment: '' })} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1 shrink-0"><Pencil className="w-3 h-3" /> Check in</button>}
                </div>
                <div className="h-1.5 bg-slate-800/60 rounded mt-1.5"><div className={`h-1.5 rounded ${k.progress >= 100 ? 'bg-emerald-500/70' : 'bg-sky-500/70'}`} style={{ width: `${Math.min(100, k.progress)}%` }} /></div>
              </div>
            ))}
            {checkin && (
              <div className="border border-brand-500/30 rounded-lg p-2.5 mb-3 space-y-1.5">
                <p className="text-xs text-slate-300">Check in — {checkin.kr.title}</p>
                <div className="flex items-center gap-1.5">
                  <input type="number" value={checkin.value} onChange={(e) => setCheckin({ ...checkin, value: e.target.value })} placeholder="Current value" className={F} />
                  <input value={checkin.comment} onChange={(e) => setCheckin({ ...checkin, comment: e.target.value })} placeholder="Note (optional)" className={F} />
                  <button onClick={doCheckin} disabled={busy} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer shrink-0">{busy ? '…' : 'Save'}</button>
                  <button onClick={() => setCheckin(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer shrink-0"><X className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            )}

            <p className="text-[11px] font-semibold text-slate-400 uppercase mb-1.5 mt-4 flex items-center gap-1.5"><MessageSquare className="w-3.5 h-3.5" /> Reviews & feedback</p>
            <div className="flex items-center gap-1.5 mb-2">
              <select value={review.review_type} onChange={(e) => setReview({ ...review, review_type: e.target.value })} className={`${F} !w-28`}>
                <option value="review">review</option>
                <option value="feedback">feedback</option>
              </select>
              <select value={review.rating} onChange={(e) => setReview({ ...review, rating: e.target.value })} className={`${F} !w-20`}>
                <option value="">rating…</option>
                {[1, 2, 3, 4, 5].map((r) => <option key={r} value={r}>{r}★</option>)}
              </select>
              <input value={review.comment} onChange={(e) => setReview({ ...review, comment: e.target.value })} placeholder="Write a review or manager feedback…" className={F} />
              <button onClick={doReview} disabled={busy} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer shrink-0">Post</button>
            </div>
            {o.reviews.length === 0 && <p className="text-xs text-slate-500">No reviews yet.</p>}
            {o.reviews.map((r) => (
              <div key={r.id} className="border-b border-slate-800/50 last:border-0 py-1.5">
                <p className="text-[11px] text-slate-500">
                  <span className="text-slate-300">{r.reviewer_name || '—'}</span> · <span className={r.review_type === 'feedback' ? 'text-amber-300' : r.review_type === 'checkin' ? 'text-sky-300' : 'text-brand-300'}>{r.review_type}</span>
                  {r.rating != null && <> · {'★'.repeat(r.rating)}</>}
                  {r.confidence != null && <> · confidence {r.confidence}%</>}
                  {r.progress_at != null && <> · at {r.progress_at}%</>}
                  {r.created_at && <> · {new Date(r.created_at).toLocaleDateString()}</>}
                </p>
                {r.comment && <p className="text-sm text-slate-200 mt-0.5">{r.comment}</p>}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
};
