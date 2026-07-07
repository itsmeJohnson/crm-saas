import React, { useCallback, useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  LayoutDashboard, Loader2, Download, RefreshCw, Save, Star, Trash2, X, Check,
  TrendingUp, Sparkles, ArrowUpRight, AlertTriangle, Settings2,
} from 'lucide-react';
import {
  executiveDashboardApi as api, ExecCatalog, ExecDashboard, ExecView,
} from '../services/executiveDashboardApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';

const fmtNum = (n: any) => (typeof n === 'number' ? n.toLocaleString() : n ?? '—');
const fmtCur = (n: any) => (typeof n === 'number' ? `₹${Math.round(n).toLocaleString()}` : '—');
const pct = (n: any) => (typeof n === 'number' ? `${n}%` : '—');

const PERSONA_LABEL: Record<string, string> = {
  ceo: 'CEO / Executive', sales: 'Sales', finance: 'Finance', hr: 'HR', support: 'Support', operations: 'Operations',
};

const Tile: React.FC<{ label: string; value: React.ReactNode; tone?: string }> = ({ label, value, tone }) => (
  <div className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
    <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{label}</p>
    <p className={`text-lg font-bold mt-0.5 ${tone || 'text-slate-100'}`}>{value}</p>
  </div>
);

const Bars: React.FC<{ data: [string, number][]; empty?: string }> = ({ data, empty }) => {
  const max = Math.max(1, ...data.map(([, v]) => v));
  if (!data.length) return <p className="text-xs text-slate-500">{empty || 'No data.'}</p>;
  return (
    <div className="space-y-1.5">
      {data.map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400 w-28 truncate" title={k}>{k}</span>
          <div className="flex-1 h-2.5 bg-slate-800/60 rounded"><div className="h-2.5 rounded bg-brand-500/70" style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="text-[11px] text-slate-300 w-10 text-right">{fmtNum(v)}</span>
        </div>
      ))}
    </div>
  );
};

// severity → reserved status tone (good/info/warning/critical), never a series hue
const SEV: Record<string, string> = {
  critical: 'text-red-400 border-red-500/30 bg-red-500/10',
  warning: 'text-amber-400 border-amber-500/30 bg-amber-500/10',
  info: 'text-brand-300 border-brand-500/30 bg-brand-500/10',
};

