import React, { useCallback, useEffect, useState } from 'react';
import {
  Wand2, Loader2, Download, LayoutDashboard, BookMarked, Plus, FlaskConical, BarChart3,
  CheckCircle2, XCircle, Send, Archive, History, Copy, Trash2, Play, Sparkles,
} from 'lucide-react';
import {
  promptStudioApi as api, Prompt, PromptAnalytics, TestResult, PROMPT_STATUS_TONE,
} from '../services/promptStudioApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const BTN2 = 'px-2 py-1 rounded-lg text-[11px] font-semibold cursor-pointer flex items-center gap-1';
const CATS = ['general', 'chat', 'crm', 'report', 'communication', 'knowledge', 'document', 'automation', 'workflow'];

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
};

const emptyForm = { key: '', name: '', task_type: 'general', system_prompt: '', template: '', description: '', tags: '' };

export const PromptStudioPage: React.FC = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'OrgAdmin' || user?.role === 'Manager' || user?.role === 'SuperAdmin';
  const [tab, setTab] = useState<'library' | 'prompts' | 'test' | 'analytics'>('prompts');
  const [prompts, setPrompts] = useState<Prompt[]>([]);
  const [analytics, setAnalytics] = useState<PromptAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [catFilter, setCatFilter] = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [q, setQ] = useState('');

  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState<any>(emptyForm);
  const [editId, setEditId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Prompt | null>(null);
  const [versions, setVersions] = useState<any[] | null>(null);

  // test harness
  const [testTemplate, setTestTemplate] = useState('Write a warm intro for {{lead_name}} about {{product}}.');
  const [testSystem, setTestSystem] = useState('');
  const [testVars, setTestVars] = useState('{\n  "lead_name": "Rahul",\n  "product": "3BHK apartment"\n}');
  const [testResult, setTestResult] = useState<TestResult | null>(null);
  const [testing, setTesting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (tab === 'prompts' || tab === 'library') {
        const params: any = {};
        if (tab === 'library') params.builtin = true;
        if (catFilter) params.task_type = catFilter;
        if (statusFilter) params.status = statusFilter;
        if (q) params.q = q;
        setPrompts((await api.list(params)).items);
      }
      if (tab === 'analytics') setAnalytics(await api.analytics());
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load Prompt Studio.')); } finally { setLoading(false); }
  }, [tab, catFilter, statusFilter, q]);
  useEffect(() => { load(); }, [load]);

  const save = async () => {
    try {
      const payload: any = { ...form, tags: form.tags ? form.tags.split(',').map((t: string) => t.trim()).filter(Boolean) : [] };
      if (editId) await api.update(editId, payload); else await api.create(payload);
      setShowForm(false); setForm(emptyForm); setEditId(null); load();
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to save prompt.')); }
  };

  const act = async (fn: () => Promise<any>) => {
    try { await fn(); setDetail(null); setVersions(null); load(); }
    catch (e) { setErr(extractErrorMessage(e, 'Action failed.')); }
  };

  const runTest = async (run: boolean) => {
    setTesting(true); setErr('');
    try {
      let variables = {};
      try { variables = JSON.parse(testVars || '{}'); } catch { setErr('Variables must be valid JSON'); setTesting(false); return; }
      setTestResult(await api.test({ template: testTemplate, system_prompt: testSystem || null, variables, run }));
    } catch (e) { setErr(extractErrorMessage(e, 'Test failed.')); } finally { setTesting(false); }
  };

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Wand2 className="w-6 h-6 text-brand-400" /> Prompt Studio</h1>
          <p className="text-sm text-slate-500 mt-1">Author, version, test and approve the AI prompts that power your CRM — system & user prompts, variables, and a reusable library.</p>
        </div>
        {isManager && (tab === 'analytics' || tab === 'prompts') && (
          <div className="flex gap-2">
            {tab === 'prompts' && <button onClick={() => { setForm(emptyForm); setEditId(null); setShowForm(true); }} className={BTN}><Plus className="w-3.5 h-3.5" /> New Prompt</button>}
            <button onClick={async () => { try { downloadText('prompts.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>
          </div>
        )}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['prompts', 'Prompts', LayoutDashboard], ['library', 'Library', BookMarked], ['test', 'Test / Preview', FlaskConical], ['analytics', 'Analytics', BarChart3]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading && tab !== 'test' ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> : (
        <>
          {(tab === 'prompts' || tab === 'library') && (
            <div className="space-y-3">
              {tab === 'prompts' && (
                <div className="flex items-center gap-2 flex-wrap">
                  <input value={q} onChange={e => setQ(e.target.value)} placeholder="Search…" className={`${F} max-w-52`} />
                  <select value={catFilter} onChange={e => setCatFilter(e.target.value)} className={`${F} max-w-40`}>
                    <option value="">All categories</option>{CATS.map(c => <option key={c} value={c}>{c}</option>)}
                  </select>
                  <select value={statusFilter} onChange={e => setStatusFilter(e.target.value)} className={`${F} max-w-40`}>
                    <option value="">All statuses</option>{['draft', 'pending_review', 'approved', 'rejected', 'archived'].map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
              )}
              <div className={card}>
                {prompts.length === 0 ? <p className="text-xs text-slate-500 py-6 text-center">No prompts.</p> : (
                  <table className="w-full text-xs">
                    <thead><tr className="text-left text-[10px] uppercase text-slate-500 border-b border-slate-800/70">
                      <th className="py-2 pr-2">Name</th><th className="pr-2">Key</th><th className="pr-2">Category</th><th className="pr-2">Status</th><th className="pr-2">v</th><th className="pr-2">Vars</th><th className="pr-2">Used</th>
                    </tr></thead>
                    <tbody>
                      {prompts.map(p => (
                        <tr key={p.id} onClick={async () => { setDetail(await api.get(p.id)); setVersions(null); }} className="border-b border-slate-800/50 last:border-0 hover:bg-slate-800/30 cursor-pointer">
                          <td className="py-2 pr-2 text-slate-200 font-medium">{p.name}{p.is_builtin && <span className="ml-1.5 text-[9px] px-1 py-0.5 rounded bg-brand-500/15 text-brand-300">builtin</span>}</td>
                          <td className="pr-2 text-slate-500 font-mono">{p.key}</td>
                          <td className="pr-2 text-slate-400">{p.task_type}</td>
                          <td className="pr-2"><span className={`px-1.5 py-0.5 rounded ${PROMPT_STATUS_TONE[p.status] || ''}`}>{p.status}</span></td>
                          <td className="pr-2 text-slate-400">{p.version}</td>
                          <td className="pr-2 text-slate-400">{p.variables.length}</td>
                          <td className="pr-2 text-slate-400">{p.usage_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          )}

          {tab === 'test' && (
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2 flex items-center gap-1.5"><FlaskConical className="w-3.5 h-3.5 text-brand-400" /> Prompt</h3>
                <label className="text-[10px] text-slate-500 uppercase">System prompt (optional)</label>
                <textarea value={testSystem} onChange={e => setTestSystem(e.target.value)} rows={2} placeholder="You are a helpful CRM assistant." className={`${F} mb-2`} />
                <label className="text-[10px] text-slate-500 uppercase">User prompt (use {`{{variables}}`})</label>
                <textarea value={testTemplate} onChange={e => setTestTemplate(e.target.value)} rows={5} className={`${F} mb-2`} />
                <label className="text-[10px] text-slate-500 uppercase">Variables (JSON)</label>
                <textarea value={testVars} onChange={e => setTestVars(e.target.value)} rows={4} className={`${F} font-mono`} />
                <div className="flex gap-2 mt-2">
                  <button disabled={testing} onClick={() => runTest(false)} className={BTN}><Play className="w-3.5 h-3.5" /> Render</button>
                  <button disabled={testing} onClick={() => runTest(true)} className={`${BTN} bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30`}>{testing ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Sparkles className="w-3.5 h-3.5" />} Run through AI</button>
                </div>
              </div>
              <div className={card}>
                <h3 className="text-xs font-bold text-slate-300 mb-2">Result</h3>
                {!testResult ? <p className="text-xs text-slate-500 py-8 text-center">Render substitutes variables; "Run through AI" sends it to your configured provider.</p> : (
                  <div className="space-y-2">
                    {testResult.missing_variables.length > 0 && <p className="text-[11px] text-amber-300">Missing variables: {testResult.missing_variables.join(', ')}</p>}
                    <div>
                      <p className="text-[10px] text-slate-500 uppercase mb-1">Rendered prompt</p>
                      <pre className="text-[11px] text-slate-200 whitespace-pre-wrap bg-slate-950/40 rounded-lg p-2">{testResult.rendered_prompt}</pre>
                    </div>
                    {testResult.ran && (
                      <div>
                        <p className="text-[10px] text-slate-500 uppercase mb-1">AI output <span className="text-slate-600">({testResult.provider}/{testResult.model})</span></p>
                        <pre className="text-[11px] text-emerald-200 whitespace-pre-wrap bg-emerald-500/5 border border-emerald-500/15 rounded-lg p-2">{testResult.output}</pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {tab === 'analytics' && analytics && (
            <div className="space-y-4">
              <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Prompts</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.totals.prompts}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Active</p><p className="text-xl font-bold text-emerald-400 mt-1">{analytics.totals.active}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Pending</p><p className="text-xl font-bold text-amber-400 mt-1">{analytics.totals.pending_review}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Custom</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.totals.custom}</p></div>
                <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Total Usage</p><p className="text-xl font-bold text-slate-100 mt-1">{analytics.totals.total_usage}</p></div>
              </div>
              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Most Used Prompts</h3>
                  {analytics.top_used.map(t => (
                    <div key={t.id} className="flex justify-between text-xs py-1 border-b border-slate-800/60 last:border-0">
                      <span className="text-slate-300 truncate pr-2">{t.name} <span className="text-slate-600">({t.task_type})</span></span>
                      <span className="text-slate-400">{t.usage_count}</span>
                    </div>
                  ))}
                </div>
                <div className={card}>
                  <h3 className="text-xs font-bold text-slate-300 mb-2">Pending Approval</h3>
                  {analytics.pending_queue.length === 0 ? <p className="text-xs text-slate-500">Nothing awaiting review.</p> :
                    analytics.pending_queue.map(p => <div key={p.id} className="text-xs text-amber-300 py-1 border-b border-slate-800/60 last:border-0">{p.name}</div>)}
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {showForm && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => setShowForm(false)}>
          <div className="glass-panel border border-slate-700/70 rounded-2xl p-5 w-full max-w-2xl space-y-3 max-h-[85vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <h3 className="text-sm font-bold text-slate-100">{editId ? 'Edit Prompt' : 'New Prompt'}</h3>
            <div className="grid grid-cols-2 gap-2">
              <input value={form.key} disabled={!!editId} onChange={e => setForm({ ...form, key: e.target.value })} placeholder="unique_key (lowercase)" className={F} />
              <input value={form.name} onChange={e => setForm({ ...form, name: e.target.value })} placeholder="Display name" className={F} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select value={form.task_type} onChange={e => setForm({ ...form, task_type: e.target.value })} className={F}>{CATS.map(c => <option key={c} value={c}>{c}</option>)}</select>
              <input value={form.tags} onChange={e => setForm({ ...form, tags: e.target.value })} placeholder="tags, comma, separated" className={F} />
            </div>
            <textarea value={form.system_prompt} onChange={e => setForm({ ...form, system_prompt: e.target.value })} placeholder="System prompt (optional)" rows={2} className={F} />
            <textarea value={form.template} onChange={e => setForm({ ...form, template: e.target.value })} placeholder="User prompt with {{variables}}" rows={6} className={F} />
            <input value={form.description} onChange={e => setForm({ ...form, description: e.target.value })} placeholder="Description (optional)" className={F} />
            <div className="flex justify-end gap-2">
              <button onClick={() => setShowForm(false)} className="px-3 py-1.5 rounded-lg text-xs text-slate-400 hover:text-slate-200 cursor-pointer">Cancel</button>
              <button onClick={save} className={BTN}>{editId ? 'Save (new version)' : 'Create Draft'}</button>
            </div>
          </div>
        </div>
      )}

      {detail && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4" onClick={() => { setDetail(null); setVersions(null); }}>
          <div className="glass-panel border border-slate-700/70 rounded-2xl p-5 w-full max-w-3xl max-h-[85vh] overflow-y-auto space-y-3" onClick={e => e.stopPropagation()}>
            <div className="flex items-start justify-between gap-3">
              <div>
                <h3 className="text-base font-bold text-slate-100">{detail.name}</h3>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  <span className={`px-1.5 py-0.5 rounded mr-2 ${PROMPT_STATUS_TONE[detail.status] || ''}`}>{detail.status}</span>
                  <span className="font-mono">{detail.key}</span> · {detail.task_type} · v{detail.version} · {detail.usage_count} uses{detail.is_active ? ' · active' : ''}
                </p>
              </div>
              <div className="flex items-center gap-1.5 flex-wrap justify-end">
                {!detail.is_builtin && <button onClick={() => { setForm({ key: detail.key, name: detail.name, task_type: detail.task_type, system_prompt: detail.system_prompt || '', template: detail.template || '', description: detail.description || '', tags: (detail.tags || []).join(', ') }); setEditId(detail.id); setDetail(null); setShowForm(true); }} className={`${BTN2} bg-slate-700/40 text-slate-300`}>Edit</button>}
                {isManager && <button onClick={() => act(() => api.duplicate(detail.id))} className={`${BTN2} bg-slate-700/40 text-slate-300`}><Copy className="w-3 h-3" /> Duplicate</button>}
                {(detail.status === 'draft' || detail.status === 'rejected') && <button onClick={() => act(() => api.submit(detail.id))} className={`${BTN2} bg-sky-500/15 text-sky-300`}><Send className="w-3 h-3" /> Submit</button>}
                {isManager && (detail.status === 'draft' || detail.status === 'pending_review') && <button onClick={() => act(() => api.approve(detail.id))} className={`${BTN2} bg-emerald-500/15 text-emerald-300`}><CheckCircle2 className="w-3 h-3" /> Approve</button>}
                {isManager && detail.status === 'pending_review' && <button onClick={() => act(() => api.reject(detail.id, 'Needs changes'))} className={`${BTN2} bg-red-500/15 text-red-300`}><XCircle className="w-3 h-3" /> Reject</button>}
                <button onClick={async () => setVersions(await api.versions(detail.id))} className={`${BTN2} bg-slate-700/40 text-slate-400`}><History className="w-3 h-3" /> Versions</button>
                {detail.status !== 'archived' && <button onClick={() => act(() => api.archive(detail.id))} className={`${BTN2} bg-slate-700/40 text-slate-400`}><Archive className="w-3 h-3" /> Archive</button>}
                {!detail.is_builtin && <button onClick={() => act(() => api.remove(detail.id))} className={`${BTN2} bg-red-500/15 text-red-300`}><Trash2 className="w-3 h-3" /> Delete</button>}
              </div>
            </div>
            {detail.review_note && <p className="text-[11px] text-amber-300 bg-amber-500/10 border border-amber-500/20 rounded-lg px-2 py-1">Review note: {detail.review_note}</p>}
            {detail.variables.length > 0 && <p className="text-[11px] text-slate-400">Variables: {detail.variables.map(v => <span key={v} className="font-mono text-brand-300 mr-1">{`{{${v}}}`}</span>)}</p>}
            {detail.system_prompt && <div><p className="text-[10px] text-slate-500 uppercase mb-1">System prompt</p><pre className="text-[11px] text-slate-300 whitespace-pre-wrap bg-slate-950/40 rounded-lg p-2">{detail.system_prompt}</pre></div>}
            <div><p className="text-[10px] text-slate-500 uppercase mb-1">User prompt</p><pre className="text-[11px] text-slate-300 whitespace-pre-wrap bg-slate-950/40 rounded-lg p-2">{detail.template}</pre></div>
            {versions && (
              <div className="border-t border-slate-800/60 pt-2 space-y-1.5">
                <h4 className="text-xs font-bold text-slate-300">Version History</h4>
                {versions.length === 0 ? <p className="text-[11px] text-slate-500">No prior versions.</p> :
                  versions.map(v => (
                    <div key={v.version} className="flex items-center justify-between text-[11px] bg-slate-950/40 border border-slate-800/60 rounded-lg px-2 py-1.5">
                      <span className="text-slate-300">v{v.version}{v.change_note ? ` — ${v.change_note}` : ''}</span>
                      {!detail.is_builtin && <button onClick={() => act(() => api.restore(detail.id, v.version))} className="text-brand-300 cursor-pointer">Restore</button>}
                    </div>
                  ))}
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
};
