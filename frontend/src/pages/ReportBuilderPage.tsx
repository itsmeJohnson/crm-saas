import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Table2, Plus, Loader2, X, Check, Trash2, Pencil, Copy, Download, Play, GripVertical,
  BarChart3, LayoutTemplate, Share2, Pin, Clock, History as HistoryIcon, ArrowLeft, Filter as FilterIcon,
  Sigma, Layers, ArrowUpDown, RotateCcw,
} from 'lucide-react';
import {
  reportBuilderApi as api, RBCatalog, ReportDef, RunResult, RBColumn, ReportVersion,
} from '../services/reportBuilderApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const OPS_NO_VALUE = ['is_empty', 'is_not_empty', 'is_true', 'is_false'];

const emptyDraft = (dataset: string): any => ({
  name: '', description: '', dataset, columns: [], filters_logic: 'and', filters_rows: [],
  group_by: [], sort: [], calculated_fields: [], pivot: null, chart: null,
  visibility: 'private', pinned_to_dashboard: false,
});

const toFilters = (draft: any) => draft.filters_rows.length
  ? { type: 'group', logic: draft.filters_logic, children: draft.filters_rows.map((r: any) => ({ type: 'condition', field: r.field, op: r.op, value: r.value })) }
  : null;

const fromReport = (r: ReportDef): any => ({
  ...r,
  filters_logic: r.filters?.logic || 'and',
  filters_rows: (r.filters?.children || []).map((c: any) => ({ field: c.field, op: c.op, value: c.value ?? '' })),
  group_by: r.group_by || [], sort: r.sort || [], calculated_fields: r.calculated_fields || [],
});

