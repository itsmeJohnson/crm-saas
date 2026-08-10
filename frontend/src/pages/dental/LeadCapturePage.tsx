import React, { useState, useEffect } from 'react';
import {
  Webhook, Plus, Copy, Check, RotateCw, Trash2, RefreshCw, X, Loader2,
  Radio, Instagram, Search as SearchIcon, Globe, Zap,
} from 'lucide-react';
import { api } from '../../services/api';

interface Source {
  id: string;
  name: string;
  provider: string;
  token: string;
  source_label: string;
  is_active: boolean;
  leads_captured: number;
  last_received_at: string | null;
  has_secret: boolean;
  webhook_url: string;
}
interface CaptureEvent {
  id: string;
  source_id: string;
  external_id: string | null;
  lead_id: string | null;
  status: string;
  error: string | null;
  created_at: string;
}

const PROVIDERS: { key: string; label: string; hint: string }[] = [
  { key: 'meta_lead_ads', label: 'Meta Lead Ads (Facebook / Instagram)', hint: 'Paste the webhook URL into your Meta app’s Webhooks → leadgen, using the verify token below.' },
  { key: 'google_ads', label: 'Google Ads Lead Forms', hint: 'Add the webhook URL as the Lead Form’s webhook endpoint in Google Ads.' },
  { key: 'web_form', label: 'Website Form', hint: 'POST your form submissions as JSON to the webhook URL.' },
  { key: 'zapier', label: 'Zapier / Make', hint: 'Use a “Webhooks by Zapier” POST action to the webhook URL.' },
  { key: 'generic', label: 'Generic (any platform)', hint: 'POST a JSON payload to the webhook URL; fields are auto-mapped.' },
];

const providerMeta = (p: string) => {
  switch (p) {
    case 'meta_lead_ads': return { icon: Instagram, tint: 'from-pink-500 to-fuchsia-600', label: 'Meta Lead Ads' };
    case 'google_ads': return { icon: SearchIcon, tint: 'from-amber-400 to-orange-500', label: 'Google Ads' };
    case 'web_form': return { icon: Globe, tint: 'from-cyan-400 to-blue-500', label: 'Website Form' };
    case 'zapier': return { icon: Zap, tint: 'from-orange-400 to-red-500', label: 'Zapier / Make' };
    default: return { icon: Radio, tint: 'from-slate-400 to-slate-600', label: 'Generic' };
  }
};

