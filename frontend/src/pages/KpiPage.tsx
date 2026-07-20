import React, { useCallback, useEffect, useMemo, useState } from 'react';
import {
  Gauge, Loader2, Plus, RefreshCw, X, Check, Pencil, Trash2, Bell, AlertTriangle, CheckCircle2, ListChecks,
} from 'lucide-react';
import { kpiApi as api, KpiCatalog, KpiDashboard, KpiEval, Kpi, KpiAlert } from '../services/kpiApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';

const STATUS: Record<string, { tone: string; ring: string; label: string }> = {
  on_track: { tone: 'text-emerald-400', ring: 'border-emerald-500/40', label: 'On track' },
  warning: { tone: 'text-amber-400', ring: 'border-amber-500/40', label: 'Warning' },
  critical: { tone: 'text-red-400', ring: 'border-red-500/40', label: 'Critical' },
  unknown: { tone: 'text-slate-500', ring: 'border-slate-700/60', label: 'No data' },
};
const fmtVal = (v: number | null, unit: string) => {
  if (v == null) return '—';
  if (unit === 'currency') return `₹${Math.round(v).toLocaleString()}`;
  if (unit === 'percent') return `${v}%`;
  if (unit === 'seconds') return `${v}s`;
  return v.toLocaleString();
};

