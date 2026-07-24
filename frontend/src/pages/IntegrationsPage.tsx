import React, { useCallback, useEffect, useState } from 'react';
import {
  Plug, Loader2, Download, LayoutDashboard, Boxes, ScrollText, Inbox, Plus,
  RefreshCw, Trash2, Activity, Copy, Check, HeartPulse, Send, ShieldCheck,
} from 'lucide-react';
import {
  integrationApi as api, Integration, IntegrationCatalog, IntegrationLog,
  IntegrationEvent, IntegrationDashboard, STATUS_TONE, LOG_TONE, inboundUrl,
} from '../services/integrationApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const BTN_GHOST = 'px-2 py-1 rounded-lg text-[11px] font-semibold text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 cursor-pointer flex items-center gap-1';

type Tab = 'overview' | 'connections' | 'catalog' | 'logs' | 'inbound';

const CopyBtn: React.FC<{ text: string }> = ({ text }) => {
  const [done, setDone] = useState(false);
  return (
    <button onClick={() => { navigator.clipboard?.writeText(text); setDone(true); setTimeout(() => setDone(false), 1500); }}
      className={BTN_GHOST}>
      {done ? <Check className="w-3 h-3 text-emerald-400" /> : <Copy className="w-3 h-3" />} {done ? 'Copied' : 'Copy'}
    </button>
  );
};

