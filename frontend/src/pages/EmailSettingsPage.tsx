import React, { useEffect, useState } from 'react';
import { Settings as SettingsIcon, Loader2, Check, Mail, Inbox, KeyRound } from 'lucide-react';
import { emailApi, EmailSettings } from '../services/emailApi';
import { extractErrorMessage } from '../utils/errors';

export const EmailSettingsPage: React.FC = () => {
  const [s, setS] = useState<EmailSettings | null>(null);
  const [smtpPassword, setSmtpPassword] = useState('');
  const [imapPassword, setImapPassword] = useState('');
  const [saving, setSaving] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => { emailApi.getSettings().then(setS).catch(() => {}); }, []);

  const save = async () => {
    if (!s) return;
    setSaving(true); setMsg(null);
    try {
      const updated = await emailApi.updateSettings({
        auth_method: s.auth_method, provider: s.provider, from_email: s.from_email || undefined,
        from_name: s.from_name || undefined, smtp_host: s.smtp_host || undefined, smtp_port: s.smtp_port || undefined,
        smtp_username: s.smtp_username || undefined, smtp_password: smtpPassword || undefined, smtp_use_tls: s.smtp_use_tls,
        imap_host: s.imap_host || undefined, imap_port: s.imap_port || undefined, imap_username: s.imap_username || undefined,
        imap_password: imapPassword || undefined, imap_use_ssl: s.imap_use_ssl,
        tracking_enabled: s.tracking_enabled, tracking_base_url: s.tracking_base_url || undefined, is_active: s.is_active,
      });
      setS(updated); setSmtpPassword(''); setImapPassword(''); setMsg('Settings saved.');
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Failed to save settings'));
    } finally {
      setSaving(false);
    }
  };

  if (!s) return <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>;
  const field = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
  const lbl = "text-[11px] font-semibold text-slate-400 uppercase tracking-wider";

  return (
    <div className="space-y-6 max-w-3xl">
      <div className="border-b border-slate-800/60 pb-6">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <SettingsIcon className="w-7 h-7 text-brand-400" /> Email Settings
        </h1>
        <p className="text-sm text-slate-400 mt-1">Mailbox connection, tracking, and sending identity.</p>
      </div>
      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}

      {/* Identity + method */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Mail className="w-4 h-4 text-brand-400" /> Sending identity</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="space-y-1"><span className={lbl}>Auth method</span>
            <select value={s.auth_method} onChange={(e) => setS({ ...s, auth_method: e.target.value })} className={field}>
              <option value="smtp">SMTP + IMAP (password)</option>
              <option value="oauth_google">OAuth · Gmail</option>
              <option value="oauth_microsoft">OAuth · Microsoft 365</option>
            </select>
          </label>
          <label className="space-y-1"><span className={lbl}>Provider</span>
            <select value={s.provider} onChange={(e) => setS({ ...s, provider: e.target.value })} className={field}>
              <option value="mock">Mock (dev / no send)</option>
              <option value="smtp">SMTP (live)</option>
            </select>
          </label>
          <label className="space-y-1"><span className={lbl}>From email</span>
            <input value={s.from_email || ''} onChange={(e) => setS({ ...s, from_email: e.target.value })} className={field} /></label>
          <label className="space-y-1"><span className={lbl}>From name</span>
            <input value={s.from_name || ''} onChange={(e) => setS({ ...s, from_name: e.target.value })} className={field} /></label>
        </div>
      </div>

      {/* SMTP */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Send2 /> SMTP (outgoing)</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="space-y-1"><span className={lbl}>Host</span>
            <input value={s.smtp_host || ''} onChange={(e) => setS({ ...s, smtp_host: e.target.value })} className={field} /></label>
          <label className="space-y-1"><span className={lbl}>Port</span>
            <input type="number" value={s.smtp_port || ''} onChange={(e) => setS({ ...s, smtp_port: parseInt(e.target.value || '0', 10) || null })} className={field} /></label>
          <label className="space-y-1"><span className={lbl}>Username</span>
            <input value={s.smtp_username || ''} onChange={(e) => setS({ ...s, smtp_username: e.target.value })} className={field} /></label>
          <label className="space-y-1"><span className={lbl}>Password (write-only)</span>
            <input type="password" value={smtpPassword} onChange={(e) => setSmtpPassword(e.target.value)} placeholder="•••• leave blank to keep" className={field} /></label>
          <label className="flex items-center gap-2 pt-6"><input type="checkbox" checked={s.smtp_use_tls} onChange={(e) => setS({ ...s, smtp_use_tls: e.target.checked })} className="w-4 h-4 rounded" /><span className="text-sm text-slate-300">Use TLS/SSL</span></label>
        </div>
      </div>

      {/* IMAP */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Inbox className="w-4 h-4 text-brand-400" /> IMAP (incoming)</h3>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <label className="space-y-1"><span className={lbl}>Host</span>
            <input value={s.imap_host || ''} onChange={(e) => setS({ ...s, imap_host: e.target.value })} className={field} /></label>
          <label className="space-y-1"><span className={lbl}>Port</span>
            <input type="number" value={s.imap_port || ''} onChange={(e) => setS({ ...s, imap_port: parseInt(e.target.value || '0', 10) || null })} className={field} /></label>
          <label className="space-y-1"><span className={lbl}>Username</span>
            <input value={s.imap_username || ''} onChange={(e) => setS({ ...s, imap_username: e.target.value })} className={field} /></label>
          <label className="space-y-1"><span className={lbl}>Password (write-only)</span>
            <input type="password" value={imapPassword} onChange={(e) => setImapPassword(e.target.value)} placeholder="•••• leave blank to keep" className={field} /></label>
          <label className="flex items-center gap-2 pt-6"><input type="checkbox" checked={s.imap_use_ssl} onChange={(e) => setS({ ...s, imap_use_ssl: e.target.checked })} className="w-4 h-4 rounded" /><span className="text-sm text-slate-300">Use SSL</span></label>
        </div>
        {s.last_synced_at && <p className="text-[11px] text-slate-500">Last synced: {new Date(s.last_synced_at).toLocaleString()}</p>}
        {s.auth_method !== 'smtp' && (
          <p className="text-[11px] text-amber-400/80 flex items-center gap-1.5"><KeyRound className="w-3.5 h-3.5" /> OAuth selected — connect the mailbox from your provider console; tokens are stored via the OAuth connect flow.</p>
        )}
      </div>

      {/* Tracking */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4">
        <h3 className="text-sm font-semibold text-slate-200">Tracking</h3>
        <label className="flex items-center gap-2"><input type="checkbox" checked={s.tracking_enabled} onChange={(e) => setS({ ...s, tracking_enabled: e.target.checked })} className="w-4 h-4 rounded" /><span className="text-sm text-slate-300">Inject open + click tracking into outgoing HTML</span></label>
        <label className="space-y-1"><span className={lbl}>Public tracking base URL</span>
          <input value={s.tracking_base_url || ''} onChange={(e) => setS({ ...s, tracking_base_url: e.target.value })} placeholder="https://crm.yourdomain.com" className={field} />
          <span className="text-[11px] text-slate-500">Where recipients' clients reach the tracking pixel / redirect. Leave blank to disable tracking links.</span>
        </label>
      </div>

      <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-5 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
        {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save settings
      </button>
    </div>
  );
};

// small inline icon alias to avoid another import name clash
const Send2: React.FC = () => <Mail className="w-4 h-4 text-brand-400" />;
