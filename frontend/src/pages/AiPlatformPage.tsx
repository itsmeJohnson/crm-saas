import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Bot, Loader2, Plus, X, Check, Trash2, Send, MessagesSquare, Server, LayoutTemplate,
  Activity as ActivityIcon, Settings as SettingsIcon, Zap, Pencil,
} from 'lucide-react';
import {
  aiApi as api, AiSettings, AiProvider, AiTemplate, AiConversation, AiMessage, AiUsageDashboard,
} from '../services/aiApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const PROVIDERS = ['mock', 'openai', 'azure_openai', 'anthropic', 'gemini', 'ollama', 'custom'];

export const AiPlatformPage: React.FC = () => {
  const [tab, setTab] = useState<'chat' | 'providers' | 'templates' | 'usage' | 'settings'>('chat');
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 2500); };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Bot className="w-6 h-6 text-brand-400" /> AI Platform</h1>
        <p className="text-sm text-slate-500 mt-1">One LLM gateway for the whole CRM — multi-provider (OpenAI · Azure · Anthropic · Gemini · Ollama · custom), prompt templates, memory, caching, budgets and full usage telemetry.</p>
      </div>

      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['chat', 'Assistant', MessagesSquare], ['providers', 'Providers', Server], ['templates', 'Prompt Templates', LayoutTemplate], ['usage', 'Usage & Costs', ActivityIcon], ['settings', 'Settings', SettingsIcon]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {tab === 'chat' && <ChatTab setErr={setErr} />}
      {tab === 'providers' && <ProvidersTab setErr={setErr} flash={flash} />}
      {tab === 'templates' && <TemplatesTab setErr={setErr} flash={flash} />}
      {tab === 'usage' && <UsageTab setErr={setErr} />}
      {tab === 'settings' && <SettingsTab setErr={setErr} flash={flash} />}
    </div>
  );
};

