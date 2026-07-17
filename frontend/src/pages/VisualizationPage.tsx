import React, { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import {
  BarChart3, Loader2, Plus, X, Check, Trash2, Pin, PinOff, Download, Image as ImageIcon,
  LayoutGrid, Wand2, Play, Table2,
} from 'lucide-react';
import { vizApi as api, VizCatalog, SavedViz, DrillResult } from '../services/vizApi';
import { VizRenderer } from '../components/viz/VizRenderer';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';

const downloadText = (name: string, text: string, mime = 'text/csv') => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: mime }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
};

/** Serialize the first SVG inside `el` to a PNG download (chart exports). */
const downloadPng = (el: HTMLElement | null, name: string) => {
  const svg = el?.querySelector('svg');
  if (!svg) return false;
  const xml = new XMLSerializer().serializeToString(svg);
  const img = new Image();
  const { width, height } = svg.getBoundingClientRect();
  img.onload = () => {
    const canvas = document.createElement('canvas');
    canvas.width = width * 2;
    canvas.height = height * 2;
    const ctx = canvas.getContext('2d')!;
    ctx.fillStyle = '#0f172a';
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.scale(2, 2);
    ctx.drawImage(img, 0, 0, width, height);
    const a = document.createElement('a');
    a.href = canvas.toDataURL('image/png');
    a.download = name;
    a.click();
  };
  img.src = `data:image/svg+xml;base64,${btoa(unescape(encodeURIComponent(xml)))}`;
  return true;
};

export const VisualizationPage: React.FC = () => {
  const [tab, setTab] = useState<'gallery' | 'studio'>('gallery');
  const [catalog, setCatalog] = useState<VizCatalog | null>(null);
  const [saved, setSaved] = useState<SavedViz[]>([]);
  const [rendered, setRendered] = useState<Record<string, any>>({});
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [drill, setDrill] = useState<DrillResult | null>(null);
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (!catalog) setCatalog(await api.catalog());
      if (tab === 'gallery') {
        const list = await api.list();
        setSaved(list);
        const out: Record<string, any> = {};
        await Promise.all(list.slice(0, 12).map(async (v) => {
          try { out[v.id] = (await api.data(v.id)).data; } catch { out[v.id] = null; }
        }));
        setRendered(out);
      }
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load visualizations.')); } finally { setLoading(false); }
  }, [tab, catalog]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await load(); } catch (e) { setErr(extractErrorMessage(e, 'Failed')); } };
  const doDrill = async (dataset: string, filters: any, field: string, value: any) => {
    try { setDrill(await api.drilldown({ dataset, field, value, filters })); }
    catch (e) { setErr(extractErrorMessage(e, 'Drill-down failed')); }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><BarChart3 className="w-6 h-6 text-brand-400" /> Data Visualization</h1>
          <p className="text-sm text-slate-500 mt-1">13 chart types over any dataset — interactive, drillable, exportable, pinnable to the dashboard.</p>
        </div>
        <button onClick={() => setTab('studio')} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5 w-fit"><Plus className="w-3.5 h-3.5" /> New visualization</button>
      </div>

      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['gallery', 'Gallery', LayoutGrid], ['studio', 'Studio', Wand2]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading && tab === 'gallery' ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'gallery' ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {saved.length === 0 && <p className="text-sm text-slate-500">No visualizations yet — build one in the Studio.</p>}
          {saved.map((v) => (
            <GalleryCard key={v.id} v={v} data={rendered[v.id]}
                         onDrill={(f, val) => doDrill(v.dataset, v.filters, f, val)}
                         onPin={() => act(() => api.update(v.id, { is_pinned: !v.is_pinned }), v.is_pinned ? 'Unpinned.' : 'Pinned to dashboard.')}
                         onCsv={async () => downloadText(`${v.name}.csv`, await api.exportCsv(v.id))}
                         onDelete={() => window.confirm(`Delete "${v.name}"?`) && act(() => api.remove(v.id), 'Deleted.')} />
          ))}
        </div>
      ) : catalog ? (
        <Studio catalog={catalog} setErr={setErr}
                onSaved={async () => { flash('Saved.'); setTab('gallery'); }}
                onDrill={doDrill} />
      ) : null}

      {drill && <DrillModal drill={drill} onClose={() => setDrill(null)} />}
    </div>
  );
};

