import React, { useCallback, useEffect, useState } from 'react';
import {
  BarChart3, HeartPulse, Trophy, Grid3x3, TrendingUp, Building2, Users, MapPin, Download, Loader2,
} from 'lucide-react';
import {
  orgAnalyticsApi, OrgOverview, OrgHealth, OrgLeaderboardRow, OrgHeatmap, OrgTrend, ORG_METRICS,
} from '../services/orgAnalyticsApi';
import { extractErrorMessage } from '../utils/errors';

const label = (m: string) => m.replace(/_/g, ' ');
const ratingTone = (r: string) => r === 'Excellent' ? 'text-emerald-400' : r === 'Good' ? 'text-brand-300' : r === 'Fair' ? 'text-amber-400' : 'text-red-400';
const heatColor = (v: number, peak: number) => {
  if (v === 0) return 'bg-slate-900/60';
  const t = peak ? v / peak : 0;
  if (t > 0.75) return 'bg-brand-500';
  if (t > 0.5) return 'bg-brand-500/70';
  if (t > 0.25) return 'bg-brand-500/45';
  return 'bg-brand-500/25';
};

export const OrganizationAnalyticsPage: React.FC = () => {
  const today = new Date();
  const [from, setFrom] = useState(new Date(today.getFullYear(), today.getMonth(), 1).toISOString().slice(0, 10));
  const [to, setTo] = useState(today.toISOString().slice(0, 10));
  const [tab, setTab] = useState<'overview' | 'heatmap' | 'trend' | 'domains'>('overview');
  const [domainKind, setDomainKind] = useState<'department' | 'team' | 'branch' | 'territory'>('department');
  const [boardMetric, setBoardMetric] = useState('sales_revenue');

  const [ov, setOv] = useState<OrgOverview | null>(null);
  const [health, setHealth] = useState<OrgHealth | null>(null);
  const [board, setBoard] = useState<OrgLeaderboardRow[]>([]);
  const [heatmap, setHeatmap] = useState<OrgHeatmap | null>(null);
  const [trend, setTrend] = useState<OrgTrend | null>(null);
  const [domain, setDomain] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const params = useCallback(() => ({ date_from: from, date_to: to }), [from, to]);

  const loadCore = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      const [o, h, b] = await Promise.all([
        orgAnalyticsApi.overview(params()),
        orgAnalyticsApi.health(),
        orgAnalyticsApi.leaderboard({ metric: boardMetric, ...params(), limit: 10 }),
      ]);
      setOv(o); setHealth(h); setBoard(b);
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to load analytics')); } finally { setLoading(false); }
  }, [params, boardMetric]);
  useEffect(() => { loadCore(); }, [loadCore]);

  useEffect(() => {
    if (tab === 'heatmap') orgAnalyticsApi.heatmap(params()).then(setHeatmap).catch(() => {});
    if (tab === 'trend') orgAnalyticsApi.trend({ granularity: 'monthly', count: 6 }).then(setTrend).catch(() => {});
    if (tab === 'domains') orgAnalyticsApi.domain(domainKind, params()).then(setDomain).catch(() => {});
  }, [tab, domainKind, params]);

  const doExport = async () => {
    const blob = await orgAnalyticsApi.exportCsv(params());
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'organization-analytics.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const KPIS = ov ? [
    { label: 'Headcount', value: ov.headcount }, { label: 'Present today', value: `${ov.present_today} (${ov.attendance_rate}%)` },
    { label: 'On leave', value: ov.on_leave_today }, { label: 'Departments', value: ov.departments },
    { label: 'Teams', value: ov.teams }, { label: 'Branches', value: ov.branches },
    { label: 'Leads', value: ov.leads }, { label: 'Converted', value: `${ov.converted} (${ov.conversion_rate}%)` },
    { label: 'Revenue', value: `₹${Math.round(ov.revenue).toLocaleString()}` }, { label: 'Calls', value: ov.calls },
    { label: 'Tasks done', value: `${ov.tasks_completed} (${ov.task_completion_rate}%)` }, { label: 'Pending leaves', value: ov.pending_leaves },
  ] : [];

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><BarChart3 className="w-5 h-5 text-brand-400" /> Organization Analytics</h1>
        <div className="flex items-center gap-2">
          <input type="date" value={from} onChange={(e) => setFrom(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs" />
          <span className="text-slate-500 text-xs">→</span>
          <input type="date" value={to} onChange={(e) => setTo(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs" />
          <button onClick={doExport} className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 cursor-pointer px-2.5 py-1.5 border border-slate-800 rounded-lg"><Download className="w-3.5 h-3.5" /> Export</button>
        </div>
      </div>

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      {/* Health + KPI band */}
      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 flex flex-col items-center justify-center">
          <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><HeartPulse className="w-3.5 h-3.5 text-brand-400" /> Org Health</p>
          {health ? (
            <>
              <p className="text-4xl font-extrabold text-slate-100 mt-2">{health.score}%</p>
              <p className={`text-sm font-semibold mt-1 ${ratingTone(health.rating)}`}>{health.rating}</p>
              <div className="w-full mt-3 space-y-1.5">
                {health.components.map((c) => (
                  <div key={c.name}>
                    <div className="flex items-center justify-between text-[10px] text-slate-500"><span>{c.name}</span><span>{c.score}%</span></div>
                    <div className="h-1 bg-slate-800 rounded-full overflow-hidden"><div className="h-full bg-brand-500" style={{ width: `${Math.min(100, c.score)}%` }} /></div>
                  </div>
                ))}
              </div>
            </>
          ) : <Loader2 className="w-5 h-5 animate-spin text-slate-500 mt-4" />}
        </div>
        <div className="lg:col-span-3 grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-2">
          {loading ? <div className="col-span-full py-8 text-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin inline" /></div> : KPIS.map((k) => (
            <div key={k.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{k.label}</p>
              <p className="text-base font-bold text-slate-100 mt-0.5 truncate">{k.value}</p>
            </div>
          ))}
        </div>
      </div>

      <div className="flex gap-1 border-b border-slate-800/60 flex-wrap">
        {([['overview', 'Leaderboard', Trophy], ['heatmap', 'Activity Heatmap', Grid3x3], ['trend', 'Trends', TrendingUp], ['domains', 'Department / Team / Branch', Building2]] as const).map(([key, lbl, Icon]) => (
          <button key={key} onClick={() => setTab(key)} className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
            <Icon className="w-3.5 h-3.5" /> {lbl}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <div className="space-y-3">
          <select value={boardMetric} onChange={(e) => setBoardMetric(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs w-56">
            {ORG_METRICS.map((m) => <option key={m} value={m}>{label(m)}</option>)}
          </select>
          <div className="space-y-1.5">
            {board.map((r) => (
              <div key={r.user_id} className="flex items-center justify-between p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <div className="flex items-center gap-3">
                  <span className={`w-6 text-center font-bold ${r.rank === 1 ? 'text-amber-400' : r.rank === 2 ? 'text-slate-300' : r.rank === 3 ? 'text-orange-400' : 'text-slate-500'}`}>#{r.rank}</span>
                  <span className="text-sm text-slate-200">{r.name}</span>
                </div>
                <span className="text-sm font-semibold text-slate-100">{boardMetric.includes('revenue') || boardMetric.includes('recovery') ? `₹${Math.round(r.value).toLocaleString()}` : boardMetric.includes('rate') ? `${r.value}%` : r.value}</span>
              </div>
            ))}
            {!board.length && <p className="text-xs text-slate-500 py-6 text-center">No data.</p>}
          </div>
        </div>
      )}

      {tab === 'heatmap' && (
        <div className="glass-panel border border-slate-800/85 rounded-2xl p-4 overflow-x-auto">
          {heatmap ? (
            <>
              <p className="text-[11px] text-slate-500 mb-2">Activity by weekday × hour · peak {heatmap.peak.weekday_label} {heatmap.peak.hour}:00 ({heatmap.peak.count})</p>
              <div className="inline-block">
                <div className="flex gap-0.5 ml-8 mb-0.5">
                  {Array.from({ length: 24 }, (_, h) => <span key={h} className="w-3.5 text-[8px] text-slate-600 text-center">{h % 6 === 0 ? h : ''}</span>)}
                </div>
                {heatmap.grid.map((row, wd) => (
                  <div key={wd} className="flex gap-0.5 items-center mb-0.5">
                    <span className="w-7 text-[9px] text-slate-500">{heatmap.weekdays[wd]}</span>
                    {row.map((v, h) => (
                      <div key={h} title={`${heatmap.weekdays[wd]} ${h}:00 — ${v}`} className={`w-3.5 h-3.5 rounded-sm ${heatColor(v, heatmap.peak.count)}`} />
                    ))}
                  </div>
                ))}
              </div>
            </>
          ) : <div className="py-8 text-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin inline" /></div>}
        </div>
      )}

      {tab === 'trend' && (
        <div className="overflow-x-auto">
          {trend ? (
            <table className="w-full text-xs">
              <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
                <th className="py-2 pr-2">Period</th><th className="py-2 pr-2">Leads</th><th className="py-2 pr-2">Converted</th><th className="py-2 pr-2">Revenue</th><th className="py-2 pr-2">Activities</th><th className="py-2">Tasks done</th>
              </tr></thead>
              <tbody>
                {trend.series.map((s: any) => (
                  <tr key={s.label} className="border-t border-slate-800/50 text-slate-300">
                    <td className="py-1.5 pr-2">{s.label}</td>
                    <td className="py-1.5 pr-2">{s.leads}</td>
                    <td className="py-1.5 pr-2">{s.converted}</td>
                    <td className="py-1.5 pr-2">₹{Math.round(s.revenue).toLocaleString()}</td>
                    <td className="py-1.5 pr-2">{s.activities}</td>
                    <td className="py-1.5">{s.tasks_completed}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : <div className="py-8 text-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin inline" /></div>}
        </div>
      )}

      {tab === 'domains' && (
        <div className="space-y-3">
          <div className="flex gap-1">
            {([['department', Building2], ['team', Users], ['branch', MapPin], ['territory', MapPin]] as const).map(([k, Icon]) => (
              <button key={k} onClick={() => setDomainKind(k)} className={`px-2.5 py-1 text-xs rounded-lg border cursor-pointer capitalize inline-flex items-center gap-1 ${domainKind === k ? 'bg-brand-500/15 text-brand-300 border-brand-500/30' : 'bg-slate-800/40 text-slate-400 border-slate-700/40'}`}><Icon className="w-3 h-3" /> {k}</button>
            ))}
          </div>
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
                <th className="py-2 pr-2">Name</th><th className="py-2 pr-2">Members</th><th className="py-2 pr-2">Converted</th><th className="py-2 pr-2">Calls</th><th className="py-2 pr-2">Revenue</th><th className="py-2">Activities</th>
              </tr></thead>
              <tbody>
                {domain.map((d: any, i: number) => (
                  <tr key={d.department_id || d.team_id || d.branch_id || d.territory_id || i} className="border-t border-slate-800/50 text-slate-300">
                    <td className="py-1.5 pr-2">{d.name}</td>
                    <td className="py-1.5 pr-2">{d.member_count ?? '—'}</td>
                    <td className="py-1.5 pr-2">{d.leads_converted ?? d.converted ?? 0}</td>
                    <td className="py-1.5 pr-2">{d.calls_made ?? d.calls ?? 0}</td>
                    <td className="py-1.5 pr-2">₹{Math.round(d.revenue || 0).toLocaleString()}</td>
                    <td className="py-1.5">{d.activities ?? 0}</td>
                  </tr>
                ))}
              </tbody>
            </table>
            {!domain.length && <p className="text-xs text-slate-500 py-6 text-center">No data for this scope.</p>}
          </div>
        </div>
      )}
    </div>
  );
};
