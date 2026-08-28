import React, { useCallback, useEffect, useState } from 'react';
import {
  MessageSquare, Send, Loader2, Search, RefreshCw, Users, Settings as SettingsIcon,
  Inbox, ArrowUpRight, ArrowDownLeft, Check, Copy, ShieldCheck,
} from 'lucide-react';
import { smsApi, SmsItem, SmsSettings } from '../services/smsApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const PAGE_SIZE = 25;

const STATUS_STYLES: Record<string, string> = {
  delivered: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  sent: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  queued: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  received: 'bg-brand-500/10 text-brand-400 border-brand-500/20',
  failed: 'bg-red-500/10 text-red-400 border-red-500/20',
  undelivered: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const StatusBadge: React.FC<{ status: string | null }> = ({ status }) => {
  const s = status || 'unknown';
  return (
    <span className={`px-2 py-0.5 text-[11px] font-semibold rounded-md border ${STATUS_STYLES[s] || 'bg-slate-800/80 text-slate-300 border-slate-700/60'}`}>
      {s}
    </span>
  );
};

const segments = (text: string) => (text.length <= 160 ? 1 : Math.ceil(text.length / 153));

/* ── Compose single SMS ── */
const Compose: React.FC<{ onSent: () => void }> = ({ onSent }) => {
  const [toNumber, setToNumber] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [ok, setOk] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null); setOk(null); setSending(true);
    try {
      const res = await smsApi.send({ to_number: toNumber.trim(), body });
      setOk(`Message ${res.sms_status} to ${res.to_number}`);
      setBody(''); setToNumber('');
      onSent();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to send SMS'));
    } finally {
      setSending(false);
    }
  };

  return (
    <form onSubmit={submit} className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Send className="w-4 h-4 text-brand-400" /> Send SMS</h3>
      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      {ok && <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs">{ok}</div>}
      <input
        value={toNumber}
        onChange={(e) => setToNumber(e.target.value)}
        placeholder="Destination number, e.g. +919876500001"
        className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={4}
        maxLength={1600}
        placeholder="Type your message…"
        className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-slate-500">{body.length} chars · {segments(body)} segment(s)</span>
        <button
          type="submit"
          disabled={sending || !toNumber.trim() || !body.trim()}
          className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer"
        >
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Send
        </button>
      </div>
    </form>
  );
};

