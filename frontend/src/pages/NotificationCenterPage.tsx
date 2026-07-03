import React, { useCallback, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Bell, Loader2, CheckCheck, Check, X, Filter, Inbox, SlidersHorizontal, BarChart3,
  BellRing, Megaphone,
} from 'lucide-react';
import { notificationApi, NotificationResponse, NotificationPreference, NotificationStats } from '../services/notificationApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const PRIORITY_STYLE: Record<string, string> = {
  urgent: 'bg-red-500/10 text-red-400 border-red-500/20',
  high: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  normal: 'bg-slate-700/40 text-slate-300 border-slate-600/40',
  low: 'bg-slate-800/40 text-slate-500 border-slate-700/40',
};

const timeAgo = (iso: string) => {
  const m = Math.floor((Date.now() - new Date(iso).getTime()) / 60000);
  if (m < 1) return 'just now';
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  return new Date(iso).toLocaleDateString();
};

/* ── Inbox tab ── */
const InboxTab: React.FC = () => {
  const navigate = useNavigate();
  const [items, setItems] = useState<NotificationResponse[]>([]);
  const [loading, setLoading] = useState(true);
  const [category, setCategory] = useState('');
  const [priority, setPriority] = useState('');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [categories, setCategories] = useState<string[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setItems(await notificationApi.list({
        category: category || undefined, priority: priority || undefined,
        unread_only: unreadOnly || undefined, limit: 100,
      }));
      setSelected(new Set());
    } finally { setLoading(false); }
  }, [category, priority, unreadOnly]);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { notificationApi.categories().then(setCategories).catch(() => {}); }, []);

  const toggle = (id: string) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const bulkRead = async () => { if (selected.size) { await notificationApi.bulkRead({ ids: [...selected] }); load(); } };
  const markAll = async () => { await notificationApi.markAllRead(); load(); };
  const dismiss = async (id: string) => { await notificationApi.dismiss(id); load(); };
  const openOne = async (n: NotificationResponse) => {
    if (!n.is_read) await notificationApi.markRead(n.id);
    if (n.link_url) navigate(n.link_url); else load();
  };

  return (
    <div className="space-y-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-4 flex flex-wrap items-center gap-3">
        <Filter className="w-4 h-4 text-slate-500" />
        <select value={category} onChange={(e) => setCategory(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
          <option value="">All categories</option>{categories.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <select value={priority} onChange={(e) => setPriority(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
          <option value="">All priorities</option>{['urgent', 'high', 'normal', 'low'].map((p) => <option key={p} value={p}>{p}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer select-none">
          <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} className="w-3.5 h-3.5 rounded" /> Unread only
        </label>
        <div className="ml-auto flex items-center gap-2">
          {selected.size > 0 && <button onClick={bulkRead} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><Check className="w-3.5 h-3.5" /> Read {selected.size}</button>}
          <button onClick={markAll} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><CheckCheck className="w-3.5 h-3.5" /> Mark all read</button>
        </div>
      </div>

      <div className="glass-panel border border-slate-800/85 rounded-2xl overflow-hidden">
        {loading ? <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
          : items.length === 0 ? <div className="py-16 text-center"><Bell className="w-10 h-10 text-slate-600 mx-auto mb-3" /><p className="text-slate-400 text-sm">You're all caught up.</p></div>
          : (
            <ul className="divide-y divide-slate-800/40">
              {items.map((n) => (
                <li key={n.id} className={`flex items-start gap-3 px-4 py-3 hover:bg-slate-900/40 ${!n.is_read ? 'bg-slate-900/20' : ''}`}>
                  <input type="checkbox" checked={selected.has(n.id)} onChange={() => toggle(n.id)} className="mt-1 w-3.5 h-3.5 rounded shrink-0" />
                  <div className="flex-1 min-w-0 cursor-pointer" onClick={() => openOne(n)}>
                    <div className="flex items-center gap-2">
                      {!n.is_read && <span className="w-2 h-2 rounded-full bg-brand-500 shrink-0" />}
                      <span className="text-sm font-semibold text-slate-200 truncate">{n.title}</span>
                      <span className={`px-1.5 py-0.5 text-[9px] font-semibold rounded border uppercase ${PRIORITY_STYLE[n.priority] || PRIORITY_STYLE.normal}`}>{n.priority}</span>
                      <span className="px-1.5 py-0.5 text-[9px] rounded bg-slate-800/60 text-slate-400 border border-slate-700/50">{n.category}</span>
                    </div>
                    <p className="text-xs text-slate-400 mt-0.5 line-clamp-2">{n.body}</p>
                    <div className="flex items-center gap-2 mt-1">
                      <span className="text-[10px] text-slate-500">{timeAgo(n.created_at)}</span>
                      {n.channels_sent && n.channels_sent.filter((c) => c !== 'in_app').map((c) => (
                        <span key={c} className="text-[9px] text-slate-500 border border-slate-700/50 rounded px-1">{c}</span>
                      ))}
                      {(n.actions || []).map((a) => (
                        <button key={a.label} onClick={(e) => { e.stopPropagation(); if (a.url) navigate(a.url); }}
                                className="text-[10px] text-brand-400 hover:text-brand-300 underline">{a.label}</button>
                      ))}
                    </div>
                  </div>
                  <button onClick={() => dismiss(n.id)} title="Dismiss" className="p-1 text-slate-500 hover:text-red-400 cursor-pointer shrink-0"><X className="w-4 h-4" /></button>
                </li>
              ))}
            </ul>
          )}
      </div>
    </div>
  );
};

/* ── Preferences tab ── */
const PrefsTab: React.FC = () => {
  const [prefs, setPrefs] = useState<NotificationPreference[]>([]);
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => { notificationApi.getPreferences().then(setPrefs).catch(() => {}); }, []);

  const toggle = (cat: string, ch: keyof NotificationPreference) =>
    setPrefs((p) => p.map((x) => (x.category === cat ? { ...x, [ch]: !x[ch] } : x)));

  const save = async () => {
    setSaving(true); setMsg(null);
    try { setPrefs(await notificationApi.updatePreferences(prefs)); setMsg('Preferences saved.'); }
    catch (e: any) { setMsg(extractErrorMessage(e, 'Failed to save')); } finally { setSaving(false); }
  };

  const channels: (keyof NotificationPreference)[] = ['in_app', 'email', 'sms', 'whatsapp', 'push'];

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}
      <p className="text-xs text-slate-400">Choose how you're notified per category. In-app shows in the bell; other channels require your email/phone and the org's providers.</p>
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-slate-500 border-b border-slate-800/80">
              <th className="px-3 py-2 font-semibold">Category</th>
              {channels.map((c) => <th key={c} className="px-3 py-2 font-semibold text-center">{c.replace('_', '-')}</th>)}
            </tr>
          </thead>
          <tbody>
            {prefs.map((p) => (
              <tr key={p.category} className="border-b border-slate-800/40">
                <td className="px-3 py-2 text-slate-300 capitalize">{p.category}</td>
                {channels.map((ch) => (
                  <td key={ch} className="px-3 py-2 text-center">
                    <input type="checkbox" checked={!!p[ch]} onChange={() => toggle(p.category, ch)} className="w-4 h-4 rounded cursor-pointer" />
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save preferences
      </button>
    </div>
  );
};

/* ── Insights tab ── */
const InsightsTab: React.FC = () => {
  const [stats, setStats] = useState<NotificationStats | null>(null);
  useEffect(() => { notificationApi.stats().then(setStats).catch(() => {}); }, []);
  if (!stats) return <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>;
  const Bar: React.FC<{ title: string; buckets: { label: string; count: number }[] }> = ({ title, buckets }) => {
    const max = Math.max(1, ...buckets.map((b) => b.count));
    return (
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
        <h3 className="text-sm font-semibold text-slate-200 mb-4">{title}</h3>
        {buckets.length === 0 ? <p className="text-xs text-slate-500">No data.</p> : (
          <ul className="space-y-3">{[...buckets].sort((a, b) => b.count - a.count).map((b) => (
            <li key={b.label}><div className="flex justify-between text-xs mb-1"><span className="text-slate-300 capitalize">{b.label}</span><span className="text-slate-400">{b.count}</span></div>
              <div className="h-1.5 bg-slate-800/60 rounded-full overflow-hidden"><div className="h-full bg-gradient-to-r from-brand-500 to-indigo-500 rounded-full" style={{ width: `${(b.count / max) * 100}%` }} /></div></li>
          ))}</ul>
        )}
      </div>
    );
  };
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        {[{ l: 'Total', v: stats.total }, { l: 'Unread', v: stats.unread }, { l: 'Read', v: stats.read }, { l: 'Read Rate', v: `${stats.read_rate}%` }].map((s) => (
          <div key={s.l} className="glass-panel border border-slate-800/85 rounded-2xl p-5">
            <p className="text-[11px] font-semibold text-slate-500 uppercase tracking-wider">{s.l}</p>
            <p className="text-xl font-bold text-slate-100 mt-1">{s.v}</p>
          </div>
        ))}
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <Bar title="By Category" buckets={stats.by_category} />
        <Bar title="By Priority" buckets={stats.by_priority} />
      </div>
    </div>
  );
};

/* ── Broadcast modal (admin) ── */
const BroadcastModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [title, setTitle] = useState('');
  const [body, setBody] = useState('');
  const [role, setRole] = useState('');
  const [priority, setPriority] = useState('normal');
  const [fanout, setFanout] = useState(false);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const send = async () => {
    if (!title.trim() || !body.trim()) { setMsg('Title and body are required'); return; }
    setBusy(true); setMsg(null);
    try {
      const r = await notificationApi.broadcast({ title, body, priority, role: role || null, category: 'system', fanout });
      setMsg(`Sent to ${r.sent} of ${r.recipients} users.`);
    } catch (e: any) { setMsg(extractErrorMessage(e, 'Broadcast failed')); } finally { setBusy(false); }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Megaphone className="w-4 h-4 text-brand-400" /> Broadcast notification</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} placeholder="Message" className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          <div className="grid grid-cols-2 gap-2">
            <select value={role} onChange={(e) => setRole(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
              <option value="">Whole org</option>{['OrgAdmin', 'Manager', 'Employee'].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
            <select value={priority} onChange={(e) => setPriority(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
              {['low', 'normal', 'high', 'urgent'].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" checked={fanout} onChange={(e) => setFanout(e.target.checked)} className="w-4 h-4 rounded" /> Also send via email/SMS/WhatsApp/push (per each user's prefs)</label>
          <button onClick={send} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Megaphone className="w-4 h-4" />} Send broadcast
          </button>
        </div>
      </div>
    </div>
  );
};

type Tab = 'inbox' | 'prefs' | 'insights';

export const NotificationCenterPage: React.FC = () => {
  const { user } = useAuthStore();
  const canBroadcast = !!user && ['SuperAdmin', 'OrgAdmin', 'Manager'].includes(user.role);
  const [tab, setTab] = useState<Tab>('inbox');
  const [showBroadcast, setShowBroadcast] = useState(false);
  const [pushBusy, setPushBusy] = useState(false);
  const [pushMsg, setPushMsg] = useState<string | null>(null);

  const enablePush = async () => {
    setPushBusy(true); setPushMsg(null);
    try {
      let permission = 'granted';
      if (typeof Notification !== 'undefined') permission = await Notification.requestPermission();
      if (permission !== 'granted') { setPushMsg('Push permission denied'); return; }
      // Register a subscription (real Web Push delivery requires a service worker + VAPID keys)
      const endpoint = `webpush:${(crypto as any).randomUUID ? crypto.randomUUID() : Date.now()}`;
      await notificationApi.subscribePush({ endpoint, user_agent: navigator.userAgent });
      setPushMsg('Push enabled on this device.');
    } catch { setPushMsg('Could not enable push'); } finally { setPushBusy(false); }
  };

  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: 'inbox', label: 'Inbox', icon: Inbox },
    { key: 'prefs', label: 'Preferences', icon: SlidersHorizontal },
    { key: 'insights', label: 'Insights', icon: BarChart3 },
  ];

  return (
    <div className="space-y-4">
      <div className="border-b border-slate-800/60 pb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <Bell className="w-7 h-7 text-brand-400" /> Notifications
          </h1>
          <p className="text-sm text-slate-400 mt-1">History, channel preferences, and analytics.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={enablePush} disabled={pushBusy} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-2 px-3 rounded-lg text-sm cursor-pointer">
            {pushBusy ? <Loader2 className="w-4 h-4 animate-spin" /> : <BellRing className="w-4 h-4" />} Enable push
          </button>
          {canBroadcast && <button onClick={() => setShowBroadcast(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm cursor-pointer"><Megaphone className="w-4 h-4" /> Broadcast</button>}
        </div>
      </div>
      {pushMsg && <div className="p-2.5 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{pushMsg}</div>}

      <div className="flex items-center gap-1 border-b border-slate-800/60">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)} className={`inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px cursor-pointer ${tab === t.key ? 'border-brand-500 text-brand-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'inbox' && <InboxTab />}
      {tab === 'prefs' && <PrefsTab />}
      {tab === 'insights' && <InsightsTab />}

      {showBroadcast && <BroadcastModal onClose={() => setShowBroadcast(false)} />}
    </div>
  );
};