const GalleryCard: React.FC<{ v: SavedViz; data: any; onDrill: (f: string, val: any) => void; onPin: () => void; onCsv: () => void; onDelete: () => void }> =
  ({ v, data, onDrill, onPin, onCsv, onDelete }) => {
    const ref = useRef<HTMLDivElement>(null);
    return (
      <div className={card}>
        <div className="flex items-center justify-between mb-2">
          <div className="min-w-0">
            <p className="text-sm font-semibold text-slate-100 truncate">{v.name}</p>
            <p className="text-[10px] text-slate-500 capitalize">{v.viz_type} · {v.dataset}{v.is_pinned ? ' · 📌 pinned' : ''}</p>
          </div>
          <div className="flex items-center gap-1 shrink-0">
            <button title={v.is_pinned ? 'Unpin from dashboard' : 'Pin to dashboard'} onClick={onPin} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer">{v.is_pinned ? <PinOff className="w-4 h-4" /> : <Pin className="w-4 h-4" />}</button>
            <button title="Export CSV" onClick={onCsv} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Download className="w-4 h-4" /></button>
            <button title="Export PNG" onClick={() => downloadPng(ref.current, `${v.name}.png`)} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><ImageIcon className="w-4 h-4" /></button>
            <button title="Delete" onClick={onDelete} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
          </div>
        </div>
        <div ref={ref}>
          {data === undefined ? <div className="py-10 text-center text-slate-500"><Loader2 className="w-4 h-4 animate-spin inline" /></div>
            : <VizRenderer vizType={v.viz_type} data={data} config={v.config} height={240} onDrill={onDrill} />}
        </div>
      </div>
    );
  };