export const LeadCapturePage: React.FC = () => {
  const [sources, setSources] = useState<Source[]>([]);
  const [events, setEvents] = useState<CaptureEvent[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [isModalOpen, setModalOpen] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const fetchAll = async () => {
    setIsLoading(true);
    try {
      const [s, e] = await Promise.all([
        api.get('/lead-capture/sources'),
        api.get('/lead-capture/events', { params: { limit: 30 } }),
      ]);
      setSources(s.data || []);
      setEvents(e.data || []);
    } catch (err) {
      console.error(err);
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => { fetchAll(); }, []);

  const copy = async (url: string, id: string) => {
    try {
      await navigator.clipboard.writeText(url);
      setCopiedId(id);
      setTimeout(() => setCopiedId(null), 1600);
    } catch { /* clipboard blocked */ }
  };

  const rotate = async (id: string) => {
    if (!confirm('Rotate this endpoint’s token? The old webhook URL will stop working immediately.')) return;
    await api.post(`/lead-capture/sources/${id}/rotate-token`);
    fetchAll();
  };

  const remove = async (id: string) => {
    if (!confirm('Delete this capture source? Its webhook will stop accepting leads.')) return;
    await api.delete(`/lead-capture/sources/${id}`);
    fetchAll();
  };

  const toggleActive = async (s: Source) => {
    await api.patch(`/lead-capture/sources/${s.id}`, { is_active: !s.is_active });
    fetchAll();
  };

  const sourceName = (id: string) => sources.find((s) => s.id === id)?.name || '—';

  return (
    <div className="space-y-6 select-none">
      {/* Header */}
      <div className="bento-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-fuchsia-500 to-cyan-500 flex items-center justify-center text-white shadow-lg shadow-fuchsia-500/25 flex-shrink-0">
            <Webhook className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-100">Lead Capture &amp; Ad Integrations</h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Connect Meta, Google, WhatsApp &amp; web forms — new ad leads flow straight into your pipeline.
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <button onClick={fetchAll} className="neo-btn px-3.5 py-2.5 text-xs flex items-center gap-2 text-slate-300">
            <RefreshCw className="w-4 h-4" /> Refresh
          </button>
          <button onClick={() => setModalOpen(true)} className="neo-btn-primary px-4 py-2.5 text-xs flex items-center gap-2">
            <Plus className="w-4 h-4" /> Add Source
          </button>
        </div>
      </div>

      {/* Sources */}
      {isLoading ? (
        <div className="bento-card p-10 flex items-center justify-center text-slate-400 text-sm">
          <Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading capture sources…
        </div>
      ) : sources.length === 0 ? (
        <div className="bento-card p-10 text-center">
          <Webhook className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-300 font-semibold">No lead sources connected yet</p>
          <p className="text-slate-500 text-xs mt-1 max-w-md mx-auto">
            Add a source to get a webhook URL you can paste into Meta Lead Ads, Google Ads, or a Zapier/landing-page flow.
          </p>
          <button onClick={() => setModalOpen(true)} className="neo-btn-primary px-4 py-2.5 text-xs inline-flex items-center gap-2 mt-4">
            <Plus className="w-4 h-4" /> Add your first source
          </button>
        </div>
      ) : (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          {sources.map((s) => {
            const meta = providerMeta(s.provider);
            const Icon = meta.icon;
            return (
              <div key={s.id} className="bento-card p-5 space-y-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-3">
                    <div className={`w-10 h-10 rounded-xl bg-gradient-to-br ${meta.tint} flex items-center justify-center text-white flex-shrink-0`}>
                      <Icon className="w-5 h-5" />
                    </div>
                    <div>
                      <div className="text-sm font-bold text-slate-100">{s.name}</div>
                      <div className="text-[11px] text-slate-400">{meta.label} · tags as “{s.source_label}”</div>
                    </div>
                  </div>
                  <button
                    onClick={() => toggleActive(s)}
                    className={`px-2.5 py-1 rounded-lg text-[10px] font-bold uppercase tracking-wider ${
                      s.is_active ? 'bg-emerald-500/15 text-emerald-400 border border-emerald-500/25'
                                  : 'bg-slate-700/40 text-slate-400 border border-slate-700'}`}
                  >
                    {s.is_active ? 'Active' : 'Paused'}
                  </button>
                </div>

                {/* webhook URL */}
                <div>
                  <label className="text-[10px] font-bold uppercase tracking-wider text-slate-500">Webhook URL</label>
                  <div className="flex items-center gap-2 mt-1.5">
                    <input readOnly value={s.webhook_url}
                           className="neo-input flex-1 px-3 py-2 text-[11px] font-mono text-slate-300 truncate" />
                    <button onClick={() => copy(s.webhook_url, s.id)}
                            className="neo-btn px-3 py-2 text-xs flex items-center gap-1.5 text-slate-300 flex-shrink-0">
                      {copiedId === s.id ? <><Check className="w-3.5 h-3.5 text-emerald-400" /> Copied</> : <><Copy className="w-3.5 h-3.5" /> Copy</>}
                    </button>
                  </div>
                </div>

                <div className="flex items-center justify-between text-[11px] text-slate-400 pt-1">
                  <span><b className="text-slate-200">{s.leads_captured}</b> leads captured</span>
                  <span>{s.has_secret ? '🔒 Signed' : 'Unsigned'}</span>
                  <span>{s.last_received_at ? `Last: ${new Date(s.last_received_at).toLocaleDateString()}` : 'No leads yet'}</span>
                </div>

                <div className="flex items-center gap-2 pt-1 border-t border-slate-800">
                  <button onClick={() => rotate(s.id)} className="neo-btn px-3 py-1.5 text-[11px] flex items-center gap-1.5 text-slate-400 mt-3">
                    <RotateCw className="w-3.5 h-3.5" /> Rotate token
                  </button>
                  <button onClick={() => remove(s.id)} className="neo-btn px-3 py-1.5 text-[11px] flex items-center gap-1.5 text-rose-400 mt-3">
                    <Trash2 className="w-3.5 h-3.5" /> Delete
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Recent captured leads */}
      <div className="bento-card p-5">
        <h2 className="text-sm font-bold text-slate-100 mb-3 flex items-center gap-2">
          <Radio className="w-4 h-4 text-cyan-400" /> Recent inbound leads
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full text-xs">
            <thead>
              <tr className="text-left text-[10px] uppercase tracking-wider text-slate-500 border-b border-slate-800">
                <th className="py-2 pr-4">When</th><th className="py-2 pr-4">Source</th>
                <th className="py-2 pr-4">Status</th><th className="py-2 pr-4">External ID</th><th className="py-2">Lead</th>
              </tr>
            </thead>
            <tbody>
              {events.length === 0 ? (
                <tr><td colSpan={5} className="py-6 text-center text-slate-500">No inbound leads captured yet.</td></tr>
              ) : events.map((e) => (
                <tr key={e.id} className="border-b border-slate-800/60">
                  <td className="py-2.5 pr-4 text-slate-400 whitespace-nowrap">{new Date(e.created_at).toLocaleString()}</td>
                  <td className="py-2.5 pr-4 text-slate-300">{sourceName(e.source_id)}</td>
                  <td className="py-2.5 pr-4">
                    <span className={`px-2 py-0.5 rounded-md text-[10px] font-bold ${
                      e.status === 'created' ? 'bg-emerald-500/15 text-emerald-400'
                      : e.status === 'duplicate' ? 'bg-amber-500/15 text-amber-400'
                      : 'bg-rose-500/15 text-rose-400'}`}>{e.status}</span>
                  </td>
                  <td className="py-2.5 pr-4 font-mono text-slate-500">{e.external_id || '—'}</td>
                  <td className="py-2.5">
                    {e.lead_id
                      ? <a href={`/leads?leadId=${e.lead_id}`} className="text-cyan-400 hover:text-cyan-300">Open →</a>
                      : <span className="text-slate-600">{e.error ? e.error.slice(0, 40) : '—'}</span>}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {isModalOpen && <AddSourceModal onClose={() => setModalOpen(false)} onSuccess={fetchAll} />}
    </div>
  );
};

const AddSourceModal: React.FC<{ onClose: () => void; onSuccess: () => void }> = ({ onClose, onSuccess }) => {
  const [name, setName] = useState('');
  const [provider, setProvider] = useState('meta_lead_ads');
  const [sourceLabel, setSourceLabel] = useState('Instagram Ads');
  const [secret, setSecret] = useState('');
  const [verifyToken, setVerifyToken] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const hint = PROVIDERS.find((p) => p.key === provider)?.hint;

  const submit = async (ev: React.FormEvent) => {
    ev.preventDefault();
    if (!name.trim()) { setError('Give this source a name.'); return; }
    setSubmitting(true); setError('');
    try {
      await api.post('/lead-capture/sources', {
        name: name.trim(),
        provider,
        source_label: sourceLabel.trim() || 'Web Lead',
        secret: secret.trim() || null,
        meta_verify_token: provider === 'meta_lead_ads' ? (verifyToken.trim() || null) : null,
      });
      onSuccess();
      onClose();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Could not create the source.');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
        <div className="p-5 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-fuchsia-500/15 border border-fuchsia-500/25 flex items-center justify-center text-fuchsia-400">
              <Webhook className="w-5 h-5" />
            </div>
            <h3 className="text-sm font-bold text-slate-100">Connect a lead source</h3>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300"><X className="w-5 h-5" /></button>
        </div>

        <form onSubmit={submit} className="p-5 space-y-4 overflow-y-auto">
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Source name</label>
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Instagram Braces Campaign"
                   className="neo-input w-full px-3.5 py-2.5 text-xs" />
          </div>
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Platform</label>
            <select value={provider} onChange={(e) => setProvider(e.target.value)} className="neo-input w-full px-3.5 py-2.5 text-xs">
              {PROVIDERS.map((p) => <option key={p.key} value={p.key}>{p.label}</option>)}
            </select>
            {hint && <p className="text-[11px] text-slate-500 mt-1.5">{hint}</p>}
          </div>
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Attribute leads as (source)
            </label>
            <input value={sourceLabel} onChange={(e) => setSourceLabel(e.target.value)} placeholder="e.g. Instagram Ads"
                   className="neo-input w-full px-3.5 py-2.5 text-xs" />
          </div>
          {provider === 'meta_lead_ads' && (
            <div>
              <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
                Meta verify token
              </label>
              <input value={verifyToken} onChange={(e) => setVerifyToken(e.target.value)} placeholder="You choose this — paste the same value in Meta"
                     className="neo-input w-full px-3.5 py-2.5 text-xs" />
            </div>
          )}
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">
              Signing secret <span className="text-slate-600 normal-case font-normal">(optional, recommended)</span>
            </label>
            <input value={secret} onChange={(e) => setSecret(e.target.value)} placeholder="HMAC secret to verify payloads"
                   className="neo-input w-full px-3.5 py-2.5 text-xs" />
          </div>

          {error && <p className="text-xs text-rose-400">{error}</p>}

          <div className="flex items-center gap-2 pt-1">
            <button type="button" onClick={onClose} className="neo-btn px-4 py-2.5 text-xs text-slate-300 flex-1">Cancel</button>
            <button type="submit" disabled={submitting} className="neo-btn-primary px-4 py-2.5 text-xs flex-1 flex items-center justify-center gap-2">
              {submitting ? <><Loader2 className="w-4 h-4 animate-spin" /> Creating…</> : 'Create & get webhook URL'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};
