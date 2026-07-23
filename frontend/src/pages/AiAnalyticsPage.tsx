import React, { useCallback, useEffect, useState } from 'react';
import {
  BarChart3, Loader2, Download, LayoutDashboard, Gauge, Timer, Users,
  Layers, Wand2, Cpu,
} from 'lucide-react';
import {
  aiAnalyticsApi as api, AiaDashboard, AiaLatency, AiaQuality, AiaUserAdoption,
  AiaFeatureAdoption, AiaPromptPerformance, AiaModelPerformance, QUALITY_TONE,
} from '../services/aiAnalyticsApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';

const Stat: React.FC<{ label: string; value: React.ReactNode; sub?: string; tone?: string }> =
  ({ label, value, sub, tone }) => (
    <div className={card}>
      <p className="text-[10px] font-semibold text-slate-500 uppercase">{label}</p>
      <p className={`text-xl font-bold mt-1 ${tone || 'text-slate-100'}`}>{value}</p>
      {sub && <p className="text-[10px] text-slate-500 mt-0.5">{sub}</p>}
    </div>
  );

export const AiAnalyticsPage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<'dashboard' | 'quality' | 'latency' | 'adoption' | 'prompts' | 'models'>('dashboard');
  const [days, setDays] = useState(30);
  const [dash, setDash] = useState<AiaDashboard | null>(null);
  const [quality, setQuality] = useState<AiaQuality | null>(null);
  const [latency, setLatency] = useState<AiaLatency | null>(null);
  const [users, setUsers] = useState<AiaUserAdoption | null>(null);
  const [features, setFeatures] = useState<AiaFeatureAdoption | null>(null);
  const [prompts, setPrompts] = useState<AiaPromptPerformance | null>(null);
  const [models, setModels] = useState<AiaModelPerformance | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'dashboard') setDash(await api.dashboard(days));
      if (tab === 'quality') setQuality(await api.quality(days));
      if (tab === 'latency') setLatency(await api.latency(days));
      if (tab === 'adoption') { setUsers(await api.userAdoption(days)); setFeatures(await api.featureAdoption(days)); }
      if (tab === 'prompts') setPrompts(await api.promptPerformance(days));
      if (tab === 'models') setModels(await api.modelPerformance(days));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load AI analytics.')); } finally { setLoading(false); }
  }, [tab, days]);
  useEffect(() => { load(); }, [load]);

  if (!isManager) return <div className="text-sm text-slate-400">AI Analytics is available to managers and admins.</div>;

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><BarChart3 className="w-6 h-6 text-brand-400" /> AI Analytics</h1>
          <p className="text-sm text-slate-500 mt-1">Usage, tokens, cost, latency, quality, adoption and per-prompt / per-model performance across every AI call.</p>
        </div>
        <div className="flex items-center gap-2">
          <select value={days} onChange={e => setDays(parseInt(e.target.value))} className={F}>
            {[7, 30, 90, 180, 365].map(d => <option key={d} value={d}>Last {d} days</option>)}
          </select>
          <button onClick={async () => { try { const t = await api.exportCsv(days); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t], { type: 'text/csv' })); a.download = 'ai-analytics.csv'; a.click(); URL.revokeObjectURL(a.href); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>
        </div>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['quality', 'Quality', Gauge], ['latency', 'Latency', Timer], ['adoption', 'Adoption', Users], ['prompts', 'Prompts', Wand2], ['models', 'Models', Cpu]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {tab === 'dashboard' && dash && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                <Stat label="Requests" value={dash.requests} />
                <Stat label="Tokens" value={dash.tokens.toLocaleString()} />
                <Stat label="Cost" value={`$${dash.cost_usd}`} />
                <Stat label="Success" value={`${dash.success_rate}%`} tone="text-emerald-400" sub={`${dash.failure_rate}% failed`} />
                <Stat label="Avg / p95 Latency" value={`${dash.avg_latency_ms}ms`} sub={`p95 ${dash.p95_latency_ms}ms`} />
                <Stat label="Quality" value={dash.quality_score} tone={QUALITY_TONE[dash.quality_band]} sub={dash.quality_band} />
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Top Features</h3>
                  {dash.top_features.map(f => (
                    <div key={f.feature} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300">{f.feature}</span>
                      <span className="text-slate-400">{f.requests} · {f.share_pct}%</span>
                    </div>
                  ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Top Models</h3>
                  {dash.top_models.map(m => (
                    <div key={`${m.provider}:${m.model}`} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300">{m.provider}/{m.model}</span>
                      <span className="text-slate-400">{m.requests} · {m.success_rate}% · {m.avg_latency_ms}ms</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {tab === 'quality' && quality && (
            <div className="space-y-4">
              <div className={card}>
                <div className="flex items-center justify-between">
                  <div>
                    <h3 className="text-xs font-bold text-slate-300">Response Quality Score</h3>
                    <p className="text-[11px] text-slate-500 mt-1 max-w-2xl">{quality.note}</p>
                  </div>
                  <span className={`text-4xl font-bold ${QUALITY_TONE[quality.band]}`}>{quality.quality_score}</span>
                </div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Components (weighted)</h3>
                  {Object.entries(quality.components).map(([k, v]) => (
                    <div key={k} className="py-1.5 border-b border-slate-800/60 last:border-0">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-300">{k.replace(/_/g, ' ')} <span className="text-slate-600">×{quality.weights[k]}</span></span>
                        <span className="text-slate-200 font-semibold">{v}%</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div className={`h-full ${v >= 90 ? 'bg-emerald-400' : v >= 75 ? 'bg-amber-400' : 'bg-red-400'}`} style={{ width: `${v}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Signals ({quality.sample_size} calls)</h3>
                  {Object.entries(quality.signals).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300">{k.replace(/_/g, ' ')}</span>
                      <span className={v > 0 ? 'text-amber-400' : 'text-emerald-400'}>{v}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {tab === 'latency' && latency && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                <Stat label="Avg" value={`${latency.avg_ms}ms`} />
                <Stat label="p50" value={`${latency.p50_ms}ms`} />
                <Stat label="p95" value={`${latency.p95_ms}ms`} />
                <Stat label="p99" value={`${latency.p99_ms}ms`} />
                <Stat label="Max" value={`${latency.max_ms}ms`} />
                <Stat label="Within SLA" value={`${latency.within_sla_rate}%`} sub={`SLA ${latency.sla_ms}ms`} tone={latency.within_sla_rate >= 95 ? 'text-emerald-400' : 'text-amber-400'} />
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Slowest Models</h3>
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70"><th className="py-2 pr-2">Model</th><th className="pr-2">Avg</th><th className="pr-2">p95</th><th className="pr-2">Samples</th></tr></thead>
                  <tbody>{latency.slowest_models.map(m => (
                    <tr key={m.model} className="border-b border-slate-800/50 last:border-0">
                      <td className="py-2 pr-2 text-slate-200">{m.model}</td>
                      <td className="pr-2 text-slate-400">{m.avg_ms}ms</td>
                      <td className="pr-2 text-slate-400">{m.p95_ms}ms</td>
                      <td className="pr-2 text-slate-500">{m.samples}</td>
                    </tr>))}</tbody>
                </table>
              </div>
            </div>
          )}

          {tab === 'adoption' && users && features && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
                <Stat label="Adoption Rate" value={`${users.adoption_rate}%`} tone="text-emerald-400" sub={`${users.ai_users}/${users.total_active_users} users`} />
                <Stat label="Non-adopters" value={users.non_adopters} tone={users.non_adopters > 0 ? 'text-amber-400' : undefined} />
                <Stat label="Avg Calls / User" value={users.avg_requests_per_ai_user} />
                <Stat label="Features Used" value={features.features_used} sub={`most: ${features.most_used || '—'}`} />
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Users className="w-3.5 h-3.5 text-brand-400" /> Top Users</h3>
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70"><th className="py-2 pr-2">User</th><th className="pr-2">Calls</th><th className="pr-2">Tokens</th><th className="pr-2">Cost</th></tr></thead>
                    <tbody>{users.top_users.slice(0, 10).map(u => (
                      <tr key={u.user_id} className="border-b border-slate-800/50 last:border-0">
                        <td className="py-2 pr-2 text-slate-200">{u.user_name}</td>
                        <td className="pr-2 text-slate-400">{u.requests}</td>
                        <td className="pr-2 text-slate-400">{u.tokens.toLocaleString()}</td>
                        <td className="pr-2 text-slate-400">${u.cost_usd}</td>
                      </tr>))}</tbody>
                  </table>
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Layers className="w-3.5 h-3.5 text-brand-400" /> Feature Adoption</h3>
                  {features.features.map(f => (
                    <div key={f.feature} className="py-1.5 border-b border-slate-800/60 last:border-0">
                      <div className="flex justify-between text-xs mb-1">
                        <span className="text-slate-300">{f.feature} <span className="text-slate-600">· {f.unique_users} user(s)</span></span>
                        <span className="text-slate-400">{f.requests} ({f.share_pct}%)</span>
                      </div>
                      <div className="w-full h-1.5 bg-slate-800 rounded-full overflow-hidden">
                        <div className="h-full bg-brand-400" style={{ width: `${f.share_pct}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {tab === 'prompts' && prompts && (
            <div className={card}>
              {prompts.prompts.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No template-based AI calls in this window.</p> : (
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                    <th className="py-2 pr-2">Prompt</th><th className="pr-2">Category</th><th className="pr-2">Calls</th><th className="pr-2">Success</th><th className="pr-2">Avg Tokens</th><th className="pr-2">Cost</th><th className="pr-2">Avg / p95</th>
                  </tr></thead>
                  <tbody>{prompts.prompts.map(p => (
                    <tr key={p.template_key} className="border-b border-slate-800/50 last:border-0">
                      <td className="py-2 pr-2 text-slate-200">{p.name}<span className="block text-[10px] text-slate-600 font-mono">{p.template_key}</span></td>
                      <td className="pr-2 text-slate-400">{p.category || '—'}</td>
                      <td className="pr-2 text-slate-400">{p.requests}</td>
                      <td className="pr-2"><span className={p.success_rate >= 95 ? 'text-emerald-400' : 'text-amber-400'}>{p.success_rate}%</span></td>
                      <td className="pr-2 text-slate-400">{p.avg_tokens}</td>
                      <td className="pr-2 text-slate-400">${p.cost_usd}</td>
                      <td className="pr-2 text-slate-500">{p.avg_latency_ms} / {p.p95_latency_ms}ms</td>
                    </tr>))}</tbody>
                </table>
              )}
            </div>
          )}

          {tab === 'models' && models && (
            <div className="space-y-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Per-Model Performance</h3>
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                    <th className="py-2 pr-2">Model</th><th className="pr-2">Calls</th><th className="pr-2">Success</th><th className="pr-2">Fallbacks</th><th className="pr-2">Tokens</th><th className="pr-2">$/1k tok</th><th className="pr-2">Avg / p95</th>
                  </tr></thead>
                  <tbody>{models.models.map(m => (
                    <tr key={`${m.provider}:${m.model}`} className="border-b border-slate-800/50 last:border-0">
                      <td className="py-2 pr-2 text-slate-200">{m.model}<span className="block text-[10px] text-slate-600">{m.provider}</span></td>
                      <td className="pr-2 text-slate-400">{m.requests}</td>
                      <td className="pr-2"><span className={m.success_rate >= 95 ? 'text-emerald-400' : 'text-amber-400'}>{m.success_rate}%</span></td>
                      <td className="pr-2 text-slate-400">{m.fallback_count}</td>
                      <td className="pr-2 text-slate-400">{m.tokens.toLocaleString()}</td>
                      <td className="pr-2 text-slate-400">${m.cost_per_1k_tokens_usd}</td>
                      <td className="pr-2 text-slate-500">{m.avg_latency_ms} / {m.p95_latency_ms}ms</td>
                    </tr>))}</tbody>
                </table>
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">By Provider</h3>
                {models.by_provider.map(p => (
                  <div key={p.provider} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                    <span className="text-slate-300">{p.provider}</span>
                    <span className="text-slate-400">{p.requests} calls · {p.success_rate}% · ${p.cost}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
