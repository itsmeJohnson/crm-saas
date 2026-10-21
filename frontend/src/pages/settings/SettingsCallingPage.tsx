import React, { useEffect, useState } from 'react';
import { settingsApi, TelephonyConfig, TelephonyConfigUpdate } from '../../services/settingsApi';
import { api } from '../../services/api';
import { Phone, ShieldCheck, Loader2, CheckCircle, AlertCircle, Building2, Smartphone, Key } from 'lucide-react';

const PROVIDERS = [
  { id: 'telecmi', label: 'TeleCMI (Connle Cloud Telephony)', desc: 'Enterprise Cloud Telephony Click2Call, Softphone & Webhooks' },
  { id: 'callerdesk', label: 'Callerdesk', desc: 'Cloud Telephony Click2Call & Inbound Webhooks' },
  { id: 'myoperator', label: 'MyOperator', desc: 'Cloud Telephony OBD & IVR' },
  { id: 'twilio', label: 'Twilio Voice (BYOK Global VoIP & SIP)', desc: 'Global Cloud Voice, Webhooks & Elastic SIP Trunking' },
  { id: 'msg91', label: 'MSG91 Voice (BYOK Cloud Audio)', desc: 'Cloud Audio IVR & Transactional Voice Gateway' },
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
  const [simToken, setSimToken] = useState<string | null>(null);
  const [simDevices, setSimDevices] = useState<any[]>([]);

  const fetchSimDevices = async () => {
    try {
      const res = await api.get('/telephony/sim/devices');
      if (Array.isArray(res.data)) {
        setSimDevices(res.data);
      }
    } catch (e) {}
  };

  const generateSimToken = async () => {
    try {
      const res = await api.post('/telephony/sim/tokens');
      setSimToken(res.data.token);
      fetchSimDevices();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to generate SIM pairing token');
    }
  };

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

  useEffect(() => {
    load();
    fetchSimDevices();
  }, []);

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

        {/* TeleCMI Fields */}
        {currentProvider === 'telecmi' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-emerald-500/10 border border-emerald-500/20 rounded-xl flex items-start gap-3">
              <Phone className="w-5 h-5 text-emerald-400 shrink-0 mt-0.5" />
              <div className="text-xs text-slate-300 space-y-1">
                <p className="font-semibold text-emerald-300">TeleCMI / Connle Cloud Telephony (rest.telecmi.com)</p>
                <p>
                  Enables instantaneous <strong>Click-to-Call</strong> from lead profiles, <strong>softphone dialing</strong>, and <strong>real-time Call Notification / CDR webhooks</strong> with call recordings.
                  Find your App ID and Secret in your TeleCMI dashboard under <em>Developer &rarr; App Secret</em>.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {textField('App ID', 'company_id', 'e.g. 33339071')}
              {secretField('App Secret', 'secret_token', cfg?.has_secret_token || cfg?.has_x_api_key || false)}
              {textField('Virtual Number (Caller ID)', 'default_caller_id', 'e.g. 917949817390')}
              {textField('Default Agent User ID / Extension', 'user_uuid', 'e.g. 5001_33339071')}
              {textField('TeleCMI Webhook URL (Paste into TeleCMI Developer > Webhooks)', 'webhook_url', `${window.location.origin}/api/v1/telephony/webhook`)}
            </div>

            <div className="p-3 bg-slate-800/60 rounded-xl border border-slate-700/60 text-xs text-slate-400">
              <span className="font-semibold text-slate-200">Webhook Configuration in TeleCMI:</span> In TeleCMI Dashboard &rarr; <em>Settings</em> &rarr; <em>Developer</em> &rarr; <em>Webhooks</em>, click <strong>+ Add</strong> and create two webhooks using the URL above: one for <strong>Call Notification (POST)</strong> and one for <strong>Call Report / CDR (POST)</strong>.
            </div>
          </div>
        )}

        {/* Callerdesk Fields */}
        {currentProvider === 'callerdesk' && (
          <div className="space-y-4">
            <div className="p-3.5 bg-indigo-500/10 border border-indigo-500/20 rounded-xl flex items-start gap-3">
              <Phone className="w-5 h-5 text-indigo-400 shrink-0 mt-0.5" />
              <div className="text-xs text-slate-300 space-y-1">
                <p className="font-semibold text-indigo-300">Callerdesk Cloud Telephony (api.callerdesk.io)</p>
                <p>
                  Enables instantaneous <strong>Click-to-Call</strong> from lead profiles and <strong>real-time Inbound Call popups</strong> with call recording logs.
                  Find your Authcode under <strong>Integration Settings</strong> in your Callerdesk dashboard.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              {secretField('Auth Code / API Key', 'x_api_key', cfg?.has_x_api_key || cfg?.has_authentication_token || false)}
              {textField('Deskphone / Virtual Number (DID)', 'default_caller_id', 'e.g. 0806924xxxx')}
              {textField('Default Agent Number (fallback)', 'user_uuid', 'e.g. 9620194983')}
              {textField('Callerdesk Webhook URL (Paste into Callerdesk)', 'webhook_url', `${window.location.origin}/api/v1/telephony/webhook`)}
            </div>

            <div className="p-3 bg-slate-800/60 rounded-xl border border-slate-700/60 text-xs text-slate-400">
              <span className="font-semibold text-slate-200">Webhook Configuration in Callerdesk:</span> Paste the Webhook URL above into your Callerdesk Dashboard &rarr; <em>API &amp; Integration</em> &rarr; <em>Webhooks</em> for both <em>Live Call</em> and <em>Call Report</em> to receive incoming popups and synced recordings.
            </div>
          </div>
        )}

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

        {/* Twilio BYOK Fields */}
        {currentProvider === 'twilio' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {textField('Twilio Account SID', 'company_id', 'ACxxxxxxxxxxxxxxxxxxxxxxxxxxxx')}
            {secretField('Twilio Auth Token', 'secret_token', cfg?.has_secret_token || false)}
            {textField('Twilio Outbound Caller ID (E.164)', 'default_caller_id', 'e.g. +14155552671')}
            {textField('Status Callback Webhook (optional)', 'webhook_url', `${window.location.origin}/api/v1/telephony/webhook`)}
          </div>
        )}

        {/* MSG91 BYOK Fields */}
        {currentProvider === 'msg91' && (
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            {secretField('MSG91 Auth Key', 'x_api_key', cfg?.has_x_api_key || false)}
            {textField('Caller DID / Outbound Number', 'default_caller_id', 'e.g. 080XXXXXXXX')}
            {textField('Status Callback Webhook (optional)', 'webhook_url', `${window.location.origin}/api/v1/telephony/webhook`)}
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

      {/* Android Mobile SIM App Synchronization */}
      <div className="bg-[#111a2e] border border-[#1e293b] rounded-2xl p-4 sm:p-6 space-y-4 shadow-xl">
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-emerald-500/15 border border-emerald-500/30 flex items-center justify-center text-emerald-400 shrink-0">
              <Smartphone className="w-5 h-5" />
            </div>
            <div>
              <h2 className="text-base font-bold text-white flex items-center gap-2">
                Android Mobile SIM App Synchronization
                <span className="text-[10px] font-bold px-2 py-0.5 rounded bg-emerald-500/15 text-emerald-400 border border-emerald-500/30">
                  GSM Background Token
                </span>
              </h2>
              <p className="text-xs text-slate-400">
                Direct GSM call synchronization: native mobile phone logs and call durations are ingested directly into the CRM database automatically.
              </p>
            </div>
          </div>
          <button
            type="button"
            onClick={generateSimToken}
            className="min-h-[40px] px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-xl text-xs font-bold transition flex items-center gap-1.5 cursor-pointer shadow-md shadow-indigo-600/20 self-start sm:self-auto"
          >
            <Key className="w-3.5 h-3.5" />
            Generate Pairing Token
          </button>
        </div>

        {simToken && (
          <div className="p-3.5 bg-[#080b14] border border-emerald-500/30 rounded-xl space-y-1.5">
            <span className="text-[10px] uppercase font-bold text-emerald-400">Pairing Token (Valid for 90 Days)</span>
            <div className="flex items-center justify-between gap-2">
              <code className="text-xs font-mono text-emerald-300 select-all truncate">{simToken}</code>
              <button
                type="button"
                onClick={() => { navigator.clipboard.writeText(simToken); alert('Pairing token copied to clipboard'); }}
                className="px-3 py-1 text-xs font-bold bg-emerald-500/20 text-emerald-300 rounded-lg hover:bg-emerald-500/30 cursor-pointer"
              >
                Copy
              </button>
            </div>
          </div>
        )}

        {/* Registered Devices List */}
        <div className="space-y-2 pt-2 border-t border-[#1e293b]">
          <span className="text-xs font-bold uppercase tracking-wider text-slate-400">Registered Floor Smartphones</span>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-3">
            {simDevices.length === 0 ? (
              <p className="text-xs text-slate-500 col-span-full">No mobile SIM devices paired yet. Click "Generate Pairing Token" to register an Android device.</p>
            ) : (
              simDevices.map((dev: any) => (
                <div key={dev.id} className="p-3 rounded-xl bg-[#080b14] border border-[#1e293b] space-y-1 text-xs">
                  <div className="flex items-center justify-between">
                    <span className="font-bold text-white">{dev.device_model || 'Android Smartphone'}</span>
                    <span className="text-[10px] text-emerald-400 bg-emerald-500/10 px-1.5 py-0.5 rounded border border-emerald-500/20">Active Sync</span>
                  </div>
                  <p className="text-slate-400 text-[11px]">Caller: {dev.phone_number || 'SIM 1'}</p>
                  <p className="text-slate-500 text-[10px]">Last Heartbeat: {new Date(dev.last_sync_at).toLocaleTimeString()}</p>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
