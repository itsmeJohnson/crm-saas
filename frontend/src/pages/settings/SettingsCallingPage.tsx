import React, { useEffect, useState } from 'react';
import { settingsApi, TelephonyConfig, TelephonyConfigUpdate } from '../../services/settingsApi';
import { Phone, ShieldCheck, Loader2, CheckCircle, AlertCircle, Building2 } from 'lucide-react';

const PROVIDERS = [
  { id: 'myoperator', label: 'MyOperator', desc: 'Cloud Telephony OBD & IVR' },
  { id: 'exotel', label: 'Exotel', desc: 'Enterprise Cloud Calling API' },
  { id: 'knowlarity', label: 'Knowlarity', desc: 'SuperReceptionist Click-to-Call' },
  { id: 'tata_smartflo', label: 'Tata Smartflo', desc: 'Tata Tele Business Cloud PBX' },
  { id: 'airtel_iq', label: 'Airtel IQ', desc: 'Bharti Airtel Cloud Communication' },
  { id: 'custom_webhook', label: 'Custom PBX / Webhook', desc: 'Asterisk, Vicidial, FreePBX, Ozonetel, or Custom VoIP' },
];

/** Settings → Communication → Calling.
 *  Org-level telephony config. Supports multiple Indian & global telephony providers.
 *  Secrets are stored AES-256 encrypted at rest and never echoed back to client. */
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
        provider: c.provider || 'myoperator', company_id: c.company_id || '', public_ivr_id: c.public_ivr_id || '',
        call_type: c.call_type || '1', default_caller_id: c.default_caller_id || '', std_code: c.std_code || '',
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
      setBanner({ ok: true, msg: 'Configuration saved successfully.' });
    } catch (e: any) {
      setBanner({ ok: false, msg: e.response?.data?.message || e.response?.data?.detail || 'Save failed.' });
    } finally { setSaving(false); }
  };

  const test = async () => {
    setTesting(true); setBanner(null);
    try {
      const r = await settingsApi.testCalling();
      setBanner({ ok: !!r.success, msg: r.message || (r.success ? 'Connection verified successfully.' : 'Test failed.') });
    } catch (e: any) {
      setBanner({ ok: false, msg: e.response?.data?.message || 'Test failed.' });
    } finally { setTesting(false); }
  };

  if (loading) return <div className="flex items-center justify-center h-64 text-slate-400"><Loader2 className="w-6 h-6 animate-spin" /></div>;

  const currentProvider = form.provider || 'myoperator';

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
    <div className="max-w-3xl mx-auto p-3 sm:p-6 space-y-4 sm:space-y-6">
      {/* Header */}
      <div className="flex items-center gap-3">
        <div className="w-10 h-10 rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 shrink-0">
          <Phone className="w-5 h-5" />
        </div>
        <div>
          <h1 className="text-xl font-bold text-slate-100">Telephony & Dialing Gateway</h1>
          <p className="text-xs sm:text-sm text-slate-400 flex items-center gap-1.5">
            <ShieldCheck className="w-3.5 h-3.5 text-emerald-400 shrink-0" /> Enterprise Click-to-Call. Multi-provider support.
          </p>
        </div>
      </div>

      {banner && (
        <div className={`flex items-center gap-2 p-3 rounded-xl text-sm ${banner.ok ? 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-400' : 'bg-red-500/10 border border-red-500/20 text-red-400'}`}>
          {banner.ok ? <CheckCircle className="w-4 h-4 shrink-0" /> : <AlertCircle className="w-4 h-4 shrink-0" />} {banner.msg}
        </div>
      )}

      {/* Provider Selector */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 space-y-3">
        <label className="text-xs font-semibold uppercase tracking-wider text-slate-300 flex items-center gap-1.5">
          <Building2 className="w-4 h-4 text-indigo-400" /> Select Telephony Provider
        </label>
        <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5">
          {PROVIDERS.map((p) => {
            const isSelected = currentProvider === p.id;
            return (
              <button
                key={p.id}
                type="button"
                onClick={() => setForm((f) => ({ ...f, provider: p.id }))}
                className={`p-3 rounded-xl border text-left transition-all flex items-start gap-3 cursor-pointer ${
                  isSelected
                    ? 'border-indigo-500/60 bg-indigo-500/10 text-white shadow-sm'
                    : 'border-slate-800 bg-slate-800/40 text-slate-300 hover:border-slate-700 hover:bg-slate-800/70'
                }`}
              >
                <div className={`mt-0.5 w-4 h-4 rounded-full border flex items-center justify-center shrink-0 ${isSelected ? 'border-indigo-400 bg-indigo-500' : 'border-slate-600'}`}>
                  {isSelected && <div className="w-1.5 h-1.5 rounded-full bg-white" />}
                </div>
                <div className="min-w-0">
                  <p className="text-sm font-semibold truncate">{p.label}</p>
                  <p className="text-xs text-slate-400 mt-0.5 line-clamp-1">{p.desc}</p>
                </div>
              </button>
            );
          })}
        </div>
      </div>

      {/* Provider-Specific Configuration Inputs */}
      <div className="bg-slate-900 border border-slate-800 rounded-2xl p-4 sm:p-6 space-y-4">
        <h2 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">
          {PROVIDERS.find((p) => p.id === currentProvider)?.label || currentProvider} Credentials
        </h2>

        {/* MyOperator Fields */}
        {currentProvider === 'myoperator' && (
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
          </div>
        )}

        {/* Exotel Fields */}
        {currentProvider === 'exotel' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {textField('Account SID', 'company_id', 'Your Exotel Account SID')}
            {secretField('API Key', 'x_api_key', cfg?.has_x_api_key || false)}
            {secretField('API Token', 'secret_token', cfg?.has_secret_token || false)}
            {textField('Exotel Virtual Caller ID (ExoPhone)', 'default_caller_id', 'e.g. 080XXXXXXXX')}
            {textField('Status Callback URL (optional)', 'webhook_url', 'https://your-domain/api/v1/telephony/webhook')}
          </div>
        )}

        {/* Knowlarity Fields */}
        {currentProvider === 'knowlarity' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {secretField('Knowlarity API Key', 'x_api_key', cfg?.has_x_api_key || false)}
            {textField('Knowlarity SRN (Caller ID)', 'default_caller_id', 'e.g. +91XXXXXXXXXX')}
          </div>
        )}

        {/* Tata Smartflo & Airtel IQ Fields */}
        {(currentProvider === 'tata_smartflo' || currentProvider === 'airtel_iq') && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {textField('Account / Subdomain ID', 'company_id', 'e.g. smartflo-corp')}
            {secretField('API Key', 'x_api_key', cfg?.has_x_api_key || false)}
            {secretField('Secret Key', 'secret_token', cfg?.has_secret_token || false)}
            {textField('Virtual Caller ID / DID', 'default_caller_id', 'e.g. +91XXXXXXXXXX')}
            {textField('PBX Webhook / Callback URL', 'webhook_url', 'e.g. https://api.smartflo.tatateleservices.com/v1/call')}
          </div>
        )}

        {/* Custom Webhook / PBX Fields */}
        {currentProvider === 'custom_webhook' && (
          <div className="space-y-4">
            <p className="text-xs text-slate-400">
              Integrate with any in-house Asterisk, Vicidial, FreePBX, Ozonetel, or custom VoIP dialer. The CRM will dispatch outbound click-to-call POST requests to your URL.
            </p>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {textField('Outbound Dialer Endpoint URL', 'webhook_url', 'https://pbx.agency.com/api/originate')}
              {secretField('API / Bearer Token', 'x_api_key', cfg?.has_x_api_key || false)}
              {textField('Default Outbound Caller ID', 'default_caller_id', 'e.g. +91XXXXXXXXXX')}
              {secretField('Inbound Webhook Secret (HMAC)', 'webhook_secret', cfg?.has_webhook_secret || false)}
            </div>
          </div>
        )}

        {/* Features & Policies */}
        <div className="border-t border-slate-800 pt-4 mt-4 space-y-1">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Telephony Features</p>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6">
            {toggle('Enable Telephony Integration', 'is_active')}
            {toggle('Call Recording Enabled', 'call_recording')}
            {toggle('Power Dialer Mode', 'power_dialer')}
            {toggle('Predictive Dialer Mode', 'predictive_dialer')}
            {toggle('Auto-Assign Inbound Calls to TLs', 'auto_assignment')}
          </div>
        </div>

        {/* Policy numbers */}
        <div className="border-t border-slate-800 pt-4 grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">Retry Count</label>
            <input type="number" value={form.call_retry_count ?? 4} min={0} max={20}
              onChange={(e) => setForm((f) => ({ ...f, call_retry_count: parseInt(e.target.value, 10) || 0 }))}
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">Retry Interval (sec)</label>
            <input type="number" value={form.retry_interval_seconds ?? 7200} min={0}
              onChange={(e) => setForm((f) => ({ ...f, retry_interval_seconds: parseInt(e.target.value, 10) || 0 }))}
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-semibold uppercase tracking-wider text-slate-300">Max Duration (sec)</label>
            <input type="number" value={form.max_call_duration_seconds ?? 3600} min={0}
              onChange={(e) => setForm((f) => ({ ...f, max_call_duration_seconds: parseInt(e.target.value, 10) || 0 }))}
              className="w-full bg-slate-800 border border-slate-700 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </div>
        </div>

        {/* Action buttons */}
        <div className="flex flex-col-reverse sm:flex-row items-stretch sm:items-center justify-end gap-3 pt-4 border-t border-slate-800">
          <button type="button" onClick={test} disabled={testing}
            className="w-full sm:w-auto px-4 py-2.5 rounded-xl border border-slate-700 hover:bg-slate-800 text-slate-200 text-sm font-medium transition-colors disabled:opacity-50 cursor-pointer">
            {testing ? 'Verifying…' : 'Test Connection'}
          </button>
          <button type="button" onClick={save} disabled={saving}
            className="w-full sm:w-auto px-5 py-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white text-sm font-semibold shadow-lg shadow-indigo-500/20 transition-all disabled:opacity-50 cursor-pointer">
            {saving ? 'Saving…' : 'Save Changes'}
          </button>
        </div>
      </div>
    </div>
  );
};
