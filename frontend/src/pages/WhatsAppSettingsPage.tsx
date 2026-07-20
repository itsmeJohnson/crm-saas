import React, { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon, Loader2, Check, Copy, RefreshCw, Zap, Trash2, Plus, MessageCircle,
} from 'lucide-react';
import { whatsappApi, WaSettings, QuickReply } from '../services/whatsappApi';
import { extractErrorMessage } from '../utils/errors';

const TokenRow: React.FC<{ label: string; value: string | null }> = ({ label, value }) => {
  const [copied, setCopied] = useState(false);
  return (
    <div className="space-y-1">
      <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{label}</span>
      <div className="flex items-center gap-2">
        <code className="flex-1 bg-slate-950/60 border border-slate-800 text-slate-300 py-2 px-3 rounded-lg text-xs truncate">{value || '—'}</code>
        <button onClick={() => { navigator.clipboard?.writeText(value || ''); setCopied(true); setTimeout(() => setCopied(false), 1500); }}
                className="p-2 rounded-lg text-slate-400 hover:text-emerald-400 border border-slate-700/60 cursor-pointer" title="Copy">
          {copied ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}
        </button>
      </div>
    </div>
  );
};

export const WhatsAppSettingsPage: React.FC = () => {
  const [settings, setSettings] = useState<WaSettings | null>(null);
  const [accessToken, setAccessToken] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [qrShortcut, setQrShortcut] = useState('');
  const [qrText, setQrText] = useState('');

  useEffect(() => {
    whatsappApi.getSettings().then(setSettings).catch(() => {});
    whatsappApi.listQuickReplies().then(setQuickReplies).catch(() => {});
  }, []);

  const save = async (opts: { regenerate_webhook_token?: boolean; regenerate_verify_token?: boolean } = {}) => {
    if (!settings) return;
    setSaving(true); setMsg(null);
    try {
      const updated = await whatsappApi.updateSettings({
        provider: settings.provider,
        phone_number_id: settings.phone_number_id || undefined,
        business_account_id: settings.business_account_id || undefined,
        access_token: accessToken || undefined,
        sender_number: settings.sender_number || undefined,
        daily_limit: settings.daily_limit,
        auto_reply_enabled: settings.auto_reply_enabled,
        auto_reply_message: settings.auto_reply_message || undefined,
        is_active: settings.is_active,
        ...opts,
      });
      setSettings(updated);
      setAccessToken('');
      setMsg('Settings saved.');
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Failed to save settings'));
    } finally {
      setSaving(false);
    }
  };

  const addQuickReply = async () => {
    if (!qrShortcut.trim() || !qrText.trim()) return;
    try {
      const qr = await whatsappApi.createQuickReply({ shortcut: qrShortcut.trim(), text: qrText.trim() });
      setQuickReplies((p) => [...p, qr]);
      setQrShortcut(''); setQrText('');
    } catch { /* ignore */ }
  };

  const removeQuickReply = async (id: string) => {
    try { await whatsappApi.deleteQuickReply(id); setQuickReplies((p) => p.filter((q) => q.id !== id)); } catch { /* ignore */ }
  };

  if (!settings) return <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>;

  const webhookBase = `${window.location.origin.replace(/:\d+$/, '')}/api/v1/whatsapp/webhook`;

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="border-b border-slate-800/60 pb-6">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <SettingsIcon className="w-7 h-7 text-emerald-400" /> WhatsApp Settings
        </h1>
        <p className="text-sm text-slate-400 mt-1">Business provider, auto-reply, quick replies, and webhooks.</p>
      </div>

      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}

      {/* Provider */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><MessageCircle className="w-4 h-4 text-emerald-400" /> Provider</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Provider</span>
            <select value={settings.provider} onChange={(e) => setSettings({ ...settings, provider: e.target.value })}
                    className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
              <option value="mock">Mock (dev / no send)</option>
              <option value="meta">Meta WhatsApp Cloud API</option>
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Sender number</span>
            <input value={settings.sender_number || ''} onChange={(e) => setSettings({ ...settings, sender_number: e.target.value })}
                   className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </label>
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Phone number ID</span>
            <input value={settings.phone_number_id || ''} onChange={(e) => setSettings({ ...settings, phone_number_id: e.target.value })}
                   className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </label>
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Business account ID</span>
            <input value={settings.business_account_id || ''} onChange={(e) => setSettings({ ...settings, business_account_id: e.target.value })}
                   className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </label>
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Access token (write-only)</span>
            <input type="password" value={accessToken} onChange={(e) => setAccessToken(e.target.value)} placeholder="•••• leave blank to keep"
                   className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </label>
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Daily limit</span>
            <input type="number" value={settings.daily_limit} onChange={(e) => setSettings({ ...settings, daily_limit: parseInt(e.target.value || '0', 10) })}
                   className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </label>
          <label className="flex items-center gap-2 pt-6">
            <input type="checkbox" checked={settings.is_active} onChange={(e) => setSettings({ ...settings, is_active: e.target.checked })} className="w-4 h-4 rounded" />
            <span className="text-sm text-slate-300">Active</span>
          </label>
        </div>
      </div>

      {/* Auto reply */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Zap className="w-4 h-4 text-emerald-400" /> Auto-reply</h3>
        <label className="flex items-center gap-2">
          <input type="checkbox" checked={settings.auto_reply_enabled} onChange={(e) => setSettings({ ...settings, auto_reply_enabled: e.target.checked })} className="w-4 h-4 rounded" />
          <span className="text-sm text-slate-300">Send an automatic reply to the first message of a new conversation</span>
        </label>
        <textarea value={settings.auto_reply_message || ''} onChange={(e) => setSettings({ ...settings, auto_reply_message: e.target.value })}
                  rows={2} placeholder="e.g. Thanks for reaching out! An agent will reply shortly."
                  className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
      </div>

      {/* Webhooks */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200">Webhooks</h3>
        <TokenRow label="Webhook token (inbound + status payloads)" value={settings.webhook_token} />
        <TokenRow label="Verify token (Meta GET handshake)" value={settings.webhook_verify_token} />
        <p className="text-[11px] text-slate-500">Callback URL: <code className="text-slate-400">{webhookBase}</code> (GET verify), <code className="text-slate-400">{webhookBase}/inbound</code>, <code className="text-slate-400">{webhookBase}/status</code>.</p>
        <div className="flex flex-wrap items-center gap-2">
          <button onClick={() => save()} disabled={saving}
                  className="inline-flex items-center gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save
          </button>
          <button onClick={() => save({ regenerate_webhook_token: true })} disabled={saving}
                  className="inline-flex items-center gap-2 bg-slate-800 text-slate-300 border border-slate-700/60 font-medium py-2 px-3 rounded-lg text-sm cursor-pointer">
            <RefreshCw className="w-4 h-4" /> New webhook token
          </button>
          <button onClick={() => save({ regenerate_verify_token: true })} disabled={saving}
                  className="inline-flex items-center gap-2 bg-slate-800 text-slate-300 border border-slate-700/60 font-medium py-2 px-3 rounded-lg text-sm cursor-pointer">
            <RefreshCw className="w-4 h-4" /> New verify token
          </button>
        </div>
      </div>

      {/* Quick replies */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Zap className="w-4 h-4 text-emerald-400" /> Quick replies</h3>
        <div className="flex flex-wrap items-end gap-2">
          <input value={qrShortcut} onChange={(e) => setQrShortcut(e.target.value)} placeholder="shortcut"
                 className="w-32 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          <input value={qrText} onChange={(e) => setQrText(e.target.value)} placeholder="Reply text"
                 className="flex-1 min-w-[180px] bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          <button onClick={addQuickReply} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-200 border border-slate-700/60 py-2 px-3 rounded-lg text-sm cursor-pointer"><Plus className="w-4 h-4" /> Add</button>
        </div>
        {quickReplies.length === 0 ? <p className="text-xs text-slate-500">No quick replies yet.</p> : (
          <ul className="space-y-1.5">
            {quickReplies.map((q) => (
              <li key={q.id} className="flex items-center gap-2 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <span className="px-1.5 py-0.5 text-[10px] font-semibold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0">{q.shortcut}</span>
                <span className="text-xs text-slate-300 truncate flex-1">{q.text}</span>
                <button onClick={() => removeQuickReply(q.id)} className="p-1 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
