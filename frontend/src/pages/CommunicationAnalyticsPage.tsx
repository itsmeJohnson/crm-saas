import React, { useCallback, useEffect, useState } from 'react';
import {
  BarChart3, Loader2, Download, Filter, PhoneCall, MessageSquare, MessageCircle, Mail,
  Timer, Clock, PhoneMissed, Trophy, Users, Flame,
} from 'lucide-react';
import {
  commAnalyticsApi, CommFilters, Overview, ChannelBreakdown, AgentPerformance,
  ResponseTime, TalkTime, Missed, Conversion, EngagementItem, Heatmap,
} from '../services/commAnalyticsApi';

const CHANNEL_ICON: Record<string, any> = { Call: PhoneCall, SMS: MessageSquare, WhatsApp: MessageCircle, Email: Mail };
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];

const fmtDur = (s: number) => (s >= 60 ? `${Math.floor(s / 60)}m ${s % 60}s` : `${s}s`);

const Bars: React.FC<{ title: string; buckets: { label: string; count: number }[] }> = ({ title, buckets }) => {
  const max = Math.max(1, ...buckets.map((b) => b.count));
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <h3 className="text-sm font-semibold text-slate-200 mb-4">{title}</h3>
      {buckets.length === 0 ? <p className="text-xs text-slate-500">No data.</p> : (
        <ul className="space-y-3">{[...buckets].sort((a, b) => b.count - a.count).map((b) => (
          <li key={b.label}><div className="flex justify-between text-xs mb-1"><span className="text-slate-300">{b.label}</span><span className="text-slate-400">{b.count}</span></div>
            <div className="h-1.5 bg-slate-800/60 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-brand-500 to-indigo-500 rounded-full" style={{ width: `${(b.count / max) * 100}%` }} /></div></li>
        ))}</ul>
      )}
    </div>
  );
};

const HeatGrid: React.FC<{ data: Heatmap }> = ({ data }) => {
  const max = Math.max(1, ...data.grid.flat());
  const color = (v: number) => v === 0 ? 'bg-slate-900/40' : `bg-brand-500`;
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 overflow-x-auto">
      <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2"><Flame className="w-4 h-4 text-amber-400" /> Heatmap (weekday × hour)</h3>
      <div className="inline-block">
        <div className="flex gap-0.5 ml-8 mb-1">
          {Array.from({ length: 24 }).map((_, h) => <div key={h} className="w-3.5 text-[8px] text-slate-600 text-center">{h % 6 === 0 ? h : ''}</div>)}
        </div>
        {data.grid.map((row, wd) => (
          <div key={wd} className="flex gap-0.5 items-center mb-0.5">
            <span className="w-7 text-[10px] text-slate-500">{DAYS[wd]}</span>
            {row.map((v, h) => (
              <div key={h} title={`${DAYS[wd]} ${h}:00 — ${v}`} className={`w-3.5 h-3.5 rounded-sm ${color(v)}`}
                   style={{ opacity: v === 0 ? 1 : 0.25 + 0.75 * (v / max) }} />
            ))}
          </div>
        ))}
      </div>
      <p className="text-[11px] text-slate-500 mt-2">Peak: {DAYS[data.peak.weekday]} {data.peak.hour}:00 ({data.peak.count})</p>
    </div>
  );
};

