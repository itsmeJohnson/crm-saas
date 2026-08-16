import React, { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { settingsApi, TelephonyConfig, TelephonyConfigUpdate } from '../../services/settingsApi';
import { extractErrorMessage } from '../../utils/errors';

// ── Marketplace catalog (frontend metadata) ─────────────────────────────────
// `kind` decides card behavior:
//   'myoperator' → fully wired Connect wizard + status (this build)
//   'route'      → managed elsewhere; Configure links to that page
//   'soon'       → placeholder (provider abstraction ready; adapter pending)
type Kind = 'myoperator' | 'route' | 'soon';
interface Provider {
  id: string; name: string; logo: string; category: Category;
  description: string; features: string[]; kind: Kind; route?: string;
}
type Category = 'Calling' | 'SMS' | 'WhatsApp' | 'Email' | 'Payments' | 'CRM' | 'AI' | 'Marketing';
const CATEGORIES: Category[] = ['Calling', 'SMS', 'WhatsApp', 'Email', 'Payments', 'CRM', 'AI', 'Marketing'];

const CATALOG: Provider[] = [
  { id: 'myoperator', name: 'MyOperator', logo: '☎️', category: 'Calling', kind: 'myoperator',
    description: 'Cloud telephony — click-to-call, IVR, call recording & logs.',
    features: ['Click-to-call', 'OBD / IVR', 'Recording', 'Call logs'] },
  { id: 'knowlarity', name: 'Knowlarity', logo: '📞', category: 'Calling', kind: 'soon',
    description: 'SuperReceptionist cloud calling.', features: ['Click-to-call', 'SRN caller ID'] },
  { id: 'exotel', name: 'Exotel', logo: '📲', category: 'Calling', kind: 'soon',
    description: 'Voice & call-flow APIs.', features: ['Click-to-call', 'Call flows'] },
  { id: 'twilio_voice', name: 'Twilio Voice', logo: '🔵', category: 'Calling', kind: 'soon',
    description: 'Programmable Voice.', features: ['Click-to-call', 'Recording'] },

  { id: 'msg91', name: 'MSG91', logo: '✉️', category: 'SMS', kind: 'route', route: '/sms',
    description: 'Transactional & promotional SMS with DLT.', features: ['DLT templates', 'Sender ID'] },
  { id: 'bhashsms', name: 'BhashSMS', logo: '📩', category: 'SMS', kind: 'route', route: '/sms',
    description: 'Bulk SMS (DND/NDND routes).', features: ['DND / NDND', 'Bulk'] },
  { id: 'twilio_sms', name: 'Twilio SMS', logo: '🔵', category: 'SMS', kind: 'soon',
    description: 'Programmable Messaging.', features: ['A2P 10DLC', 'Global'] },

  { id: 'meta_whatsapp', name: 'WhatsApp Cloud', logo: '🟢', category: 'WhatsApp', kind: 'route', route: '/whatsapp',
    description: 'Meta WhatsApp Business Cloud API.', features: ['Templates', 'Media', '24h window'] },
  { id: 'gupshup', name: 'Gupshup', logo: '💬', category: 'WhatsApp', kind: 'soon',
    description: 'WhatsApp BSP.', features: ['Templates', 'Bot'] },

  { id: 'smtp', name: 'Email (SMTP/IMAP)', logo: '📧', category: 'Email', kind: 'route', route: '/email',
    description: 'Send & sync email over SMTP/IMAP or OAuth.', features: ['SMTP', 'IMAP sync', 'Tracking'] },

  { id: 'cashfree', name: 'Cashfree', logo: '💳', category: 'Payments', kind: 'route', route: '/subscription',
    description: 'Payment gateway for subscriptions & invoices.', features: ['Checkout', 'Webhooks'] },
  { id: 'razorpay', name: 'Razorpay', logo: '💰', category: 'Payments', kind: 'soon',
    description: 'Payments & payouts.', features: ['Checkout', 'Payouts'] },

  { id: 'zoho', name: 'Zoho CRM', logo: '🗂️', category: 'CRM', kind: 'soon',
    description: 'Two-way lead & contact sync.', features: ['Sync', 'Webhooks'] },
  { id: 'openai', name: 'OpenAI', logo: '🤖', category: 'AI', kind: 'soon',
    description: 'LLM provider for the AI suite.', features: ['Chat', 'Embeddings'] },
  { id: 'mailchimp', name: 'Mailchimp', logo: '📣', category: 'Marketing', kind: 'soon',
    description: 'Marketing campaigns & audiences.', features: ['Campaigns', 'Audiences'] },
];

// ── Status ──────────────────────────────────────────────────────────────────
type Status = 'connected' | 'disconnected' | 'error' | 'unavailable';
const badge: Record<Status, { label: string; cls: string }> = {
  connected: { label: 'Connected', cls: 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30' },
  disconnected: { label: 'Not Configured', cls: 'bg-slate-600/20 text-slate-400 border-slate-600/40' },
  error: { label: 'Error', cls: 'bg-red-500/15 text-red-400 border-red-500/30' },
  unavailable: { label: 'Coming Soon', cls: 'bg-slate-700/20 text-slate-500 border-slate-700/40' },
};

const card = 'rounded-xl border border-slate-800/85 bg-slate-900/50 p-4 flex flex-col';

export const IntegrationMarketplacePage: React.FC = () => {
  const navigate = useNavigate();
  const [calling, setCalling] = useState<TelephonyConfig | null>(null);
  const [callingError, setCallingError] = useState<string | null>(null);
  const [lastSync, setLastSync] = useState<string | null>(null);
  const [wizardOpen, setWizardOpen] = useState(false);

  const loadCalling = async () => {
    try { setCalling(await settingsApi.getCalling()); }
    catch { setCalling(null); }
  };
  useEffect(() => { loadCalling(); }, []);

  const myopStatus: Status = useMemo(() => {
    if (callingError) return 'error';
    if (calling && calling.provider === 'myoperator' && calling.is_active &&
        calling.company_id && calling.public_ivr_id && calling.has_x_api_key) return 'connected';
    return 'disconnected';
  }, [calling, callingError]);

  const statusFor = (p: Provider): Status => {
    if (p.kind === 'myoperator') return myopStatus;
    if (p.kind === 'soon') return 'unavailable';
    return 'disconnected'; // 'route' providers: managed on their own page
  };

  const disconnectMyop = async () => {
    await settingsApi.updateCalling({ is_active: false });
    try { await settingsApi.disconnectCalling(); } catch { /* best-effort */ }
    setCallingError(null); setLastSync(null); loadCalling();
  };

  return (
    <div className="space-y-8">
      <div>
        <h1 className="text-xl font-bold text-slate-100">Integration Marketplace</h1>
        <p className="text-sm text-slate-400 mt-1">
          Connect your own provider accounts (BYOK). Credentials are stored <span className="text-indigo-300">org-level, AES-256 encrypted</span>,
          and never exposed to employees.
        </p>
      </div>

      {CATEGORIES.map((cat) => {
        const providers = CATALOG.filter((p) => p.category === cat);
        if (!providers.length) return null;
        return (
          <section key={cat}>
            <h2 className="text-sm font-semibold uppercase tracking-wider text-slate-400 mb-3">{cat}</h2>
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {providers.map((p) => {
                const st = statusFor(p);
                const connected = st === 'connected';
                return (
                  <div key={p.id} className={card}>
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-center gap-3">
                        <div className="w-10 h-10 rounded-lg bg-slate-800 flex items-center justify-center text-xl">{p.logo}</div>
                        <div>
                          <p className="font-semibold text-slate-100 leading-tight">{p.name}</p>
                          <span className={`inline-block mt-1 text-[10px] font-semibold px-2 py-0.5 rounded-full border ${badge[st].cls}`}>
                            {badge[st].label}
                          </span>
                        </div>
                      </div>
                    </div>

                    <p className="text-xs text-slate-400 mt-3">{p.description}</p>
                    <div className="flex flex-wrap gap-1.5 mt-2">
                      {p.features.map((f) => (
                        <span key={f} className="text-[10px] px-2 py-0.5 rounded bg-slate-800/70 text-slate-400">{f}</span>
                      ))}
                    </div>
                    {p.kind === 'myoperator' && connected && (
                      <p className="text-[10px] text-slate-500 mt-2">
                        {lastSync ? `Last checked: ${lastSync}` : (calling?.is_connected ? 'Verified' : 'Not verified — run a test')}
                      </p>
                    )}
                    {p.kind === 'myoperator' && callingError && (
                      <p className="text-[10px] text-red-400 mt-2">{callingError}</p>
                    )}

                    {/* Actions */}
                    <div className="mt-4 pt-3 border-t border-slate-800/80 flex gap-2">
                      {p.kind === 'soon' && (
                        <button disabled title="Provider adapter coming soon"
                          className="flex-1 text-xs font-semibold py-2 rounded-lg bg-slate-800/60 text-slate-500 cursor-not-allowed">
                          Coming soon
                        </button>
                      )}
                      {p.kind === 'route' && (
                        <button onClick={() => navigate(p.route!)}
                          className="flex-1 text-xs font-semibold py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white">
                          Configure
                        </button>
                      )}
                      {p.kind === 'myoperator' && !connected && (
                        <button onClick={() => { setCallingError(null); setWizardOpen(true); }}
                          className="flex-1 text-xs font-semibold py-2 rounded-lg bg-indigo-600 hover:bg-indigo-500 text-white">
                          Connect
                        </button>
                      )}
                      {p.kind === 'myoperator' && connected && (
                        <>
                          <button onClick={() => setWizardOpen(true)}
                            className="flex-1 text-xs font-semibold py-2 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200 border border-slate-700">
                            Configure
                          </button>
                          <button onClick={disconnectMyop}
                            className="flex-1 text-xs font-semibold py-2 rounded-lg bg-red-600/90 hover:bg-red-600 text-white">
                            Disconnect
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        );
      })}

      {wizardOpen && (
        <MyOperatorWizard
          initial={calling}
          onClose={() => setWizardOpen(false)}
          onDone={(msg, ok, when) => {
            setWizardOpen(false);
            setCallingError(ok ? null : msg);
            setLastSync(when);
            loadCalling();
          }}
        />
      )}
    </div>
  );
};

// ── MyOperator Connect wizard ───────────────────────────────────────────────
const MyOperatorWizard: React.FC<{
  initial: TelephonyConfig | null;
  onClose: () => void;
  onDone: (message: string, ok: boolean, when: string) => void;
}> = ({ initial, onClose, onDone }) => {
  const [f, setF] = useState({
    company_id: initial?.company_id ?? '',
    authentication_token: '',
    x_api_key: '',
    secret_token: '',
    public_ivr_id: initial?.public_ivr_id ?? '',
    call_type: initial?.call_type ?? '1',
  });
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  const set = (k: keyof typeof f) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) =>
    setF((s) => ({ ...s, [k]: e.target.value }));

  // Required to connect: company + (x-api-key/secret unless already stored).
  // Public IVR ID is needed only for OUTBOUND — incoming-only plans can skip it.
  const secretsPresent = initial?.has_x_api_key && initial?.has_secret_token;
  const ready = !!f.company_id.trim() &&
    (secretsPresent || (!!f.x_api_key.trim() && !!f.secret_token.trim()));

  const submit = async () => {
    setBusy(true); setErr(null);
    try {
      const payload: TelephonyConfigUpdate = {
        provider: 'myoperator',
        is_active: true,                    // auto-enable calling features
        company_id: f.company_id.trim(),
        public_ivr_id: f.public_ivr_id.trim(),
        call_type: f.call_type,
      };
      if (f.authentication_token.trim()) payload.authentication_token = f.authentication_token.trim();
      if (f.x_api_key.trim()) payload.x_api_key = f.x_api_key.trim();
      if (f.secret_token.trim()) payload.secret_token = f.secret_token.trim();
      await settingsApi.updateCalling(payload);           // encrypt + persist (org-level)
      const res = await settingsApi.testCalling();        // validate against the live provider
      const when = new Date().toLocaleString();
      if (res.success) onDone(res.message || 'Connected', true, when);
      else { setErr(res.message || 'Validation failed. Check your credentials / Public IVR ID.'); onDone(res.message || 'Validation failed', false, when); }
    } catch (e: any) {
      setErr(extractErrorMessage(e, 'Failed to save telephony configuration.'));
    } finally { setBusy(false); }
  };

  const field = (label: string, node: React.ReactNode, hint?: string) => (
    <div className="space-y-1">
      <label className="text-xs font-semibold text-slate-300">{label}</label>
      {node}
      {hint && <p className="text-[10px] text-slate-500">{hint}</p>}
    </div>
  );
  const input = 'w-full bg-slate-950 border border-slate-800 rounded-lg py-2 px-3 text-sm text-slate-200 focus:outline-none focus:ring-2 focus:ring-indigo-500/50';

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4" onClick={onClose}>
      <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 p-6 max-h-[90vh] overflow-y-auto"
        onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center gap-3 mb-4">
          <div className="w-9 h-9 rounded-lg bg-slate-800 flex items-center justify-center text-lg">☎️</div>
          <div>
            <h3 className="font-bold text-slate-100">Connect MyOperator</h3>
            <p className="text-xs text-slate-500">Org-level · encrypted at rest</p>
          </div>
        </div>

        <div className="space-y-3">
          {field('Company ID', <input className={input} value={f.company_id} onChange={set('company_id')} placeholder="e.g. 6a675bc2efc87963" />)}
          {field('Authentication Token', <input className={input} type="password" value={f.authentication_token} onChange={set('authentication_token')}
            placeholder={initial?.has_authentication_token ? '•••• stored — leave blank to keep' : ''} />)}
          {field('X-API-Key', <input className={input} type="password" value={f.x_api_key} onChange={set('x_api_key')}
            placeholder={initial?.has_x_api_key ? '•••• stored — leave blank to keep' : ''} />)}
          {field('Secret Token', <input className={input} type="password" value={f.secret_token} onChange={set('secret_token')}
            placeholder={initial?.has_secret_token ? '•••• stored — leave blank to keep' : ''} />)}
          {field('Public IVR ID', <input className={input} value={f.public_ivr_id} onChange={set('public_ivr_id')}
            placeholder="from MyOperator → outbound / Public IVR flow" />,
            'Required to route OBD calls. Found in your MyOperator panel, not in Endpoint Details.')}
          {field('Default Call Type',
            <select className={input} value={f.call_type} onChange={set('call_type')}>
              <option value="1">Type 1</option><option value="2">Type 2</option><option value="3">Type 3</option>
            </select>)}
        </div>

        {err && <p className="text-xs text-red-400 mt-3">{err}</p>}

        <div className="flex gap-2 mt-5">
          <button onClick={onClose} className="flex-1 text-sm font-semibold py-2.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-200">Cancel</button>
          <button onClick={submit} disabled={!ready || busy}
            className="flex-1 text-sm font-semibold py-2.5 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:opacity-40 text-white">
            {busy ? 'Validating…' : 'Save & Connect'}
          </button>
        </div>
      </div>
    </div>
  );
};
