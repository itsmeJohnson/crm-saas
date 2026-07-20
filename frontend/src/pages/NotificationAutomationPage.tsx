import React, { useCallback, useEffect, useState } from 'react';
import {
  BellRing, Loader2, X, Check, Trash2, Plus, Power, Pencil, RotateCcw, Send, Layers,
  ListChecks, LayoutTemplate, BarChart3, Mail,
} from 'lucide-react';
import {
  notificationAutomationApi as api, NotifRule, NotifDelivery, NotifTemplate, NotifCatalog, NotifAutomationReport,
} from '../services/notificationAutomationApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm';

const StatusChip: React.FC<{ s: string }> = ({ s }) => {
  const tone = s === 'sent' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
    : s === 'failed' ? 'bg-red-500/10 text-red-400 border-red-500/20'
      : s === 'retrying' ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
        : 'bg-slate-700/40 text-slate-400 border-slate-600/40';
  return <span className={`px-1.5 py-0.5 text-[10px] font-semibold rounded-md border ${tone}`}>{s}</span>;
};

type Tab = 'rules' | 'deliveries' | 'templates' | 'reports';

export const NotificationAutomationPage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('rules');
  const [catalog, setCatalog] = useState<NotifCatalog | null>(null);
  const [rules, setRules] = useState<NotifRule[]>([]);
  const [deliveries, setDeliveries] = useState<NotifDelivery[]>([]);
  const [templates, setTemplates] = useState<NotifTemplate[]>([]);
  const [report, setReport] = useState<NotifAutomationReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const [ruleDraft, setRuleDraft] = useState<any>(null);
  const [tplDraft, setTplDraft] = useState<any>(null);

  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };
  const fail = (e: any) => setErr(extractErrorMessage(e, 'Something went wrong.'));

  const load = useCallback(async () => {
    setLoading(true);
    try { const [c, r] = await Promise.all([api.catalog(), api.listRules()]); setCatalog(c); setRules(r); }
    catch (e) { fail(e); } finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);
  useEffect(() => {
    if (tab === 'deliveries') api.deliveries({ limit: 50 }).then(setDeliveries).catch(() => {});
    if (tab === 'templates') api.listTemplates().then(setTemplates).catch(() => {});
    if (tab === 'reports') api.report().then(setReport).catch(() => {});
  }, [tab]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); } catch (e) { fail(e); } };

  const newRule = () => setRuleDraft({
    name: '', trigger_event: catalog?.trigger_events[1] || 'lead.created', entity_type: 'lead',
    recipients: [{ type: 'owner', value: '' }], channels: ['in_app'], title: '', body: '', conditions: '',
    template_key: '', category: 'system', priority: 'normal', digest: false, is_active: true,
  });
  const editRule = (r: NotifRule) => setRuleDraft({ ...r, conditions: r.conditions ? JSON.stringify(r.conditions, null, 2) : '' });

  const saveRule = async () => {
    if (!ruleDraft?.name?.trim()) { setErr('Name is required.'); return; }
    try {
      const payload: any = { ...ruleDraft };
      payload.conditions = ruleDraft.conditions?.trim() ? JSON.parse(ruleDraft.conditions) : null;
      payload.recipients = (ruleDraft.recipients || []).filter((r: any) => r.type);
      if (ruleDraft.id) await api.updateRule(ruleDraft.id, payload);
      else await api.createRule(payload);
      setRuleDraft(null); flash('Rule saved.'); await load();
    } catch (e) { fail(e); }
  };
  const saveTpl = async () => {
    if (!tplDraft?.template_key?.trim() || !tplDraft?.template_name?.trim()) { setErr('Key and name required.'); return; }
    try {
      if (tplDraft._edit) await api.updateTemplate(tplDraft.template_key, tplDraft);
      else await api.createTemplate(tplDraft);
      setTplDraft(null); flash('Template saved.'); api.listTemplates().then(setTemplates);
    } catch (e) { fail(e); }
  };

  const toggleChannel = (c: string) => {
    const has = ruleDraft.channels.includes(c);
    setRuleDraft({ ...ruleDraft, channels: has ? ruleDraft.channels.filter((x: string) => x !== c) : [...ruleDraft.channels, c] });
  };
  const setRecipient = (i: number, patch: any) => {
    const recipients = [...ruleDraft.recipients]; recipients[i] = { ...recipients[i], ...patch };
    setRuleDraft({ ...ruleDraft, recipients });
  };

  const Tabs = (
    <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
      {([['rules', 'Rules', ListChecks], ['deliveries', 'Deliveries', Send], ['templates', 'Templates', LayoutTemplate], ['reports', 'Reports', BarChart3]] as [Tab, string, any][])
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
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><BellRing className="w-6 h-6 text-brand-400" /> Notification Automation</h1>
          <p className="text-sm text-slate-500 mt-1">Rule-driven notifications on domain events — multi-channel, templated, with digests, delivery tracking and retry.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => act(async () => { const r = await api.flushDigests(); flash(`Sent ${r.digests_sent} digest(s).`); }, '')} className="px-3 py-2 rounded-lg text-xs font-semibold bg-slate-800/70 hover:bg-slate-700/70 text-slate-200 cursor-pointer flex items-center gap-1.5"><Layers className="w-3.5 h-3.5" /> Flush digests</button>
          <button onClick={newRule} className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New rule</button>
        </div>
      </div>

      {Tabs}
      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2 flex items-center justify-between"><span>{err}</span><button onClick={() => setErr('')}><X className="w-3.5 h-3.5" /></button></div>}

      {loading ? (
        <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'rules' ? (
        <div className="space-y-2">
          {rules.length === 0 && <p className="text-sm text-slate-500">No notification rules yet.</p>}
          {rules.map((r) => (
            <div key={r.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-semibold text-slate-100 truncate">{r.name}</span>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">{r.trigger_event}</span>
                  {r.channels.map((c) => <span key={c} className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-400">{c}</span>)}
                  {r.digest && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-indigo-500/10 text-indigo-300 border border-indigo-500/20">digest</span>}
                  {!r.is_active && <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-slate-700/40 text-slate-500">paused</span>}
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5">→ {r.recipients.map((x) => x.type).join(', ') || 'no recipients'} · fired {r.run_count} · {r.notif_count} notifications</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button title={r.is_active ? 'Pause' : 'Resume'} onClick={() => act(async () => { await api.enableRule(r.id, !r.is_active); await load(); }, 'Updated.')} className={`p-1.5 rounded-md hover:bg-slate-800 cursor-pointer ${r.is_active ? 'text-emerald-400' : 'text-slate-500'}`}><Power className="w-4 h-4" /></button>
                <button title="Edit" onClick={() => editRule(r)} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                <button title="Delete" onClick={() => window.confirm(`Delete "${r.name}"?`) && act(async () => { await api.removeRule(r.id); await load(); }, 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : tab === 'deliveries' ? (
        <div className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <table className="w-full text-xs">
            <thead className="bg-slate-900/60 text-slate-400"><tr>
              <th className="text-left px-4 py-2 font-semibold">Title</th>
              <th className="text-left px-4 py-2 font-semibold">Channel</th>
              <th className="text-left px-4 py-2 font-semibold">Status</th>
              <th className="text-left px-4 py-2 font-semibold">Attempts</th>
              <th className="text-left px-4 py-2 font-semibold">When</th>
              <th className="px-4 py-2"></th>
            </tr></thead>
            <tbody>
              {deliveries.length === 0 && <tr><td colSpan={6} className="px-4 py-6 text-center text-slate-500">No deliveries recorded yet.</td></tr>}
              {deliveries.map((d) => (
                <tr key={d.id} className="border-t border-slate-800/60">
                  <td className="px-4 py-2 text-slate-300 truncate max-w-[16rem]">{d.title || '—'}</td>
                  <td className="px-4 py-2 text-slate-400">{d.channel}</td>
                  <td className="px-4 py-2"><StatusChip s={d.status} /></td>
                  <td className="px-4 py-2 text-slate-500">{d.attempts}</td>
                  <td className="px-4 py-2 text-slate-500">{d.created_at ? new Date(d.created_at).toLocaleString() : ''}</td>
                  <td className="px-4 py-2 text-right">
                    {['failed', 'retrying'].includes(d.status) && <button onClick={() => act(async () => { await api.retryDelivery(d.id); api.deliveries({ limit: 50 }).then(setDeliveries); }, 'Retried.')} className="text-brand-400 hover:text-brand-300 cursor-pointer inline-flex items-center gap-1"><RotateCcw className="w-3.5 h-3.5" /></button>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : tab === 'templates' ? (
        <div className="space-y-3">
          <div className="flex justify-end">
            <button onClick={() => setTplDraft({ template_key: '', template_name: '', channel: 'email', subject: '', body: '', category: 'system' })} className="px-3 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Plus className="w-3.5 h-3.5" /> New template</button>
          </div>
          {templates.length === 0 && <p className="text-sm text-slate-500">No templates. Templates support {'{{variable}}'} substitution.</p>}
          {templates.map((t) => (
            <div key={t.template_key} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-4">
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="text-sm font-semibold text-slate-100">{t.template_name}</span>
                  <span className="font-mono text-[10px] px-1.5 py-0.5 rounded-md bg-slate-700/40 text-slate-400">{t.template_key}</span>
                  <span className="px-1.5 py-0.5 text-[10px] rounded-md bg-brand-500/10 text-brand-300 border border-brand-500/20">{t.channel}</span>
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5 truncate">{t.subject || t.body?.slice(0, 80)}</p>
              </div>
              <div className="flex items-center gap-1.5 shrink-0">
                <button onClick={() => setTplDraft({ ...t, _edit: true })} className="px-2 py-1 text-xs rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer">Edit</button>
                <button onClick={() => window.confirm(`Delete "${t.template_name}"?`) && act(async () => { await api.removeTemplate(t.template_key); api.listTemplates().then(setTemplates); }, 'Deleted.')} className="p-1.5 rounded-md hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
            </div>
          ))}
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
            {report && [['Rules', report.rules], ['Active', report.active_rules], ['Deliveries', report.deliveries],
              ['Delivery rate', `${report.delivery_rate}%`], ['Pending digest', report.pending_digest]].map(([k, v]) => (
              <div key={k as string} className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-[10px] font-semibold text-slate-500 uppercase">{k}</p>
                <p className="text-xl font-bold text-slate-100 mt-1">{v}</p>
              </div>
            ))}
          </div>
          {report && (
            <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
              <div className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><Mail className="w-3.5 h-3.5" /> By channel</p>
                {Object.keys(report.by_channel).length === 0 ? <p className="text-xs text-slate-500">No deliveries.</p> :
                  Object.entries(report.by_channel).map(([c, n]) => <div key={c} className="flex justify-between text-xs py-0.5"><span className="text-slate-400">{c}</span><span className="text-slate-300">{n}</span></div>)}
              </div>
              <div className="glass-panel border border-slate-800/85 rounded-xl p-4">
                <p className="text-xs font-semibold text-slate-300 mb-2">By status</p>
                {Object.keys(report.by_status).length === 0 ? <p className="text-xs text-slate-500">No deliveries.</p> :
                  Object.entries(report.by_status).map(([s, n]) => <div key={s} className="flex justify-between text-xs py-0.5"><span className="text-slate-400">{s}</span><span className="text-slate-300">{n}</span></div>)}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Rule editor */}
      {ruleDraft && catalog && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setRuleDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-xl max-h-[90vh] overflow-y-auto p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{ruleDraft.id ? 'Edit rule' : 'New notification rule'}</h3>
              <button onClick={() => setRuleDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <input value={ruleDraft.name} onChange={(e) => setRuleDraft({ ...ruleDraft, name: e.target.value })} placeholder="Rule name" className={F} />
              <div className="grid grid-cols-2 gap-3">
                <div><label className="text-[11px] text-slate-500">Trigger event</label>
                  <select value={ruleDraft.trigger_event} onChange={(e) => setRuleDraft({ ...ruleDraft, trigger_event: e.target.value })} className={`${F} font-mono`}>
                    {catalog.trigger_events.map((t) => <option key={t} value={t}>{t}</option>)}
                  </select></div>
                <div><label className="text-[11px] text-slate-500">Priority</label>
                  <select value={ruleDraft.priority} onChange={(e) => setRuleDraft({ ...ruleDraft, priority: e.target.value })} className={F}>
                    {catalog.priorities.map((p) => <option key={p} value={p}>{p}</option>)}
                  </select></div>
              </div>
              <div>
                <label className="text-[11px] text-slate-500">Channels</label>
                <div className="flex flex-wrap gap-2 mt-1">
                  {catalog.channels.map((c) => (
                    <button key={c} onClick={() => toggleChannel(c)} className={`px-2.5 py-1 rounded-lg text-xs cursor-pointer border ${ruleDraft.channels.includes(c) ? 'bg-brand-500/20 text-brand-300 border-brand-500/30' : 'bg-slate-800/50 text-slate-400 border-slate-700/60'}`}>{c}</button>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-[11px] text-slate-500">Recipients</label>
                {ruleDraft.recipients.map((r: any, i: number) => (
                  <div key={i} className="flex items-center gap-2 mt-1">
                    <select value={r.type} onChange={(e) => setRecipient(i, { type: e.target.value })} className={`${F} !w-auto`}>
                      {catalog.recipient_types.map((t) => <option key={t} value={t}>{t}</option>)}
                    </select>
                    {['role', 'user'].includes(r.type) && <input value={r.value || ''} onChange={(e) => setRecipient(i, { value: e.target.value })} placeholder={r.type === 'role' ? 'role name' : 'user id'} className={`${F} !w-auto flex-1`} />}
                    <button onClick={() => setRuleDraft({ ...ruleDraft, recipients: ruleDraft.recipients.filter((_: any, x: number) => x !== i) })} className="text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-4 h-4" /></button>
                  </div>
                ))}
                <button onClick={() => setRuleDraft({ ...ruleDraft, recipients: [...ruleDraft.recipients, { type: 'owner' }] })} className="text-[11px] px-2 py-1 mt-2 rounded-md bg-slate-800/70 hover:bg-slate-700/70 text-slate-300 cursor-pointer flex items-center gap-1"><Plus className="w-3 h-3" /> Recipient</button>
              </div>
              <input value={ruleDraft.title} onChange={(e) => setRuleDraft({ ...ruleDraft, title: e.target.value })} placeholder="Title (supports {{variable}})" className={F} />
              <textarea value={ruleDraft.body} onChange={(e) => setRuleDraft({ ...ruleDraft, body: e.target.value })} placeholder="Body (supports {{variable}}) — or leave blank to use a template" rows={2} className={F} />
              <div className="grid grid-cols-2 gap-3">
                <input value={ruleDraft.template_key} onChange={(e) => setRuleDraft({ ...ruleDraft, template_key: e.target.value })} placeholder="Template key (optional)" className={F} />
                <input value={ruleDraft.category} onChange={(e) => setRuleDraft({ ...ruleDraft, category: e.target.value })} placeholder="Category" className={F} />
              </div>
              <textarea value={ruleDraft.conditions} onChange={(e) => setRuleDraft({ ...ruleDraft, conditions: e.target.value })} placeholder='Conditions (Rule-Engine JSON, optional)' rows={2} className={`${F} font-mono`} />
              <div className="flex items-center gap-4">
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={ruleDraft.digest} onChange={(e) => setRuleDraft({ ...ruleDraft, digest: e.target.checked })} /> Batch into digest</label>
                <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={ruleDraft.is_active} onChange={(e) => setRuleDraft({ ...ruleDraft, is_active: e.target.checked })} /> Active</label>
              </div>
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setRuleDraft(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={saveRule} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Save</button>
            </div>
          </div>
        </div>
      )}

      {/* Template editor */}
      {tplDraft && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setTplDraft(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-lg p-5" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-bold text-slate-100">{tplDraft._edit ? 'Edit template' : 'New template'}</h3>
              <button onClick={() => setTplDraft(null)} className="text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-5 h-5" /></button>
            </div>
            <div className="space-y-3">
              <div className="grid grid-cols-2 gap-3">
                <input value={tplDraft.template_key} disabled={tplDraft._edit} onChange={(e) => setTplDraft({ ...tplDraft, template_key: e.target.value })} placeholder="template_key" className={`${F} font-mono ${tplDraft._edit ? 'opacity-60' : ''}`} />
                <input value={tplDraft.template_name} onChange={(e) => setTplDraft({ ...tplDraft, template_name: e.target.value })} placeholder="Template name" className={F} />
              </div>
              <input value={tplDraft.subject || ''} onChange={(e) => setTplDraft({ ...tplDraft, subject: e.target.value })} placeholder="Subject (supports {{variable}})" className={F} />
              <textarea value={tplDraft.body} onChange={(e) => setTplDraft({ ...tplDraft, body: e.target.value })} placeholder="Body (supports {{variable}})" rows={4} className={F} />
            </div>
            <div className="flex items-center justify-end gap-2 mt-5">
              <button onClick={() => setTplDraft(null)} className="px-3 py-2 rounded-lg text-xs font-semibold text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={saveTpl} className="px-4 py-2 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5"><Check className="w-3.5 h-3.5" /> Save</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
