import React, { useEffect, useState } from 'react';
import { settingsApi, TelephonyConfig, TelephonyConfigUpdate } from '../../services/settingsApi';
import { Phone, ShieldCheck, Loader2, CheckCircle, AlertCircle } from 'lucide-react';

/** Settings → Communication → Calling → MyOperator.
 *  Org-level telephony config. Secrets are shown only as "configured" (never the
 *  value); leaving a secret field blank keeps the stored value. */
export const SettingsCallingPage: React.FC = () => {
  const [cfg, setCfg] = useState<TelephonyConfig | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [banner, setBanner] = useState<{ ok: boolean; msg: string } | null>(null);

  // Non-secret fields (controlled). Secrets are write-only (separate state, blank = unchanged).
  const [form, setForm] = useState<TelephonyConfigUpdate>({});
  const [secrets, setSecrets] = useState({ x_api_key: '', secret_token: '', authentication_token: '', webhook_secret: '' });

  const load = async () => {
    setLoading(true);
    try {
      const c = await settingsApi.getCalling();
      setCfg(c);
      setForm({
        provider: c.provider, company_id: c.company_id || '', public_ivr_id: c.public_ivr_id || '',
        call_type: c.call_type, default_caller_id: c.default_caller_id || '', std_code: c.std_code || '',
        webhook_url: c.webhook_url || '', user_uuid: c.user_uuid || '', is_active: c.is_active,
        call_recording: c.call_recording, power_dialer: c.power_dialer, predictive_dialer: c.predictive_dialer,
        auto_assignment: c.auto_assignment, call_retry_count: c.call_retry_count,
        retry_interval_seconds: c.retry_interval_seconds, max_call_duration_seconds: c.max_call_duration_seconds,
      });
    } catch (e: any) {
      setBanner({ ok: false, msg: e.response?.data?.message || e.response?.data?.detail || 'Failed to load.' });
    } finally { setLoading(false); }
  };

  useEffect(() => { load(); }, []);

  const save = async () => {
    setSaving(true); setBanner(null);
    try {
      const payload: TelephonyConfigUpdate = { ...form };
      // Only send secrets the admin actually typed.
      (['x_api_key', 'secret_token', 'authentication_token', 'webhook_secret'] as const).forEach((k) => {
        if (secrets[k].trim()) (payload as any)[k] = secrets[k].trim();
      });
      const updated = await settingsApi.updateCalling(payload);
      setCfg(updated);
      setSecrets({ x_api_key: '', secret_token: '', authentication_token: '', webhook_secret: '' });
      setBanner({ ok: true, msg: 'Configuration saved.' });
    } catch (e: any) {
      setBanner({ ok: false, msg: e.response?.data?.message || e.response?.data?.detail || 'Save failed.' });
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true); setBanner(null);
    try {
      const r = await settingsApi.testCalling();
      setBanner({ ok: !!r.success, msg: r.message || (r.success ? 'Connection OK.' : 'Test failed.') });
    } catch (e: any) {
      setBanner({ ok: false, msg: e.response?.data?.message || 'Test failed.' });
    } finally { setTesting(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-400"><Loader2 className="w-6 h-6 animate-spin" /></div>;

  const secretField = (label: string, key: keyof typeof secrets, has: boolean) => (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">{label}</label>
      <input
        type="password"
        value={secrets[key]}
        onChange={(e) => setSecrets((s) => ({ ...s, [key]: e.target.value }))}
        placeholder={has ? '•••••••• (configured — leave blank to keep)' : 'Not set'}
        className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2 px-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
      />
    </div>
  );

  const textField = (label: string, key: keyof TelephonyConfigUpdate, placeholder = '') => (
    <div className="space-y-1.5">
      <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">{label}</label>
      <input
        type="text"
        value={(form[key] as string) ?? ''}
        onChange={(e) => setForm((f) => ({ ...f, [key]: e.target.value }))}
        placeholder={placeholder}
        className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2 px-3 rounded-lg focus:outline-none focus:ring-2 focus:ring-indigo-500 text-sm"
      />
    </div>
  );

  const toggle = (label: string, key: keyof TelephonyConfigUpdate) => (
    <label className="flex items-center justify-between py-2">
      <span className="text-sm text-slate-300">{label}</span>
      <button type="button" onClick={() => setForm((f) => ({ ...f, [key]: !(f[key] as boolean) }))}
        className={`w-10 h-5 rounded-full transition-colors ${form[key] ? 'bg-emerald-500/70' : 'bg-slate-700'}`}>
        <span className={`block w-4 h-4 bg-white rounded-full transition-transform mt-0.5 ${form[key] ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </button>
    </label>
  );

  return (
    <div className="max-w-3xl mx-auto p-6 space-y-6">
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
          <Phone className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-100">Calling — MyOperator</h1>
          <p className="text-sm text-slate-400 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400" /> Organization-level. Encrypted at rest. Employees never see these credentials.
          </p>
        </div>
      </div>

      {banner && (
        <div className={`flex items-center gap-2 p-3 rounded-xl text-sm ${banner.ok ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border border-red-500/20 text-red-400'}`}>
          {banner.ok ? <CheckCircle className="w-4 h-4" /> : <AlertCircle className="w-4 h-4" />} {banner.msg}
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-6 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          {textField('Company ID', 'company_id', 'e.g. 6a675bc2efc87963')}
          {textField('Public IVR ID', 'public_ivr_id', 'From MyOperator outbound flow')}
          {secretField('X-API-Key', 'x_api_key', cfg?.has_x_api_key || false)}
          {secretField('Secret Token', 'secret_token', cfg?.has_secret_token || false)}
          {secretField('Authentication Token', 'authentication_token', cfg?.has_authentication_token || false)}
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">Call Type</label>
            <select value={form.call_type ?? '1'} onChange={(e) => setForm((f) => ({ ...f, call_type: e.target.value }))}
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500">
              <option value="1">Type 1</option><option value="2">Type 2</option><option value="3">Type 3</option>
            </select>
          </div>
          {textField('Default Caller ID', 'default_caller_id', 'e.g. +91XXXXXXXXXX')}
          {textField('STD Code', 'std_code', 'e.g. 080')}
          {textField('User UUID (optional)', 'user_uuid')}
          {textField('Webhook URL', 'webhook_url', 'https://your-crm/api/v1/settings/calling/webhook')}
          {secretField('Webhook Secret', 'webhook_secret', cfg?.has_webhook_secret || false)}
        </div>

        <div className="border-t border-slate-800 pt-4 grid grid-cols-1 sm:grid-cols-2 gap-x-8">
          {toggle('Call Recording', 'call_recording')}
          {toggle('Power Dialer', 'power_dialer')}
          {toggle('Predictive Dialer', 'predictive_dialer')}
          {toggle('Auto Assignment', 'auto_assignment')}
          {toggle('Active', 'is_active')}
        </div>

        <div className="border-t border-slate-800 pt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          {textField('Call Retry Count', 'call_retry_count' as any)}
          {textField('Retry Interval (sec)', 'retry_interval_seconds' as any)}
          {textField('Max Call Duration (sec)', 'max_call_duration_seconds' as any)}
        </div>
      </div>

      <div className="flex items-center gap-3">
        <button onClick={save} disabled={saving}
          className="flex items-center gap-2 bg-gradient-to-r from-emerald-600 to-teal-600 hover:from-emerald-500 hover:to-teal-500 disabled:opacity-40 text-white font-semibold py-2.5 px-5 rounded-xl text-sm">
          {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <CheckCircle className="w-4 h-4" />} Save Configuration
        </button>
        <button onClick={test} disabled={testing}
          className="flex items-center gap-2 bg-slate-800 hover:bg-slate-700 border border-slate-700 text-slate-200 font-semibold py-2.5 px-5 rounded-xl text-sm">
          {testing ? <Loader2 className="w-4 h-4 animate-spin" /> : <ShieldCheck className="w-4 h-4" />} Test Connection
        </button>
        {cfg?.is_connected && <span className="text-xs text-emerald-400 flex items-center gap-1"><CheckCircle className="w-3.5 h-3.5" /> Connected</span>}
      </div>
    </div>
  );
};