export const KpiPage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'manage' | 'alerts'>('dashboard');
  const [catalog, setCatalog] = useState<KpiCatalog | null>(null);
  const [dash, setDash] = useState<KpiDashboard | null>(null);
  const [kpis, setKpis] = useState<Kpi[]>([]);
  const [alerts, setAlerts] = useState<KpiAlert[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [edit, setEdit] = useState<any | null>(null);
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (!catalog) setCatalog(await api.catalog());
      if (tab === 'dashboard') setDash(await api.dashboard());
      else if (tab === 'manage') setKpis(await api.list());
      else if (tab === 'alerts') setAlerts(await api.alerts({ limit: 100 }));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load KPIs.')); } finally { setLoading(false); }
  }, [tab, catalog]);
  useEffect(() => { load(); }, [load]);

  const runEval = async () => {
    setBusy(true);
    try { const r = await api.evaluateAll(); flash(`Evaluated ${r.evaluated} · ${r.raised} raised · ${r.resolved} resolved`); await load(); }
    catch (e) { setErr(extractErrorMessage(e, 'Evaluation failed')); } finally { setBusy(false); }
  };
  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await load(); } catch (e) { setErr(extractErrorMessage(e, 'Failed')); } };

  const S = dash?.summary;
  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Gauge className="w-6 h-6 text-brand-400" /> KPI Engine</h1>
          <p className="text-sm text-slate-500 mt-1">Track custom KPIs across every domain with thresholds, alerts and notifications.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={runEval} disabled={busy} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><RefreshCw className={`w-3.5 h-3.5 ${busy ? 'animate-spin' : ''}`} /> Evaluate</button>
          <button onClick={() => setEdit({ metric: 'manual', comparison: 'higher_better', unit: 'count', target_value: 0, window_days: 30, is_active: true, notify: true })} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New KPI</button>
        </div>
      </div>

      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', Gauge], ['manage', 'Manage', ListChecks], ['alerts', 'Alerts', Bell]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}{k === 'alerts' && dash?.open_alerts ? ` (${dash.open_alerts})` : ''}</button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          {S && (
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Total KPIs</p><p className="text-xl font-bold text-slate-100 mt-1">{S.total}</p></div>
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">On track</p><p className="text-xl font-bold text-emerald-400 mt-1">{S.on_track}</p></div>
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Warning</p><p className="text-xl font-bold text-amber-400 mt-1">{S.warning}</p></div>
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Critical</p><p className="text-xl font-bold text-red-400 mt-1">{S.critical}</p></div>
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Open alerts</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.open_alerts}</p></div>
            </div>
          )}
          {Object.keys(dash.by_category).length === 0 ? <p className="text-sm text-slate-500">No KPIs yet — create one to start tracking.</p> : (
            Object.entries(dash.by_category).map(([cat, items]) => (
              <div key={cat}>
                <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2 capitalize">{cat}</p>
                <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3">
                  {items.map((k: KpiEval) => {
                    const st = STATUS[k.status] || STATUS.unknown;
                    return (
                      <div key={k.id} className={`glass-panel border ${st.ring} rounded-xl p-4`}>
                        <div className="flex items-center justify-between">
                          <span className="text-sm font-semibold text-slate-200 truncate">{k.name}</span>
                          <span className={`text-[10px] font-semibold ${st.tone}`}>{st.label}</span>
                        </div>
                        <div className="flex items-end justify-between mt-2">
                          <p className={`text-2xl font-bold ${st.tone}`}>{fmtVal(k.value, k.unit)}</p>
                          <p className="text-[11px] text-slate-500">target {fmtVal(k.target_value, k.unit)}{k.attainment != null ? ` · ${k.attainment}%` : ''}</p>
                        </div>
                        {k.attainment != null && (
                          <div className="h-1.5 bg-slate-800/60 rounded mt-2"><div className={`h-1.5 rounded ${k.status === 'critical' ? 'bg-red-500/70' : k.status === 'warning' ? 'bg-amber-500/70' : 'bg-emerald-500/70'}`} style={{ width: `${Math.min(100, k.attainment)}%` }} /></div>
                        )}
                      </div>
                    );
                  })}
                </div>
              </div>
            ))
          )}
        </div>
      ) : tab === 'manage' ? (
        <div className="space-y-2">
          {kpis.length === 0 && <p className="text-sm text-slate-500">No KPIs defined.</p>}
          {kpis.map((k) => (
            <div key={k.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-100 truncate">{k.name}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-700/40 text-slate-400 border border-slate-600/40 capitalize">{k.category}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded bg-brand-500/10 text-brand-300">{k.metric}</span>
                  {!k.is_active && <span className="text-[10px] text-slate-500">inactive</span>}
                  {k.notify && <Bell className="w-3 h-3 text-slate-500" />}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">target {fmtVal(k.target_value, k.unit)} · warn {fmtVal(k.warning_value, k.unit)} · crit {fmtVal(k.critical_value, k.unit)} · {k.comparison.replace('_', ' ')}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title="Edit" onClick={() => setEdit({ ...k })} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                <button title="Delete" onClick={() => window.confirm(`Delete "${k.name}"?`) && act(() => api.remove(k.id), 'Deleted.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'alerts' ? (
        <div className="space-y-2">
          {alerts.length === 0 && <p className="text-sm text-slate-500">No alerts.</p>}
          {alerts.map((a) => (
            <div key={a.id} className={`glass-panel border ${a.resolved ? 'border-slate-800/85' : a.status === 'critical' ? 'border-red-500/30' : 'border-amber-500/30'} rounded-xl p-3 flex items-center gap-3`}>
              {a.status === 'critical' ? <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" /> : <AlertTriangle className="w-4 h-4 text-amber-400 shrink-0" />}
              <div className="flex-1 min-w-0">
                <p className="text-sm text-slate-200 truncate">{a.kpi_name} <span className={`text-[10px] ${a.status === 'critical' ? 'text-red-400' : 'text-amber-400'}`}>{a.status}</span>{a.resolved && <span className="text-[10px] text-emerald-400"> · resolved</span>}</p>
                <p className="text-[11px] text-slate-500 truncate">{a.message}</p>
              </div>
              {!a.resolved && <button onClick={() => act(() => api.resolveAlert(a.id), 'Resolved.')} className="text-xs text-emerald-400 hover:text-emerald-300 cursor-pointer flex items-center gap-1 shrink-0"><CheckCircle2 className="w-3.5 h-3.5" /> Resolve</button>}
            </div>
          ))}
        </div>
      ) : null}

      {edit && catalog && <KpiModal draft={edit} catalog={catalog} onClose={() => setEdit(null)} onSaved={async () => { setEdit(null); flash('Saved.'); await load(); }} setErr={setErr} />}
    </div>
  );
};

const KpiModal: React.FC<{ draft: any; catalog: KpiCatalog; onClose: () => void; onSaved: () => void; setErr: (s: string) => void }> = ({ draft, catalog, onClose, onSaved, setErr }) => {
  const [f, setF] = useState<any>(draft);
  const [busy, setBusy] = useState(false);
  const meta = useMemo(() => catalog.metrics.find((m) => m.key === f.metric), [catalog, f.metric]);
  const set = (patch: any) => setF({ ...f, ...patch });
  const onMetric = (key: string) => {
    const m = catalog.metrics.find((x) => x.key === key);
    set({ metric: key, category: m?.category, unit: m?.unit, comparison: m?.comparison });
  };
  const save = async () => {
    if (!f.name?.trim()) { setErr('Name is required'); return; }
    setBusy(true); setErr('');
    const payload = {
      name: f.name, description: f.description || undefined, category: f.category, metric: f.metric, unit: f.unit,
      comparison: f.comparison, target_value: Number(f.target_value) || 0,
      warning_value: f.warning_value === '' || f.warning_value == null ? null : Number(f.warning_value),
      critical_value: f.critical_value === '' || f.critical_value == null ? null : Number(f.critical_value),
      manual_value: f.metric === 'manual' && f.manual_value != null && f.manual_value !== '' ? Number(f.manual_value) : null,
      window_days: Number(f.window_days) || 30, is_active: f.is_active !== false, notify: f.notify !== false,
    };
    try { if (f.id) await api.update(f.id, payload); else await api.create(payload); onSaved(); }
    catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Gauge className="w-4 h-4 text-brand-400" /> {f.id ? 'Edit' : 'New'} KPI</h3>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="space-y-2">
          <input value={f.name || ''} onChange={(e) => set({ name: e.target.value })} placeholder="KPI name" className={F} />
          <input value={f.description || ''} onChange={(e) => set({ description: e.target.value })} placeholder="Description (optional)" className={F} />
          <label className="text-[11px] text-slate-400">Metric
            <select value={f.metric} onChange={(e) => onMetric(e.target.value)} className={F}>
              {catalog.metrics.map((m) => <option key={m.key} value={m.key}>{m.category} · {m.label}</option>)}
            </select>
          </label>
          <div className="grid grid-cols-2 gap-2">
            <label className="text-[11px] text-slate-400">Comparison<select value={f.comparison} onChange={(e) => set({ comparison: e.target.value })} className={F}>{catalog.comparisons.map((c) => <option key={c} value={c}>{c.replace('_', ' ')}</option>)}</select></label>
            <label className="text-[11px] text-slate-400">Unit<select value={f.unit} onChange={(e) => set({ unit: e.target.value })} className={F}>{catalog.units.map((u) => <option key={u} value={u}>{u}</option>)}</select></label>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <label className="text-[11px] text-slate-400">Target<input type="number" value={f.target_value ?? ''} onChange={(e) => set({ target_value: e.target.value })} className={F} /></label>
            <label className="text-[11px] text-amber-400">Warning<input type="number" value={f.warning_value ?? ''} onChange={(e) => set({ warning_value: e.target.value })} className={F} /></label>
            <label className="text-[11px] text-red-400">Critical<input type="number" value={f.critical_value ?? ''} onChange={(e) => set({ critical_value: e.target.value })} className={F} /></label>
          </div>
          {f.metric === 'manual' && <label className="text-[11px] text-slate-400 block">Current value<input type="number" value={f.manual_value ?? ''} onChange={(e) => set({ manual_value: e.target.value })} className={F} /></label>}
          <div className="flex items-center gap-4 pt-1">
            <label className="flex items-center gap-1.5 text-xs text-slate-300"><input type="checkbox" checked={f.is_active !== false} onChange={(e) => set({ is_active: e.target.checked })} /> Active</label>
            <label className="flex items-center gap-1.5 text-xs text-slate-300"><input type="checkbox" checked={f.notify !== false} onChange={(e) => set({ notify: e.target.checked })} /> <Bell className="w-3 h-3" /> Notify on breach</label>
            <span className="text-[11px] text-slate-600 ml-auto">{meta?.unit}</span>
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 font-medium py-2 rounded-lg text-sm cursor-pointer mt-2">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save</button>
        </div>
      </div>
    </div>
  );
};
