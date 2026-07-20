import React, { useCallback, useEffect, useState } from 'react';
import {
  LayoutTemplate, Plus, Loader2, Search, Eye, Send, Trash2, Check, X, Clock,
  History, RotateCcw, Mail, MessageSquare, MessageCircle, Phone, ChevronRight,
} from 'lucide-react';
import { templateApi, Template, TemplateVariable, TemplateVersion } from '../services/templateApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const CHANNELS = ['Email', 'SMS', 'WhatsApp', 'Call'];
const CHANNEL_ICON: Record<string, any> = { Email: Mail, SMS: MessageSquare, WhatsApp: MessageCircle, Call: Phone };
const STATUS_STYLE: Record<string, string> = {
  draft: 'bg-slate-700/40 text-slate-300 border-slate-600/40',
  pending_approval: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  approved: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  rejected: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const StatusChip: React.FC<{ status: string }> = ({ status }) => (
  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${STATUS_STYLE[status] || STATUS_STYLE.draft}`}>
    {status.replace('_', ' ')}
  </span>
);

const emptyDraft = { name: '', channel: 'Email', subject: '', body: '', category: '', description: '' };

export const TemplatesPage: React.FC = () => {
  const { user } = useAuthStore();
  const canApprove = !!user && ['SuperAdmin', 'OrgAdmin', 'Manager'].includes(user.role);

  const [list, setList] = useState<Template[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [channelF, setChannelF] = useState('');
  const [statusF, setStatusF] = useState('');

  const [selected, setSelected] = useState<Template | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState<any>(emptyDraft);
  const [variables, setVariables] = useState<TemplateVariable[]>([]);
  const [preview, setPreview] = useState<{ subject: string | null; body: string } | null>(null);
  const [versions, setVersions] = useState<TemplateVersion[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [msg, setMsg] = useState<string | null>(null);
  const [testTo, setTestTo] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setList(await templateApi.list({ search: search || undefined, channel: channelF || undefined, status: statusF || undefined }));
    } finally {
      setLoading(false);
    }
  }, [search, channelF, statusF]);

  useEffect(() => { const t = setTimeout(load, search ? 300 : 0); return () => clearTimeout(t); }, [load, search]);
  useEffect(() => { templateApi.variables().then(setVariables).catch(() => {}); }, []);

  const openNew = () => { setCreating(true); setSelected(null); setForm(emptyDraft); setPreview(null); setVersions(null); setError(null); setMsg(null); };
  const openTemplate = (t: Template) => {
    setCreating(false); setSelected(t); setPreview(null); setVersions(null); setError(null); setMsg(null);
    setForm({ name: t.name, channel: t.channel, subject: t.subject || '', body: t.body, category: t.category || '', description: t.description || '' });
  };

  const insertVar = (key: string) => setForm((f: any) => ({ ...f, body: `${f.body}{{${key}}}` }));

  const save = async () => {
    setError(null); setMsg(null);
    if (!form.name.trim() || !form.body.trim()) { setError('Name and body are required'); return; }
    try {
      if (creating) {
        const t = await templateApi.create({ ...form, subject: form.subject || undefined, category: form.category || undefined, description: form.description || undefined });
        setCreating(false); setSelected(t); setMsg('Template created (draft).');
      } else if (selected) {
        const t = await templateApi.update(selected.id, form);
        setSelected(t); setMsg('Saved.');
      }
      load();
    } catch (err: any) { setError(extractErrorMessage(err, 'Failed to save')); }
  };

  const act = async (fn: () => Promise<Template>, okMsg: string) => {
    setError(null); setMsg(null);
    try { const t = await fn(); setSelected(t); setMsg(okMsg); load(); } catch (err: any) { setError(extractErrorMessage(err, 'Action failed')); }
  };

  const doPreview = async () => {
    if (!selected) return;
    try { setPreview(await templateApi.preview(selected.id)); } catch (err: any) { setError(extractErrorMessage(err, 'Preview failed')); }
  };

  const doTest = async () => {
    if (!selected) return;
    setError(null); setMsg(null);
    try {
      const r = await templateApi.test(selected.id, { to: testTo || undefined });
      setMsg(r.sent ? `Test ${r.channel} sent.` : `Call script preview: ${r.preview?.slice(0, 80)}`);
      load();
    } catch (err: any) { setError(extractErrorMessage(err, 'Test failed')); }
  };

  const loadVersions = async () => {
    if (!selected) return;
    setVersions(await templateApi.versions(selected.id));
  };

  const del = async (t: Template) => {
    if (!confirm(`Delete "${t.name}"?`)) return;
    try { await templateApi.remove(t.id); if (selected?.id === t.id) setSelected(null); load(); } catch (err: any) { setError(extractErrorMessage(err, 'Delete failed')); }
  };

  return (
    <div className="space-y-4">
      <div className="border-b border-slate-800/60 pb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <LayoutTemplate className="w-7 h-7 text-brand-400" /> Templates
          </h1>
          <p className="text-sm text-slate-400 mt-1">Message templates &amp; call scripts with approval workflow and versioning.</p>
        </div>
        <button onClick={openNew} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm cursor-pointer"><Plus className="w-4 h-4" /> New</button>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-210px)] min-h-[520px]">
        {/* List */}
        <div className="glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          <div className="p-3 border-b border-slate-800/60 space-y-2">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search…"
                     className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 pl-9 pr-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
            <div className="flex gap-2">
              <select value={channelF} onChange={(e) => setChannelF(e.target.value)} className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-300 py-1.5 px-2 rounded-lg text-xs">
                <option value="">All channels</option>{CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
              </select>
              <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-300 py-1.5 px-2 rounded-lg text-xs">
                <option value="">All statuses</option>{['draft', 'pending_approval', 'approved', 'rejected'].map((s) => <option key={s} value={s}>{s.replace('_', ' ')}</option>)}
              </select>
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
              : list.length === 0 ? <p className="py-10 text-center text-xs text-slate-500">No templates.</p>
              : list.map((t) => {
                const Icon = CHANNEL_ICON[t.channel] || Mail;
                return (
                  <button key={t.id} onClick={() => openTemplate(t)}
                          className={`w-full text-left px-3 py-2.5 border-b border-slate-800/40 hover:bg-slate-900/50 cursor-pointer ${selected?.id === t.id ? 'bg-slate-900/60' : ''}`}>
                    <div className="flex items-center gap-2">
                      <Icon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="text-sm font-semibold text-slate-200 truncate flex-1">{t.name}</span>
                      <StatusChip status={t.status} />
                    </div>
                    <div className="flex items-center gap-2 mt-0.5 text-[11px] text-slate-500">
                      <span>{t.category || 'Uncategorized'}</span>·<span>v{t.version}</span>{t.usage_count > 0 && <>·<span>used {t.usage_count}×</span></>}
                    </div>
                  </button>
                );
              })}
          </div>
        </div>

        {/* Editor */}
        <div className="lg:col-span-2 glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          {!creating && !selected ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
              <div className="text-center"><LayoutTemplate className="w-10 h-10 mx-auto mb-2 text-slate-600" />Select or create a template</div>
            </div>
          ) : (
            <div className="flex-1 overflow-y-auto p-5 space-y-4">
              {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
              {msg && <div className="p-3 bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 rounded-lg text-xs">{msg}</div>}

              {selected && (
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2"><StatusChip status={selected.status} /><span className="text-xs text-slate-500">v{selected.version} · used {selected.usage_count}×</span></div>
                  <button onClick={() => del(selected)} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer" title="Delete"><Trash2 className="w-4 h-4" /></button>
                </div>
              )}
              {selected?.status === 'rejected' && selected.rejected_reason && (
                <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">Rejected: {selected.rejected_reason}</div>
              )}

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Template name"
                       className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
                <select value={form.channel} onChange={(e) => setForm({ ...form, channel: e.target.value })}
                        className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
                  {CHANNELS.map((c) => <option key={c} value={c}>{c === 'Call' ? 'Call (script)' : c}</option>)}
                </select>
                <input value={form.category} onChange={(e) => setForm({ ...form, category: e.target.value })} placeholder="Category (e.g. Sales)"
                       className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
                <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} placeholder="Description (optional)"
                       className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
              </div>

              {form.channel === 'Email' && (
                <input value={form.subject} onChange={(e) => setForm({ ...form, subject: e.target.value })} placeholder="Subject"
                       className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
              )}

              <div>
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{form.channel === 'Call' ? 'Call script' : 'Body'}</span>
                  <div className="flex flex-wrap gap-1 justify-end">
                    {variables.map((v) => (
                      <button key={v.key} onClick={() => insertVar(v.key)} title={v.label}
                              className="px-1.5 py-0.5 text-[10px] rounded bg-slate-800/80 text-brand-400 border border-slate-700/60 hover:border-brand-500/40 cursor-pointer">{`{{${v.key}}}`}</button>
                    ))}
                  </div>
                </div>
                <textarea value={form.body} onChange={(e) => setForm({ ...form, body: e.target.value })} rows={8}
                          placeholder="Message body — click a variable chip to insert"
                          className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm font-mono" />
              </div>

              <div className="flex flex-wrap items-center gap-2">
                <button onClick={save} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm cursor-pointer"><Check className="w-4 h-4" /> {creating ? 'Create' : 'Save'}</button>
                {selected && (
                  <>
                    <button onClick={doPreview} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-2 px-3 rounded-lg text-sm cursor-pointer"><Eye className="w-4 h-4" /> Preview</button>
                    <button onClick={loadVersions} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-2 px-3 rounded-lg text-sm cursor-pointer"><History className="w-4 h-4" /> Versions</button>
                    {(selected.status === 'draft' || selected.status === 'rejected') && (
                      <button onClick={() => act(() => templateApi.submit(selected.id), 'Submitted for approval.')} className="inline-flex items-center gap-1.5 bg-amber-500/15 text-amber-400 border border-amber-500/25 py-2 px-3 rounded-lg text-sm cursor-pointer"><Clock className="w-4 h-4" /> Submit</button>
                    )}
                    {canApprove && selected.status === 'pending_approval' && (
                      <>
                        <button onClick={() => act(() => templateApi.approve(selected.id), 'Approved.')} className="inline-flex items-center gap-1.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 py-2 px-3 rounded-lg text-sm cursor-pointer"><Check className="w-4 h-4" /> Approve</button>
                        <button onClick={() => act(() => templateApi.reject(selected.id, prompt('Reason for rejection?') || undefined), 'Rejected.')} className="inline-flex items-center gap-1.5 bg-red-500/15 text-red-400 border border-red-500/25 py-2 px-3 rounded-lg text-sm cursor-pointer"><X className="w-4 h-4" /> Reject</button>
                      </>
                    )}
                  </>
                )}
              </div>

              {selected && (
                <div className="flex items-center gap-2 pt-2 border-t border-slate-800/60">
                  <input value={testTo} onChange={(e) => setTestTo(e.target.value)} placeholder={selected.channel === 'Call' ? 'No recipient needed' : selected.channel === 'Email' ? 'test@email.com' : '+15551234567'}
                         disabled={selected.channel === 'Call'}
                         className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-3 rounded-lg text-xs disabled:opacity-50" />
                  <button onClick={doTest} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><Send className="w-3.5 h-3.5" /> Send test</button>
                </div>
              )}

              {preview && (
                <div className="p-3 bg-slate-950/50 border border-slate-800/70 rounded-lg space-y-1">
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Preview (sample data)</p>
                  {preview.subject && <p className="text-sm font-semibold text-slate-200">{preview.subject}</p>}
                  <div className="text-sm text-slate-300 whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: preview.body }} />
                </div>
              )}

              {versions && (
                <div className="p-3 bg-slate-950/50 border border-slate-800/70 rounded-lg space-y-2">
                  <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Version history</p>
                  {versions.length === 0 ? <p className="text-xs text-slate-500">No prior versions.</p> : versions.map((v) => (
                    <div key={v.id} className="flex items-center gap-2 text-xs">
                      <span className="text-slate-500 shrink-0">v{v.version}</span>
                      <ChevronRight className="w-3 h-3 text-slate-600 shrink-0" />
                      <span className="text-slate-400 truncate flex-1">{v.change_note || v.body.slice(0, 50)}</span>
                      <button onClick={() => act(() => templateApi.restore(selected!.id, v.version), `Restored v${v.version}.`)}
                              className="inline-flex items-center gap-1 text-brand-400 hover:text-brand-300 cursor-pointer shrink-0"><RotateCcw className="w-3 h-3" /> Restore</button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
};