/* per-widget renderers: block → card body. colSpan hints the grid. */
const RENDER: Record<string, { span?: number; body: (b: any) => React.ReactNode }> = {
  revenue: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Revenue" value={fmtCur(b.revenue)} tone="text-emerald-400" /><Tile label="Conversion" value={pct(b.conversion_rate)} /><Tile label="Leads" value={fmtNum(b.leads)} /><Tile label="Converted" value={fmtNum(b.converted)} /></div> },
  conversion_rate: { body: (b) => <div className="grid grid-cols-3 gap-2"><Tile label="Conversion" value={pct(b.conversion_rate)} tone="text-emerald-400" /><Tile label="Leads" value={fmtNum(b.leads)} /><Tile label="Converted" value={fmtNum(b.converted)} /></div> },
  pipeline: { span: 2, body: (b) => <Bars data={(b.by_stage || []).map((s: any) => [s.stage_name || s.label || '—', s.count || 0])} empty="No pipeline." /> },
  lead_sources: { span: 2, body: (b) => <Bars data={(b.by_source || []).map((s: any) => [s.source || s.label || 'Unknown', s.count || s.lead_count || 0])} empty="No sources." /> },
  collections: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Collected" value={fmtCur(b.collected)} tone="text-emerald-400" /><Tile label="Outstanding" value={fmtCur(b.outstanding)} /><Tile label="Overdue" value={fmtCur(b.overdue)} tone={b.overdue ? 'text-red-400' : undefined} /><Tile label="Collection rate" value={pct(b.collection_rate)} /></div> },
  cash_flow: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Realised inflow" value={fmtCur(b.realised_inflow)} tone="text-emerald-400" /><Tile label="Expected inflow" value={fmtCur(b.expected_inflow)} /><Tile label="At risk" value={fmtCur(b.at_risk)} tone={b.at_risk ? 'text-red-400' : undefined} /><Tile label="Net position" value={fmtCur(b.net_position)} /></div> },
  forecast: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Open pipeline" value={fmtCur(b.open_pipeline_value)} /><Tile label="Weighted" value={fmtCur(b.weighted_pipeline)} /><Tile label="Realised" value={fmtCur(b.realised_revenue)} tone="text-emerald-400" /><Tile label="Projected total" value={fmtCur(b.projected_total)} tone="text-brand-300" /></div> },
  communication_summary: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Total" value={fmtNum(b.total)} /><Tile label="Delivery rate" value={pct(b.delivery_rate)} /><Tile label="Outbound" value={fmtNum(b.outbound)} /><Tile label="Inbound" value={fmtNum(b.inbound)} /></div> },
  call_statistics: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Calls" value={fmtNum(b.total_calls)} /><Tile label="Connected" value={fmtNum(b.connected)} tone="text-emerald-400" /><Tile label="Missed" value={fmtNum(b.missed)} tone={b.missed ? 'text-amber-400' : undefined} /><Tile label="Inbound" value={fmtNum(b.inbound)} /></div> },
  agent_productivity: { span: 2, body: (b) => (b.agents || []).length ? (
    <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Agent</th><th className="text-right">Total</th><th className="text-right">Calls</th><th className="text-right">Failed</th></tr></thead>
      <tbody>{b.agents.map((a: any) => <tr key={a.agent_id} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{a.agent_name}</td><td className="text-right">{fmtNum(a.total)}</td><td className="text-right">{fmtNum(a.calls)}</td><td className="text-right text-red-400">{fmtNum(a.failed)}</td></tr>)}</tbody></table>
  ) : <p className="text-xs text-slate-500">No agent activity.</p> },
  department_performance: { span: 2, body: (b) => (b.rows || []).length ? (
    <div className="space-y-1.5">{b.rows.map((r: any, i: number) => <div key={i} className="flex items-center justify-between text-xs border-b border-slate-800/40 pb-1"><span className="text-slate-300 truncate">{r.name || r.label || r.department || `#${i + 1}`}</span><span className="text-slate-500">{[r.headcount != null ? `${r.headcount} ppl` : null, r.leads != null ? `${r.leads} leads` : null, r.revenue != null ? fmtCur(r.revenue) : null].filter(Boolean).join(' · ') || '—'}</span></div>)}</div>
  ) : <p className="text-xs text-slate-500">No {b.dimension || 'structure'} data.</p> },
  target_achievement: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Avg attainment" value={pct(b.avg_attainment)} tone="text-emerald-400" /><Tile label="On track" value={fmtNum(b.on_track)} /><Tile label="Missed" value={fmtNum(b.missed)} tone={b.missed ? 'text-red-400' : undefined} /><Tile label="Total" value={fmtNum(b.total)} /></div> },
  attendance: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Headcount" value={fmtNum(b.headcount)} /><Tile label="Present" value={fmtNum(b.present_today)} tone="text-emerald-400" /><Tile label="Attendance" value={pct(b.attendance_rate)} /><Tile label="On leave" value={fmtNum(b.on_leave_today)} /></div> },
  leave: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Pending" value={fmtNum(b.pending_leaves)} tone={b.pending_leaves ? 'text-amber-400' : undefined} /><Tile label="On leave today" value={fmtNum(b.on_leave_today)} /></div> },
  workflow_status: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Runs" value={fmtNum(b.total_runs)} /><Tile label="Success" value={pct(b.success_rate)} tone="text-emerald-400" /><Tile label="Failed" value={fmtNum(b.failed)} tone={b.failed ? 'text-red-400' : undefined} /><Tile label="Avg exec" value={b.avg_execution_ms != null ? `${Math.round(b.avg_execution_ms)}ms` : '—'} /></div> },
  automation_health: { body: (b) => <div className="grid grid-cols-3 gap-2"><Tile label="Jobs OK" value={pct(b.jobs?.success_rate)} /><Tile label="Queue OK" value={pct(b.queue?.success_rate)} /><Tile label="Rule match" value={pct(b.rules?.match_rate)} /></div> },
  sla_compliance: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Compliance" value={pct(b.compliance_rate)} tone="text-emerald-400" /><Tile label="Tracked" value={fmtNum(b.tracked)} /><Tile label="Breached" value={fmtNum(b.breached)} tone={b.breached ? 'text-red-400' : undefined} /><Tile label="Open breaches" value={fmtNum(b.open_breaches)} tone={b.open_breaches ? 'text-red-400' : undefined} /></div> },
  escalations: { body: (b) => <div><Tile label="Escalation events" value={fmtNum(b.total)} tone={b.total ? 'text-amber-400' : undefined} /><div className="mt-2"><Bars data={Object.entries(b.by_entity || {}) as [string, number][]} empty="No escalations." /></div></div> },
  campaign_performance: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="Campaigns" value={fmtNum(b.total)} /><Tile label="Running" value={fmtNum(b.running)} /><Tile label="Sent" value={fmtNum(b.total_sent)} /><Tile label="ROI" value={fmtCur(b.total_roi)} tone="text-emerald-400" /></div> },
  customer_satisfaction: { body: (b) => <div className="grid grid-cols-2 gap-2"><Tile label="CSAT (proxy)" value={pct(b.csat_proxy)} tone="text-emerald-400" /><Tile label="Resolution rate" value={pct(b.resolution_rate)} /><Tile label="Open" value={fmtNum(b.open)} /><Tile label="Critical open" value={fmtNum(b.critical_open)} tone={b.critical_open ? 'text-red-400' : undefined} /></div> },
  ai_insights: { span: 3, body: (b) => (
    <div className="space-y-2">
      {(b.insights || []).map((ins: any, i: number) => (
        <div key={i} className={`p-2.5 rounded-lg border ${SEV[ins.severity] || SEV.info}`}>
          <p className="text-xs font-semibold flex items-center gap-1.5"><Sparkles className="w-3.5 h-3.5" /> {ins.title}</p>
          <p className="text-[11px] text-slate-400 mt-0.5">{ins.detail}</p>
        </div>
      ))}
    </div>
  ) },
};

