import React, { useCallback, useEffect, useState } from 'react';
import {
  Mail, Inbox, Send, FileText, Loader2, Search, RefreshCw, Eye, MousePointerClick,
  Reply, Forward, X, PenSquare,
} from 'lucide-react';
import { emailApi, EmailItem } from '../services/emailApi';
import { communicationApi, CommTemplate } from '../services/communicationApi';
import { extractErrorMessage } from '../utils/errors';

type Folder = 'inbox' | 'sent' | 'drafts';
type ComposeMode = null | { kind: 'new' } | { kind: 'reply'; on: EmailItem } | { kind: 'forward'; on: EmailItem } | { kind: 'draft'; on: EmailItem };

const fmt = (iso: string) => new Date(iso).toLocaleString();

const Composer: React.FC<{ mode: Exclude<ComposeMode, null>; onClose: () => void; onSent: () => void }> = ({ mode, onClose, onSent }) => {
  const initialTo = mode.kind === 'reply' ? (mode.on.direction === 'INBOUND' ? mode.on.email_from : mode.on.email_to) : '';
  const initialSubject = mode.kind === 'draft' ? mode.on.subject : mode.kind === 'forward' ? '' : '';
  const [to, setTo] = useState(mode.kind === 'draft' ? (mode.on.email_to || '') : (initialTo || ''));
  const [cc, setCc] = useState(mode.kind === 'draft' ? (mode.on.email_cc || '') : '');
  const [subject, setSubject] = useState(initialSubject || (mode.kind === 'draft' ? mode.on.subject : ''));
  const [body, setBody] = useState(mode.kind === 'draft' ? (mode.on.body || '') : '');
  const [templates, setTemplates] = useState<CommTemplate[]>([]);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    communicationApi.listTemplates().then((t) => setTemplates(t.filter((x) => x.channel === 'Email'))).catch(() => {});
  }, []);

  const title = mode.kind === 'reply' ? 'Reply' : mode.kind === 'forward' ? 'Forward' : mode.kind === 'draft' ? 'Edit draft' : 'New email';
  const needsSubjectTo = mode.kind === 'new' || mode.kind === 'forward' || mode.kind === 'draft';

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSending(true); setError(null);
    try {
      if (mode.kind === 'reply') await emailApi.reply(mode.on.id, { body, cc: cc || undefined });
      else if (mode.kind === 'forward') await emailApi.forward(mode.on.id, { to, cc: cc || undefined, body });
      else if (mode.kind === 'draft') { await emailApi.updateDraft(mode.on.id, { subject, body, to, cc }); await emailApi.sendDraft(mode.on.id); }
      else await emailApi.send({ subject, body, to, cc: cc || undefined });
      onSent();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to send'));
    } finally {
      setSending(false);
    }
  };

  const saveDraft = async () => {
    setSending(true); setError(null);
    try {
      if (mode.kind === 'draft') await emailApi.updateDraft(mode.on.id, { subject, body, to, cc });
      else await emailApi.createDraft({ subject, body, to, cc });
      onSent();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to save draft'));
    } finally {
      setSending(false);
    }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-2xl bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Mail className="w-4 h-4 text-brand-400" /> {title}</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <form onSubmit={submit} className="p-4 space-y-3">
          {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          {needsSubjectTo && (
            <input value={to} onChange={(e) => setTo(e.target.value)} placeholder="To (comma-separated)"
                   className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          )}
          <input value={cc} onChange={(e) => setCc(e.target.value)} placeholder="Cc (optional)"
                 className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          {needsSubjectTo && (
            <div className="flex items-center gap-2">
              <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject"
                     className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
              {templates.length > 0 && (
                <select onChange={(e) => { const t = templates.find((x) => x.id === e.target.value); if (t) { setSubject(t.subject || subject); setBody(t.body); } }}
                        value="" className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-2 rounded-lg text-xs focus:outline-none">
                  <option value="">Template…</option>
                  {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              )}
            </div>
          )}
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={10} placeholder="Write your message… (HTML supported)"
                    className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
          <div className="flex items-center justify-end gap-2">
            <button type="button" onClick={saveDraft} disabled={sending}
                    className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-2 px-4 rounded-lg text-sm cursor-pointer">
              <FileText className="w-4 h-4" /> Save draft
            </button>
            <button type="submit" disabled={sending}
                    className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
              {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Send
            </button>
          </div>
        </form>
      </div>
    </div>
  );
};

export const EmailPage: React.FC = () => {
  const [folder, setFolder] = useState<Folder>('inbox');
  const [items, setItems] = useState<EmailItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [selected, setSelected] = useState<EmailItem | null>(null);
  const [compose, setCompose] = useState<ComposeMode>(null);
  const [syncing, setSyncing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await emailApi.messages({ folder, search: search || undefined });
      setItems(data.items);
    } finally {
      setLoading(false);
    }
  }, [folder, search]);

  useEffect(() => { const t = setTimeout(load, search ? 300 : 0); return () => clearTimeout(t); }, [load, search]);
  useEffect(() => { setSelected(null); }, [folder]);

  const sync = async () => {
    setSyncing(true);
    try { await emailApi.sync(); await load(); } finally { setSyncing(false); }
  };

  const afterSend = () => { setCompose(null); load(); };

  const folders: { key: Folder; label: string; icon: any }[] = [
    { key: 'inbox', label: 'Inbox', icon: Inbox },
    { key: 'sent', label: 'Sent', icon: Send },
    { key: 'drafts', label: 'Drafts', icon: FileText },
  ];

  return (
    <div className="space-y-4">
      <div className="border-b border-slate-800/60 pb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <Mail className="w-7 h-7 text-brand-400" /> Email
          </h1>
          <p className="text-sm text-slate-400 mt-1">Threaded email with open &amp; click tracking.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={sync} disabled={syncing} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-2 px-3 rounded-lg text-sm cursor-pointer">
            <RefreshCw className={`w-4 h-4 ${syncing ? 'animate-spin' : ''}`} /> Sync
          </button>
          <button onClick={() => setCompose({ kind: 'new' })} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm cursor-pointer">
            <PenSquare className="w-4 h-4" /> Compose
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-220px)] min-h-[520px]">
        {/* Folders + list */}
        <div className="glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          <div className="flex items-center gap-1 p-2 border-b border-slate-800/60">
            {folders.map((f) => (
              <button key={f.key} onClick={() => setFolder(f.key)}
                      className={`flex-1 inline-flex items-center justify-center gap-1.5 py-1.5 rounded-lg text-xs font-medium cursor-pointer ${folder === f.key ? 'bg-slate-800 text-brand-400' : 'text-slate-400 hover:text-slate-200'}`}>
                <f.icon className="w-3.5 h-3.5" /> {f.label}
              </button>
            ))}
          </div>
          <div className="p-2 border-b border-slate-800/60">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search mail…"
                     className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 pl-9 pr-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? (
              <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
            ) : items.length === 0 ? (
              <p className="py-10 text-center text-xs text-slate-500">No messages.</p>
            ) : items.map((m) => (
              <button key={m.id} onClick={() => (folder === 'drafts' ? setCompose({ kind: 'draft', on: m }) : setSelected(m))}
                      className={`w-full text-left px-3 py-2.5 border-b border-slate-800/40 hover:bg-slate-900/50 cursor-pointer ${selected?.id === m.id ? 'bg-slate-900/60' : ''}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-xs font-semibold text-slate-200 truncate">{folder === 'inbox' ? m.email_from : m.email_to}</span>
                  <span className="text-[10px] text-slate-500 shrink-0">{new Date(m.timestamp).toLocaleDateString()}</span>
                </div>
                <p className="text-sm text-slate-300 truncate">{m.subject}</p>
                <div className="flex items-center gap-2 mt-0.5">
                  {m.status === 'failed' && <span className="text-[9px] text-red-400 font-semibold uppercase">failed</span>}
                  {folder === 'sent' && m.open_count > 0 && <span title="Opened" className="inline-flex items-center gap-0.5 text-[10px] text-emerald-400"><Eye className="w-3 h-3" />{m.open_count}</span>}
                  {folder === 'sent' && m.click_count > 0 && <span title="Clicked" className="inline-flex items-center gap-0.5 text-[10px] text-sky-400"><MousePointerClick className="w-3 h-3" />{m.click_count}</span>}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Reader */}
        <div className="lg:col-span-2 glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
              <div className="text-center"><Mail className="w-10 h-10 mx-auto mb-2 text-slate-600" />Select a message</div>
            </div>
          ) : (
            <>
              <div className="p-4 border-b border-slate-800/60">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <h2 className="text-lg font-bold text-slate-100 truncate">{selected.subject}</h2>
                    <p className="text-xs text-slate-400 mt-1"><span className="text-slate-500">From:</span> {selected.email_from} · <span className="text-slate-500">To:</span> {selected.email_to}</p>
                    {selected.email_cc && <p className="text-xs text-slate-500">Cc: {selected.email_cc}</p>}
                    <p className="text-[11px] text-slate-500 mt-0.5">{fmt(selected.timestamp)}</p>
                  </div>
                  <div className="flex items-center gap-1.5 shrink-0">
                    <button onClick={() => setCompose({ kind: 'reply', on: selected })} title="Reply" className="p-2 rounded-lg text-slate-400 hover:text-brand-400 border border-slate-700/60 cursor-pointer"><Reply className="w-4 h-4" /></button>
                    <button onClick={() => setCompose({ kind: 'forward', on: selected })} title="Forward" className="p-2 rounded-lg text-slate-400 hover:text-brand-400 border border-slate-700/60 cursor-pointer"><Forward className="w-4 h-4" /></button>
                  </div>
                </div>
                {selected.direction === 'OUTBOUND' && (
                  <div className="flex items-center gap-3 mt-2 text-[11px]">
                    <span className={`inline-flex items-center gap-1 ${selected.open_count > 0 ? 'text-emerald-400' : 'text-slate-500'}`}><Eye className="w-3.5 h-3.5" /> {selected.open_count > 0 ? `Opened ${selected.open_count}×` : 'Not opened'}</span>
                    <span className={`inline-flex items-center gap-1 ${selected.click_count > 0 ? 'text-sky-400' : 'text-slate-500'}`}><MousePointerClick className="w-3.5 h-3.5" /> {selected.click_count > 0 ? `${selected.click_count} click(s)` : 'No clicks'}</span>
                  </div>
                )}
              </div>
              <div className="flex-1 overflow-y-auto p-5">
                <div className="prose prose-invert prose-sm max-w-none text-slate-300" dangerouslySetInnerHTML={{ __html: selected.body || '<p class="text-slate-500">(no content)</p>' }} />
              </div>
            </>
          )}
        </div>
      </div>

      {compose && <Composer mode={compose} onClose={() => setCompose(null)} onSent={afterSend} />}
    </div>
  );
};
