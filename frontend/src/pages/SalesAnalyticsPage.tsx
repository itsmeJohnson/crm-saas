import React, { useCallback, useEffect, useState } from 'react';
import {
  TrendingUp, Loader2, Download, Filter as FunnelIcon, Layers, XCircle, Gauge, LineChart,
  Target, Grid3x3, DollarSign,
} from 'lucide-react';
import {
  salesAnalyticsApi as api, SalesOverview, SalesFunnel, SourceROI, LostReasons, Velocity,
  SalesForecast, SalesTrend, SalesHeatmap,
} from '../services/salesAnalyticsApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const cur = (n: any) => (typeof n === 'number' ? `₹${Math.round(n).toLocaleString()}` : '—');
const num = (n: any) => (typeof n === 'number' ? n.toLocaleString() : '—');

const Tile: React.FC<{ label: string; value: React.ReactNode; tone?: string }> = ({ label, value, tone }) => (
  <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{label}</p><p className={`text-xl font-bold mt-1 ${tone || 'text-slate-100'}`}>{value}</p></div>
);

const Bars: React.FC<{ data: [string, number][]; fmt?: (n: number) => string; empty?: string }> = ({ data, fmt = num, empty }) => {
  const max = Math.max(1, ...data.map(([, v]) => v));
  if (!data.length) return <p className="text-xs text-slate-500">{empty || 'No data.'}</p>;
  return (
    <div className="space-y-1.5">
      {data.map(([k, v]) => (
        <div key={k} className="flex items-center gap-2">
          <span className="text-[11px] text-slate-400 w-32 truncate" title={k}>{k}</span>
          <div className="flex-1 h-2.5 bg-slate-800/60 rounded"><div className="h-2.5 rounded bg-brand-500/70" style={{ width: `${(v / max) * 100}%` }} /></div>
          <span className="text-[11px] text-slate-300 w-16 text-right">{fmt(v)}</span>
        </div>
      ))}
    </div>
  );
};

type Tab = 'overview' | 'funnel' | 'sources' | 'lost' | 'velocity' | 'trends' | 'forecast' | 'heatmap';

