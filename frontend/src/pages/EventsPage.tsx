import React, { useCallback, useEffect, useState } from 'react';
import {
  Radio, Loader2, X, Check, Trash2, Plus, Send, AlertOctagon, RotateCcw, ChevronRight,
  Rss, ScrollText, BarChart3, Power,
} from 'lucide-react';
import {
  eventApi, DomainEvent, EventDelivery, EventSubscription, EventCatalog, EventStats,
} from '../services/eventApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm';

const Dot: React.FC<{ s: string }> = ({ s }) => {
  const tone = s === 'success' ? 'bg-emerald-400' : s === 'dead_letter' ? 'bg-red-400' : s === 'failed' ? 'bg-amber-400' : 'bg-slate-600';
  return <span className={`inline-block w-2 h-2 rounded-full ${tone}`} />;
};

type Tab = 'log' | 'subscriptions' | 'dlq' | 'monitoring';

export const EventsPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('log');
  const [catalog, setCatalog] = useState<EventCatalog | null>(null);
  const [events, setEvents] = useState<DomainEvent[]>([]);
  const [subs, setSubs] = useState<EventSubscription[]>([]);
  const [dlq, setDlq] = useState<EventDelivery[]>([]);
  const [stats, setStats] = useState<EventStats | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');

  const [expanded, setExpanded] = useState<string | null>(null);
  const [deliveries, setDeliveries] = useState<Record<string, EventDelivery[]>>({});
  const [subDraft, setSubDraft] = useState<any>(null);
  const [pubDraft, setPubDraft] = useState<any>(null);

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };
  const fail = (e: any) => setErr(extractErrorMessage(e, 'Something went wrong.'));

  const loadTab = useCallback(async (t: Tab) => {
    try {
      if (t === 'log') setEvents(await eventApi.events({ limit: 50 }));
      if (t === 'subscriptions') setSubs(await eventApi.listSubscriptions());
      if (t === 'dlq') setDlq(await eventApi.deadLetter({ limit: 50 }));
      if (t === 'monitoring') setStats(await eventApi.stats());
    } catch (e) { fail(e); }
  }, []);

  useEffect(() => {
    (async () => {
      setLoading(true);
      try { setCatalog(await eventApi.catalog()); await loadTab('log'); } catch (e) { fail(e); } finally { setLoading(false); }
    })();
  }, [loadTab]);
  useEffect(() => { loadTab(tab); }, [tab, loadTab]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); } catch (e) { fail(e); } };

  const toggleExpand = async (e: DomainEvent) => {
    if (expanded === e.id) { setExpanded(null); return; }
    setExpanded(e.id);
    if (!deliveries[e.id]) {
      try { setDeliveries((d) => ({ ...d, [e.id]: [] })); const dl = await eventApi.deliveries(e.id); setDeliveries((d) => ({ ...d, [e.id]: dl })); }
      catch (er) { fail(er); }
    }
  };

  const saveSub = async () => {
    if (!subDraft?.name?.trim()) { setErr('Name is required.'); return; }
    try {
      const payload = { ...subDraft, config: subDraft.subscriber_type === 'webhook' ? { url: subDraft.url } : null };
      if (subDraft.id) await eventApi.updateSubscription(subDraft.id, payload);
      else await eventApi.createSubscription(payload);
      setSubDraft(null); flash('Subscription saved.'); loadTab('subscriptions');
    } catch (e) { fail(e); }
  };
  const publishCustom = async () => {
    if (!pubDraft?.name?.trim()) { setErr('Event name is required.'); return; }
    try {
      let payload = undefined;
      if (pubDraft.payload?.trim()) payload = JSON.parse(pubDraft.payload);
      await eventApi.publishCustom({ name: pubDraft.name, payload });
      setPubDraft(null); flash('Event published.'); loadTab('log');
    } catch (e) { fail(e); }
  };

  const Tabs = (
    <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
      {([['log', 'Event Log', ScrollText], ['subscriptions', 'Subscriptions', Rss],
         ['dlq', 'Dead Letter Queue', AlertOctagon], ['monitoring', 'Monitoring', BarChart3]] as [Tab, string, any][])
        .map(([k, label, Icon]) => (
          <button key={k} onClick={() => setTab(k)}
            className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
    </div>
  );

  return (
    <div className="space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Radio className="w-6 h-6 text-brand-400" /> Event Bus</h1>
          <p className="text-sm text-slate-500 mt-1">Decoupled domain events with publish/subscribe, retry, dead-letter queue and monitoring.</p>
        </div>
        <button onClick={() => setPubDraft({ name: '', payload: '' })} className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Send className="w-3.5 h-3.5" /> Publish custom event</button>
      </div>

      {Tabs}
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'log' ? (
        <div className="space-y-2">
          {events.length === 0 && <p className="text-sm text-slate-500">No events published yet.</p>}
          {events.map((e) => (
            <div key={e.id} className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
              <button onClick={() => toggleExpand(e)} className="w-full flex items-center gap-3 p-4 text-left cursor-pointer">
                <ChevronRight className={`w-4 h-4 text-slate-500 transition-transform ${expanded === e.id ? 'rotate-90' : ''}`} />
                <span className="font-mono text-xs text-brand-300">{e.event_type}</span>
                <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400 border border-slate-600/40">{e.source}</span>
                <span className="text-[11px] text-slate-500 ml-auto">{e.delivered_count}/{e.subscriber_count} delivered{e.failed_count ? ` · ${e.failed_count} failed` : ''} · {e.duration_ms}ms</span>
                <span className="text-[11px] text-slate-600">{e.published_at ? new Date(e.published_at).toLocaleTimeString() : ''}</span>
              </button>
              {expanded === e.id && (
                <div className="px-4 pb-3 border-t border-slate-800/60">
                  <p className="text-[10px] uppercase font-semibold text-slate-500 py-2">Deliveries (execution log)</p>
                  {(deliveries[e.id] || []).length === 0 ? <p className="text-xs text-slate-600 pb-2">No subscribers matched this event.</p> : (
                    <div className="space-y-1 pb-2">
                      {(deliveries[e.id] || []).map((d) => (
                        <div key={d.id} className="flex items-center gap-2 text-xs">
                          <Dot s={d.status} />
                          <span className="text-slate-300">{d.subscriber}</span>
                          <span className="text-slate-500">· {d.attempts} attempt(s) · {d.duration_ms}ms</span>
                          {d.error && <span className="text-red-400 truncate">· {d.error}</span>}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          ))}
        </div>
      ) : tab === 'subscriptions' ? (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setSubDraft({ name: '', event_pattern: '*', subscriber_type: 'webhook', url: '', max_attempts: 3, is_active: true })}
              className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New subscription</button>
          </div>
          {subs.length === 0 && <p className="text-sm text-slate-500">No subscriptions. Add a webhook to receive events.</p>}
          {subs.map((s) => (
            <div key={s.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-100">{s.name}</span>
                  <span className="font-mono text-[11px] px-1.5 py-0.5 rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">{s.event_pattern}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400">{s.subscriber_type}</span>
                  {!s.is_active && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-500">inactive</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5 truncate">{s.config?.url || '—'} · {s.delivered_count} delivered · {s.failed_count} failed · retry ×{s.max_attempts}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title={s.is_active ? 'Disable' : 'Enable'} onClick={() => act(async () => { await eventApi.updateSubscription(s.id, { is_active: !s.is_active }); loadTab('subscriptions'); }, 'Updated.')} className={`p-1.5 rounded-md hover:bg-slate-800 cursor-pointer ${s.is_active ? 'text-emerald-400' : 'text-slate-500'}`}><Power className="w-4 h-4" /></button>
                <button onClick={() => setSubDraft({ ...s, url: s.config?.url || '' })} className="px-2 py-1 text-xs rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer">Edit</button>
                <button onClick={() => window.confirm(`Delete "${s.name}"?`) && act(async () => { await eventApi.removeSubscription(s.id); loadTab('subscriptions'); }, 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'dlq' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Event</th>
              <th className="text-left px-4 py-2 font-semibold">Subscriber</th>
              <th className="text-left px-4 py-2 font-semibold">Attempts</th>
              <th className="text-left px-4 py-2 font-semibold">Error</th>
              <th className="px-4 py-2"></th>
            </tr></thead>
            <tbody>
              {dlq.length === 0 && <tr><td colSpan={5} className="px-4 py-6 text-center text-slate-500">Dead-letter queue is empty. 🎉</td></tr>}
              {dlq.map((d) => (
                <tr key={d.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2 font-mono text-brand-300">{d.event_type}</td>
                  <td className="px-4 py-2 text-slate-300">{d.subscriber}</td>
                  <td className="px-4 py-2 text-slate-400">{d.attempts}</td>
                  <td className="px-4 py-2 text-red-400 truncate max-w-[16rem]">{d.error}</td>
                  <td className="px-4 py-2 text-right">
                    <button onClick={() => act(async () => { const r = await eventApi.requeue(d.id); loadTab('dlq'); flash(r.delivered ? 'Requeued & delivered.' : 'Requeued (still failing).'); }, '')} className="text-brand-400 hover:text-brand-300 cursor-pointer inline-flex items-center gap-1"><RotateCcw className="w-3.5 h-3.5" /> Requeue</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {stats && [['Total events', stats.total_events], ['Deliveries', stats.deliveries], ['Failed', stats.failed_deliveries],
              ['Success rate', `${stats.success_rate}%`], ['Dead-letter', stats.dead_letter], ['Avg publish', `${stats.avg_publish_ms}ms`]].map(([k, v]) => (
              <div key={k as string} className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-[10px] font-semibold text-slate-500 uppercase">{k}</p>
                <p className="text-xl font-bold text-slate-100 mt-1">{v}</p>
              </div>
            ))}
          </div>
          {stats && Object.keys(stats.by_type).length > 0 && (
            <div className="glass-panel border border-slate-800/85 rounded-xl p-4">
              <p className="text-xs font-semibold text-slate-300 mb-3">Events by type</p>
              <div className="space-y-1.5">
                {Object.entries(stats.by_type).sort((a, b) => b[1] - a[1]).map(([t, n]) => (
                  <div key={t} className="flex items-center gap-2 text-xs">
                    <span className="font-mono text-brand-300 w-56 truncate">{t}</span>
                    <div className="flex-1 h-2 bg-slate-800/60 rounded-full overflow-hidden">
                      <div className="h-full bg-brand-500/60" style={{ width: `${Math.min(100, (n / Math.max(...Object.values(stats.by_type))) * 100)}%` }} />
                    </div>
                    <span className="text-slate-400 w-8 text-right">{n}</span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Subscription editor */}
      {subDraft && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setSubDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{subDraft.id ? 'Edit subscription' : 'New subscription'}</h3>
              <button onClick={() => setSubDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <input value={subDraft.name} onChange={(e) => setSubDraft({ ...subDraft, name: e.target.value })} placeholder="Subscription name" className={F} />
              <div>
                <label className="text-[11px] text-slate-500">Event pattern (e.g. lead.* or payment.received or *)</label>
                <input value={subDraft.event_pattern} onChange={(e) => setSubDraft({ ...subDraft, event_pattern: e.target.value })} placeholder="*" className={`${F} font-mono`} list="event-patterns" />
                <datalist id="event-patterns">
                  {catalog.families.map((f) => <option key={f} value={`${f}.*`} />)}
                  {catalog.all_event_types.map((t) => <option key={t} value={t} />)}
                </datalist>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <select value={subDraft.subscriber_type} onChange={(e) => setSubDraft({ ...subDraft, subscriber_type: e.target.value })} className={F}>
                  {catalog.subscriber_types.map((t) => <option key={t} value={t}>{t}</option>)}
                </select>
                <input type="number" value={subDraft.max_attempts} onChange={(e) => setSubDraft({ ...subDraft, max_attempts: parseInt(e.target.value) || 1 })} placeholder="Max attempts" className={F} />
              </div>
              {subDraft.subscriber_type === 'webhook' && (
                <input value={subDraft.url} onChange={(e) => setSubDraft({ ...subDraft, url: e.target.value })} placeholder="https://your-endpoint.example/webhook" className={F} />
              )}
              <label className="flex items-center gap-2 text-xs text-slate-300 px-1"><input type="checkbox" checked={subDraft.is_active} onChange={(e) => setSubDraft({ ...subDraft, is_active: e.target.checked })} /> Active</label>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setSubDraft(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={saveSub} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Publish custom event */}
      {pubDraft && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setPubDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Send className="w-5 h-5 text-brand-400" /> Publish custom event</h3>
              <button onClick={() => setPubDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-[11px] text-slate-500">Event name (published as custom.&lt;name&gt;)</label>
                <input value={pubDraft.name} onChange={(e) => setPubDraft({ ...pubDraft, name: e.target.value })} placeholder="deal_won" className={`${F} font-mono`} />
              </div>
              <div>
                <label className="text-[11px] text-slate-500">Payload (JSON, optional)</label>
                <textarea value={pubDraft.payload} onChange={(e) => setPubDraft({ ...pubDraft, payload: e.target.value })} rows={4} placeholder='{"key": "value"}' className={`${F} font-mono`} />
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setPubDraft(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={publishCustom} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Send className="w-3.5 h-3.5" /> Publish</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