export const IntegrationsPage: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'OrgAdmin' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [note, setNote] = useState('');

  const [dash, setDash] = useState<IntegrationDashboard | null>(null);
  const [rows, setRows] = useState<Integration[]>([]);
  const [catalog, setCatalog] = useState<IntegrationCatalog | null>(null);
  const [logs, setLogs] = useState<IntegrationLog[]>([]);
  const [events, setEvents] = useState<IntegrationEvent[]>([]);
  const [newInbound, setNewInbound] = useState<Integration | null>(null);
  const [categoryFilter, setCategoryFilter] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({ provider: '', name: '', base_url: '', credential: '' });

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'overview') setDash(await api.dashboard());
      if (tab === 'connections') setRows(await api.list(categoryFilter ? { category: categoryFilter } : {}));
      if (tab === 'catalog') setCatalog(await api.catalog());
      if (tab === 'logs') setLogs(await api.logs({ limit: 100 }));
      if (tab === 'inbound') {
        const [r, e] = await Promise.all([api.list({ category: 'webhook' }), api.events({ limit: 50 })]);
        setRows(r); setEvents(e);
      }
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load integrations.')); }
    finally { setLoading(false); }
  }, [tab, categoryFilter]);
  useEffect(() => { load(); }, [load]);

  useEffect(() => { if (!catalog && (tab === 'connections' || tab === 'inbound')) api.catalog().then(setCatalog).catch(() => {}); }, [tab, catalog]);

  const act = async (fn: () => Promise<any>, msg?: string, after?: (r: any) => void) => {
    setErr(''); setNote('');
    try {
      const r = await fn();
      after?.(r);
      if (msg) { setNote(msg); setTimeout(() => setNote(''), 2500); }
      await load();
    } catch (e) { setErr(extractErrorMessage(e, 'Action failed.')); }
  };

  const hubConnectors = (catalog?.categories || []).filter(c => !c.managed_by);

  const create = () => act(async () => {
    const conn = hubConnectors.flatMap(c => c.connectors).find(c => c.key === form.provider);
    const credField = conn?.credential_fields?.[0];
    return api.create({
      provider: form.provider,
      name: form.name || undefined,
      config: form.base_url ? { base_url: form.base_url } : {},
      credentials: credField && form.credential ? { [credField]: form.credential } : {},
    });
  }, 'Connection created', (r) => {
    setShowForm(false);
    setForm({ provider: '', name: '', base_url: '', credential: '' });
    if (r?.inbound_token) setNewInbound(r);
  });

  const statusPill = (s: string) => (
    <span className={`px-1.5 py-0.5 rounded text-[10px] ${STATUS_TONE[s] || ''}`}>{s}</span>
  );

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Plug className="w-6 h-6 text-brand-400" /> Integration Hub</h1>
          <p className="text-sm text-slate-500 mt-1">Every external connection in one place — health, retries, fallback and audit across all categories.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => act(() => api.syncManaged(), 'Channel modules re-scanned')} className={BTN}>
            <RefreshCw className="w-3.5 h-3.5" /> Sync modules
          </button>
          <button onClick={() => act(() => api.healthCheckAll(), 'Health check complete')} className={BTN}>
            <HeartPulse className="w-3.5 h-3.5" /> Check all
          </button>
          <button onClick={async () => { try { const t = await api.exportCsv(); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t], { type: 'text/csv' })); a.download = 'integrations.csv'; a.click(); URL.revokeObjectURL(a.href); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}>
            <Download className="w-3.5 h-3.5" /> Export
          </button>
        </div>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}
      {note && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{note}</div>}

      {newInbound?.inbound_token && (
        <div className="text-xs bg-amber-500/10 border border-amber-500/25 rounded-lg px-3 py-2.5 space-y-1.5">
          <p className="font-semibold text-amber-300">Inbound endpoint ready — point your vendor at this URL.</p>
          <div className="flex items-center gap-2 flex-wrap">
            <code className="text-[11px] text-slate-200 bg-slate-950/60 rounded px-2 py-1 break-all">{inboundUrl(newInbound.inbound_token)}</code>
            <CopyBtn text={inboundUrl(newInbound.inbound_token)} />
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-slate-400">Signing secret:</span>
            <code className="text-[11px] text-slate-200 bg-slate-950/60 rounded px-2 py-1 break-all">{newInbound.inbound_secret}</code>
            <CopyBtn text={newInbound.inbound_secret || ''} />
            <button onClick={() => setNewInbound(null)} className={BTN_GHOST}>Dismiss</button>
          </div>
        </div>
      )}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['overview', 'Overview', LayoutDashboard], ['connections', 'Connections', Boxes], ['catalog', 'Catalog', Plug], ['logs', 'Activity Log', ScrollText], ['inbound', 'Inbound', Inbox]] as [Tab, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {/* ---------------- Overview ---------------- */}
          {tab === 'overview' && dash && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Connections</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.total}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Healthy</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.healthy}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Degraded</p><p className={`text-xl font-bold mt-1 ${dash.degraded ? 'text-amber-400' : 'text-slate-100'}`}>{dash.degraded}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Down</p><p className={`text-xl font-bold mt-1 ${dash.down ? 'text-red-400' : 'text-slate-100'}`}>{dash.down}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Success 7d</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.success_rate}%</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Fallbacks 7d</p><p className="text-xl font-bold text-sky-400 mt-1">{dash.fallbacks_7d}</p></div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Coverage</h3>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Categories in use</span><span className="text-slate-200">{dash.categories_used} / {dash.categories_available}</span></div>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Connectors available</span><span className="text-slate-200">{dash.connectors_available}</span></div>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Configured in the hub</span><span className="text-slate-200">{dash.active}</span></div>
                  <div className="flex justify-between text-xs py-1"><span className="text-slate-400">Owned by other modules</span><span className="text-slate-200">{dash.managed_elsewhere}</span></div>
                  <p className="text-[11px] text-slate-600 mt-2">Channels with their own settings pages (SMS, email, WhatsApp, payments) are mirrored here read-only.</p>
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Reliability (7 days)</h3>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Calls</span><span className="text-slate-200">{dash.calls_7d}</span></div>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Failures</span><span className={dash.failures_7d ? 'text-amber-400' : 'text-slate-200'}>{dash.failures_7d}</span></div>
                  <div className="flex justify-between text-xs py-1 border-b border-slate-800/60"><span className="text-slate-400">Calls that needed a retry</span><span className="text-slate-200">{dash.retries_7d}</span></div>
                  <div className="flex justify-between text-xs py-1"><span className="text-slate-400">Saved by fallback</span><span className="text-sky-400">{dash.fallbacks_7d}</span></div>
                </div>
              </div>

              {dash.needs_attention.length > 0 && (
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Needs Attention</h3>
                  {dash.needs_attention.map(i => (
                    <div key={i.id} className="flex justify-between items-center text-xs py-1.5 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300">{i.name} <span className="text-slate-600">· {i.provider_label}</span></span>
                      <span className="flex items-center gap-2">
                        <span className="text-slate-500 truncate max-w-[280px]">{i.last_error}</span>
                        {statusPill(i.status)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ---------------- Connections ---------------- */}
          {tab === 'connections' && (
            <div className="space-y-4">
              <div className={card}>
                <div className="flex items-center justify-between gap-2 flex-wrap">
                  <select value={categoryFilter} onChange={e => setCategoryFilter(e.target.value)} className={`${F} w-auto`}>
                    <option value="">All categories</option>
                    {(catalog?.categories || []).map(c => <option key={c.key} value={c.key}>{c.label}</option>)}
                  </select>
                  {isAdmin && <button onClick={() => setShowForm(v => !v)} className={BTN}><Plus className="w-3.5 h-3.5" /> Add connection</button>}
                </div>
                {showForm && isAdmin && (
                  <div className="grid grid-cols-1 md:grid-cols-5 gap-2 mt-3">
                    <select value={form.provider} onChange={e => setForm({ ...form, provider: e.target.value })} className={F}>
                      <option value="">Select a connector…</option>
                      {hubConnectors.map(c => (
                        <optgroup key={c.key} label={c.label}>
                          {c.connectors.map(x => <option key={x.key} value={x.key}>{x.label}</option>)}
                        </optgroup>
                      ))}
                    </select>
                    <input placeholder="Name" value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} className={F} />
                    <input placeholder="Base URL (optional)" value={form.base_url} onChange={e => setForm({ ...form, base_url: e.target.value })} className={F} />
                    <input placeholder="Credential" type="password" value={form.credential} onChange={e => setForm({ ...form, credential: e.target.value })} className={F} />
                    <button onClick={create} disabled={!form.provider} className={`${BTN} ${!form.provider ? 'opacity-50' : ''}`}>Create</button>
                  </div>
                )}
              </div>

              <div className={card}>
                {rows.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No connections yet. Add one, or press “Sync modules” to pull in the channels you already configured.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">Name</th><th className="pr-2">Category</th><th className="pr-2">Connector</th><th className="pr-2">Status</th><th className="pr-2">Calls</th><th className="pr-2">Owner</th><th className="pr-2 text-right">Actions</th>
                    </tr></thead>
                    <tbody>
                      {rows.map(i => (
                        <tr key={i.id} className="border-b border-slate-800/50 last:border-0">
                          <td className="py-2 pr-2 text-slate-200">{i.name}</td>
                          <td className="pr-2 text-slate-400">{i.category}</td>
                          <td className="pr-2 text-slate-400">{i.provider_label}</td>
                          <td className="pr-2">{statusPill(i.status)}</td>
                          <td className="pr-2 text-slate-400">{i.total_calls}{i.failed_calls > 0 && <span className="text-red-400"> ({i.failed_calls} failed)</span>}</td>
                          <td className="pr-2 text-slate-500">{i.is_managed_elsewhere ? i.managed_by : 'hub'}</td>
                          <td className="pr-2">
                            <div className="flex items-center justify-end gap-1">
                              {!i.is_managed_elsewhere && (
                                <button onClick={() => act(() => api.healthCheck(i.id))} className={BTN_GHOST}><HeartPulse className="w-3 h-3" /> Check</button>
                              )}
                              {isAdmin && !i.is_managed_elsewhere && (
                                <>
                                  <button onClick={() => act(() => api.update(i.id, { is_enabled: !i.is_enabled }))} className={BTN_GHOST}>
                                    {i.is_enabled ? 'Disable' : 'Enable'}
                                  </button>
                                  <button onClick={() => act(() => api.remove(i.id), 'Connection removed')} className={BTN_GHOST}><Trash2 className="w-3 h-3" /></button>
                                </>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {/* ---------------- Catalog ---------------- */}
          {tab === 'catalog' && catalog && (
            <div className="space-y-4">
              <p className="text-xs text-slate-500">{catalog.total_connectors} connectors across {catalog.categories.length} categories. Categories marked <span className="text-amber-300">module-owned</span> keep their credentials in their own settings page.</p>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                {catalog.categories.map(c => (
                  <div key={c.key} className={card}>
                    <div className="flex items-center justify-between mb-2">
                      <h3 className="text-xs font-bold text-slate-300">{c.label}</h3>
                      {c.managed_by && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/15 text-amber-300 flex items-center gap-1"><ShieldCheck className="w-3 h-3" /> {c.managed_by}</span>}
                    </div>
                    <div className="flex flex-wrap gap-1">
                      {c.connectors.map(x => (
                        <span key={x.key} title={x.capabilities.join(', ')}
                          className="text-[10px] px-1.5 py-0.5 rounded bg-slate-950/50 border border-slate-800/60 text-slate-400">{x.label}</span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* ---------------- Logs ---------------- */}
          {tab === 'logs' && (
            <div className={card}>
              {logs.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No integration activity recorded yet.</p> : (
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                    <th className="py-2 pr-2">When</th><th className="pr-2">Operation</th><th className="pr-2">Endpoint</th><th className="pr-2">Status</th><th className="pr-2">Attempts</th><th className="pr-2">Latency</th><th className="pr-2">Error</th>
                  </tr></thead>
                  <tbody>
                    {logs.map(l => (
                      <tr key={l.id} className="border-b border-slate-800/50 last:border-0">
                        <td className="py-2 pr-2 text-slate-400">{l.created_at ? new Date(l.created_at).toLocaleString() : '—'}</td>
                        <td className="pr-2 text-slate-300">{l.operation}</td>
                        <td className="pr-2 text-slate-500 truncate max-w-[220px]">{l.endpoint || '—'}</td>
                        <td className="pr-2"><span className={`px-1.5 py-0.5 rounded ${LOG_TONE[l.status] || ''}`}>{l.status}</span></td>
                        <td className={`pr-2 ${l.attempts > 1 ? 'text-amber-400' : 'text-slate-400'}`}>{l.attempts}</td>
                        <td className="pr-2 text-slate-400">{l.latency_ms}ms</td>
                        <td className="pr-2 text-slate-500 truncate max-w-[200px]">{l.error || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {/* ---------------- Inbound ---------------- */}
          {tab === 'inbound' && (
            <div className="space-y-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Send className="w-3.5 h-3.5 text-brand-400" /> Inbound Endpoints</h3>
                {rows.filter(r => r.has_inbound_endpoint).length === 0 ? (
                  <p className="text-xs text-slate-500 py-4">No inbound endpoints. Add an “Inbound Webhook” connection to receive payloads from an external system.</p>
                ) : rows.filter(r => r.has_inbound_endpoint).map(i => (
                  <div key={i.id} className="flex items-center justify-between text-xs py-2 border-b border-slate-800/60 last:border-0">
                    <span className="text-slate-300">{i.name}</span>
                    <span className="flex items-center gap-2">
                      {statusPill(i.status)}
                      {isAdmin && <button onClick={() => act(() => api.rotateInbound(i.id), 'Endpoint rotated', setNewInbound)} className={BTN_GHOST}><RefreshCw className="w-3 h-3" /> Rotate</button>}
                    </span>
                  </div>
                ))}
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><Activity className="w-3.5 h-3.5" /> Received Payloads</h3>
                {events.length === 0 ? <p className="text-xs text-slate-500 py-4 text-center">Nothing received yet.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">When</th><th className="pr-2">Event</th><th className="pr-2">Signature</th><th className="pr-2">Forwarded</th>
                    </tr></thead>
                    <tbody>
                      {events.map(e => (
                        <tr key={e.id} className="border-b border-slate-800/50 last:border-0">
                          <td className="py-2 pr-2 text-slate-400">{e.received_at ? new Date(e.received_at).toLocaleString() : '—'}</td>
                          <td className="pr-2 text-slate-300">{e.event_type}</td>
                          <td className="pr-2">
                            {e.signature_valid === null ? <span className="text-slate-500">unsigned</span>
                              : e.signature_valid ? <span className="text-emerald-400">verified</span>
                                : <span className="text-red-400">invalid</span>}
                          </td>
                          <td className="pr-2 text-slate-400">{e.processed ? 'yes' : 'no'}</td>
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
    </div>
  );
};