export const SalesAnalyticsPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('overview');
  const [from, setFrom] = useState('');
  const [to, setTo] = useState('');
  const [granularity, setGranularity] = useState('monthly');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const [ov, setOv] = useState<SalesOverview | null>(null);
  const [fn, setFn] = useState<SalesFunnel | null>(null);
  const [roi, setRoi] = useState<SourceROI | null>(null);
  const [lost, setLost] = useState<LostReasons | null>(null);
  const [vel, setVel] = useState<Velocity | null>(null);
  const [tr, setTr] = useState<SalesTrend | null>(null);
  const [fc, setFc] = useState<SalesForecast | null>(null);
  const [hm, setHm] = useState<SalesHeatmap | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    const p = { date_from: from || undefined, date_to: to || undefined };
    try {
      if (tab === 'overview') setOv(await api.overview(p));
      else if (tab === 'funnel') setFn(await api.funnel(p));
      else if (tab === 'sources') setRoi(await api.sources(p));
      else if (tab === 'lost') setLost(await api.lostReasons(p));
      else if (tab === 'velocity') setVel(await api.velocity(p));
      else if (tab === 'trends') setTr(await api.trend({ ...p, granularity }));
      else if (tab === 'forecast') setFc(await api.forecast(p));
      else if (tab === 'heatmap') setHm(await api.heatmap(p));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load sales analytics.')); } finally { setLoading(false); }
  }, [tab, from, to, granularity]);
  useEffect(() => { load(); }, [load]);

  const exportCsv = async () => {
    try {
      const blob = await api.exportCsv({ date_from: from || undefined, date_to: to || undefined });
      const url = URL.createObjectURL(blob); const a = document.createElement('a');
      a.href = url; a.download = 'sales-analytics.csv'; a.click(); URL.revokeObjectURL(url);
    } catch (e) { setErr(extractErrorMessage(e, 'Export failed.')); }
  };

  const TABS: [Tab, string, any][] = [
    ['overview', 'Overview', Target], ['funnel', 'Funnel', FunnelIcon], ['sources', 'Source ROI', DollarSign],
    ['lost', 'Lost Reasons', XCircle], ['velocity', 'Velocity & Cycle', Gauge], ['trends', 'Trends', LineChart],
    ['forecast', 'Forecast', TrendingUp], ['heatmap', 'Heat Map', Grid3x3],
  ];

  const heatColor = (v: number, max: number) => {
    if (!v) return 'rgba(148,163,184,0.06)';
    const t = Math.min(1, v / max);
    return `rgba(99,102,241,${0.15 + t * 0.65})`;
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><TrendingUp className="w-6 h-6 text-brand-400" /> Sales Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">Funnel, conversion, win rate, velocity, source ROI, lost reasons, trends and forecast.</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className={F} />
          <span className="text-slate-600 text-xs">→</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className={F} />
          <button onClick={exportCsv} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Download className="w-3.5 h-3.5" /> Export</button>
        </div>
      </div>

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {TABS.map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {label}</button>
        ))}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'overview' && ov ? (
        <div className="grid grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-3">
          <Tile label="Revenue (won)" value={cur(ov.revenue)} tone="text-emerald-400" />
          <Tile label="Pipeline value" value={cur(ov.pipeline_value)} />
          <Tile label="Win rate" value={`${ov.win_rate}%`} tone="text-emerald-400" />
          <Tile label="Conversion" value={`${ov.conversion_rate}%`} />
          <Tile label="Avg deal size" value={cur(ov.avg_deal_size)} />
          <Tile label="Sales cycle" value={`${ov.avg_sales_cycle_days}d`} />
          <Tile label="Sales velocity" value={`${cur(ov.sales_velocity)}/day`} tone="text-brand-300" />
          <Tile label="Won / Lost / Open" value={`${ov.won} / ${ov.lost} / ${ov.open}`} />
        </div>
      ) : tab === 'funnel' && fn ? (
        <div className="grid md:grid-cols-2 gap-4">
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-3 flex items-center gap-1.5"><Layers className="w-3.5 h-3.5" /> Sales funnel (by stage)</p>
            <div className="space-y-2">
              {fn.sales_funnel.map((s) => {
                const max = Math.max(1, ...fn.sales_funnel.map((x) => x.count));
                return (
                  <div key={s.stage}>
                    <div className="flex justify-between text-[11px] text-slate-400 mb-0.5"><span>{s.stage}</span><span>{s.count} · {cur(s.value)}{s.drop_off_pct ? ` · ▼${s.drop_off_pct}%` : ''}</span></div>
                    <div className="h-3 bg-slate-800/60 rounded"><div className="h-3 rounded bg-brand-500/70" style={{ width: `${(s.count / max) * 100}%` }} /></div>
                  </div>
                );
              })}
            </div>
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-3 flex items-center gap-1.5"><FunnelIcon className="w-3.5 h-3.5" /> Lead funnel (by status)</p>
            <Bars data={fn.lead_funnel.map((s) => [s.status, s.count])} />
          </div>
        </div>
      ) : tab === 'sources' && roi ? (
        <div className={`${card} overflow-x-auto`}>
          <table className="w-full text-xs">
            <thead className="text-slate-500"><tr><th className="text-left py-1">Source</th><th className="text-right">Leads</th><th className="text-right">Won</th><th className="text-right">Conv %</th><th className="text-right">Revenue</th><th className="text-right">₹/lead</th><th className="text-right">Avg deal</th></tr></thead>
            <tbody>
              {roi.sources.length === 0 && <tr><td colSpan={7} className="py-6 text-center text-slate-500">No lead sources.</td></tr>}
              {roi.sources.map((s) => (
                <tr key={s.source} className="border-t border-slate-800/60 text-slate-300">
                  <td className="py-1.5">{s.source}</td><td className="text-right">{s.leads}</td><td className="text-right">{s.won}</td>
                  <td className="text-right">{s.conversion_rate}%</td><td className="text-right text-emerald-400">{cur(s.revenue)}</td>
                  <td className="text-right">{cur(s.value_per_lead)}</td><td className="text-right">{cur(s.avg_deal_size)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : tab === 'lost' && lost ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Tile label="Total lost" value={num(lost.total_lost)} tone="text-red-400" />
            <Tile label="Lost value" value={cur(lost.lost_value)} tone="text-red-400" />
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-3">Lost reasons</p>
            <Bars data={lost.by_reason.map((r) => [r.reason, r.count])} empty="No lost leads (or reasons not recorded)." />
          </div>
        </div>
      ) : tab === 'velocity' && vel ? (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <Tile label="Sales velocity" value={`${cur(vel.sales_velocity)}/day`} tone="text-brand-300" />
          <Tile label="Win rate" value={`${vel.win_rate}%`} tone="text-emerald-400" />
          <Tile label="Opportunities" value={num(vel.opportunities)} />
          <Tile label="Avg deal size" value={cur(vel.avg_deal_size)} />
          <Tile label="Avg cycle" value={`${vel.avg_sales_cycle_days}d`} />
          <Tile label="Median cycle" value={`${vel.median_cycle_days}d`} />
          <Tile label="Min cycle" value={`${vel.min_cycle_days}d`} />
          <Tile label="Max cycle" value={`${vel.max_cycle_days}d`} />
          <div className={`${card} col-span-2 md:col-span-4`}><p className="text-[11px] text-slate-500">Velocity = {vel.velocity_note}</p></div>
        </div>
      ) : tab === 'trends' && tr ? (
        <div className="space-y-3">
          <div className="flex items-center gap-2">
            <span className="text-xs text-slate-400">Granularity</span>
            <select value={granularity} onChange={(e) => setGranularity(e.target.value)} className={F}>{['daily', 'weekly', 'monthly'].map((g) => <option key={g} value={g}>{g}</option>)}</select>
          </div>
          <div className={`${card} overflow-x-auto`}>
            <table className="w-full text-xs">
              <thead className="text-slate-500"><tr><th className="text-left py-1">Period</th><th className="text-right">Leads</th><th className="text-right">Won</th><th className="text-right">Lost</th><th className="text-right">Win %</th><th className="text-right">Revenue</th></tr></thead>
              <tbody>
                {tr.series.length === 0 && <tr><td colSpan={6} className="py-6 text-center text-slate-500">No activity in range.</td></tr>}
                {tr.series.map((b) => (
                  <tr key={b.bucket} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{b.bucket}</td><td className="text-right">{b.leads}</td><td className="text-right text-emerald-400">{b.won}</td><td className="text-right text-red-400">{b.lost}</td><td className="text-right">{b.win_rate}%</td><td className="text-right">{cur(b.revenue)}</td></tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      ) : tab === 'forecast' && fc ? (
        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
          <Tile label="Realised revenue" value={cur(fc.realised_revenue)} tone="text-emerald-400" />
          <Tile label="Open pipeline" value={cur(fc.open_pipeline_value)} />
          <Tile label="Weighted pipeline" value={cur(fc.weighted_pipeline)} />
          <Tile label="Projected total" value={cur(fc.projected_total)} tone="text-brand-300" />
          <Tile label="Open deals" value={num(fc.open_deals)} />
          <Tile label="Conversion applied" value={`${fc.conversion_rate}%`} />
        </div>
      ) : tab === 'heatmap' && hm ? (
        <div className={`${card} overflow-x-auto`}>
          <p className="text-xs font-semibold text-slate-400 mb-3">Leads created · weekday × hour {hm.peak.count > 0 && <span className="text-slate-500">· peak {hm.peak.weekday_label} {hm.peak.hour}:00 ({hm.peak.count})</span>}</p>
          {(() => { const max = Math.max(1, ...hm.grid.flat()); return (
            <table className="text-[9px] border-separate" style={{ borderSpacing: 2 }}>
              <thead><tr><th></th>{Array.from({ length: 24 }).map((_, h) => <th key={h} className="text-slate-600 font-normal w-4">{h % 3 === 0 ? h : ''}</th>)}</tr></thead>
              <tbody>
                {hm.grid.map((row, wd) => (
                  <tr key={wd}><td className="text-slate-500 pr-1 text-right">{hm.weekdays[wd]}</td>
                    {row.map((v, h) => <td key={h} title={`${hm.weekdays[wd]} ${h}:00 — ${v} lead(s), ${hm.won_grid[wd][h]} won`} style={{ background: heatColor(v, max), width: 14, height: 14 }} className="rounded-sm"></td>)}
                  </tr>
                ))}
              </tbody>
            </table>
          ); })()}
        </div>
      ) : null}
    </div>
  );
};
