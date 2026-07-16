import React, { useCallback, useEffect, useState } from 'react';
import {
  LineChart, Loader2, Download, GitCompareArrows, CalendarRange, Target, GitBranch, CheckCircle2,
} from 'lucide-react';
import {
  forecastingApi as api, Forecast, Scenario, Seasonality, TrendAnalysis, HistoricalComparison,
  PipelineForecast, GoalForecast, FORECAST_METRICS, FORECAST_METHODS, FORECAST_GRANULARITIES,
} from '../services/forecastingApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const numf = (n: any) => (typeof n === 'number' ? Math.round(n).toLocaleString() : '—');
const dirTone = (d: string) => (d === 'up' ? 'text-emerald-400' : d === 'down' ? 'text-red-400' : 'text-slate-400');
const dirArrow = (d: string) => (d === 'up' ? '↑' : d === 'down' ? '↓' : '→');

const Tile: React.FC<{ label: string; value: React.ReactNode; tone?: string }> = ({ label, value, tone }) => (
  <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{label}</p><p className={`text-xl font-bold mt-1 ${tone || 'text-slate-100'}`}>{value}</p></div>
);

type Tab = 'forecast' | 'scenario' | 'seasonality' | 'accuracy' | 'pipeline' | 'goals';

export const ForecastingPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('forecast');
  const [metric, setMetric] = useState('revenue');
  const [method, setMethod] = useState('linear');
  const [granularity, setGranularity] = useState('monthly');
  const [periods, setPeriods] = useState(6);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const [fc, setFc] = useState<Forecast | null>(null);
  const [sc, setSc] = useState<Scenario | null>(null);
  const [seas, setSeas] = useState<Seasonality | null>(null);
  const [tr, setTr] = useState<TrendAnalysis | null>(null);
  const [hc, setHc] = useState<HistoricalComparison | null>(null);
  const [pf, setPf] = useState<PipelineForecast | null>(null);
  const [gf, setGf] = useState<GoalForecast | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    const p = { metric, method, granularity, periods };
    try {
      if (tab === 'forecast') setFc(await api.forecast(p));
      else if (tab === 'scenario') setSc(await api.scenario(p));
      else if (tab === 'seasonality') { setSeas(await api.seasonality({ metric, granularity })); setTr(await api.trend({ metric, granularity })); }
      else if (tab === 'accuracy') setHc(await api.historicalComparison({ metric, granularity }));
      else if (tab === 'pipeline') setPf(await api.pipeline({ periods, granularity }));
      else if (tab === 'goals') setGf(await api.goals());
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load forecast.')); } finally { setLoading(false); }
  }, [tab, metric, method, granularity, periods]);
  useEffect(() => { load(); }, [load]);

  const exportCsv = async () => {
    try { const b = await api.exportCsv({ metric, method, granularity, periods }); const u = URL.createObjectURL(b); const a = document.createElement('a'); a.href = u; a.download = 'forecast.csv'; a.click(); URL.revokeObjectURL(u); }
    catch (e) { setErr(extractErrorMessage(e, 'Export failed.')); }
  };

  const TABS: [Tab, string, any][] = [
    ['forecast', 'Forecast', LineChart], ['scenario', 'Scenarios', GitCompareArrows], ['seasonality', 'Seasonality & Trend', CalendarRange],
    ['accuracy', 'Accuracy', Target], ['pipeline', 'Pipeline', GitBranch], ['goals', 'Goals', CheckCircle2],
  ];

  // combined history+forecast bar chart
  const Chart: React.FC<{ f: Forecast }> = ({ f }) => {
    const all = [...f.history.map((h) => ({ ...h, kind: 'h' as const })), ...f.forecast.map((p) => ({ bucket: p.bucket, value: p.value, kind: 'f' as const }))];
    const shown = all.slice(-24);
    const max = Math.max(1, ...shown.map((p) => p.value));
    return (
      <div className="flex items-end gap-1 h-40 overflow-x-auto pb-1">
        {shown.map((p, i) => (
          <div key={i} className="flex flex-col items-center justify-end gap-1 min-w-[16px] flex-1" title={`${p.bucket}: ${numf(p.value)}`}>
            <div className={`w-full rounded-t ${p.kind === 'f' ? 'bg-brand-500/40 border border-brand-400/50 border-dashed' : 'bg-brand-500/70'}`} style={{ height: `${(p.value / max) * 100}%` }} />
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="space-y-5">
      <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><LineChart className="w-6 h-6 text-brand-400" /> Forecasting Engine</h1>
          <p className="text-sm text-slate-500 mt-1">Project revenue, sales, leads, collections, staff, pipeline and goals — with scenarios, seasonality and accuracy.</p>
        </div>
        <button onClick={exportCsv} className="px-3 py-1.5 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5 w-fit"><Download className="w-3.5 h-3.5" /> Export</button>
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <select value={metric} onChange={(e) => setMetric(e.target.value)} className={F}>{FORECAST_METRICS.map((m) => <option key={m} value={m}>{m}</option>)}</select>
        <select value={granularity} onChange={(e) => setGranularity(e.target.value)} className={F}>{FORECAST_GRANULARITIES.map((g) => <option key={g} value={g}>{g}</option>)}</select>
        {(tab === 'forecast' || tab === 'scenario' || tab === 'pipeline') && (
          <select value={periods} onChange={(e) => setPeriods(Number(e.target.value))} className={F}>{[3, 6, 9, 12].map((n) => <option key={n} value={n}>{n} periods</option>)}</select>
        )}
        {(tab === 'forecast' || tab === 'scenario') && (
          <select value={method} onChange={(e) => setMethod(e.target.value)} className={F}>{FORECAST_METHODS.map((m) => <option key={m} value={m}>{m.replace('_', ' ')}</option>)}</select>
        )}
      </div>

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {TABS.map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {label}</button>
        ))}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      {loading ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'forecast' && fc ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tile label={`Forecast total (${periods})`} value={numf(fc.total_forecast)} tone="text-brand-300" />
            <Tile label="History avg" value={numf(fc.history_avg)} />
            <Tile label="Trend" value={<span className={dirTone(fc.trend.direction)}>{dirArrow(fc.trend.direction)} {fc.trend.direction}</span>} />
            <Tile label="Growth rate" value={`${fc.trend.growth_rate}%`} tone={dirTone(fc.trend.direction)} />
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-3">{metric} · actual (solid) vs forecast (dashed)</p>
            <Chart f={fc} />
          </div>
          <div className={`${card} overflow-x-auto`}>
            <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Period</th><th className="text-right px-2">Forecast</th><th className="text-right px-2">Low</th><th className="text-right px-2">High</th></tr></thead>
              <tbody>{fc.forecast.map((p) => <tr key={p.bucket} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{p.bucket}</td><td className="text-right px-2 font-semibold">{numf(p.value)}</td><td className="text-right px-2 text-slate-500">{numf(p.lower)}</td><td className="text-right px-2 text-slate-500">{numf(p.upper)}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      ) : tab === 'scenario' && sc ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <Tile label="Pessimistic (−15%)" value={numf(sc.scenarios.pessimistic.total)} tone="text-red-400" />
            <Tile label="Base" value={numf(sc.scenarios.base.total)} tone="text-slate-100" />
            <Tile label="Optimistic (+15%)" value={numf(sc.scenarios.optimistic.total)} tone="text-emerald-400" />
          </div>
          <div className={`${card} overflow-x-auto`}>
            <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Period</th><th className="text-right px-2">Pessimistic</th><th className="text-right px-2">Base</th><th className="text-right px-2">Optimistic</th></tr></thead>
              <tbody>{sc.scenarios.base.series.map((b, i) => <tr key={b.bucket} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{b.bucket}</td><td className="text-right px-2 text-red-400">{numf(sc.scenarios.pessimistic.series[i]?.value)}</td><td className="text-right px-2">{numf(b.value)}</td><td className="text-right px-2 text-emerald-400">{numf(sc.scenarios.optimistic.series[i]?.value)}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      ) : tab === 'seasonality' && seas && tr ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            <Tile label="Direction" value={<span className={dirTone(tr.direction)}>{dirArrow(tr.direction)} {tr.direction}</span>} />
            <Tile label="Growth rate" value={`${tr.growth_rate}%`} />
            <Tile label="Peak period" value={seas.peak ? `${seas.peak.label} (${seas.peak.index})` : '—'} tone="text-emerald-400" />
            <Tile label="Trough period" value={seas.trough ? `${seas.trough.label} (${seas.trough.index})` : '—'} />
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 mb-3">Seasonal index (1.0 = average)</p>
            <div className="space-y-1.5">
              {seas.indices.map((r) => (
                <div key={r.label} className="flex items-center gap-2">
                  <span className="text-[11px] text-slate-400 w-12">{r.label}</span>
                  <div className="flex-1 h-2.5 bg-slate-800/60 rounded relative">
                    <div className={`h-2.5 rounded ${r.index >= 1 ? 'bg-emerald-500/60' : 'bg-amber-500/60'}`} style={{ width: `${Math.min(100, r.index * 50)}%` }} />
                  </div>
                  <span className="text-[11px] text-slate-300 w-10 text-right">{r.index}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      ) : tab === 'accuracy' && hc ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Tile label="Forecast accuracy" value={hc.accuracy != null ? `${hc.accuracy}%` : '—'} tone={hc.accuracy != null && hc.accuracy >= 80 ? 'text-emerald-400' : 'text-amber-400'} />
            <Tile label="MAPE (error)" value={hc.mape != null ? `${hc.mape}%` : '—'} />
          </div>
          {hc.note ? <p className="text-xs text-slate-500">{hc.note}</p> : (
            <div className={`${card} overflow-x-auto`}>
              <p className="text-xs font-semibold text-slate-400 mb-2">Backtest: forecast vs actual</p>
              <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Period</th><th className="text-right px-2">Actual</th><th className="text-right px-2">Forecast</th><th className="text-right px-2">Error</th></tr></thead>
                <tbody>{hc.comparison.map((r) => <tr key={r.bucket} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{r.bucket}</td><td className="text-right px-2">{numf(r.actual)}</td><td className="text-right px-2">{numf(r.forecast)}</td><td className="text-right px-2 text-amber-400">{r.error_pct}%</td></tr>)}</tbody>
              </table>
            </div>
          )}
        </div>
      ) : tab === 'pipeline' && pf ? (
        <div className="space-y-3">
          <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
            <Tile label="Open pipeline" value={`₹${numf(pf.open_pipeline_value)}`} />
            <Tile label="Conversion rate" value={`${pf.conversion_rate}%`} />
            <Tile label="Expected close" value={`₹${numf(pf.expected_close_total)}`} tone="text-emerald-400" />
          </div>
          <div className={`${card} overflow-x-auto`}>
            <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Period</th><th className="text-right px-2">Projected close</th></tr></thead>
              <tbody>{pf.forecast.map((b) => <tr key={b.bucket} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{b.bucket}</td><td className="text-right px-2 font-semibold">₹{numf(b.value)}</td></tr>)}</tbody>
            </table>
          </div>
        </div>
      ) : tab === 'goals' && gf ? (
        <div className="space-y-3">
          <div className="grid grid-cols-3 gap-3">
            <Tile label="Targets" value={gf.total} />
            <Tile label="On track" value={gf.on_track} tone="text-emerald-400" />
            <Tile label="At risk" value={gf.at_risk} tone={gf.at_risk ? 'text-red-400' : undefined} />
          </div>
          <div className={`${card} overflow-x-auto`}>
            {gf.targets.length === 0 ? <p className="text-xs text-slate-500">No active targets.</p> : (
              <table className="w-full text-xs"><thead className="text-slate-500"><tr><th className="text-left py-1">Metric</th><th className="text-right px-2">Target</th><th className="text-right px-2">Actual</th><th className="text-right px-2">Progress</th><th className="text-right px-2">Projected</th><th className="text-right px-2">Status</th></tr></thead>
                <tbody>{gf.targets.map((t: any) => <tr key={t.target_id} className="border-t border-slate-800/60 text-slate-300"><td className="py-1">{String(t.metric_type).replace('MetricType.', '')}</td><td className="text-right px-2">{numf(t.target_value)}</td><td className="text-right px-2">{numf(t.actual_value)}</td><td className="text-right px-2">{t.progress_pct}%</td><td className="text-right px-2">{t.projected_attainment}%</td><td className={`text-right px-2 ${t.on_track ? 'text-emerald-400' : 'text-red-400'}`}>{t.on_track ? 'on track' : 'at risk'}</td></tr>)}</tbody>
              </table>
            )}
          </div>
        </div>
      ) : null}
    </div>
  );
};