export const CommunicationAnalyticsPage: React.FC = () => {
  const [filters, setFilters] = useState<CommFilters>({});
  const [range, setRange] = useState('30');
  const [loading, setLoading] = useState(true);

  const [overview, setOverview] = useState<Overview | null>(null);
  const [channels, setChannels] = useState<ChannelBreakdown[]>([]);
  const [agents, setAgents] = useState<AgentPerformance[]>([]);
  const [resp, setResp] = useState<ResponseTime | null>(null);
  const [talk, setTalk] = useState<TalkTime | null>(null);
  const [missed, setMissed] = useState<Missed | null>(null);
  const [conv, setConv] = useState<Conversion | null>(null);
  const [engagement, setEngagement] = useState<EngagementItem[]>([]);
  const [heatmap, setHeatmap] = useState<Heatmap | null>(null);

  const load = useCallback(async () => {
    setLoading(true);
    const days = range === 'all' ? 0 : parseInt(range, 10);
    const f: CommFilters = { ...filters };
    if (days) f.date_from = new Date(Date.now() - days * 864e5).toISOString();
    try {
      const [ov, ch, ag, rt, tt, ms, cv, en, hm] = await Promise.all([
        commAnalyticsApi.overview(f), commAnalyticsApi.byChannel(f), commAnalyticsApi.agents(f),
        commAnalyticsApi.responseTime(f), commAnalyticsApi.talkTime(f), commAnalyticsApi.missed(f),
        commAnalyticsApi.conversion(f), commAnalyticsApi.engagement(f), commAnalyticsApi.heatmap(f),
      ]);
      setOverview(ov); setChannels(ch); setAgents(ag); setResp(rt); setTalk(tt);
      setMissed(ms); setConv(cv); setEngagement(en); setHeatmap(hm);
    } finally { setLoading(false); }
  }, [filters, range]);

  useEffect(() => { load(); }, [load]);

  const doExport = async () => {
    const days = range === 'all' ? 0 : parseInt(range, 10);
    const f: CommFilters = { ...filters };
    if (days) f.date_from = new Date(Date.now() - days * 864e5).toISOString();
    const blob = await commAnalyticsApi.exportCsv(f);
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = 'communication-analytics.csv'; a.click();
    URL.revokeObjectURL(url);
  };

  const kpis = overview && resp && talk && missed && conv ? [
    { label: 'Total Comms', value: String(overview.total), icon: BarChart3, color: 'text-brand-400' },
    { label: 'Delivery Rate', value: `${overview.delivery_rate}%`, icon: MessageSquare, color: 'text-emerald-400' },
    { label: 'Avg Response', value: fmtDur(resp.avg_response_seconds), icon: Timer, color: 'text-sky-400' },
    { label: 'Avg Talk Time', value: fmtDur(talk.avg_talk_seconds), icon: Clock, color: 'text-indigo-400' },
    { label: 'Missed', value: String(missed.total_missed), icon: PhoneMissed, color: 'text-red-400' },
    { label: 'Conversion', value: `${conv.conversion_rate}%`, icon: Trophy, color: 'text-amber-400' },
  ] : [];

  return (
    <div className="space-y-5">
      <div className="border-b border-slate-800/60 pb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <BarChart3 className="w-7 h-7 text-brand-400" /> Communication Analytics
          </h1>
          <p className="text-sm text-slate-400 mt-1">Cross-channel volume, agent performance, engagement &amp; conversion.</p>
        </div>
        <button onClick={doExport} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-2 px-3 rounded-lg text-sm cursor-pointer"><Download className="w-4 h-4" /> Export CSV</button>
      </div>

      {/* Filters */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-4 flex flex-wrap items-center gap-3">
        <Filter className="w-4 h-4 text-slate-500" />
        <select value={filters.channel || ''} onChange={(e) => setFilters((f) => ({ ...f, channel: e.target.value || undefined }))} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
          <option value="">All channels</option>{['Call', 'SMS', 'WhatsApp', 'Email'].map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={filters.direction || ''} onChange={(e) => setFilters((f) => ({ ...f, direction: e.target.value || undefined }))} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
          <option value="">All directions</option><option value="OUTBOUND">Outbound</option><option value="INBOUND">Inbound</option>
        </select>
        <select value={range} onChange={(e) => setRange(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
          {[['7', 'Last 7 days'], ['30', 'Last 30 days'], ['90', 'Last 90 days'], ['all', 'All time']].map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>

      {loading ? <div className="py-24 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          <div className="grid grid-cols-2 lg:grid-cols-6 gap-4">
            {kpis.map((k) => (
              <div key={k.label} className="glass-panel border border-slate-800/85 rounded-2xl p-4">
                <div className="flex items-center gap-1.5 mb-1"><k.icon className={`w-4 h-4 ${k.color}`} /><span className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{k.label}</span></div>
                <p className="text-lg font-bold text-slate-100">{k.value}</p>
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {overview && <Bars title="By Channel" buckets={overview.by_channel} />}
            {overview && <Bars title="By Direction" buckets={overview.by_direction} />}
          </div>

          {/* Per-channel table */}
          <div className="glass-panel border border-slate-800/85 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800/60"><h3 className="text-sm font-semibold text-slate-200">Channel breakdown</h3></div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-800/80">
                  {['Channel', 'Total', 'Out', 'In', 'Delivered', 'Failed', 'Opened', 'Avg Talk'].map((h) => <th key={h} className="px-4 py-2 font-semibold">{h}</th>)}
                </tr></thead>
                <tbody>
                  {channels.filter((c) => c.total > 0).map((c) => {
                    const Icon = CHANNEL_ICON[c.channel] || MessageSquare;
                    return (
                      <tr key={c.channel} className="border-b border-slate-800/40">
                        <td className="px-4 py-2 text-slate-200 flex items-center gap-2"><Icon className="w-3.5 h-3.5 text-slate-400" /> {c.channel}</td>
                        <td className="px-4 py-2 text-slate-300">{c.total}</td>
                        <td className="px-4 py-2 text-slate-400">{c.outbound}</td>
                        <td className="px-4 py-2 text-slate-400">{c.inbound}</td>
                        <td className="px-4 py-2 text-emerald-400">{c.delivery_rate}%</td>
                        <td className="px-4 py-2 text-red-400">{c.failed}</td>
                        <td className="px-4 py-2 text-sky-400">{c.channel === 'Email' ? `${c.open_rate}%` : '—'}</td>
                        <td className="px-4 py-2 text-slate-400">{c.channel === 'Call' ? fmtDur(c.avg_talk_time) : '—'}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>

          {/* Agents */}
          <div className="glass-panel border border-slate-800/85 rounded-2xl overflow-hidden">
            <div className="px-4 py-3 border-b border-slate-800/60"><h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Users className="w-4 h-4 text-brand-400" /> Agent performance</h3></div>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead><tr className="text-left text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-800/80">
                  {['Agent', 'Total', 'Out', 'In', 'Calls', 'Avg Talk', 'Avg Response', 'Failed'].map((h) => <th key={h} className="px-4 py-2 font-semibold">{h}</th>)}
                </tr></thead>
                <tbody>
                  {agents.length === 0 ? <tr><td colSpan={8} className="px-4 py-6 text-center text-xs text-slate-500">No agent activity.</td></tr>
                    : agents.map((a) => (
                      <tr key={a.agent_id} className="border-b border-slate-800/40">
                        <td className="px-4 py-2 text-slate-200">{a.agent_name}</td>
                        <td className="px-4 py-2 text-slate-300">{a.total}</td>
                        <td className="px-4 py-2 text-slate-400">{a.outbound}</td>
                        <td className="px-4 py-2 text-slate-400">{a.inbound}</td>
                        <td className="px-4 py-2 text-slate-400">{a.calls}</td>
                        <td className="px-4 py-2 text-indigo-400">{fmtDur(a.avg_talk_time)}</td>
                        <td className="px-4 py-2 text-sky-400">{a.avg_response_seconds ? fmtDur(a.avg_response_seconds) : '—'}</td>
                        <td className="px-4 py-2 text-red-400">{a.failed}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            </div>
          </div>

          {heatmap && <HeatGrid data={heatmap} />}

          {/* Engagement */}
          <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
            <h3 className="text-sm font-semibold text-slate-200 mb-4 flex items-center gap-2"><Trophy className="w-4 h-4 text-amber-400" /> Most engaged</h3>
            {engagement.length === 0 ? <p className="text-xs text-slate-500">No engagement yet.</p> : (
              <ul className="space-y-2">
                {engagement.map((e) => (
                  <li key={`${e.entity_type}-${e.entity_id}`} className="flex items-center gap-3 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                    <span className="text-sm text-slate-200 flex-1 truncate">{e.name} <span className="text-[10px] text-slate-500">· {e.entity_type}</span></span>
                    <span className="text-xs text-slate-400">{e.channels.join(', ')}</span>
                    <span className="text-xs text-slate-300"><b>{e.interactions}</b> touches</span>
                  </li>
                ))}
              </ul>
            )}
          </div>
        </>
      )}
    </div>
  );
};