export const ExecutiveDashboardPage: React.FC = () => {
  const navigate = useNavigate();
  const [catalog, setCatalog] = useState<ExecCatalog | null>(null);
  const [data, setData] = useState<ExecDashboard | null>(null);
  const [views, setViews] = useState<ExecView[]>([]);
  const [persona, setPersona] = useState('ceo');
  const [scope, setScope] = useState('organization');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [customWidgets, setCustomWidgets] = useState<string[] | null>(null);
  const [auto, setAuto] = useState(false);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [err, setErr] = useState('');
  const [saveOpen, setSaveOpen] = useState(false);
  const [configOpen, setConfigOpen] = useState(false);

  useEffect(() => {
    api.catalog().then((c) => { setCatalog(c); }).catch((e) => setErr(extractErrorMessage(e, 'Failed to load.')));
    api.listViews().then(setViews).catch(() => {});
  }, []);

  const load = useCallback(async (silent = false) => {
    silent ? setRefreshing(true) : setLoading(true);
    setErr('');
    try {
      const body = { persona, scope, date_from: from || undefined, date_to: to || undefined, widgets: customWidgets || undefined };
      setData(customWidgets ? await api.dashboardCustom(body) : await api.dashboard(body));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load dashboard.')); }
    finally { silent ? setRefreshing(false) : setLoading(false); }
  }, [persona, scope, from, to, customWidgets]);
  useEffect(() => { load(); }, [load]);

  // real-time refresh
  useEffect(() => {
    if (!auto) return;
    const id = setInterval(() => load(true), 30000);
    return () => clearInterval(id);
  }, [auto, load]);

  const widgetMeta = useMemo(() => Object.fromEntries((catalog?.widgets || []).map((w) => [w.id, w])), [catalog]);

  const applyView = (v: ExecView) => { setPersona(v.persona === 'custom' ? persona : v.persona); setScope(v.scope); setCustomWidgets(v.widgets); };
  const applyPersona = (p: string) => { setPersona(p); setCustomWidgets(null); };
  const exportCsv = async () => {
    try {
      const blob = await api.exportCsv({ persona, scope, date_from: from || undefined, date_to: to || undefined });
      const url = URL.createObjectURL(blob); const a = document.createElement('a');
      a.href = url; a.download = 'executive-dashboard.csv'; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setErr(extractErrorMessage(e, 'Export failed.')); }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><LayoutDashboard className="w-6 h-6 text-brand-400" /> Executive Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">A role-aware executive cockpit across sales, finance, operations, HR and support.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={F} />
          <span className="text-slate-600 text-xs">→</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={F} />
          <button onClick={() => setAuto((a) => !a)} title="Real-time refresh (30s)" className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold cursor-pointer flex items-center gap-1.5 ${auto ? 'bg-emerald-500/20 text-emerald-300' : 'bg-slate-800/70 text-slate-300 hover:bg-slate-700/70'}`}><RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} /> {auto ? 'Live' : 'Refresh'}</button>
          <button onClick={() => setConfigOpen(true)} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Settings2 className="w-3.5 h-3.5" /> Widgets</button>
          <button onClick={() => setSaveOpen(true)} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Save className="w-3.5 h-3.5" /> Save view</button>
          <button onClick={exportCsv} className="px-2.5 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Export</button>
        </div>
      </div>

      {/* persona + scope + saved views */}
      <div className="flex flex-wrap items-center gap-2">
        <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 flex-wrap">
          {(catalog?.personas || []).map((p) => (
            <button key={p} onClick={() => applyPersona(p)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer ${persona === p && !customWidgets ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}>{PERSONA_LABEL[p] || p}</button>
          ))}
        </div>
        <select value={scope} onChange={(e) => setScope(e.target.value)} className={F} title="Structural scope">
          {(catalog?.scopes || []).map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
        {views.length > 0 && (
          <select value="" onChange={(e) => { const v = views.find((x) => x.id === e.target.value); if (v) applyView(v); }} className={F} title="Saved views">
            <option value="">Saved views…</option>
            {views.map((v) => <option key={v.id} value={v.id}>{v.name}{v.is_default ? ' ★' : ''}</option>)}
          </select>
        )}
        {customWidgets && <button onClick={() => setCustomWidgets(null)} className="text-[11px] text-brand-400 hover:text-brand-300 cursor-pointer">reset to persona</button>}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : data ? (
        <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-3 auto-rows-min">
          {data.widgets.map((wid) => {
            const meta = widgetMeta[wid]; const block = data.blocks[wid]; const r = RENDER[wid];
            if (!r) return null;
            const span = r.span === 3 ? 'md:col-span-2 xl:col-span-3' : r.span === 2 ? 'md:col-span-2 xl:col-span-2' : '';
            return (
              <div key={wid} className={`${card} ${span}`}>
                <div className="flex items-center justify-between mb-2.5">
                  <h3 className="text-xs font-semibold text-slate-300 flex items-center gap-1.5">{wid === 'ai_insights' && <Sparkles className="w-3.5 h-3.5 text-brand-400" />}{meta?.label || wid}</h3>
                  {meta?.drill && <button onClick={() => navigate(meta.drill!)} className="text-slate-500 hover:text-brand-300 cursor-pointer" title="Drill down"><ArrowUpRight className="w-3.5 h-3.5" /></button>}
                </div>
                {block?.error ? <p className="text-[11px] text-amber-400 flex items-center gap-1"><AlertTriangle className="w-3.5 h-3.5" /> Unavailable</p> : r.body(block || {})}
              </div>
            );
          })}
        </div>
      ) : null}

      {data && <p className="text-[10px] text-slate-600 flex items-center gap-1"><TrendingUp className="w-3 h-3" /> {data.from} → {data.to} · generated {new Date(data.generated_at).toLocaleTimeString()}</p>}

      {saveOpen && catalog && <SaveViewModal persona={persona} scope={scope} widgets={customWidgets || catalog.persona_layouts[persona] || []} onClose={() => setSaveOpen(false)} onSaved={() => { setSaveOpen(false); api.listViews().then(setViews); }} />}
      {configOpen && catalog && <ConfigModal catalog={catalog} current={customWidgets || data?.widgets || []} views={views} onClose={() => setConfigOpen(false)} onApply={(w) => { setCustomWidgets(w); setConfigOpen(false); }} onDeleteView={async (id) => { await api.deleteView(id); api.listViews().then(setViews); }} />}
    </div>
  );
};

/* save current configuration as a named view */
const SaveViewModal: React.FC<{ persona: string; scope: string; widgets: string[]; onClose: () => void; onSaved: () => void }> = ({ persona, scope, widgets, onClose, onSaved }) => {
  const [name, setName] = useState(''); const [isDefault, setIsDefault] = useState(false);
  const [busy, setBusy] = useState(false); const [err, setErr] = useState('');
  const save = async () => {
    if (!name.trim()) { setErr('Name is required'); return; }
    setBusy(true); setErr('');
    try { await api.createView({ name, persona, scope, widgets, is_default: isDefault }); onSaved(); }
    catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
  };
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-sm p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Save className="w-4 h-4 text-brand-400" /> Save view</h3><button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button></div>
        {err && <div className="text-xs text-red-400 mb-2">{err}</div>}
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="View name" className={`${F} w-full mb-2`} />
        <label className="flex items-center gap-2 text-xs text-slate-300 mb-3"><input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} /> <Star className="w-3.5 h-3.5" /> Make default</label>
        <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 font-medium py-2 rounded-lg text-sm cursor-pointer">{busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save</button>
      </div>
    </div>
  );
};

/* widget configuration: toggle which widgets show + manage saved views */
const ConfigModal: React.FC<{ catalog: ExecCatalog; current: string[]; views: ExecView[]; onClose: () => void; onApply: (w: string[]) => void; onDeleteView: (id: string) => void }> = ({ catalog, current, views, onClose, onApply, onDeleteView }) => {
  const [sel, setSel] = useState<string[]>(current);
  const toggle = (id: string) => setSel((s) => s.includes(id) ? s.filter((x) => x !== id) : [...s, id]);
  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg max-h-[85vh] overflow-y-auto p-5 bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between mb-3"><h3 className="text-sm font-bold text-slate-100 flex items-center gap-2"><Settings2 className="w-4 h-4 text-brand-400" /> Configure widgets</h3><button onClick={onClose} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button></div>
        <div className="grid grid-cols-2 gap-1.5 mb-4">
          {catalog.widgets.map((w) => (
            <label key={w.id} className={`flex items-center gap-2 text-xs px-2 py-1.5 rounded-lg cursor-pointer border ${sel.includes(w.id) ? 'border-brand-500/40 bg-brand-500/10 text-slate-200' : 'border-slate-800 text-slate-400'}`}>
              <input type="checkbox" checked={sel.includes(w.id)} onChange={() => toggle(w.id)} /> {w.label}
            </label>
          ))}
        </div>
        <button onClick={() => onApply(sel)} className="w-full bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 font-medium py-2 rounded-lg text-sm cursor-pointer mb-4">Apply {sel.length} widget(s)</button>
        {views.length > 0 && (
          <div>
            <p className="text-[11px] font-semibold text-slate-500 uppercase mb-1.5">Saved views</p>
            <div className="space-y-1">
              {views.map((v) => (
                <div key={v.id} className="flex items-center justify-between text-xs px-2 py-1.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
                  <span className="text-slate-300">{v.name}{v.is_default ? ' ★' : ''} <span className="text-slate-600">· {v.persona}</span></span>
                  <button onClick={() => onDeleteView(v.id)} className="text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
