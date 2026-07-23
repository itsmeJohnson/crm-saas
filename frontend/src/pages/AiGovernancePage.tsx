import React, { useCallback, useEffect, useState } from 'react';
import {
  ShieldCheck, Loader2, Download, LayoutDashboard, SlidersHorizontal, ScrollText,
  FlaskConical, Ban, EyeOff, AlertTriangle, Save,
} from 'lucide-react';
import {
  aiGovernanceApi as api, GovPolicy, GovDashboard, GovEvent, GovPreview, GOV_ACTION_TONE,
} from '../services/aiGovernanceApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';

const Toggle: React.FC<{ label: string; hint?: string; value: boolean; onChange: (v: boolean) => void; disabled?: boolean }> =
  ({ label, hint, value, onChange, disabled }) => (
    <div className="flex items-start justify-between gap-3 py-2 border-b border-slate-800/60 last:border-0">
      <div>
        <p className="text-xs font-semibold text-slate-200">{label}</p>
        {hint && <p className="text-[11px] text-slate-500 mt-0.5">{hint}</p>}
      </div>
      <button disabled={disabled} onClick={() => onChange(!value)}
        className={`shrink-0 w-10 h-5 rounded-full transition-colors cursor-pointer ${value ? 'bg-emerald-500/70' : 'bg-slate-700'} ${disabled ? 'opacity-50' : ''}`}>
        <span className={`block w-4 h-4 bg-white rounded-full transition-transform mt-0.5 ${value ? 'translate-x-5' : 'translate-x-0.5'}`} />
      </button>
    </div>
  );

