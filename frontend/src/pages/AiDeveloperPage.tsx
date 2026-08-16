import React, { useCallback, useEffect, useState } from 'react';
import {
  Code2, Loader2, Download, LayoutDashboard, KeyRound, Webhook, BookOpen, Package,
  BarChart3, Plus, RefreshCw, Ban, Trash2, Copy, Check, Send, History, Terminal,
} from 'lucide-react';
import {
  aiDeveloperApi as api, ApiKey, DevWebhook, WebhookDelivery, DevPortal, DevDocs,
  DevAnalytics, CodeExample, SdkLanguage, ApiRequestLog, DELIVERY_TONE, statusTone,
  publicApiBaseUrl,
} from '../services/aiDeveloperApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const BTN_GHOST = 'px-2 py-1 rounded-lg text-[11px] font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 cursor-pointer flex items-center gap-1';

type Tab = 'overview' | 'keys' | 'webhooks' | 'docs' | 'sdk' | 'analytics';

const CopyBtn: React.FC<{ text: string; label?: string }> = ({ text, label }) => {
  const [done, setDone] = useState(false);
  return (
    <button onClick={() => { navigator.clipboard?.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); }}
      className={BTN_GHOST}>
      {done ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />} {label || (done ? 'Copied' : 'Copy')}
    </button>
  );
};

const Code: React.FC<{ code: string; max?: string }> = ({ code, max = 'max-h-96' }) => (
  <pre className={`text-[11px] text-slate-200 whitespace-pre-wrap bg-slate-950/50 border border-slate-800/60 rounded-lg p-3 overflow-auto ${max}`}>{code}</pre>
);

