import React, { useCallback, useEffect, useState } from 'react';
import {
  History, Loader2, Camera, Download, LayoutDashboard, TrendingUp, ArrowLeftRight, Layers, Check,
  ArrowUpRight, ArrowDownRight,
} from 'lucide-react';
import { ResponsiveContainer, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip } from 'recharts';
import {
  historyApi as api, HistMeta, HistDashboard, HistTrend, HistComparison, HistSnapshotRow,
} from '../services/historyApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const AXIS = { stroke: '#64748b', fontSize: 11 };
const TT = { backgroundColor: '#0f172a', border: '1px solid #334155', borderRadius: 8, fontSize: 12, color: '#e2e8f0' };

const fmtVal = (v: number | null | undefined, unit: string) => {
  if (v == null) return '—';
  if (unit === 'currency') return `₹${Math.round(v).toLocaleString()}`;
  if (unit === 'percent') return `${v}%`;
  if (unit === 'seconds') return `${v}s`;
  return v.toLocaleString();
};

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const HistoricalAnalyticsPage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'trends' | 'comparison' | 'snapshots'>('dashboard');
  const [meta, setMeta] = useState<HistMeta | null>(null);
  const [dash, setDash] = useState<HistDashboard | null>(null);
  const [metric, setMetric] = useState('sales_revenue');
  const [days, setDays] = useState(90);
  const [window_, setWindow] = useState(30);
  const [trend, setTrend] = useState<HistTrend | null>(null);
  const [rollingData, setRollingData] = useState<any>(null);
  const [period, setPeriod] = useState('month');
  const [comp, setComp] = useState<HistComparison | null>(null);
  const [snaps, setSnaps] = useState<HistSnapshotRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (!meta) setMeta(await api.meta());
      if (tab === 'dashboard') setDash(await api.dashboard());
      else if (tab === 'trends') {
        setTrend(await api.trends(metric, days));
        setRollingData(await api.rolling(metric, window_, days));
      } else if (tab === 'comparison') setComp(await api.report(period));
      else setSnaps(await api.snapshots({ limit: 200 }));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load history.')); } finally { setLoading(false); }
  }, [tab, meta, metric, days, window_, period]);
  useEffect(() => { load(); }, [load]);

  const capture = async () => {
    setBusy(true);
    try { const r = await api.capture(); flash(`Captured ${r.captured} metrics for ${r.date}.`); await load(); }
    catch (e) { setErr(extractErrorMessage(e, 'Capture failed')); } finally { setBusy(false); }
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><History className="w-6 h-6 text-brand-400" /> Historical Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">Daily metric snapshots, long-term trends, period comparisons, rolling reports and retention-managed archives.</p>
        </div>
        <button onClick={capture} disabled={busy} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5 w-fit"><Camera className={`w-3.5 h-3.5 ${busy ? 'animate-pulse' : ''}`} /> Capture snapshot now</button>
      </div>

      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['trends', 'Trends & Rolling', TrendingUp], ['comparison', 'Comparison', ArrowLeftRight], ['snapshots', 'Snapshots & Retention', Layers]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Days covered</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.days_covered}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Metrics tracked</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.metrics_tracked}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Archived rows</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.archived_rows}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Last capture</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.last_capture || '—'}</p></div>
          </div>
          <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-4 gap-3">
            {Object.entries(dash.sparklines).map(([k, s]) => (
              <div key={k} className={card}>
                <p className="text-[11px] text-slate-400 mb-1">{s.label}</p>
                {s.points.length === 0 ? <p className="text-xs text-slate-600 py-6 text-center">No history yet</p> : (
                  <>
                    <p className="text-lg font-bold text-slate-100">{fmtVal(s.points[s.points.length - 1]?.value, s.unit)}</p>
                    <ResponsiveContainer width="100%" height={50}>
                      <LineChart data={s.points}><Line type="monotone" dataKey="value" stroke="#818cf8" strokeWidth={1.5} dot={false} /></LineChart>
                    </ResponsiveContainer>
                  </>
                )}
              </div>
            ))}
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Top movers — this month vs last</p>
            {dash.top_movers.length === 0 ? <p className="text-xs text-slate-500">Not enough history yet — snapshots build up daily.</p> :
              dash.top_movers.map((r) => <MoverRow key={r.metric} r={r} />)}
          </div>
        </div>
      ) : tab === 'trends' && meta ? (
        <div className="space-y-4">
          <div className="flex items-center gap-2 flex-wrap">
            <select value={metric} onChange={(e) => setMetric(e.target.value)} className={`${F} !w-64`}>
              {meta.metrics.map((m) => <option key={m.key} value={m.key}>{m.category} · {m.label}</option>)}
            </select>
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} className={`${F} !w-32`}>
              {[30, 90, 180, 365, 730].map((d) => <option key={d} value={d}>{d} days</option>)}
            </select>
            <select value={window_} onChange={(e) => setWindow(Number(e.target.value))} className={`${F} !w-36`}>
              {meta.rolling_windows.map((w) => <option key={w} value={w}>rolling {w}d</option>)}
            </select>
            <button onClick={async () => downloadText(`${metric}-trend.csv`, await api.exportCsv({ kind: 'trend', metric, days }))} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1"><Download className="w-3.5 h-3.5" /> CSV</button>
          </div>
          {trend && (
            <div className={card}>
              <div className="flex items-center justify-between mb-2">
                <p className="text-sm font-semibold text-slate-200">{trend.label}</p>
                <p className="text-[11px] text-slate-500">latest {fmtVal(trend.latest, trend.unit)} · min {fmtVal(trend.min, trend.unit)} · max {fmtVal(trend.max, trend.unit)}{trend.change_pct != null ? ` · ${trend.change_pct > 0 ? '+' : ''}${trend.change_pct}%` : ''}</p>
              </div>
              {(rollingData?.points || trend.points).length === 0 ? (
                <p className="text-sm text-slate-500 py-10 text-center">No snapshots yet — hit "Capture snapshot now" and let the daily cron build history.</p>
              ) : (
                <ResponsiveContainer width="100%" height={320}>
                  <LineChart data={rollingData?.points || trend.points} margin={{ top: 5, right: 10, left: -10, bottom: 5 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                    <XAxis dataKey="date" {...AXIS} /><YAxis {...AXIS} />
                    <Tooltip contentStyle={TT} />
                    <Line type="monotone" dataKey="value" name="value" stroke="#818cf8" strokeWidth={2} dot={false} />
                    <Line type="monotone" dataKey="rolling_avg" name={`rolling ${window_}d`} stroke="#34d399" strokeWidth={2} strokeDasharray="6 3" dot={false} />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </div>
          )}
        </div>
      ) : tab === 'comparison' && comp ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            {['month', 'quarter', 'year'].map((p) => (
              <button key={p} onClick={() => setPeriod(p)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer capitalize ${period === p ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-800/60 text-slate-400 hover:text-slate-200'}`}>{p}ly</button>
            ))}
            <span className="text-[11px] text-slate-500">{comp.current_window.start} → {comp.current_window.end} vs {comp.previous_window.start} → {comp.previous_window.end}</span>
            <span className="flex-1" />
            <span className="text-[11px] text-emerald-400">{comp.improved} improved</span>
            <span className="text-[11px] text-red-400">{comp.declined} declined</span>
            <button onClick={async () => downloadText(`comparison-${period}.csv`, await api.exportCsv({ kind: 'comparison', period }))} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1"><Download className="w-3.5 h-3.5" /> CSV</button>
          </div>
          {comp.rows.length === 0 ? <p className="text-sm text-slate-500">No snapshot history in these windows yet.</p> :
            <div className={card}>{comp.rows.map((r) => <MoverRow key={r.metric} r={r} />)}</div>}
        </div>
      ) : tab === 'snapshots' ? (
        <SnapshotsTab snaps={snaps} flash={flash} setErr={setErr} />
      ) : null}
    </div>
  );
};

const MoverRow: React.FC<{ r: any }> = ({ r }) => (
  <div className="flex items-center gap-3 py-1.5 border-b border-slate-800/50 last:border-0 text-sm">
    <span className="flex-1 text-slate-300 truncate">{r.label}</span>
    <span className="text-slate-500 text-[11px] w-40 text-right">{fmtVal(r.previous, r.unit)} → <span className="text-slate-200">{fmtVal(r.current, r.unit)}</span></span>
    <span className={`w-20 text-right text-xs font-semibold flex items-center justify-end gap-0.5 ${r.improved === true ? 'text-emerald-400' : r.improved === false ? 'text-red-400' : 'text-slate-500'}`}>
      {r.change_pct > 0 ? <ArrowUpRight className="w-3 h-3" /> : r.change_pct < 0 ? <ArrowDownRight className="w-3 h-3" /> : null}
      {r.change_pct > 0 ? '+' : ''}{r.change_pct}%
    </span>
  </div>
);

const SnapshotsTab: React.FC<{ snaps: any[]; flash: (s: string) => void; setErr: (s: string) => void }> = ({ snaps, flash, setErr }) => {
  const [settings, setSettings] = useState<any>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { api.settings().then(setSettings).catch(() => {}); }, []);
  const save = async () => {
    setBusy(true);
    try { setSettings(await api.updateSettings(settings)); flash('Retention policy saved.'); }
    catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
  };
  return (
    <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
      <div className={`${card} lg:col-span-2`}>
        <div className="flex items-center justify-between mb-2">
          <p className="text-xs font-semibold text-slate-400 uppercase">Raw snapshots (latest 200)</p>
          <button onClick={async () => { try { const t = await api.exportCsv({ kind: 'snapshots' }); downloadText('snapshots.csv', t); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1"><Download className="w-3.5 h-3.5" /> CSV</button>
        </div>
        <div className="overflow-x-auto max-h-[480px] overflow-y-auto">
          <table className="w-full text-[11px]">
            <thead><tr className="text-slate-400 border-b border-slate-800 sticky top-0 bg-slate-900"><th className="text-left py-1.5 px-2">Date</th><th className="text-left py-1.5 px-2">Metric</th><th className="text-right py-1.5 px-2">Value</th><th className="text-left py-1.5 px-2">Granularity</th></tr></thead>
            <tbody>
              {snaps.map((s) => (
                <tr key={s.id} className="border-b border-slate-800/50">
                  <td className="py-1 px-2 text-slate-400">{s.date}</td>
                  <td className="py-1 px-2 text-slate-200">{s.label}</td>
                  <td className="py-1 px-2 text-right text-slate-100">{s.value.toLocaleString()}</td>
                  <td className="py-1 px-2"><span className={`text-[10px] px-1.5 py-0.5 rounded ${s.granularity === 'monthly' ? 'bg-amber-500/10 text-amber-300' : 'bg-slate-700/40 text-slate-400'}`}>{s.granularity === 'monthly' ? 'archived' : 'daily'}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
          {snaps.length === 0 && <p className="text-sm text-slate-500 py-8 text-center">No snapshots yet.</p>}
        </div>
      </div>
      <div className={`${card} h-fit space-y-2`}>
        <p className="text-xs font-semibold text-slate-400 uppercase">Retention policy</p>
        {!settings ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : (
          <>
            <label className="text-[11px] text-slate-400 block">Keep daily snapshots for (days)
              <input type="number" min={30} max={3650} value={settings.retention_days}
                     onChange={(e) => setSettings({ ...settings, retention_days: Number(e.target.value) })} className={F} />
            </label>
            <label className="flex items-center gap-1.5 text-xs text-slate-300">
              <input type="checkbox" checked={settings.archive_enabled} onChange={(e) => setSettings({ ...settings, archive_enabled: e.target.checked })} />
              Archive older data as monthly averages
            </label>
            <label className="flex items-center gap-1.5 text-xs text-slate-300">
              <input type="checkbox" checked={settings.capture_enabled} onChange={(e) => setSettings({ ...settings, capture_enabled: e.target.checked })} />
              Daily automatic capture
            </label>
            <p className="text-[11px] text-slate-600">Daily rows older than the window are compacted into monthly averages (shown as “archived”) and removed. History is also queryable as the <code>metric_history</code> dataset in Report Builder, Visualizations and BI feeds.</p>
            <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 font-medium py-2 rounded-lg text-xs cursor-pointer">{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} Save policy</button>
          </>
        )}
      </div>
    </div>
  );
};