export const AiGovernancePage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<'dashboard' | 'policy' | 'events' | 'test'>('dashboard');
  const [dash, setDash] = useState<GovDashboard | null>(null);
  const [policy, setPolicy] = useState<GovPolicy | null>(null);
  const [events, setEvents] = useState<GovEvent[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [saved, setSaved] = useState(false);

  const [testText, setTestText] = useState('Email the quote to rahul@acme.com and call +91 98765 43210');
  const [preview, setPreview] = useState<GovPreview | null>(null);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'dashboard') setDash(await api.dashboard());
      if (tab === 'policy') setPolicy(await api.policy());
      if (tab === 'events') setEvents((await api.events({ limit: 100 })).items);
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load AI governance.')); } finally { setLoading(false); }
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  const savePolicy = async (patch: Partial<GovPolicy>) => {
    if (!policy) return;
    setPolicy({ ...policy, ...patch });
    try { await api.updatePolicy(patch); setSaved(true); setTimeout(() => setSaved(false), 1500); }
    catch (e) { setErr(extractErrorMessage(e, 'Failed to save policy.')); load(); }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><ShieldCheck className="w-6 h-6 text-brand-400" /> AI Security & Governance</h1>
          <p className="text-sm text-slate-500 mt-1">Guard rails on every AI request — PII masking, prompt-injection protection, content filtering, model restrictions and a full compliance log.</p>
        </div>
        {isManager && (
          <button onClick={async () => { try { const t = await api.exportCsv(); const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([t], { type: 'text/csv' })); a.download = 'ai-governance.csv'; a.click(); URL.revokeObjectURL(a.href); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>
        )}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}
      {saved && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2 flex items-center gap-1.5"><Save className="w-3.5 h-3.5" /> Policy saved</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['policy', 'Policy', SlidersHorizontal], ['events', 'Compliance Log', ScrollText], ['test', 'Test Controls', FlaskConical]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading && tab !== 'test' ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {tab === 'dashboard' && dash && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Controls Active</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.controls_active}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Events 30d</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.events_30d}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><EyeOff className="w-3 h-3 text-amber-400" /> Masked</p><p className="text-xl font-bold text-amber-400 mt-1">{dash.masked_30d}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Ban className="w-3 h-3 text-red-400" /> Blocked</p><p className="text-xl font-bold text-red-400 mt-1">{dash.blocked_30d}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><AlertTriangle className="w-3 h-3 text-sky-400" /> Flagged</p><p className="text-xl font-bold text-sky-400 mt-1">{dash.flagged_30d}</p></div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Active Controls</h3>
                  {Object.entries(dash.controls).map(([k, v]) => (
                    <div key={k} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300">{k.replace(/_/g, ' ')}</span>
                      <span className={v ? 'text-emerald-400' : 'text-slate-600'}>{v ? 'on' : 'off'}</span>
                    </div>
                  ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Recent Decisions</h3>
                  {dash.recent.length === 0 ? <p className="text-xs text-slate-500">No governance events yet.</p> :
                    dash.recent.map(e => (
                      <div key={e.id} className="flex justify-between items-center text-xs py-1 border-b border-slate-800/60 last:border-0">
                        <span className="text-slate-300 truncate pr-2">{e.event_type}{e.rule ? ` · ${e.rule}` : ''}</span>
                        <span className={`px-1.5 py-0.5 rounded shrink-0 ${GOV_ACTION_TONE[e.action_taken] || ''}`}>{e.action_taken}</span>
                      </div>
                    ))}
                </div>
              </div>
            </div>
          )}

          {tab === 'policy' && policy && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-1">Data Protection</h3>
                <Toggle label="Master switch" hint="Turn all AI governance controls on or off." value={policy.is_enabled} disabled={!isManager} onChange={v => savePolicy({ is_enabled: v })} />
                <Toggle label="PII detection" hint="Scan every prompt for emails, phones, PAN, Aadhaar, cards and more." value={policy.pii_detection} disabled={!isManager} onChange={v => savePolicy({ pii_detection: v })} />
                <div className="py-2">
                  <p className="text-xs font-semibold text-slate-200 mb-1">When PII is found</p>
                  <select disabled={!isManager} value={policy.pii_action} onChange={e => savePolicy({ pii_action: e.target.value })} className={F}>
                    <option value="mask">Mask it before sending (recommended)</option>
                    <option value="block">Block the request</option>
                    <option value="flag">Allow but log</option>
                  </select>
                </div>
                <Toggle label="Log prompt snippets" hint="Store a redacted excerpt with each event for audits." value={policy.log_prompt_snippets} disabled={!isManager} onChange={v => savePolicy({ log_prompt_snippets: v })} />
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-1">Threat & Content</h3>
                <Toggle label="Prompt-injection protection" hint="Detect attempts to override instructions or extract the system prompt." value={policy.injection_protection} disabled={!isManager} onChange={v => savePolicy({ injection_protection: v })} />
                <div className="py-2">
                  <p className="text-xs font-semibold text-slate-200 mb-1">On injection</p>
                  <select disabled={!isManager} value={policy.injection_action} onChange={e => savePolicy({ injection_action: e.target.value })} className={F}>
                    <option value="block">Block the request</option>
                    <option value="flag">Allow but log</option>
                  </select>
                </div>
                <Toggle label="Content filtering" hint="Block prompts containing your banned terms." value={policy.content_filter} disabled={!isManager} onChange={v => savePolicy({ content_filter: v })} />
                <div className="py-2">
                  <p className="text-xs font-semibold text-slate-200 mb-1">Blocked terms (comma separated)</p>
                  <input disabled={!isManager} defaultValue={(policy.blocked_terms || []).join(', ')}
                    onBlur={e => savePolicy({ blocked_terms: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })} className={F} />
                </div>
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-1">Model Restrictions</h3>
                <p className="text-[11px] text-slate-500 mb-2">Leave empty for no restriction.</p>
                <div className="py-1">
                  <p className="text-xs font-semibold text-slate-200 mb-1">Allowed providers</p>
                  <input disabled={!isManager} defaultValue={(policy.allowed_providers || []).join(', ')}
                    onBlur={e => savePolicy({ allowed_providers: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })} placeholder="openai, anthropic…" className={F} />
                </div>
                <div className="py-1">
                  <p className="text-xs font-semibold text-slate-200 mb-1">Allowed models</p>
                  <input disabled={!isManager} defaultValue={(policy.allowed_models || []).join(', ')}
                    onBlur={e => savePolicy({ allowed_models: e.target.value.split(',').map(t => t.trim()).filter(Boolean) })} placeholder="gpt-4o, claude-3…" className={F} />
                </div>
              </div>

              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-1">Usage Policy</h3>
                <div className="py-1">
                  <p className="text-xs font-semibold text-slate-200 mb-1">Max prompt characters</p>
                  <input disabled={!isManager} type="number" defaultValue={policy.max_prompt_chars}
                    onBlur={e => savePolicy({ max_prompt_chars: parseInt(e.target.value) || 100000 })} className={F} />
                </div>
                <Toggle label="Require grounding" hint="Prefer retrieval-grounded answers to reduce hallucination." value={policy.require_grounding} disabled={!isManager} onChange={v => savePolicy({ require_grounding: v })} />
              </div>
            </div>
          )}

          {tab === 'events' && (
            <div className={card}>
              {events.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No governance events recorded yet.</p> : (
                <table className="w-full text-xs">
                  <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                    <th className="py-2 pr-2">When</th><th className="pr-2">Type</th><th className="pr-2">Action</th><th className="pr-2">Rule</th><th className="pr-2">Task</th><th className="pr-2">Findings</th>
                  </tr></thead>
                  <tbody>
                    {events.map(e => (
                      <tr key={e.id} className="border-b border-slate-800/50 last:border-0">
                        <td className="py-2 pr-2 text-slate-400">{e.created_at ? new Date(e.created_at).toLocaleString() : '—'}</td>
                        <td className="pr-2 text-slate-300">{e.event_type}</td>
                        <td className="pr-2"><span className={`px-1.5 py-0.5 rounded ${GOV_ACTION_TONE[e.action_taken] || ''}`}>{e.action_taken}</span></td>
                        <td className="pr-2 text-slate-500 truncate max-w-[180px]">{e.rule || '—'}</td>
                        <td className="pr-2 text-slate-400">{e.task_type || '—'}</td>
                        <td className="pr-2 text-slate-500">{Object.entries(e.findings || {}).map(([k, v]) => `${k}:${v}`).join(', ') || '—'}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
            </div>
          )}

          {tab === 'test' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><FlaskConical className="w-3.5 h-3.5 text-brand-400" /> Test your controls</h3>
                <p className="text-[11px] text-slate-500 mb-2">Paste any text to see exactly what the guard rails would do — no AI call is made.</p>
                <textarea value={testText} onChange={e => setTestText(e.target.value)} rows={7} className={F} />
                <button onClick={async () => { try { setPreview(await api.preview(testText)); } catch (e) { setErr(extractErrorMessage(e, 'Preview failed')); } }} className={`${BTN} mt-2`}>Run check</button>
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Result</h3>
                {!preview ? <p className="text-xs text-slate-500 py-8 text-center">Run a check to see detections and the redacted output.</p> : (
                  <div className="space-y-2">
                    <p className="text-[11px] text-slate-400">PII found: {Object.keys(preview.pii).length === 0 ? <span className="text-emerald-400">none</span> : Object.entries(preview.pii).map(([k, v]) => `${k} ×${v}`).join(', ')}</p>
                    <p className="text-[11px] text-slate-400">Injection: {preview.injection.length === 0 ? <span className="text-emerald-400">none</span> : <span className="text-red-400">{preview.injection.join(', ')}</span>}</p>
                    <p className="text-[11px] text-slate-400">Blocked terms: {preview.blocked_terms.length === 0 ? <span className="text-emerald-400">none</span> : <span className="text-red-400">{preview.blocked_terms.join(', ')}</span>}</p>
                    <p className="text-[11px] text-slate-500">Length {preview.length} / {preview.max_prompt_chars}</p>
                    <div>
                      <p className="text-[10px] text-slate-500 uppercase mb-1">What the provider would receive</p>
                      <pre className="text-[11px] text-slate-200 whitespace-pre-wrap bg-slate-950/40 rounded-lg p-2">{preview.masked_preview}</pre>
                    </div>
                  </div>
                )}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
};