export const AiDeveloperPage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const [portal, setPortal] = useState<DevPortal | null>(null);
  const [keys, setKeys] = useState<ApiKey[]>([]);
  const [webhooks, setWebhooks] = useState<DevWebhook[]>([]);
  const [deliveries, setDeliveries] = useState<WebhookDelivery[]>([]);
  const [docs, setDocs] = useState<DevDocs | null>(null);
  const [examples, setExamples] = useState<CodeExample[]>([]);
  const [analytics, setAnalytics] = useState<DevAnalytics | null>(null);
  const [requests, setRequests] = useState<ApiRequestLog[]>([]);
  const [sdkLangs, setSdkLangs] = useState<SdkLanguage[]>([]);
  const [sdkLang, setSdkLang] = useState('python');
  const [sdkSource, setSdkSource] = useState<{ source: string; filename: string; install: string } | null>(null);

  // one-time secret reveals
  const [newKey, setNewKey] = useState<ApiKey | null>(null);
  const [newHook, setNewHook] = useState<DevWebhook | null>(null);

  const [keyForm, setKeyForm] = useState({ name: '', environment: 'live', rate_limit_per_min: 60, daily_quota: 1000, expires_in_days: '' });
  const [hookForm, setHookForm] = useState({ name: '', url: '', events: [] as string[] });
  const [showKeyForm, setShowKeyForm] = useState(false);
  const [showHookForm, setShowHookForm] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'overview') setPortal(await api.portal());
      if (tab === 'keys') setKeys(await api.listKeys());
      if (tab === 'webhooks') {
        const [w, d] = await Promise.all([api.listWebhooks(), api.deliveries({ limit: 50 })]);
        setWebhooks(w); setDeliveries(d);
      }
      if (tab === 'docs') {
        const [d, e] = await Promise.all([api.docs(), api.examples()]);
        setDocs(d); setExamples(e);
      }
      if (tab === 'sdk') setSdkLangs(await api.sdkList());
      if (tab === 'analytics') {
        const [a, r] = await Promise.all([api.analytics(30), api.requests({ limit: 50 })]);
        setAnalytics(a); setRequests(r);
      }
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load the developer portal.')); }
    finally { setLoading(false); }
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    if (tab !== 'sdk') return;
    api.sdk(sdkLang).then(setSdkSource).catch(e => setErr(extractErrorMessage(e, 'Failed to load the SDK.')));
  }, [tab, sdkLang]);

  const act = async (fn: () => Promise<any>, after?: (r: any) => void) => {
    try { const r = await fn(); after?.(r); await load(); }
    catch (e) { setErr(extractErrorMessage(e, 'Action failed.')); }
  };

  const createKey = () => act(
    () => api.createKey({
      name: keyForm.name || 'API key', environment: keyForm.environment,
      rate_limit_per_min: Number(keyForm.rate_limit_per_min), daily_quota: Number(keyForm.daily_quota),
      expires_in_days: keyForm.expires_in_days ? Number(keyForm.expires_in_days) : null,
    } as any),
    k => { setNewKey(k); setShowKeyForm(false); setKeyForm({ ...keyForm, name: '' }); });

  const createWebhook = () => act(
    () => api.createWebhook({ name: hookForm.name || 'AI webhook', url: hookForm.url, events: hookForm.events }),
    w => { setNewHook(w); setShowHookForm(false); setHookForm({ name: '', url: '', events: [] }); });

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Code2 className="w-6 h-6 text-brand-400" /> AI API &amp; SDK</h1>
          <p className="text-sm text-slate-500 mt-1">Developer portal for the public AI API — keys, scopes, rate limits, signed webhooks, official SDKs and reference docs.</p>
        </div>
        {isManager && (
          <button onClick={async () => { try { const t = await api.exportCsv(); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t], { type: 'text/csv' })); a.download = 'ai-api-usage.csv'; a.click(); URL.revokeObjectURL(a.href); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>
        )}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      {newKey?.api_key && (
        <div className="text-xs bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-2.5 space-y-1.5">
          <p className="font-semibold text-amber-300">Copy your API key now — it is never shown again.</p>
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-[11px] text-slate-200 bg-slate-950/60 rounded px-2 py-1 break-all">{newKey.api_key}</code>
            <CopyBtn text={newKey.api_key} />
            <button onClick={() => setNewKey(null)} className={BTN_GHOST}>Dismiss</button>
          </div>
        </div>
      )}
      {newHook?.secret && (
        <div className="text-xs bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-2.5 space-y-1.5">
          <p className="font-semibold text-amber-300">Signing secret — store it in your receiver to verify deliveries.</p>
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-[11px] text-slate-200 bg-slate-950/60 rounded px-2 py-1 break-all">{newHook.secret}</code>
            <CopyBtn text={newHook.secret} />
            <button onClick={() => setNewHook(null)} className={BTN_GHOST}>Dismiss</button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['overview', 'Overview', LayoutDashboard], ['keys', 'API Keys', KeyRound], ['webhooks', 'Webhooks', Webhook], ['docs', 'Documentation', BookOpen], ['sdk', 'SDKs', Package], ['analytics', 'Analytics', BarChart3]] as [Tab, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {/* ---------------- Overview ---------------- */}
          {tab === 'overview' && portal && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Active Keys</p><p className="text-xl font-bold text-slate-100 mt-1">{portal.keys_active}<span className="text-xs text-slate-500"> / {portal.keys_total}</span></p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Requests 30d</p><p className="text-xl font-bold text-slate-100 mt-1">{portal.requests_30d}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Success Rate</p><p className={`text-xl font-bold mt-1 ${portal.success_rate >= 95 ? 'text-emerald-400' : 'text-amber-400'}`}>{portal.success_rate}%</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Throttled</p><p className={`text-xl font-bold mt-1 ${portal.throttled_30d > 0 ? 'text-amber-400' : 'text-slate-100'}`}>{portal.throttled_30d}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Webhooks</p><p className="text-xl font-bold text-slate-100 mt-1">{portal.webhooks_active}<span className="text-xs text-slate-500"> / {portal.webhooks_total}</span></p></div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Terminal className="w-3.5 h-3.5 text-brand-400" /> Base URL</h3>
                  <div className="flex items-center gap-2 flex-wrap">
                    <code className="text-[11px] text-slate-200 bg-slate-950/60 rounded px-2 py-1 break-all">{portal.base_url}</code>
                    <CopyBtn text={portal.base_url} />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-2">Authenticate with <code className="text-slate-400">Authorization: Bearer &lt;key&gt;</code> or <code className="text-slate-400">X-API-Key</code>.</p>
                  <div className="mt-3 space-y-1">
                    {portal.versions.map(v => (
                      <div key={v.version} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                        <span className="text-slate-300">{v.version} <span className="text-[10px] text-emerald-400 uppercase">{v.status}</span></span>
                        <span className="text-slate-500">{v.sunset ? `sunsets ${v.sunset}` : 'no sunset'}</span>
                      </div>
                    ))}
                  </div>
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Token &amp; Cost Usage (30d)</h3>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Tokens</span><span className="text-slate-200">{portal.tokens_30d.toLocaleString()}</span></div>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Cost</span><span className="text-slate-200">${portal.cost_30d}</span></div>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Failed requests</span><span className={portal.failed_30d > 0 ? 'text-amber-400' : 'text-slate-200'}>{portal.failed_30d}</span></div>
                  <div className="flex justify-between text-xs py-1"><span className="text-slate-400">Dead-letter deliveries</span><span className={portal.dead_letter_deliveries > 0 ? 'text-red-400' : 'text-slate-200'}>{portal.dead_letter_deliveries}</span></div>
                </div>
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Scopes</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-x-6">
                  {portal.scopes.map(s => (
                    <div key={s.key} className="flex justify-between gap-3 text-xs py-1 border-b border-slate-800/60">
                      <code className="text-brand-300 shrink-0">{s.key}</code>
                      <span className="text-slate-500 text-right">{s.description}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          )}

          {/* ---------------- API Keys ---------------- */}
          {tab === 'keys' && (
            <div className="space-y-4">
              {isManager && (
                <div className={card}>
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-slate-300">Issue a key</h3>
                    <button onClick={() => setShowKeyForm(v => !v)} className={BTN}><Plus className="w-3.5 h-3.5" /> New key</button>
                  </div>
                  {showKeyForm && (
                    <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mt-3">
                      <input placeholder="Name" value={keyForm.name} onChange={e => setKeyForm({ ...keyForm, name: e.target.value })} className={F} />
                      <select value={keyForm.environment} onChange={e => setKeyForm({ ...keyForm, environment: e.target.value })} className={F}>
                        <option value="live">live</option><option value="test">test</option>
                      </select>
                      <input type="number" placeholder="Req/min" value={keyForm.rate_limit_per_min} onChange={e => setKeyForm({ ...keyForm, rate_limit_per_min: Number(e.target.value) })} className={F} />
                      <input type="number" placeholder="Daily quota" value={keyForm.daily_quota} onChange={e => setKeyForm({ ...keyForm, daily_quota: Number(e.target.value) })} className={F} />
                      <div className="flex gap-2">
                        <input type="number" placeholder="Expires (days)" value={keyForm.expires_in_days} onChange={e => setKeyForm({ ...keyForm, expires_in_days: e.target.value })} className={F} />
                        <button onClick={createKey} className={BTN}>Create</button>
                      </div>
                    </div>
                  )}
                </div>
              )}
              <div className={card}>
                {keys.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No API keys yet. Issue one to start calling the AI API.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">Name</th><th className="pr-2">Key</th><th className="pr-2">Env</th><th className="pr-2">Limits</th><th className="pr-2">Used</th><th className="pr-2">Status</th><th className="pr-2 text-right">Actions</th>
                    </tr></thead>
                    <tbody>
                      {keys.map(k => (
                        <tr key={k.id} className="border-b border-slate-800/50 last:border-0">
                          <td className="py-2 pr-2 text-slate-200">{k.name}</td>
                          <td className="pr-2"><code className="text-slate-400">{k.masked_key}</code></td>
                          <td className="pr-2 text-slate-400">{k.environment}</td>
                          <td className="pr-2 text-slate-400">{k.rate_limit_per_min}/min · {k.daily_quota}/day</td>
                          <td className="pr-2 text-slate-400">{k.use_count}</td>
                          <td className="pr-2">
                            <span className={`px-1.5 py-0.5 rounded ${k.is_active ? 'bg-emerald-500/15 text-emerald-300' : 'bg-red-500/15 text-red-300'}`}>{k.is_active ? 'active' : 'revoked'}</span>
                          </td>
                          <td className="pr-2">
                            {isManager && (
                              <div className="flex items-center justify-end gap-1">
                                <button onClick={() => act(() => api.rotateKey(k.id), setNewKey)} className={BTN_GHOST}><RefreshCw className="w-3 h-3" /> Rotate</button>
                                {k.is_active && <button onClick={() => act(() => api.revokeKey(k.id))} className={BTN_GHOST}><Ban className="w-3 h-3" /> Revoke</button>}
                                <button onClick={() => act(() => api.deleteKey(k.id))} className={BTN_GHOST}><Trash2 className="w-3 h-3" /></button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {/* ---------------- Webhooks ---------------- */}
          {tab === 'webhooks' && (
            <div className="space-y-4">
              {isManager && (
                <div className={card}>
                  <div className="flex items-center justify-between">
                    <h3 className="text-xs font-bold text-slate-300">Register an endpoint</h3>
                    <button onClick={() => setShowHookForm(v => !v)} className={BTN}><Plus className="w-3.5 h-3.5" /> New webhook</button>
                  </div>
                  {showHookForm && (
                    <div className="grid grid-cols-1 md:grid-cols-3 gap-2 mt-3">
                      <input placeholder="Name" value={hookForm.name} onChange={e => setHookForm({ ...hookForm, name: e.target.value })} className={F} />
                      <input placeholder="https://your-app.com/hooks/ai" value={hookForm.url} onChange={e => setHookForm({ ...hookForm, url: e.target.value })} className={F} />
                      <button onClick={createWebhook} className={BTN}>Create</button>
                      <p className="md:col-span-3 text-[11px] text-slate-500">Leave events unset to receive every AI event. Each delivery is signed with HMAC-SHA256 in the <code className="text-slate-400">X-CRM-AI-Signature</code> header.</p>
                    </div>
                  )}
                </div>
              )}

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Endpoints</h3>
                {webhooks.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No webhook endpoints registered.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">Name</th><th className="pr-2">URL</th><th className="pr-2">Events</th><th className="pr-2">Delivered</th><th className="pr-2">Failed</th><th className="pr-2 text-right">Actions</th>
                    </tr></thead>
                    <tbody>
                      {webhooks.map(w => (
                        <tr key={w.id} className="border-b border-slate-800/50 last:border-0">
                          <td className="py-2 pr-2 text-slate-200">{w.name}</td>
                          <td className="pr-2 text-slate-400 truncate max-w-[220px]">{w.url}</td>
                          <td className="pr-2 text-slate-400">{w.subscribes_all ? 'all' : w.events.length}</td>
                          <td className="pr-2 text-emerald-400">{w.delivered_count}</td>
                          <td className={`pr-2 ${w.failed_count > 0 ? 'text-amber-400' : 'text-slate-400'}`}>{w.failed_count}</td>
                          <td className="pr-2">
                            {isManager && (
                              <div className="flex items-center justify-end gap-1">
                                <button onClick={() => act(() => api.testWebhook(w.id))} className={BTN_GHOST}><Send className="w-3 h-3" /> Test</button>
                                <button onClick={() => act(() => api.rotateWebhookSecret(w.id), setNewHook)} className={BTN_GHOST}><RefreshCw className="w-3 h-3" /> Secret</button>
                                <button onClick={() => act(() => api.deleteWebhook(w.id))} className={BTN_GHOST}><Trash2 className="w-3 h-3" /></button>
                              </div>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><History className="w-3.5 h-3.5" /> Recent Deliveries</h3>
                {deliveries.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No deliveries yet.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">When</th><th className="pr-2">Event</th><th className="pr-2">Status</th><th className="pr-2">Attempts</th><th className="pr-2">Code</th><th className="pr-2 text-right">Actions</th>
                    </tr></thead>
                    <tbody>
                      {deliveries.map(d => (
                        <tr key={d.id} className="border-b border-slate-800/50 last:border-0">
                          <td className="py-2 pr-2 text-slate-400">{d.created_at ? new Date(d.created_at).toLocaleString() : '—'}</td>
                          <td className="pr-2 text-slate-300">{d.event_type}</td>
                          <td className="pr-2"><span className={`px-1.5 py-0.5 rounded ${DELIVERY_TONE[d.status] || ''}`}>{d.status.replace('_', ' ')}</span></td>
                          <td className="pr-2 text-slate-400">{d.attempts}</td>
                          <td className="pr-2 text-slate-400">{d.response_code ?? '—'}</td>
                          <td className="pr-2 text-right">
                            {isManager && d.status !== 'success' && (
                              <button onClick={() => act(() => api.replayDelivery(d.id))} className={BTN_GHOST}><RefreshCw className="w-3 h-3" /> Replay</button>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {/* ---------------- Documentation ---------------- */}
          {tab === 'docs' && docs && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Authentication</h3>
                  {docs.authentication.schemes.map(s => <code key={s} className="block text-[11px] text-slate-300 bg-slate-950/50 rounded px-2 py-1 mb-1">{s}</code>)}
                  <p className="text-[11px] text-slate-500 mt-2">{docs.authentication.notes}</p>
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Rate Limits &amp; Versioning</h3>
                  <p className="text-[11px] text-slate-400">Per minute: {docs.rate_limits.per_minute}</p>
                  <p className="text-[11px] text-slate-400">Daily quota: {docs.rate_limits.daily_quota}</p>
                  <div className="flex flex-wrap gap-1 mt-2">
                    {docs.rate_limits.headers.map(h => <code key={h} className="text-[10px] text-slate-400 bg-slate-950/50 rounded px-1.5 py-0.5">{h}</code>)}
                  </div>
                  <p className="text-[11px] text-slate-500 mt-2">{docs.versioning.policy}</p>
                </div>
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Endpoints</h3>
                {docs.endpoints.map(e => (
                  <div key={`${e.method}${e.path}`} className="py-2 border-b border-slate-800/60 last:border-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className={`text-[10px] font-bold px-1.5 py-0.5 rounded ${e.method === 'GET' ? 'bg-sky-500/15 text-sky-300' : 'bg-emerald-500/15 text-emerald-300'}`}>{e.method}</span>
                      <code className="text-xs text-slate-200">{e.path}</code>
                      {e.scope && <code className="text-[10px] text-brand-300">{e.scope}</code>}
                    </div>
                    <p className="text-[11px] text-slate-500 mt-1">{e.description || e.summary}</p>
                  </div>
                ))}
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Webhook Events</h3>
                <p className="text-[11px] text-slate-500 mb-2">Signature: <code className="text-slate-400">{docs.webhooks.signature_scheme}</code> · retries after {docs.webhooks.retry_backoff_minutes.join(', ')} minutes.</p>
                {docs.webhooks.events.map(ev => (
                  <div key={ev.key} className="flex justify-between gap-3 text-xs py-1 border-b border-slate-800/60 last:border-0">
                    <code className="text-brand-300 shrink-0">{ev.key}</code>
                    <span className="text-slate-500 text-right">{ev.description}</span>
                  </div>
                ))}
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Examples</h3>
                <div className="space-y-3">
                  {examples.map(ex => (
                    <div key={ex.key}>
                      <div className="flex items-center justify-between mb-1">
                        <p className="text-[11px] font-semibold text-slate-300">{ex.title} <span className="text-slate-600">· {ex.language}</span></p>
                        <CopyBtn text={ex.code} />
                      </div>
                      <Code code={ex.code} max="max-h-60" />
                    </div>
                  ))}
                </div>
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Errors</h3>
                {docs.errors.map(e => (
                  <div key={e.status} className="flex justify-between gap-3 text-xs py-1 border-b border-slate-800/60 last:border-0">
                    <span className={statusTone(e.status)}>{e.status}</span>
                    <span className="text-slate-500 text-right">{e.meaning}</span>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ---------------- SDKs ---------------- */}
          {tab === 'sdk' && (
            <div className="space-y-4">
              <div className={card}>
                <div className="flex items-center gap-2 flex-wrap">
                  {sdkLangs.map(l => (
                    <button key={l.key} onClick={() => setSdkLang(l.key)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-semibold cursor-pointer ${sdkLang === l.key ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200 bg-slate-900/50'}`}>
                      {l.label}
                    </button>
                  ))}
                </div>
                {sdkLangs.filter(l => l.key === sdkLang).map(l => (
                  <p key={l.key} className="text-[11px] text-slate-500 mt-2">
                    {l.filename} · requires {l.label} {l.min_version}+ · {l.install}
                  </p>
                ))}
              </div>
              <div className={card}>
                {!sdkSource ? <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div> : (
                  <>
                    <div className="flex items-center justify-between mb-2">
                      <p className="text-xs font-bold text-slate-300">{sdkSource.filename}</p>
                      <div className="flex items-center gap-1">
                        <CopyBtn text={sdkSource.source} />
                        <button onClick={() => { const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([sdkSource.source], { type: 'text/plain' })); a.download = sdkSource.filename; a.click(); URL.revokeObjectURL(a.href); }} className={BTN_GHOST}><Download className="w-3 h-3" /> Download</button>
                      </div>
                    </div>
                    <Code code={sdkSource.source} max="max-h-[32rem]" />
                  </>
                )}
              </div>
            </div>
          )}

          {/* ---------------- Analytics ---------------- */}
          {tab === 'analytics' && analytics && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Requests</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.requests}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Errors</p><p className={`text-xl font-bold mt-1 ${analytics.errors > 0 ? 'text-amber-400' : 'text-slate-100'}`}>{analytics.errors}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Throttled</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.throttled}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">p50 Latency</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.p50_latency_ms}<span className="text-xs text-slate-500">ms</span></p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">p95 Latency</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.p95_latency_ms}<span className="text-xs text-slate-500">ms</span></p></div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">By Endpoint</h3>
                  {Object.keys(analytics.by_endpoint).length === 0 ? <p className="text-xs text-slate-500">No traffic yet.</p> : Object.entries(analytics.by_endpoint).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <code className="text-slate-300">{k}</code>
                      <span className="text-slate-500">{v.requests} req · {v.errors} err · {v.avg_latency_ms}ms</span>
                    </div>
                  ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">By Key</h3>
                  {Object.keys(analytics.by_key).length === 0 ? <p className="text-xs text-slate-500">No traffic yet.</p> : Object.entries(analytics.by_key).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300">{k}</span>
                      <span className="text-slate-500">{v.requests} req · {v.tokens} tok · ${v.cost_usd}</span>
                    </div>
                  ))}
                </div>
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Recent Requests</h3>
                {requests.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No API requests recorded yet.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">When</th><th className="pr-2">Endpoint</th><th className="pr-2">Status</th><th className="pr-2">Latency</th><th className="pr-2">Tokens</th><th className="pr-2">Model</th>
                    </tr></thead>
                    <tbody>
                      {requests.map(r => (
                        <tr key={r.id} className="border-b border-slate-800/50 last:border-0">
                          <td className="py-2 pr-2 text-slate-400">{r.created_at ? new Date(r.created_at).toLocaleString() : '—'}</td>
                          <td className="pr-2 text-slate-300">{r.method} {r.endpoint}</td>
                          <td className={`pr-2 ${statusTone(r.status_code)}`}>{r.status_code}</td>
                          <td className="pr-2 text-slate-400">{r.latency_ms}ms</td>
                          <td className="pr-2 text-slate-400">{r.tokens}</td>
                          <td className="pr-2 text-slate-500">{r.model || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}
        </>
      )}

      <p className="text-[11px] text-slate-600">Public API base URL: <code>{publicApiBaseUrl()}</code></p>
    </div>
  );
};