export const ReportBuilderPage: React.FC = () => {
  const [catalog, setCatalog] = useState<RBCatalog | null>(null);
  const [tab, setTab] = useState<'mine' | 'shared' | 'templates'>('mine');
  const [reports, setReports] = useState<ReportDef[]>([]);
  const [templates, setTemplates] = useState<ReportDef[]>([]);
  const [mode, setMode] = useState<'list' | 'build'>('list');
  const [draft, setDraft] = useState<any>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [preview, setPreview] = useState<RunResult | null>(null);
  const [versions, setVersions] = useState<ReportVersion[] | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [cat, rs, tpls] = await Promise.all([api.catalog(), api.list({ box: tab === 'templates' ? 'mine' : tab }), api.listTemplates()]);
      setCatalog(cat); setReports(rs); setTemplates(tpls);
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load.')); } finally { setLoading(false); }
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  const ds = useMemo(() => catalog?.datasets.find((x) => x.key === draft?.dataset), [catalog, draft?.dataset]);
  const allOps = catalog ? [...catalog.operators.comparison, ...catalog.operators.date, ...catalog.operators.boolean] : [];
  const fieldOptions = useMemo(() => {
    const base = (ds?.columns || []).map((c) => c.field);
    const calc = (draft?.calculated_fields || []).map((c: any) => c.name).filter(Boolean);
    return [...base, ...calc];
  }, [ds, draft?.calculated_fields]);

  const startNew = () => { const d0 = emptyDraft(catalog?.datasets[0]?.key || 'leads'); setDraft(d0); setEditingId(null); setPreview(null); setVersions(null); setMode('build'); };
  const edit = (r: ReportDef) => { setDraft(fromReport(r)); setEditingId(r.id); setPreview(null); setVersions(null); setMode('build'); };

  const payload = () => ({
    name: draft.name, description: draft.description || undefined, dataset: draft.dataset,
    columns: draft.columns, filters: toFilters(draft),
    group_by: draft.group_by.length ? draft.group_by : null,
    sort: draft.sort.length ? draft.sort : null,
    calculated_fields: draft.calculated_fields.length ? draft.calculated_fields : null,
    pivot: draft.pivot, chart: draft.chart, visibility: draft.visibility, pinned_to_dashboard: draft.pinned_to_dashboard,
  });

  const runPreview = async () => {
    setBusy(true); setErr('');
    try { setPreview(await api.preview({ ...payload(), limit: 100, offset: 0 })); }
    catch (e) { setErr(extractErrorMessage(e, 'Preview failed')); } finally { setBusy(false); }
  };
  const save = async () => {
    if (!draft.name.trim()) { setErr('Name is required'); return; }
    if (!draft.columns.length) { setErr('Pick at least one column'); return; }
    setBusy(true); setErr('');
    try {
      const r = editingId ? await api.update(editingId, payload()) : await api.create(payload());
      setEditingId(r.id); flash('Saved.'); await load();
    } catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
  };
  const exportCsv = async (id: string) => {
    const blob = await api.exportCsv(id); const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'report.csv'; a.click(); URL.revokeObjectURL(url);
  };
  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await load(); } catch (e) { setErr(extractErrorMessage(e, 'Failed')); } };

  /* ---------- column drag & drop ---------- */
  const [dragIdx, setDragIdx] = useState<number | null>(null);
  const onDrop = (i: number) => {
    if (dragIdx === null || dragIdx === i) return;
    const cols = [...draft.columns]; const [m] = cols.splice(dragIdx, 1); cols.splice(i, 0, m);
    setDraft({ ...draft, columns: cols }); setDragIdx(null);
  };
  const addColumn = (field: string) => { if (!draft.columns.some((c: RBColumn) => c.field === field)) setDraft({ ...draft, columns: [...draft.columns, { field }] }); };
  const setCol = (i: number, patch: Partial<RBColumn>) => setDraft({ ...draft, columns: draft.columns.map((c: RBColumn, j: number) => j === i ? { ...c, ...patch } : c) });

  if (loading) return <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>;

  /* ================= BUILD MODE ================= */
  if (mode === 'build' && draft && catalog) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between gap-3 flex-wrap">
          <button onClick={() => { setMode('list'); setDraft(null); }} className="text-xs text-slate-400 hover:text-slate-200 cursor-pointer flex items-center gap-1"><ArrowLeft className="w-4 h-4" /> Reports</button>
          <div className="flex items-center gap-2 flex-wrap">
            <button onClick={() => setDraft({ ...draft, visibility: draft.visibility === 'private' ? 'organization' : 'private' })} className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold cursor-pointer flex items-center gap-1.5 ${draft.visibility === 'organization' ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800/70 text-slate-300'}`}><Share2 className="w-3.5 h-3.5" /> {draft.visibility === 'organization' ? 'Shared' : 'Private'}</button>
            <button onClick={() => setDraft({ ...draft, pinned_to_dashboard: !draft.pinned_to_dashboard })} className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold cursor-pointer flex items-center gap-1.5 ${draft.pinned_to_dashboard ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-800/70 text-slate-300'}`}><Pin className="w-3.5 h-3.5" /> {draft.pinned_to_dashboard ? 'Pinned' : 'Pin'}</button>
            {editingId && <button onClick={() => api.versions(editingId).then(setVersions)} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 text-slate-300 cursor-pointer flex items-center gap-1.5"><HistoryIcon className="w-3.5 h-3.5" /> Versions</button>}
            {editingId && <button onClick={() => exportCsv(editingId)} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 text-slate-300 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Export</button>}
            <button onClick={runPreview} disabled={busy} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Play className="w-3.5 h-3.5" /> Preview</button>
            <button onClick={save} disabled={busy} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} Save</button>
          </div>
        </div>
        {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
        {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

        <div className="grid grid-cols-2 gap-2">
          <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })} placeholder="Report name" className={`${F} text-sm`} />
          <select value={draft.dataset} onChange={(e) => setDraft({ ...emptyDraft(e.target.value), name: draft.name, description: draft.description })} className={F}>
            {catalog.datasets.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
          </select>
        </div>

        <div className="grid lg:grid-cols-2 gap-3">
          {/* Columns (drag & drop) */}
          <div className={card}>
            <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><Table2 className="w-3.5 h-3.5 text-brand-400" /> Columns <span className="text-slate-600">· drag to reorder</span></p>
            <div className="space-y-1.5 mb-2">
              {draft.columns.map((c: RBColumn, i: number) => (
                <div key={c.field} draggable onDragStart={() => setDragIdx(i)} onDragOver={(e) => e.preventDefault()} onDrop={() => onDrop(i)}
                  className="flex items-center gap-2 p-1.5 rounded-lg bg-slate-950/50 border border-slate-800/70">
                  <GripVertical className="w-3.5 h-3.5 text-slate-600 cursor-grab" />
                  <span className="text-xs text-slate-300 flex-1 truncate">{c.field}</span>
                  <select value={c.agg || ''} onChange={(e) => setCol(i, { agg: e.target.value || null })} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 text-[11px] rounded px-1 py-0.5">
                    <option value="">raw</option>
                    {catalog.aggregations.map((a) => <option key={a} value={a}>{a}</option>)}
                  </select>
                  <button onClick={() => setDraft({ ...draft, columns: draft.columns.filter((_: any, j: number) => j !== i) })} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
                </div>
              ))}
              {!draft.columns.length && <p className="text-[11px] text-slate-600 italic">No columns yet.</p>}
            </div>
            <select value="" onChange={(e) => e.target.value && addColumn(e.target.value)} className={`${F} w-full`}>
              <option value="">+ add column…</option>
              {(ds?.columns || []).map((c) => <option key={c.field} value={c.field}>{c.field}</option>)}
            </select>
          </div>

          {/* Filters */}
          <div className={card}>
            <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><FilterIcon className="w-3.5 h-3.5 text-brand-400" /> Filters
              <select value={draft.filters_logic} onChange={(e) => setDraft({ ...draft, filters_logic: e.target.value })} className="ml-1 bg-slate-800/70 border border-slate-700/70 text-slate-300 text-[11px] rounded px-1 py-0.5"><option value="and">AND</option><option value="or">OR</option></select>
            </p>
            <div className="space-y-1.5 mb-2">
              {draft.filters_rows.map((r: any, i: number) => (
                <div key={i} className="flex items-center gap-1.5">
                  <select value={r.field} onChange={(e) => setDraft({ ...draft, filters_rows: draft.filters_rows.map((x: any, j: number) => j === i ? { ...x, field: e.target.value } : x) })} className={`${F} flex-1`}>
                    <option value="">field…</option>{fieldOptions.map((f) => <option key={f} value={f}>{f}</option>)}
                  </select>
                  <select value={r.op} onChange={(e) => setDraft({ ...draft, filters_rows: draft.filters_rows.map((x: any, j: number) => j === i ? { ...x, op: e.target.value } : x) })} className={F}>
                    {allOps.map((o) => <option key={o} value={o}>{o.replace(/_/g, ' ')}</option>)}
                  </select>
                  {!OPS_NO_VALUE.includes(r.op) && <input value={r.value} onChange={(e) => setDraft({ ...draft, filters_rows: draft.filters_rows.map((x: any, j: number) => j === i ? { ...x, value: e.target.value } : x) })} placeholder="value" className={`${F} w-24`} />}
                  <button onClick={() => setDraft({ ...draft, filters_rows: draft.filters_rows.filter((_: any, j: number) => j !== i) })} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
            <button onClick={() => setDraft({ ...draft, filters_rows: [...draft.filters_rows, { field: fieldOptions[0] || '', op: 'eq', value: '' }] })} className="text-[11px] text-brand-400 cursor-pointer flex items-center gap-1"><Plus className="w-3 h-3" /> condition</button>
          </div>

          {/* Group by + Sort */}
          <div className={card}>
            <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><Layers className="w-3.5 h-3.5 text-brand-400" /> Group by</p>
            <div className="flex flex-wrap gap-1.5 mb-2">
              {draft.group_by.map((g: string) => <span key={g} className="text-[11px] bg-brand-500/10 text-brand-300 border border-brand-500/20 rounded px-1.5 py-0.5 flex items-center gap-1">{g}<button onClick={() => setDraft({ ...draft, group_by: draft.group_by.filter((x: string) => x !== g) })}><X className="w-3 h-3" /></button></span>)}
            </div>
            <select value="" onChange={(e) => e.target.value && !draft.group_by.includes(e.target.value) && setDraft({ ...draft, group_by: [...draft.group_by, e.target.value] })} className={`${F} w-full mb-3`}>
              <option value="">+ group field…</option>{fieldOptions.map((f) => <option key={f} value={f}>{f}</option>)}
            </select>
            <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><ArrowUpDown className="w-3.5 h-3.5 text-brand-400" /> Sort</p>
            {draft.sort.map((s: any, i: number) => (
              <div key={i} className="flex items-center gap-1.5 mb-1">
                <select value={s.field} onChange={(e) => setDraft({ ...draft, sort: draft.sort.map((x: any, j: number) => j === i ? { ...x, field: e.target.value } : x) })} className={`${F} flex-1`}>{fieldOptions.map((f) => <option key={f} value={f}>{f}</option>)}</select>
                <select value={s.dir} onChange={(e) => setDraft({ ...draft, sort: draft.sort.map((x: any, j: number) => j === i ? { ...x, dir: e.target.value } : x) })} className={F}><option value="asc">asc</option><option value="desc">desc</option></select>
                <button onClick={() => setDraft({ ...draft, sort: draft.sort.filter((_: any, j: number) => j !== i) })} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
              </div>
            ))}
            <button onClick={() => setDraft({ ...draft, sort: [...draft.sort, { field: fieldOptions[0] || '', dir: 'asc' }] })} className="text-[11px] text-brand-400 cursor-pointer flex items-center gap-1"><Plus className="w-3 h-3" /> sort key</button>
          </div>

          {/* Calculated fields + Pivot + Chart */}
          <div className={card}>
            <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><Sigma className="w-3.5 h-3.5 text-brand-400" /> Calculated fields</p>
            {draft.calculated_fields.map((c: any, i: number) => (
              <div key={i} className="flex items-center gap-1.5 mb-1">
                <input value={c.name} onChange={(e) => setDraft({ ...draft, calculated_fields: draft.calculated_fields.map((x: any, j: number) => j === i ? { ...x, name: e.target.value } : x) })} placeholder="name" className={`${F} w-24`} />
                <input value={c.expression} onChange={(e) => setDraft({ ...draft, calculated_fields: draft.calculated_fields.map((x: any, j: number) => j === i ? { ...x, expression: e.target.value } : x) })} placeholder="e.g. total_amount - amount_paid" className={`${F} flex-1 font-mono`} />
                <button onClick={() => setDraft({ ...draft, calculated_fields: draft.calculated_fields.filter((_: any, j: number) => j !== i) })} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
              </div>
            ))}
            <button onClick={() => setDraft({ ...draft, calculated_fields: [...draft.calculated_fields, { name: '', expression: '', type: 'number' }] })} className="text-[11px] text-brand-400 cursor-pointer flex items-center gap-1 mb-3"><Plus className="w-3 h-3" /> calculated field</button>

            <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><Table2 className="w-3.5 h-3.5 text-brand-400" /> Pivot</p>
            <div className="grid grid-cols-2 gap-1.5 mb-3">
              {(['row', 'col', 'measure'] as const).map((k) => (
                <select key={k} value={draft.pivot?.[k] || ''} onChange={(e) => setDraft({ ...draft, pivot: { ...(draft.pivot || { agg: 'count' }), [k]: e.target.value || undefined } })} className={F}>
                  <option value="">{k}…</option>{fieldOptions.map((f) => <option key={f} value={f}>{f}</option>)}
                </select>
              ))}
              <select value={draft.pivot?.agg || 'count'} onChange={(e) => setDraft({ ...draft, pivot: { ...(draft.pivot || {}), agg: e.target.value } })} className={F}>{catalog.aggregations.map((a) => <option key={a} value={a}>{a}</option>)}</select>
            </div>
            {draft.pivot && <button onClick={() => setDraft({ ...draft, pivot: null })} className="text-[11px] text-slate-500 cursor-pointer mb-3">clear pivot</button>}

            <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><BarChart3 className="w-3.5 h-3.5 text-brand-400" /> Chart</p>
            <div className="grid grid-cols-3 gap-1.5">
              <select value={draft.chart?.type || ''} onChange={(e) => setDraft({ ...draft, chart: e.target.value ? { ...(draft.chart || {}), type: e.target.value } : null })} className={F}><option value="">none</option>{catalog.chart_types.map((t) => <option key={t} value={t}>{t}</option>)}</select>
              <select value={draft.chart?.x || ''} onChange={(e) => setDraft({ ...draft, chart: { ...(draft.chart || {}), x: e.target.value } })} className={F}><option value="">x…</option>{fieldOptions.map((f) => <option key={f} value={f}>{f}</option>)}</select>
              <select value={draft.chart?.y || ''} onChange={(e) => setDraft({ ...draft, chart: { ...(draft.chart || {}), y: e.target.value } })} className={F}><option value="">y…</option>{fieldOptions.map((f) => <option key={f} value={f}>{f}</option>)}</select>
            </div>
          </div>
        </div>

        {/* Preview */}
        {preview && <PreviewPanel result={preview} />}

        {/* Versions panel */}
        {versions && editingId && (
          <div className={card}>
            <div className="flex items-center justify-between mb-2"><p className="text-xs font-semibold text-slate-300 flex items-center gap-1.5"><HistoryIcon className="w-3.5 h-3.5 text-brand-400" /> Versions</p><button onClick={() => setVersions(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button></div>
            <div className="space-y-1">
              {versions.map((v) => (
                <div key={v.id} className="flex items-center justify-between text-xs px-2 py-1.5 rounded bg-slate-950/40 border border-slate-800/60">
                  <span className="text-slate-400">v{v.version_no} · {v.snapshot?.name} {v.note ? `· ${v.note}` : ''}</span>
                  <button onClick={() => act(async () => { const r = await api.restore(editingId, v.version_no); setDraft(fromReport(r)); }, 'Restored.')} className="text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1"><RotateCcw className="w-3 h-3" /> restore</button>
                </div>
              ))}
              {!versions.length && <p className="text-[11px] text-slate-600">No versions.</p>}
            </div>
          </div>
        )}
      </div>
    );
  }

  /* ================= LIST MODE ================= */
  const rows = tab === 'templates' ? templates : reports;
  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Table2 className="w-6 h-6 text-brand-400" /> Report Builder</h1>
          <p className="text-sm text-slate-500 mt-1">Build custom reports over your data — columns, filters, grouping, pivots and charts.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => act(() => api.seedTemplates(), 'Templates seeded.')} className="px-3 py-2 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><LayoutTemplate className="w-3.5 h-3.5" /> Seed templates</button>
          <button onClick={startNew} className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New report</button>
        </div>
      </div>
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['mine', 'My Reports'], ['shared', 'Shared'], ['templates', 'Templates']] as [any, string][]).map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}>{l}</button>
        ))}
      </div>

      <div className="space-y-2">
        {rows.length === 0 && <p className="text-sm text-slate-500">No reports here yet.</p>}
        {rows.map((r) => (
          <div key={r.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-100 truncate">{r.name}</span>
                <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-700/40 text-slate-400 border border-slate-600/40">{r.dataset}</span>
                {r.visibility === 'organization' && <span className="px-1.5 py-0.5 text-[10px] rounded bg-emerald-500/10 text-emerald-400 flex items-center gap-1"><Share2 className="w-2.5 h-2.5" /> shared</span>}
                {r.pinned_to_dashboard && <span className="px-1.5 py-0.5 text-[10px] rounded bg-brand-500/10 text-brand-300 flex items-center gap-1"><Pin className="w-2.5 h-2.5" /> pinned</span>}
                {r.schedule_frequency && <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-700/40 text-slate-400 flex items-center gap-1"><Clock className="w-2.5 h-2.5" /> {r.schedule_frequency}</span>}
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">{r.columns.length} column(s){r.group_by?.length ? ` · grouped` : ''}{r.pivot ? ' · pivot' : ''}{r.chart?.type ? ` · ${r.chart.type}` : ''} · v{r.version}</p>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              {tab === 'templates'
                ? <button onClick={() => act(() => api.instantiate(r.id), 'Report created.')} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 cursor-pointer">Use</button>
                : <>
                  <button title="Edit" onClick={() => edit(r)} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                  <button title="Export" onClick={() => exportCsv(r.id)} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Download className="w-4 h-4" /></button>
                  <button title="Clone" onClick={() => act(() => api.clone(r.id), 'Cloned.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Copy className="w-4 h-4" /></button>
                  <button title="Delete" onClick={() => window.confirm(`Delete "${r.name}"?`) && act(() => api.remove(r.id), 'Deleted.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                </>}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

/* preview table + optional bar chart + pivot table */
const PreviewPanel: React.FC<{ result: RunResult }> = ({ result }) => {
  const chart = result.chart;
  const bar = chart?.type === 'bar' && chart.x && chart.y;
  const yKey = bar ? (result.columns.find((c) => c.key.endsWith(`__${chart.y}`) || c.key === chart.y)?.key) : null;
  const max = bar && yKey ? Math.max(1, ...result.rows.map((r) => Number(r[yKey!]) || 0)) : 1;
  return (
    <div className={card}>
      <div className="flex items-center justify-between mb-2">
        <p className="text-xs font-semibold text-slate-300">Preview <span className="text-slate-600">· {result.total} row(s){result.scanned ? ` · scanned ${result.scanned}` : ''}</span></p>
      </div>
      {bar && yKey && (
        <div className="space-y-1.5 mb-4">
          {result.rows.slice(0, 15).map((r, i) => (
            <div key={i} className="flex items-center gap-2">
              <span className="text-[11px] text-slate-400 w-28 truncate">{String(r[chart!.x!])}</span>
              <div className="flex-1 h-2.5 bg-slate-800/60 rounded"><div className="h-2.5 rounded bg-brand-500/70" style={{ width: `${((Number(r[yKey]) || 0) / max) * 100}%` }} /></div>
              <span className="text-[11px] text-slate-300 w-14 text-right">{r[yKey]}</span>
            </div>
          ))}
        </div>
      )}
      {result.pivot ? (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-500"><tr><th className="text-left py-1 pr-2">{result.pivot.row_field}</th>{result.pivot.columns.map((c: string) => <th key={c} className="text-right px-2">{c}</th>)}</tr></thead>
            <tbody>{result.pivot.rows.map((row: any, i: number) => <tr key={i} className="border-t border-slate-800/60 text-slate-300"><td className="py-1 pr-2">{String(row.__row)}</td>{result.pivot.columns.map((c: string) => <td key={c} className="text-right px-2">{row[c]}</td>)}</tr>)}</tbody>
          </table>
        </div>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead className="text-slate-500"><tr>{result.columns.map((c) => <th key={c.key} className="text-left py-1 pr-3 whitespace-nowrap">{c.label}</th>)}</tr></thead>
            <tbody>
              {result.rows.slice(0, 50).map((row, i) => <tr key={i} className="border-t border-slate-800/60 text-slate-300">{result.columns.map((c) => <td key={c.key} className="py-1 pr-3 whitespace-nowrap">{row[c.key] == null ? '—' : String(row[c.key])}</td>)}</tr>)}
              {!result.rows.length && <tr><td colSpan={result.columns.length} className="py-6 text-center text-slate-500">No rows match.</td></tr>}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};