const ChatTab: React.FC<{ setErr: (s: string) => void }> = ({ setErr }) => {
  const [conversations, setConversations] = useState<AiConversation[]>([]);
  const [active, setActive] = useState<string | null>(null);
  const [messages, setMessages] = useState<AiMessage[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const endRef = useRef<HTMLDivElement>(null);

  const loadConvos = useCallback(async () => {
    try { setConversations(await api.conversations()); } catch { /* non-admin ok */ }
  }, []);
  useEffect(() => { loadConvos(); }, [loadConvos]);
  useEffect(() => {
    if (active) api.messages(active).then(setMessages).catch(() => setMessages([]));
    else setMessages([]);
  }, [active]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [messages]);

  const send = async () => {
    const text = input.trim();
    if (!text || busy) return;
    setBusy(true); setErr(''); setInput('');
    setMessages((m) => [...m, { id: 'tmp', role: 'user', content: text, model: null, provider: null, tokens: 0, cost_usd: 0, created_at: null }]);
    try {
      const r = await api.chat({ message: text, conversation_id: active || undefined });
      if (!active && r.conversation_id) setActive(r.conversation_id);
      setMessages(await api.messages(r.conversation_id || active!));
      await loadConvos();
    } catch (e) { setErr(extractErrorMessage(e, 'AI request failed')); } finally { setBusy(false); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
      <div className={`${card} h-fit`}>
        <button onClick={() => { setActive(null); setMessages([]); }} className={`${BTN} w-full justify-center mb-2`}><Plus className="w-3.5 h-3.5" /> New conversation</button>
        {conversations.map((c) => (
          <button key={c.id} onClick={() => setActive(c.id)} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs truncate cursor-pointer ${active === c.id ? 'bg-brand-500/15 text-brand-300' : 'text-slate-400 hover:bg-slate-800/60'}`}>
            {c.title} <span className="text-[9px] text-slate-600">({c.message_count})</span>
          </button>
        ))}
        {conversations.length === 0 && <p className="text-[11px] text-slate-600 px-1">No conversations yet.</p>}
      </div>
      <div className={`${card} lg:col-span-3 flex flex-col`} style={{ minHeight: 480 }}>
        <div className="flex-1 overflow-y-auto space-y-3 pr-1" style={{ maxHeight: 460 }}>
          {messages.length === 0 && <p className="text-sm text-slate-500 py-16 text-center">Ask anything — the assistant remembers this conversation and runs through the org's provider chain.</p>}
          {messages.map((m, i) => (
            <div key={m.id + i} className={`flex ${m.role === 'user' ? 'justify-end' : 'justify-start'}`}>
              <div className={`max-w-[80%] rounded-2xl px-3 py-2 text-sm whitespace-pre-wrap ${m.role === 'user' ? 'bg-brand-500/20 text-brand-100' : 'bg-slate-800/70 text-slate-200'}`}>
                {m.content}
                {m.role === 'assistant' && m.model && <p className="text-[9px] text-slate-500 mt-1">{m.provider} · {m.model} · {m.tokens} tok</p>}
              </div>
            </div>
          ))}
          {busy && <div className="flex justify-start"><div className="bg-slate-800/70 rounded-2xl px-3 py-2"><Loader2 className="w-4 h-4 animate-spin text-slate-400" /></div></div>}
          <div ref={endRef} />
        </div>
        <div className="flex items-center gap-2 pt-3 border-t border-slate-800/60 mt-3">
          <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && send()}
                 placeholder="Message the assistant…" className={F} />
          <button onClick={send} disabled={busy} className={`${BTN} shrink-0`}><Send className="w-3.5 h-3.5" /> Send</button>
        </div>
      </div>
    </div>
  );
};

const ProvidersTab: React.FC<{ setErr: (s: string) => void; flash: (s: string) => void }> = ({ setErr, flash }) => {
  const [providers, setProviders] = useState<AiProvider[]>([]);
  const [f, setF] = useState<any>({ provider: 'openai', name: '', default_model: 'gpt-4o-mini', priority: 1 });
  const [testing, setTesting] = useState('');
  const load = useCallback(async () => {
    try { setProviders(await api.providers()); } catch (e) { setErr(extractErrorMessage(e, 'Failed to load providers')); }
  }, [setErr]);
  useEffect(() => { load(); }, [load]);
  const set = (patch: any) => setF({ ...f, ...patch });

  const create = async () => {
    try {
      await api.createProvider({ ...f, name: f.name || f.provider });
      flash('Provider added to the fallback chain.');
      await load();
    } catch (e) { setErr(extractErrorMessage(e, 'Failed')); }
  };
  const test = async (id: string) => {
    setTesting(id);
    try {
      const r = await api.testProvider(id);
      r.status === 'success' ? flash(`Connection OK (${r.latency_ms}ms)`) : setErr(r.error || 'Connection failed');
    } catch (e) { setErr(extractErrorMessage(e, 'Test failed')); } finally { setTesting(''); }
  };
  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await load(); } catch (e) { setErr(extractErrorMessage(e, 'Failed')); } };

  return (
    <div className="space-y-4">
      <div className={`${card} space-y-2`}>
        <p className="text-xs font-semibold text-slate-400 uppercase">Add provider (fallback chain runs in priority order)</p>
        <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
          <select value={f.provider} onChange={(e) => set({ provider: e.target.value })} className={F}>
            {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
          <input value={f.name} onChange={(e) => set({ name: e.target.value })} placeholder="Display name" className={F} />
          <input value={f.default_model} onChange={(e) => set({ default_model: e.target.value })} placeholder="Default model" className={F} />
          <input type="number" min={1} max={20} value={f.priority} onChange={(e) => set({ priority: Number(e.target.value) || 1 })} placeholder="Priority" className={F} />
          {f.provider !== 'mock' && f.provider !== 'ollama' && (
            <input value={f.api_key || ''} onChange={(e) => set({ api_key: e.target.value })} placeholder="API key" type="password" className={`${F} col-span-2`} />
          )}
          {(f.provider === 'azure_openai' || f.provider === 'ollama' || f.provider === 'custom') && (
            <input value={f.base_url || ''} onChange={(e) => set({ base_url: e.target.value })} placeholder={f.provider === 'azure_openai' ? 'https://<resource>.openai.azure.com' : 'Base URL'} className={`${F} col-span-2`} />
          )}
          {f.provider === 'azure_openai' && (
            <>
              <input value={f.deployment || ''} onChange={(e) => set({ deployment: e.target.value })} placeholder="Deployment name" className={F} />
              <input value={f.api_version || ''} onChange={(e) => set({ api_version: e.target.value })} placeholder="API version (2024-06-01)" className={F} />
            </>
          )}
        </div>
        <button onClick={create} className={BTN}><Plus className="w-3.5 h-3.5" /> Add provider</button>
      </div>
      {providers.map((p) => (
        <div key={p.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-3">
          <span className="text-lg font-bold text-brand-400 w-6 text-center shrink-0">{p.priority}</span>
          <div className="flex-1 min-w-0">
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-sm font-semibold text-slate-100">{p.name}</span>
              <span className="px-1.5 py-0.5 text-[10px] rounded bg-brand-500/10 text-brand-300">{p.provider}</span>
              <span className="text-[10px] text-slate-400">{p.default_model}</span>
              {p.api_key && <code className="text-[10px] text-slate-500">{p.api_key}</code>}
              {!p.is_active && <span className="text-[10px] text-slate-500">disabled</span>}
            </div>
            <p className="text-[11px] text-slate-500 truncate">{p.base_url || 'default endpoint'}{p.deployment ? ` · ${p.deployment}` : ''}</p>
          </div>
          <div className="flex items-center gap-1.5 shrink-0">
            <button title="Test connection" onClick={() => test(p.id)} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-emerald-400 cursor-pointer">{testing === p.id ? <Loader2 className="w-4 h-4 animate-spin" /> : <Zap className="w-4 h-4" />}</button>
            <button title={p.is_active ? 'Disable' : 'Enable'} onClick={() => act(() => api.updateProvider(p.id, { is_active: !p.is_active }), p.is_active ? 'Disabled.' : 'Enabled.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-300 cursor-pointer">{p.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}</button>
            <button title="Delete" onClick={() => window.confirm(`Remove "${p.name}"?`) && act(() => api.removeProvider(p.id), 'Removed.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
          </div>
        </div>
      ))}
      {providers.length === 0 && <p className="text-sm text-slate-500">No providers configured — the platform answers with the built-in Mock provider until you add one.</p>}
    </div>
  );
};

const TemplatesTab: React.FC<{ setErr: (s: string) => void; flash: (s: string) => void }> = ({ setErr, flash }) => {
  const [templates, setTemplates] = useState<AiTemplate[]>([]);
  const [edit, setEdit] = useState<any | null>(null);
  const load = useCallback(async () => {
    try { setTemplates(await api.templates()); } catch (e) { setErr(extractErrorMessage(e, 'Failed to load templates')); }
  }, [setErr]);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      if (edit.id) await api.updateTemplate(edit.id, edit);
      else await api.createTemplate(edit);
      setEdit(null); flash('Template saved.'); await load();
    } catch (e) { setErr(extractErrorMessage(e, 'Save failed')); }
  };

  return (
    <div className="space-y-3">
      <button onClick={() => setEdit({ key: '', name: '', task_type: 'general', template: '' })} className={BTN}><Plus className="w-3.5 h-3.5" /> New template</button>
      {templates.map((t) => (
        <div key={t.id} className="glass-panel border border-slate-800/85 rounded-xl p-4">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-sm font-semibold text-slate-100">{t.name}</span>
            <code className="text-[10px] bg-slate-950/50 text-brand-300 px-1.5 py-0.5 rounded">{t.key}</code>
            <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-700/40 text-slate-400 capitalize">{t.task_type}</span>
            {t.is_builtin && <span className="text-[10px] text-slate-500">built-in</span>}
            <span className="text-[10px] text-slate-500">used {t.usage_count}×</span>
            <span className="flex-1" />
            <button onClick={() => setEdit({ ...t })} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
          </div>
          <p className="text-[11px] text-slate-500 mt-1 line-clamp-2">{t.template}</p>
        </div>
      ))}
      {edit && (
        <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={() => setEdit(null)}>
          <div className="glass-panel border border-slate-800 rounded-2xl w-full max-w-xl p-5 bg-slate-900 space-y-2" onClick={(e) => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-slate-100">{edit.id ? 'Edit' : 'New'} prompt template</h3>
            <div className="grid grid-cols-2 gap-2">
              <input value={edit.key} disabled={!!edit.id} onChange={(e) => setEdit({ ...edit, key: e.target.value })} placeholder="key (snake_case)" className={F} />
              <input value={edit.name} onChange={(e) => setEdit({ ...edit, name: e.target.value })} placeholder="Name" className={F} />
            </div>
            <input value={edit.system_prompt || ''} onChange={(e) => setEdit({ ...edit, system_prompt: e.target.value })} placeholder="System prompt (optional)" className={F} />
            <textarea value={edit.template} onChange={(e) => setEdit({ ...edit, template: e.target.value })} placeholder={'Prompt body with {{variables}}'} rows={6} className={F} />
            <button onClick={save} className={`${BTN} w-full justify-center`}><Check className="w-3.5 h-3.5" /> Save</button>
          </div>
        </div>
      )}
    </div>
  );
};

const UsageTab: React.FC<{ setErr: (s: string) => void }> = ({ setErr }) => {
  const [data, setData] = useState<AiUsageDashboard | null>(null);
  useEffect(() => {
    api.usage().then(setData).catch((e) => setErr(extractErrorMessage(e, 'Failed to load usage')));
  }, [setErr]);
  if (!data) return <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>;
  const budgetPct = data.budget.monthly_budget_usd ? Math.min(100, (data.budget.spent_this_month_usd * 100) / data.budget.monthly_budget_usd) : 0;
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 md:grid-cols-6 gap-3">
        <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Requests (30d)</p><p className="text-xl font-bold text-slate-100 mt-1">{data.requests}</p></div>
        <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Tokens</p><p className="text-xl font-bold text-slate-100 mt-1">{data.tokens.toLocaleString()}</p></div>
        <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Cost</p><p className="text-xl font-bold text-emerald-400 mt-1">${data.cost_usd}</p></div>
        <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Error rate</p><p className="text-xl font-bold text-red-400 mt-1">{data.error_rate}%</p></div>
        <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Cache hits</p><p className="text-xl font-bold text-sky-400 mt-1">{data.cache_hit_rate}%</p></div>
        <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Avg latency</p><p className="text-xl font-bold text-slate-100 mt-1">{data.avg_latency_ms}ms</p></div>
      </div>
      <div className={card}>
        <div className="flex items-center justify-between mb-1">
          <p className="text-xs font-semibold text-slate-400 uppercase">Monthly budget</p>
          <p className="text-[11px] text-slate-500">${data.budget.spent_this_month_usd} / ${data.budget.monthly_budget_usd}</p>
        </div>
        <div className="h-2 bg-slate-800/60 rounded"><div className={`h-2 rounded ${budgetPct >= 90 ? 'bg-red-500/70' : 'bg-brand-500/70'}`} style={{ width: `${budgetPct}%` }} /></div>
      </div>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <div className={card}>
          <p className="text-xs font-semibold text-slate-400 uppercase mb-2">By provider</p>
          {Object.entries(data.by_provider).map(([p, v]) => (
            <div key={p} className="flex items-center justify-between py-1 text-sm">
              <span className="text-slate-300">{p}</span>
              <span className="text-[11px] text-slate-500">{v.requests} req · {v.tokens.toLocaleString()} tok · ${v.cost}{v.failed ? ` · ${v.failed} failed` : ''}</span>
            </div>
          ))}
          {Object.keys(data.by_provider).length === 0 && <p className="text-xs text-slate-500">No usage yet.</p>}
        </div>
        <div className={card}>
          <p className="text-xs font-semibold text-slate-400 uppercase mb-2">By task</p>
          {Object.entries(data.by_task).map(([t, n]) => (
            <div key={t} className="flex items-center justify-between py-1 text-sm">
              <span className="text-slate-300 capitalize">{t}</span><span className="text-slate-100 font-semibold">{n}</span>
            </div>
          ))}
          {Object.keys(data.by_task).length === 0 && <p className="text-xs text-slate-500">No usage yet.</p>}
        </div>
      </div>
    </div>
  );
};

const SettingsTab: React.FC<{ setErr: (s: string) => void; flash: (s: string) => void }> = ({ setErr, flash }) => {
  const [s, setS] = useState<AiSettings | null>(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    api.settings().then(setS).catch((e) => setErr(extractErrorMessage(e, 'Failed to load settings')));
  }, [setErr]);
  if (!s) return <div className="py-16 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>;
  const set = (patch: any) => setS({ ...s, ...patch });
  const save = async () => {
    setBusy(true);
    try { setS(await api.updateSettings(s)); flash('AI settings saved.'); }
    catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
  };
  return (
    <div className={`${card} max-w-2xl space-y-3`}>
      <label className="flex items-center gap-2 text-sm text-slate-200"><input type="checkbox" checked={s.is_enabled} onChange={(e) => set({ is_enabled: e.target.checked })} /> AI Platform enabled</label>
      <div className="grid grid-cols-2 gap-2">
        <label className="text-[11px] text-slate-400">Default provider
          <select value={s.default_provider} onChange={(e) => set({ default_provider: e.target.value })} className={F}>
            {PROVIDERS.map((p) => <option key={p} value={p}>{p}</option>)}
          </select>
        </label>
        <label className="text-[11px] text-slate-400">Default model<input value={s.default_model} onChange={(e) => set({ default_model: e.target.value })} className={F} /></label>
        <label className="text-[11px] text-slate-400">Daily request limit<input type="number" value={s.daily_request_limit} onChange={(e) => set({ daily_request_limit: Number(e.target.value) })} className={F} /></label>
        <label className="text-[11px] text-slate-400">Monthly budget (USD)<input type="number" value={s.monthly_budget_usd} onChange={(e) => set({ monthly_budget_usd: Number(e.target.value) })} className={F} /></label>
        <label className="text-[11px] text-slate-400">Temperature<input type="number" step={0.1} min={0} max={2} value={s.temperature} onChange={(e) => set({ temperature: Number(e.target.value) })} className={F} /></label>
        <label className="text-[11px] text-slate-400">Max tokens<input type="number" value={s.max_tokens} onChange={(e) => set({ max_tokens: Number(e.target.value) })} className={F} /></label>
        <label className="text-[11px] text-slate-400">Memory window (messages)<input type="number" value={s.memory_messages} onChange={(e) => set({ memory_messages: Number(e.target.value) })} className={F} /></label>
        <label className="text-[11px] text-slate-400">Cache TTL (minutes)<input type="number" value={s.cache_ttl_minutes} onChange={(e) => set({ cache_ttl_minutes: Number(e.target.value) })} className={F} /></label>
      </div>
      <div className="flex items-center gap-4">
        <label className="flex items-center gap-1.5 text-xs text-slate-300"><input type="checkbox" checked={s.cache_enabled} onChange={(e) => set({ cache_enabled: e.target.checked })} /> Response caching</label>
        <label className="flex items-center gap-1.5 text-xs text-slate-300"><input type="checkbox" checked={s.streaming_enabled} onChange={(e) => set({ streaming_enabled: e.target.checked })} /> Streaming</label>
      </div>
      <button onClick={save} disabled={busy} className={`${BTN} w-full justify-center`}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} Save settings</button>
    </div>
  );
};
