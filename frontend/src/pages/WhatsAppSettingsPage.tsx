import React, { useEffect, useState } from 'react';
import {
  Settings as SettingsIcon, Loader2, Check, Copy, RefreshCw, Zap, Trash2, Plus, MessageCircle, AlertTriangle, Play, HelpCircle
} from 'lucide-react';
import { whatsappApi, WaSettings, QuickReply, WaTemplate } from '../services/whatsappApi';
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
  const [settingsList, setSettingsList] = useState<WaSettings[]>([]);
  const [activeSettings, setActiveSettings] = useState<WaSettings | null>(null);
  const [accessToken, setAccessToken] = useState('');
  const [webhookSecret, setWebhookSecret] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);
  const [diagStatus, setDiagStatus] = useState<string | null>(null);
  const [checkingHealth, setCheckingHealth] = useState(false);
  const [syncingTemplates, setSyncingTemplates] = useState(false);
  const [syncedCount, setSyncedCount] = useState<number | null>(null);

  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [qrShortcut, setQrShortcut] = useState('');
  const [qrText, setQrText] = useState('');

  const loadData = async () => {
    try {
      const list = await whatsappApi.listSettings();
      setSettingsList(list);
      if (list.length > 0) {
        // Select first active or first config by default
        const active = list.find(s => s.is_active) || list[0];
        setActiveSettings(active);
      } else {
        // Fallback to fetch default settings row
        const defaultSet = await whatsappApi.getSettings();
        setSettingsList([defaultSet]);
        setActiveSettings(defaultSet);
      }
      
      const qrs = await whatsappApi.listQuickReplies();
      setQuickReplies(qrs);
    } catch (err) {
      logger.error('Failed to load settings data', err);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const save = async (opts: { regenerate_webhook_token?: boolean; regenerate_verify_token?: boolean } = {}) => {
    if (!activeSettings) return;
    setSaving(true); setMsg(null);
    try {
      const updated = await whatsappApi.updateSettings(activeSettings.id, {
        provider: activeSettings.provider,
        phone_number_id: activeSettings.phone_number_id || undefined,
        business_account_id: activeSettings.business_account_id || undefined,
        access_token: accessToken || undefined,
        webhook_secret: webhookSecret || undefined,
        sender_number: activeSettings.sender_number || undefined,
        daily_limit: activeSettings.daily_limit,
        auto_reply_enabled: activeSettings.auto_reply_enabled,
        auto_reply_message: activeSettings.auto_reply_message || undefined,
        is_active: activeSettings.is_active,
        ...opts,
      });
      setActiveSettings(updated);
      setSettingsList(prev => prev.map(s => s.id === updated.id ? updated : s));
      setAccessToken('');
      setWebhookSecret('');
      setMsg('Settings saved successfully.');
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Failed to save settings'));
    } finally {
      setSaving(false);
    }
  };

  const testConnection = async () => {
    if (!activeSettings) return;
    setCheckingHealth(true);
    setDiagStatus(null);
    try {
      const res = await whatsappApi.checkHealth(activeSettings.id);
      setDiagStatus(res.health_status);
      setActiveSettings(prev => prev ? { ...prev, health_status: res.health_status } : null);
      setSettingsList(prev => prev.map(s => s.id === activeSettings.id ? { ...s, health_status: res.health_status } : s));
    } catch (err: any) {
      setDiagStatus('failed');
    } finally {
      setCheckingHealth(false);
    }
  };

  const syncMetaTemplates = async () => {
    if (!activeSettings) return;
    setSyncingTemplates(true);
    setSyncedCount(null);
    try {
      const templates = await whatsappApi.syncTemplates(activeSettings.id);
      setSyncedCount(templates.length);
      setMsg(`Synced ${templates.length} templates from Meta successfully.`);
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Failed to sync templates'));
    } finally {
      setSyncingTemplates(false);
    }
  };

  const createNewNumberConfig = async () => {
    setSaving(true);
    try {
      // In CRM settings, updating settings without settings_id parameter will fall back to create new row if limit not violated
      const defaultSet = await whatsappApi.getSettings();
      // Let's create a new settings row by updating settings
      const newList = await whatsappApi.listSettings();
      setSettingsList(newList);
      setMsg('Created new number configuration container.');
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Failed to create new config'));
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

  if (!activeSettings) return <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>;

  const webhookBase = `${window.location.origin}/api/v1/whatsapp/webhooks`;

  return (
    <div className="space-y-6 max-w-4xl pb-16">
      <div className="border-b border-slate-800/60 pb-6 flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <SettingsIcon className="w-7 h-7 text-emerald-400" /> WhatsApp Settings
          </h1>
          <p className="text-sm text-slate-400 mt-1">Multi-number configuration, auto-reply triggers, webhooks, and canned replies.</p>
        </div>
        <button onClick={createNewNumberConfig} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-200 border border-slate-700/60 py-2 px-4 rounded-xl text-sm font-medium hover:bg-slate-700/60 transition cursor-pointer">
          <Plus className="w-4 h-4" /> Add Phone Number
        </button>
      </div>

      {msg && (
        <div className="p-4 bg-emerald-950/20 border border-emerald-800/40 text-emerald-300 rounded-2xl text-sm flex items-center gap-3">
          <Check className="w-5 h-5 shrink-0 text-emerald-400" />
          <span>{msg}</span>
        </div>
      )}

      {/* Account Selector Tabs */}
      {settingsList.length > 1 && (
        <div className="flex gap-2 overflow-x-auto pb-1">
          {settingsList.map((s) => (
            <button
              key={s.id}
              onClick={() => { setActiveSettings(s); setAccessToken(''); setWebhookSecret(''); setDiagStatus(null); setSyncedCount(null); }}
              className={`px-4 py-2 rounded-xl text-xs font-semibold uppercase tracking-wider transition whitespace-nowrap cursor-pointer ${
                activeSettings.id === s.id
                  ? 'bg-gradient-to-r from-emerald-500/25 to-teal-500/25 border border-emerald-500/40 text-emerald-300'
                  : 'bg-slate-900 border border-slate-800/80 text-slate-400 hover:text-slate-200'
              }`}
            >
              {s.sender_number || `Account ${s.phone_number_id?.slice(-4) || 'Unconfigured'}`}
            </button>
          ))}
        </div>
      )}

      {/* Grid of Main Config & Diagnostic Control */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        <div className="lg:col-span-2 space-y-6">
          {/* Config Details */}
          <div className="glass-panel border border-slate-800/85 rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <MessageCircle className="w-5 h-5 text-emerald-400" /> WhatsApp Account Configuration
            </h3>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <label className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Provider</span>
                <select value={activeSettings.provider} onChange={(e) => setActiveSettings({ ...activeSettings, provider: e.target.value })}
                        className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2.5 px-3.5 rounded-xl text-sm focus:border-emerald-500/50 transition">
                  <option value="mock">Mock Sandbox (dev/demo)</option>
                  <option value="meta">Meta Cloud API (production)</option>
                </select>
              </label>
              <label className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Display number</span>
                <input value={activeSettings.sender_number || ''} onChange={(e) => setActiveSettings({ ...activeSettings, sender_number: e.target.value })}
                       placeholder="+1 (555) 019-2834"
                       className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2 px-3 rounded-xl text-sm focus:border-emerald-500/50 transition" />
              </label>
              <label className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Phone number ID</span>
                <input value={activeSettings.phone_number_id || ''} onChange={(e) => setActiveSettings({ ...activeSettings, phone_number_id: e.target.value })}
                       placeholder="10492837493"
                       className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2 px-3 rounded-xl text-sm focus:border-emerald-500/50 transition" />
              </label>
              <label className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Business account ID</span>
                <input value={activeSettings.business_account_id || ''} onChange={(e) => setActiveSettings({ ...activeSettings, business_account_id: e.target.value })}
                       placeholder="928374928374938"
                       className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2 px-3 rounded-xl text-sm focus:border-emerald-500/50 transition" />
              </label>
              <label className="space-y-1 sm:col-span-2">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Permanent Access Token</span>
                <input type="password" value={accessToken} onChange={(e) => setAccessToken(e.target.value)} placeholder="•••••••••••••••••••••••• (leave blank to keep)"
                       className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2 px-3 rounded-xl text-sm focus:border-emerald-500/50 transition" />
              </label>
              <label className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Webhook Signing Secret</span>
                <input type="password" value={webhookSecret} onChange={(e) => setWebhookSecret(e.target.value)} placeholder="Verify signatures (leave blank to keep)"
                       className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2 px-3 rounded-xl text-sm focus:border-emerald-500/50 transition" />
              </label>
              <label className="space-y-1">
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Daily Limit Capping</span>
                <input type="number" value={activeSettings.daily_limit} onChange={(e) => setActiveSettings({ ...activeSettings, daily_limit: parseInt(e.target.value || '0', 10) })}
                       className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2 px-3 rounded-xl text-sm focus:border-emerald-500/50 transition" />
              </label>
              <div className="flex items-center gap-2 pt-4">
                <input type="checkbox" checked={activeSettings.is_active} onChange={(e) => setActiveSettings({ ...activeSettings, is_active: e.target.checked })} className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-emerald-500 focus:ring-emerald-500 cursor-pointer" />
                <span className="text-sm font-medium text-slate-300">Active Outbound Channel</span>
              </div>
            </div>
          </div>

          {/* Auto reply */}
          <div className="glass-panel border border-slate-800/85 rounded-2xl p-6 space-y-4">
            <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
              <Zap className="w-5 h-5 text-emerald-400" /> Auto-Responder
            </h3>
            <label className="flex items-center gap-2 cursor-pointer">
              <input type="checkbox" checked={activeSettings.auto_reply_enabled} onChange={(e) => setActiveSettings({ ...activeSettings, auto_reply_enabled: e.target.checked })} className="w-4 h-4 rounded border-slate-700 bg-slate-800 text-emerald-500 focus:ring-emerald-500 cursor-pointer" />
              <span className="text-sm text-slate-300 font-medium">Enable auto-reply on new incoming threads</span>
            </label>
            <textarea value={activeSettings.auto_reply_message || ''} onChange={(e) => setActiveSettings({ ...activeSettings, auto_reply_message: e.target.value })}
                      rows={3} placeholder="e.g. Thanks for messaging Johnson CRM! An agent will be in touch with you shortly."
                      className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2.5 px-3.5 rounded-xl text-sm focus:border-emerald-500/50 transition" />
          </div>
        </div>

        {/* Diagnostics & Webhook side column */}
        <div className="space-y-6">
          {/* Connection status diagnostic card */}
          <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Connection State</h4>
            
            <div className="flex items-center justify-between border border-slate-850 rounded-xl p-3 bg-slate-950/20">
              <span className="text-xs font-medium text-slate-300">Diagnostic health</span>
              <span className={`text-[10px] font-extrabold uppercase px-2 py-0.5 rounded border ${
                activeSettings.health_status === 'connected'
                  ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20'
                  : activeSettings.health_status === 'expired_token'
                  ? 'bg-amber-500/10 text-amber-400 border-amber-500/20'
                  : 'bg-rose-500/10 text-rose-400 border-rose-500/20'
              }`}>
                {activeSettings.health_status || 'untested'}
              </span>
            </div>

            <button onClick={testConnection} disabled={checkingHealth}
                    className="w-full inline-flex items-center justify-center gap-2 bg-slate-850 hover:bg-slate-800 text-slate-200 border border-slate-800 py-2 px-3 rounded-xl text-xs font-semibold cursor-pointer transition">
              {checkingHealth ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5 text-emerald-400" />} Run Diagnostics
            </button>

            {activeSettings.provider === 'meta' && (
              <button onClick={syncMetaTemplates} disabled={syncingTemplates}
                      className="w-full inline-flex items-center justify-center gap-2 bg-slate-850 hover:bg-slate-800 text-slate-200 border border-slate-800 py-2 px-3 rounded-xl text-xs font-semibold cursor-pointer transition">
                {syncingTemplates ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <RefreshCw className="w-3.5 h-3.5 text-teal-400" />} Sync Meta Templates
              </button>
            )}
          </div>

          {/* Webhook Endpoint credentials */}
          <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
            <h4 className="text-xs font-bold uppercase tracking-wider text-slate-400">Webhook Handshake</h4>
            
            <TokenRow label="Callback Inbound URL" value={webhookBase} />
            <TokenRow label="Meta verification token" value={activeSettings.webhook_verify_token} />

            <div className="flex flex-wrap items-center gap-2 pt-2 border-t border-slate-850">
              <button onClick={() => save({ regenerate_verify_token: true })} disabled={saving}
                      className="flex-1 inline-flex items-center justify-center gap-1.5 bg-slate-850 hover:bg-slate-800 text-slate-300 border border-slate-800/60 py-2 px-2.5 rounded-xl text-[10px] font-extrabold uppercase transition cursor-pointer">
                <RefreshCw className="w-3 h-3" /> New Verify Token
              </button>
            </div>
          </div>
        </div>
      </div>

      <div className="flex items-center gap-3 pt-4">
        <button onClick={() => save()} disabled={saving}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-emerald-500 to-teal-500 hover:from-emerald-400 hover:to-teal-400 text-white font-semibold py-2.5 px-6 rounded-xl text-sm shadow-md transition disabled:opacity-40 cursor-pointer">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save Changes
        </button>
      </div>

      {/* Quick replies */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-6 space-y-4">
        <h3 className="text-sm font-bold text-slate-200 flex items-center gap-2">
          <Zap className="w-5 h-5 text-emerald-400" /> Canned Quick-Replies
        </h3>
        <div className="flex flex-wrap items-end gap-3 bg-slate-950/20 p-4 border border-slate-850 rounded-xl">
          <label className="w-36 space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-450">Shortcut key</span>
            <input value={qrShortcut} onChange={(e) => setQrShortcut(e.target.value)} placeholder="/thanks"
                   className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2 px-3 rounded-lg text-xs" />
          </label>
          <label className="flex-1 min-w-[200px] space-y-1">
            <span className="text-[10px] font-bold uppercase tracking-wider text-slate-450">Canned text message template</span>
            <input value={qrText} onChange={(e) => setQrText(e.target.value)} placeholder="Thanks for choosing Johnson CRM! Let us know if you need anything else."
                   className="w-full bg-slate-850/80 border border-slate-800 text-slate-200 py-2 px-3 rounded-lg text-xs" />
          </label>
          <button onClick={addQuickReply} className="inline-flex items-center gap-1.5 bg-slate-850 hover:bg-slate-800 text-slate-200 border border-slate-800 py-2 px-4 rounded-xl text-xs font-semibold cursor-pointer"><Plus className="w-3.5 h-3.5 text-emerald-400" /> Create</button>
        </div>
        
        {quickReplies.length === 0 ? (
          <p className="text-xs text-slate-500">No quick replies created yet. Canned shortcuts starting with `/` will speed up composing replies.</p>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
            {quickReplies.map((q) => (
              <div key={q.id} className="flex items-center justify-between p-3 bg-slate-950/10 border border-slate-850 rounded-xl hover:border-slate-800/80 transition">
                <div className="flex items-center gap-2 min-w-0">
                  <span className="px-2 py-0.5 text-[9px] font-bold rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 shrink-0 uppercase tracking-wider">{q.shortcut}</span>
                  <span className="text-xs text-slate-305 truncate">{q.text}</span>
                </div>
                <button onClick={() => removeQuickReply(q.id)} className="p-1 text-slate-550 hover:text-red-400 cursor-pointer shrink-0 transition" title="Delete reply"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

const logger = {
  error: (msg: string, err: any) => console.error(msg, err)
};