/* ── Bulk SMS ── */
const BulkCompose: React.FC<{ onSent: () => void }> = ({ onSent }) => {
  const [numbers, setNumbers] = useState('');
  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<string | null>(null);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null); setResult(null); setSending(true);
    try {
      const recipients = numbers.split(/[\n,]/).map((n) => n.trim()).filter(Boolean).map((to_number) => ({ to_number }));
      if (recipients.length === 0) { setError('Add at least one number'); setSending(false); return; }
      const res = await smsApi.sendBulk({ body, recipients });
      setResult(`${res.queued} queued, ${res.failed} failed of ${res.total}`);
      setNumbers(''); setBody('');
      onSent();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Bulk send failed'));
    } finally {
      setSending(false);
    }
  };

  return (
    <form onSubmit={submit} className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Users className="w-4 h-4 text-brand-400" /> Bulk SMS</h3>
      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      {result && <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs">{result}</div>}
      <textarea
        value={numbers}
        onChange={(e) => setNumbers(e.target.value)}
        rows={4}
        placeholder="One number per line (or comma-separated)"
        className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm font-mono focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
      <textarea
        value={body}
        onChange={(e) => setBody(e.target.value)}
        rows={3}
        maxLength={1600}
        placeholder="Message sent to everyone…"
        className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
      />
      <div className="flex items-center justify-between">
        <span className="text-[11px] text-slate-500">
          {numbers.split(/[\n,]/).map((n) => n.trim()).filter(Boolean).length} recipients · {segments(body)} segment(s) each
        </span>
        <button
          type="submit"
          disabled={sending || !body.trim()}
          className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer"
        >
          {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
          Send to all
        </button>
      </div>
    </form>
  );
};

/* ── BulkSMSPlans account panel: live balance + sender-ID list/request ── */
const BulkSmsAccountPanel: React.FC = () => {
  const [balance, setBalance] = useState<string | null>(null);
  const [senders, setSenders] = useState<{ sender_id: string | null; country: string | null; status: string | null }[]>([]);
  const [loading, setLoading] = useState(false);
  const [note, setNote] = useState<string | null>(null);
  const [newSender, setNewSender] = useState('');
  const [requesting, setRequesting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setNote(null);
    try {
      const [bal, list] = await Promise.all([smsApi.balance(), smsApi.senderIds()]);
      setBalance(bal.success && bal.amount != null ? `${bal.amount} ${bal.currency || ''}`.trim() : (bal.message || 'Unavailable'));
      setSenders(list.success ? list.items : []);
      if (!list.success && list.message) setNote(list.message);
    } catch (err: any) {
      setNote(extractErrorMessage(err, 'Failed to load account info'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const request = async () => {
    if (!newSender.trim()) return;
    setRequesting(true); setNote(null);
    try {
      const res = await smsApi.requestSenderId({ sender: newSender.trim() });
      setNote(res.message || (res.success ? 'Sender ID requested.' : 'Request failed.'));
      setNewSender('');
      if (res.success) load();
    } catch (err: any) {
      setNote(extractErrorMessage(err, 'Failed to request sender ID'));
    } finally {
      setRequesting(false);
    }
  };

  return (
    <div className="space-y-3 pt-3 border-t border-slate-800/60">
      <div className="flex items-center justify-between">
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">BulkSMSPlans account</span>
        <button onClick={load} disabled={loading}
                className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-brand-400 cursor-pointer">
          <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} /> Refresh
        </button>
      </div>
      <div className="text-sm text-slate-300">Balance: <span className="font-semibold text-emerald-400">{balance ?? '—'}</span></div>
      {note && <div className="text-[11px] text-amber-400">{note}</div>}
      <div className="space-y-1.5">
        <span className="text-[11px] text-slate-500">Sender IDs</span>
        {senders.length === 0 ? (
          <div className="text-[11px] text-slate-500">No sender IDs found.</div>
        ) : (
          <div className="flex flex-wrap gap-1.5">
            {senders.map((s, i) => (
              <span key={i} className="inline-flex items-center gap-1 bg-slate-800/70 border border-slate-700/60 rounded-lg px-2 py-1 text-xs text-slate-300">
                <b>{s.sender_id}</b>
                <span className={s.status === 'Approved' ? 'text-emerald-400' : 'text-amber-400'}>{s.status}</span>
              </span>
            ))}
          </div>
        )}
      </div>
      <div className="flex items-center gap-2">
        <input value={newSender} onChange={(e) => setNewSender(e.target.value)} placeholder="Request new sender ID (e.g. CRMTXT)"
               className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        <button onClick={request} disabled={requesting || !newSender.trim()}
                className="inline-flex items-center gap-1 bg-slate-800/80 border border-slate-700/60 text-slate-200 py-2 px-3 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
          {requesting ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Request
        </button>
      </div>
    </div>
  );
};

/* ── Provider settings (OrgAdmin) ── */
const SmsSettingsPanel: React.FC = () => {
  const [settings, setSettings] = useState<SmsSettings | null>(null);
  const [authToken, setAuthToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);

  useEffect(() => { smsApi.getSettings().then(setSettings).catch(() => {}); }, []);

  const save = async (regenerate = false) => {
    if (!settings) return;
    setSaving(true); setMsg(null);
    try {
      const updated = await smsApi.updateSettings({
        provider: settings.provider,
        sender_id: settings.sender_id || undefined,
        account_sid: settings.account_sid || undefined,
        auth_token: authToken || undefined,
        sms_priority: settings.sms_priority || undefined,
        sms_type: settings.sms_type || undefined,
        default_template_id: settings.default_template_id || undefined,
        daily_limit: settings.daily_limit,
        is_active: settings.is_active,
        regenerate_webhook_token: regenerate,
      });
      setSettings(updated);
      setAuthToken('');
      setMsg('Settings saved.');
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Failed to save settings'));
    } finally {
      setSaving(false);
    }
  };

  if (!settings) return <div className="py-12 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>;

  const webhookBase = `${window.location.origin.replace(/:\d+$/, '')}/api/v1/sms/webhook`;

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4 max-w-2xl">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><SettingsIcon className="w-4 h-4 text-brand-400" /> Provider Settings</h3>
      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        <label className="space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Provider</span>
          <select value={settings.provider} onChange={(e) => setSettings({ ...settings, provider: e.target.value })}
                  className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
            <option value="mock">Mock (dev / no send)</option>
            <option value="twilio">Twilio</option>
            <option value="bhash">BhashSMS</option>
            <option value="bulksmsplans">BulkSMSPlans</option>
          </select>
          {settings.provider === 'bhash' && (
            <p className="text-[11px] text-slate-500">Account SID = BhashSMS <b>user</b>, Auth Token = <b>pass</b>, Sender ID = approved <b>sender</b>.</p>
          )}
          {settings.provider === 'bulksmsplans' && (
            <p className="text-[11px] text-slate-500">Account SID = BulkSMSPlans <b>api_id</b>, Auth Token = <b>api_password</b>, Sender ID = approved DLT <b>sender</b>.</p>
          )}
        </label>
        {settings.provider === 'bhash' && (
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Route / Priority</span>
            <select value={settings.sms_priority || 'ndnd'} onChange={(e) => setSettings({ ...settings, sms_priority: e.target.value })}
                    className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
              <option value="ndnd">Transactional (ndnd) — reaches DND numbers</option>
              <option value="dnd">Promotional (dnd) — for promotional senders</option>
            </select>
          </label>
        )}
        {settings.provider === 'bulksmsplans' && (
          <>
            <label className="space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">SMS Type</span>
              <select value={settings.sms_type || 'Transactional'} onChange={(e) => setSettings({ ...settings, sms_type: e.target.value })}
                      className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
                <option value="Transactional">Transactional</option>
                <option value="Promotional">Promotional</option>
                <option value="OTP">OTP</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">DLT Template ID (optional)</span>
              <input value={settings.default_template_id || ''} onChange={(e) => setSettings({ ...settings, default_template_id: e.target.value })}
                     placeholder="Registered template id" className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
            </label>
          </>
        )}
        <label className="space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Sender ID / From</span>
          <input value={settings.sender_id || ''} onChange={(e) => setSettings({ ...settings, sender_id: e.target.value })}
                 placeholder="e.g. CRMTXT or +1..." className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Account SID / API Key</span>
          <input value={settings.account_sid || ''} onChange={(e) => setSettings({ ...settings, account_sid: e.target.value })}
                 className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Auth Token (write-only)</span>
          <input type="password" value={authToken} onChange={(e) => setAuthToken(e.target.value)}
                 placeholder="•••• leave blank to keep" className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Daily Limit</span>
          <input type="number" value={settings.daily_limit} onChange={(e) => setSettings({ ...settings, daily_limit: parseInt(e.target.value || '0', 10) })}
                 className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        </label>
        <label className="flex items-center gap-2 pt-6">
          <input type="checkbox" checked={settings.is_active} onChange={(e) => setSettings({ ...settings, is_active: e.target.checked })} className="w-4 h-4 rounded" />
          <span className="text-sm text-slate-300">Active</span>
        </label>
      </div>

      {settings.provider === 'bulksmsplans' && settings.is_active && <BulkSmsAccountPanel />}

      <div className="space-y-1.5 pt-2 border-t border-slate-800/60">
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Webhook token (for inbound + delivery callbacks)</span>
        <div className="flex items-center gap-2">
          <code className="flex-1 bg-slate-950/60 border border-slate-800 text-slate-300 py-2 px-3 rounded-lg text-xs truncate">{settings.webhook_token}</code>
          <button onClick={() => { navigator.clipboard?.writeText(settings.webhook_token || ''); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                  className="p-2 rounded-lg text-slate-400 hover:text-brand-400 border border-slate-700/60 cursor-pointer" title="Copy token">
            {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
          </button>
        </div>
        <p className="text-[11px] text-slate-500">Point your provider to <code className="text-slate-400">{webhookBase}/inbound</code> and <code className="text-slate-400">{webhookBase}/status</code>, sending this token in the payload.</p>
      </div>

      <div className="flex items-center gap-2 pt-2">
        <button onClick={() => save(false)} disabled={saving}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save
        </button>
        <button onClick={() => save(true)} disabled={saving}
                className="inline-flex items-center gap-2 bg-slate-800 text-slate-300 border border-slate-700/60 font-medium py-2 px-4 rounded-lg text-sm cursor-pointer">
          <RefreshCw className="w-4 h-4" /> Regenerate token
        </button>
      </div>
    </div>
  );
};

/* ── History with retry ── */
const History: React.FC<{ refreshKey: number }> = ({ refreshKey }) => {
  const [items, setItems] = useState<SmsItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [direction, setDirection] = useState('');
  const [smsStatus, setSmsStatus] = useState('');

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      const data = await smsApi.messages({
        search: search || undefined, direction: direction || undefined,
        sms_status: smsStatus || undefined, skip: page * PAGE_SIZE, limit: PAGE_SIZE,
      });
      setItems(data.items); setTotal(data.total);
    } finally {
      setIsLoading(false);
    }
  }, [search, direction, smsStatus, page]);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, search, refreshKey]);

  const retry = async (id: string) => {
    try {
      const updated = await smsApi.retry(id);
      setItems((prev) => prev.map((i) => (i.id === id ? updated : i)));
    } catch { /* keep row as-is on failure */ }
  };

  const refreshStatus = async (id: string) => {
    try {
      const updated = await smsApi.refreshStatus(id);
      setItems((prev) => prev.map((i) => (i.id === id ? updated : i)));
    } catch { /* keep row as-is on failure */ }
  };

  return (
    <div className="space-y-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input value={search} onChange={(e) => { setSearch(e.target.value); setPage(0); }} placeholder="Search messages / numbers…"
                 className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 pl-9 pr-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
        </div>
        <select value={direction} onChange={(e) => { setDirection(e.target.value); setPage(0); }}
                className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
          <option value="">All directions</option>
          <option value="OUTBOUND">Outbound</option>
          <option value="INBOUND">Inbound</option>
        </select>
        <select value={smsStatus} onChange={(e) => { setSmsStatus(e.target.value); setPage(0); }}
                className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
          <option value="">All statuses</option>
          {['queued', 'sent', 'delivered', 'failed', 'undelivered', 'received'].map((s) => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <div className="glass-panel border border-slate-800/85 rounded-2xl overflow-hidden">
        {isLoading ? (
          <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
        ) : items.length === 0 ? (
          <div className="py-20 text-center"><MessageSquare className="w-10 h-10 text-slate-600 mx-auto mb-3" /><p className="text-slate-400 text-sm">No messages found.</p></div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800/80 text-left text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3 font-semibold">Dir</th>
                  <th className="px-4 py-3 font-semibold">Number</th>
                  <th className="px-4 py-3 font-semibold">Message</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-4 py-3 font-semibold">Agent</th>
                  <th className="px-4 py-3 font-semibold">When</th>
                  <th className="px-4 py-3 font-semibold"></th>
                </tr>
              </thead>
              <tbody>
                {items.map((it) => (
                  <tr key={it.id} className="border-b border-slate-800/40 hover:bg-slate-900/40">
                    <td className="px-4 py-3">
                      {it.direction === 'INBOUND'
                        ? <ArrowDownLeft className="w-4 h-4 text-brand-400" />
                        : <ArrowUpRight className="w-4 h-4 text-emerald-400" />}
                    </td>
                    <td className="px-4 py-3 text-slate-300 font-mono text-xs">{it.direction === 'INBOUND' ? it.from_number : it.to_number}</td>
                    <td className="px-4 py-3 text-slate-300 max-w-[280px] truncate" title={it.body || ''}>{it.body}</td>
                    <td className="px-4 py-3">
                      <StatusBadge status={it.sms_status} />
                      {it.error && <p className="text-[10px] text-red-400/80 mt-1 max-w-[180px] truncate" title={it.error}>{it.error}</p>}
                    </td>
                    <td className="px-4 py-3 text-slate-400">{it.agent_name || '—'}</td>
                    <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">{new Date(it.timestamp).toLocaleString()}</td>
                    <td className="px-4 py-3">
                      {it.direction === 'OUTBOUND' && (it.sms_status === 'failed' || it.sms_status === 'undelivered') && (
                        <button onClick={() => retry(it.id)} title="Retry"
                                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-semibold rounded-md bg-slate-800/80 text-slate-300 border border-slate-700/60 hover:text-brand-400 cursor-pointer">
                          <RefreshCw className="w-3 h-3" /> Retry
                        </button>
                      )}
                      {it.direction === 'OUTBOUND' && (it.sms_status === 'sent' || it.sms_status === 'queued' || it.sms_status === 'pending') && (
                        <button onClick={() => refreshStatus(it.id)} title="Check delivery status"
                                className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-semibold rounded-md bg-slate-800/80 text-slate-300 border border-slate-700/60 hover:text-brand-400 cursor-pointer">
                          <RefreshCw className="w-3 h-3" /> Status
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {!isLoading && total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800/60">
            <span className="text-xs text-slate-500">{total} messages · page {page + 1}</span>
            <div className="flex items-center gap-1">
              <button disabled={page === 0} onClick={() => setPage((p) => p - 1)} className="px-2 py-1 rounded text-slate-400 hover:bg-slate-800/60 disabled:opacity-30 cursor-pointer text-xs">Prev</button>
              <button disabled={(page + 1) * PAGE_SIZE >= total} onClick={() => setPage((p) => p + 1)} className="px-2 py-1 rounded text-slate-400 hover:bg-slate-800/60 disabled:opacity-30 cursor-pointer text-xs">Next</button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

/* ── OTP verification tool (send code → verify) ── */
const OtpVerifyPanel: React.FC = () => {
  const [number, setNumber] = useState('');
  const [verificationId, setVerificationId] = useState<string | null>(null);
  const [masked, setMasked] = useState('');
  const [otp, setOtp] = useState('');
  const [status, setStatus] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const send = async () => {
    if (!number.trim()) return;
    setBusy(true); setMsg(null); setStatus(null);
    try {
      const rec = await smsApi.otpSend({ number: number.trim(), purpose: 'manual' });
      setVerificationId(rec.id); setMasked(rec.number_masked); setStatus(rec.status);
      setMsg(`Code sent to ${rec.number_masked}.`);
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Failed to send code'));
    } finally { setBusy(false); }
  };

  const verify = async () => {
    if (!verificationId || !otp.trim()) return;
    setBusy(true); setMsg(null);
    try {
      const rec = await smsApi.otpVerify({ verification_id: verificationId, otp: otp.trim() });
      setStatus(rec.status);
      setMsg(rec.status === 'verified' ? '✓ Number verified.' : 'Verification updated.');
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Invalid code'));
    } finally { setBusy(false); }
  };

  const reset = () => { setVerificationId(null); setOtp(''); setStatus(null); setMsg(null); setNumber(''); setMasked(''); };

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4 max-w-lg">
      <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><ShieldCheck className="w-4 h-4 text-brand-400" /> Verify a phone number</h3>
      <p className="text-[11px] text-slate-500">Sends a one-time code via the SMS gateway (requires the BulkSMSPlans provider). The gateway generates and validates the code.</p>
      {msg && <div className={`p-3 border rounded-lg text-xs ${status === 'verified' ? 'bg-emerald-900/30 border-emerald-700/50 text-emerald-300' : 'bg-slate-800/60 border-slate-700/60 text-slate-300'}`}>{msg}</div>}

      {!verificationId ? (
        <div className="flex items-center gap-2">
          <input value={number} onChange={(e) => setNumber(e.target.value)} placeholder="Phone number, e.g. 9620194983"
                 className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          <button onClick={send} disabled={busy || !number.trim()}
                  className="inline-flex items-center gap-1 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Send code
          </button>
        </div>
      ) : (
        <div className="space-y-3">
          <div className="text-xs text-slate-400">Code sent to <b className="text-slate-200">{masked}</b> · status: <b className={status === 'verified' ? 'text-emerald-400' : 'text-amber-400'}>{status}</b></div>
          {status !== 'verified' && (
            <div className="flex items-center gap-2">
              <input value={otp} onChange={(e) => setOtp(e.target.value)} placeholder="Enter code" inputMode="numeric"
                     className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm tracking-widest" />
              <button onClick={verify} disabled={busy || !otp.trim()}
                      className="inline-flex items-center gap-1 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Verify
              </button>
            </div>
          )}
          <button onClick={reset} className="text-xs text-slate-400 hover:text-brand-400 cursor-pointer">Start over</button>
        </div>
      )}
    </div>
  );
};

type Tab = 'compose' | 'history' | 'bulk' | 'otp' | 'settings';

export const SmsPage: React.FC = () => {
  const { user } = useAuthStore();
  const isAdmin = user?.role === 'OrgAdmin' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<Tab>('compose');
  const [refreshKey, setRefreshKey] = useState(0);

  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: 'compose', label: 'Compose', icon: Send },
    { key: 'history', label: 'History', icon: Inbox },
    { key: 'bulk', label: 'Bulk', icon: Users },
    { key: 'otp', label: 'Verify', icon: ShieldCheck },
    ...(isAdmin ? [{ key: 'settings' as Tab, label: 'Settings', icon: SettingsIcon }] : []),
  ];

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <MessageSquare className="w-7 h-7 text-brand-400" /> SMS
        </h1>
        <p className="text-sm text-slate-400 mt-1">Send, track delivery, and automate text messages.</p>
      </div>

      <div className="flex items-center gap-1 border-b border-slate-800/60">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
                  className={`inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors cursor-pointer ${
                    tab === t.key ? 'border-brand-500 text-brand-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'compose' && <Compose onSent={() => setRefreshKey((k) => k + 1)} />}
      {tab === 'history' && <History refreshKey={refreshKey} />}
      {tab === 'bulk' && <BulkCompose onSent={() => setRefreshKey((k) => k + 1)} />}
      {tab === 'otp' && <OtpVerifyPanel />}
      {tab === 'settings' && isAdmin && <SmsSettingsPanel />}
    </div>
  );
};