const Studio: React.FC<{ catalog: VizCatalog; setErr: (s: string) => void; onSaved: () => void; onDrill: (dataset: string, filters: any, f: string, val: any) => void }> =
  ({ catalog, setErr, onSaved, onDrill }) => {
    const [f, setF] = useState<any>({ viz_type: 'bar', dataset: 'leads', config: {} });
    const [preview, setPreview] = useState<any>(null);
    const [busy, setBusy] = useState(false);
    const [saveOpen, setSaveOpen] = useState(false);
    const previewRef = useRef<HTMLDivElement>(null);
    const ds = useMemo(() => catalog.datasets.find((d) => d.key === f.dataset), [catalog, f.dataset]);
    const meta = useMemo(() => catalog.viz_types.find((v) => v.key === f.viz_type), [catalog, f.viz_type]);
    const set = (patch: any) => setF({ ...f, ...patch });
    const setC = (patch: any) => setF({ ...f, config: { ...f.config, ...patch } });
    const strCols = ds?.columns.filter((c) => c.type === 'string') || [];
    const numCols = ds?.columns.filter((c) => c.type === 'number') || [];
    const dateCols = ds?.columns.filter((c) => c.type === 'date') || [];

    const run = async () => {
      setBusy(true); setErr('');
      try { setPreview(await api.render({ viz_type: f.viz_type, dataset: f.dataset, config: f.config })); }
      catch (e) { setPreview(null); setErr(extractErrorMessage(e, 'Render failed')); } finally { setBusy(false); }
    };

    const needs = meta?.needs || [];
    const show = (k: string) => needs.includes(k) || (meta?.optional || []).includes(k);
    return (
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
        <div className={`${card} space-y-2 h-fit`}>
          <label className="text-[11px] text-slate-400 block">Visualization type
            <select value={f.viz_type} onChange={(e) => { set({ viz_type: e.target.value, config: {} }); setPreview(null); }} className={F}>
              {catalog.viz_types.map((v) => <option key={v.key} value={v.key}>{v.label}</option>)}
            </select>
          </label>
          <label className="text-[11px] text-slate-400 block">Dataset
            <select value={f.dataset} onChange={(e) => { set({ dataset: e.target.value, config: {} }); setPreview(null); }} className={F}>
              {catalog.datasets.map((d) => <option key={d.key} value={d.key}>{d.label}</option>)}
            </select>
          </label>

          {(show('dimension')) && (
            <label className="text-[11px] text-slate-400 block">Dimension
              <select value={f.config.dimension || ''} onChange={(e) => setC({ dimension: e.target.value })} className={F}>
                <option value="">Select…</option>
                {ds?.columns.map((c) => <option key={c.field} value={c.field}>{c.field}</option>)}
              </select>
            </label>
          )}
          {(show('row')) && (
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[11px] text-slate-400">Row<select value={f.config.row || ''} onChange={(e) => setC({ row: e.target.value })} className={F}><option value="">Select…</option>{strCols.map((c) => <option key={c.field} value={c.field}>{c.field}</option>)}</select></label>
              <label className="text-[11px] text-slate-400">Column<select value={f.config.col || ''} onChange={(e) => setC({ col: e.target.value })} className={F}><option value="">Select…</option>{strCols.map((c) => <option key={c.field} value={c.field}>{c.field}</option>)}</select></label>
            </div>
          )}
          {(show('date_field')) && (
            <label className="text-[11px] text-slate-400 block">Date field
              <select value={f.config.date_field || ''} onChange={(e) => setC({ date_field: e.target.value })} className={F}>
                <option value="">Select…</option>
                {dateCols.map((c) => <option key={c.field} value={c.field}>{c.field}</option>)}
              </select>
            </label>
          )}
          {(show('interval')) && (
            <label className="text-[11px] text-slate-400 block">Interval
              <select value={f.config.interval || 'month'} onChange={(e) => setC({ interval: e.target.value })} className={F}>
                {catalog.intervals.map((i) => <option key={i} value={i}>{i}</option>)}
              </select>
            </label>
          )}
          {(show('window_days')) && (
            <label className="text-[11px] text-slate-400 block">Window (days)<input type="number" value={f.config.window_days || 30} onChange={(e) => setC({ window_days: Number(e.target.value) || 30 })} className={F} /></label>
          )}
          {(show('target')) && (
            <label className="text-[11px] text-slate-400 block">Target<input type="number" value={f.config.target ?? ''} onChange={(e) => setC({ target: Number(e.target.value) || 0 })} className={F} /></label>
          )}
          {(show('field')) && (
            <label className="text-[11px] text-slate-400 block">Location field
              <select value={f.config.field || ''} onChange={(e) => setC({ field: e.target.value })} className={F}>
                <option value="">Select…</option>
                {strCols.map((c) => <option key={c.field} value={c.field}>{c.field}</option>)}
              </select>
            </label>
          )}
          {(show('stages')) && (
            <label className="text-[11px] text-slate-400 block">Stages (ordered, comma-separated — optional)
              <input value={(f.config.stages || []).join(', ')} onChange={(e) => setC({ stages: e.target.value ? e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean) : undefined })} placeholder="New, Contacted, Converted" className={F} />
            </label>
          )}
          {(show('measure')) && (
            <div className="grid grid-cols-2 gap-2">
              <label className="text-[11px] text-slate-400">Measure<select value={f.config.measure?.field || ''} onChange={(e) => setC({ measure: { ...f.config.measure, field: e.target.value || undefined, agg: e.target.value ? (f.config.measure?.agg || 'sum') : 'count' } })} className={F}><option value="">count</option>{numCols.map((c) => <option key={c.field} value={c.field}>{c.field}</option>)}</select></label>
              <label className="text-[11px] text-slate-400">Aggregation<select value={f.config.measure?.agg || 'count'} onChange={(e) => setC({ measure: { ...f.config.measure, agg: e.target.value } })} className={F}>{catalog.aggregations.map((a) => <option key={a} value={a}>{a}</option>)}</select></label>
            </div>
          )}
          {(show('columns')) && (
            <label className="text-[11px] text-slate-400 block flex items-center gap-1"><Table2 className="w-3 h-3" /> Columns (comma-separated — optional)
              <input value={(f.config.columns || []).join(', ')} onChange={(e) => setC({ columns: e.target.value ? e.target.value.split(',').map((s: string) => s.trim()).filter(Boolean) : undefined })} placeholder="status, value, city" className={F} />
            </label>
          )}

          <div className="flex items-center gap-2 pt-1">
            <button onClick={run} disabled={busy} className="flex-1 inline-flex items-center justify-center gap-1.5 bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 font-medium py-2 rounded-lg text-xs cursor-pointer">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />} Preview</button>
            <button onClick={() => preview && setSaveOpen(true)} disabled={!preview} className="flex-1 inline-flex items-center justify-center gap-1.5 bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 font-medium py-2 rounded-lg text-xs cursor-pointer disabled:opacity-40"><Check className="w-3.5 h-3.5" /> Save…</button>
          </div>
        </div>

        <div className={`${card} lg:col-span-2`}>
          <div className="flex items-center justify-between mb-2">
            <p className="text-xs font-semibold text-slate-400 uppercase">Preview</p>
            {preview && <button onClick={() => downloadPng(previewRef.current, 'visualization.png')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1"><ImageIcon className="w-3.5 h-3.5" /> PNG</button>}
          </div>
          <div ref={previewRef}>
            {!preview ? <p className="text-sm text-slate-500 py-16 text-center">Configure and hit Preview.</p>
              : <VizRenderer vizType={preview.viz_type} data={preview.data} config={preview.config} height={340}
                             onDrill={(field, value) => onDrill(f.dataset, undefined, field, value)} />}
          </div>
        </div>

        {saveOpen && (
          <SaveModal onClose={() => setSaveOpen(false)} setErr={setErr} onSaved={onSaved} spec={f} />
        )}
      </div>
    );
  };

const SaveModal: React.FC<{ spec: any; onClose: () => void; onSaved: () => void; setErr: (s: string) => void }> = ({ spec, onClose, onSaved, setErr }) => {
  const [name, setName] = useState('');
  const [pinned, setPinned] = useState(false);
  const [busy, setBusy] = useState(false);
  const save = async () => {
    if (!name.trim()) { setErr('Name is required'); return; }
    setBusy(true);
    try {
      await api.create({ name, viz_type: spec.viz_type, dataset: spec.dataset, config: spec.config, is_pinned: pinned });
      onSaved();
    } catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-sm p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3">
          <h3 className="text-sm font-bold text-slate-100">Save visualization</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-2">
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Name" className={F} />
          <label className="flex items-center gap-1.5 text-xs text-slate-300"><input type="checkbox" checked={pinned} onChange={(e) => setPinned(e.target.checked)} /> <Pin className="w-3 h-3" /> Pin to Home dashboard</label>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 font-medium py-2 rounded-lg text-sm cursor-pointer">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save</button>
        </div>
      </div>
    </div>
  );
};

const DrillModal: React.FC<{ drill: DrillResult; onClose: () => void }> = ({ drill, onClose }) => (
  <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
    <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-3xl max-h-[85vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-bold text-slate-100">Drill-down — {drill.field} = {String(drill.value)} <span className="text-[11px] font-normal text-slate-500">({drill.total} rows)</span></h3>
        <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
      </div>
      <VizRenderer vizType="table" data={drill} />
    </div>
  </div>
);
