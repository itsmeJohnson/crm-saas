import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  MessageCircle, Send, Loader2, Search, Check, CheckCheck, Clock, Paperclip,
  FileText, Image as ImageIcon, Video, Mic, UserCheck, Zap, AlertTriangle, X,
} from 'lucide-react';
import { whatsappApi, WaConversation, WaThread, WaMessage, QuickReply } from '../services/whatsappApi';
import { communicationApi, CommTemplate } from '../services/communicationApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const StatusTick: React.FC<{ status: string | null }> = ({ status }) => {
  if (status === 'read') return <CheckCheck className="w-3.5 h-3.5 text-sky-400" />;
  if (status === 'delivered') return <CheckCheck className="w-3.5 h-3.5 text-slate-400" />;
  if (status === 'sent') return <Check className="w-3.5 h-3.5 text-slate-400" />;
  if (status === 'failed') return <AlertTriangle className="w-3.5 h-3.5 text-red-400" />;
  return <Clock className="w-3.5 h-3.5 text-slate-500" />;
};

const MediaIcon: React.FC<{ type: string | null }> = ({ type }) => {
  if (type === 'image') return <ImageIcon className="w-3.5 h-3.5" />;
  if (type === 'video') return <Video className="w-3.5 h-3.5" />;
  if (type === 'audio') return <Mic className="w-3.5 h-3.5" />;
  if (type === 'document') return <FileText className="w-3.5 h-3.5" />;
  return null;
};

const timeAgo = (iso: string | null) => {
  if (!iso) return '';
  const diff = Date.now() - new Date(iso).getTime();
  const m = Math.floor(diff / 60000);
  if (m < 1) return 'now';
  if (m < 60) return `${m}m`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h`;
  return `${Math.floor(h / 24)}d`;
};

export const WhatsAppPage: React.FC = () => {
  const { user } = useAuthStore();
  const canAssign = !!user && ['SuperAdmin', 'OrgAdmin', 'Manager'].includes(user.role);

  const [conversations, setConversations] = useState<WaConversation[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [search, setSearch] = useState('');
  const [unreadOnly, setUnreadOnly] = useState(false);

  const [activeId, setActiveId] = useState<string | null>(null);
  const [thread, setThread] = useState<WaThread | null>(null);
  const [loadingThread, setLoadingThread] = useState(false);

  const [body, setBody] = useState('');
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<CommTemplate[]>([]);
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [team, setTeam] = useState<{ id: string; name: string }[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await whatsappApi.conversations({ search: search || undefined, unread_only: unreadOnly || undefined });
      setConversations(data);
    } finally {
      setLoadingList(false);
    }
  }, [search, unreadOnly]);

  useEffect(() => { const t = setTimeout(loadList, search ? 300 : 0); return () => clearTimeout(t); }, [loadList, search]);

  useEffect(() => {
    communicationApi.listTemplates().then((t) => setTemplates(t.filter((x) => x.channel === 'WhatsApp'))).catch(() => {});
    whatsappApi.listQuickReplies().then(setQuickReplies).catch(() => {});
    if (canAssign) userApi.getUsers({ is_active: true, limit: 100 }).then((u) =>
      setTeam(u.map((x: any) => ({ id: x.id, name: `${x.first_name || ''} ${x.last_name || ''}`.trim() || x.email })))).catch(() => {});
  }, [canAssign]);

  const openConversation = async (id: string) => {
    setActiveId(id);
    setLoadingThread(true);
    setError(null);
    try {
      const data = await whatsappApi.thread(id);
      setThread(data);
      setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, unread_count: 0 } : c)));
    } finally {
      setLoadingThread(false);
    }
  };

  const refreshThread = async () => {
    if (activeId) {
      const data = await whatsappApi.thread(activeId);
      setThread(data);
    }
  };

  const send = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!thread || !body.trim()) return;
    setSending(true);
    setError(null);
    try {
      await whatsappApi.sendText({ conversation_id: thread.conversation.id, body });
      setBody('');
      await refreshThread();
      loadList();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to send'));
    } finally {
      setSending(false);
    }
  };

  const sendTemplate = async (templateId: string) => {
    if (!thread) return;
    setSending(true);
    setError(null);
    try {
      await whatsappApi.sendTemplate({ conversation_id: thread.conversation.id, template_id: templateId });
      await refreshThread();
      loadList();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to send template'));
    } finally {
      setSending(false);
    }
  };

  const onFile = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file || !thread) return;
    setSending(true);
    setError(null);
    try {
      const form = new FormData();
      form.append('file', file);
      form.append('conversation_id', thread.conversation.id);
      if (body.trim()) form.append('caption', body);
      await whatsappApi.sendMedia(form);
      setBody('');
      await refreshThread();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to send media'));
    } finally {
      setSending(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const assign = async (userId: string) => {
    if (!thread) return;
    try {
      const updated = await whatsappApi.assign(thread.conversation.id, userId || null);
      setThread({ ...thread, conversation: updated });
      loadList();
    } catch { /* ignore */ }
  };

  const windowOpen = thread?.conversation.window_open;

  return (
    <div className="space-y-4">
      <div className="border-b border-slate-800/60 pb-4">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <MessageCircle className="w-7 h-7 text-emerald-400" /> WhatsApp
        </h1>
        <p className="text-sm text-slate-400 mt-1">Two-way conversations with delivery &amp; read receipts.</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-220px)] min-h-[520px]">
        {/* Conversation list */}
        <div className="glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          <div className="p-3 border-b border-slate-800/60 space-y-2">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search…"
                     className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 pl-9 pr-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500" />
            </div>
            <label className="flex items-center gap-1.5 text-xs text-slate-400 cursor-pointer select-none">
              <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} className="w-3.5 h-3.5 rounded" /> Unread only
            </label>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loadingList ? (
              <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
            ) : conversations.length === 0 ? (
              <p className="py-10 text-center text-xs text-slate-500">No conversations.</p>
            ) : conversations.map((c) => (
              <button key={c.id} onClick={() => openConversation(c.id)}
                      className={`w-full text-left px-3 py-2.5 border-b border-slate-800/40 hover:bg-slate-900/50 cursor-pointer ${activeId === c.id ? 'bg-slate-900/60' : ''}`}>
                <div className="flex items-center justify-between gap-2">
                  <span className="text-sm font-semibold text-slate-200 truncate">{c.display_name || c.phone}</span>
                  <span className="text-[10px] text-slate-500 shrink-0">{timeAgo(c.last_message_at)}</span>
                </div>
                <div className="flex items-center justify-between gap-2 mt-0.5">
                  <span className="text-[11px] text-slate-500 truncate">{c.assigned_user_name || 'Unassigned'}</span>
                  <div className="flex items-center gap-1.5 shrink-0">
                    {!c.window_open && <span title="24h window closed" className="text-[9px] text-amber-500/80 font-semibold uppercase">closed</span>}
                    {c.unread_count > 0 && <span className="min-w-4 h-4 px-1 rounded-full bg-emerald-500 text-[10px] font-black text-white flex items-center justify-center">{c.unread_count}</span>}
                  </div>
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Thread */}
        <div className="lg:col-span-2 glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          {!thread ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
              <div className="text-center"><MessageCircle className="w-10 h-10 mx-auto mb-2 text-slate-600" />Select a conversation</div>
            </div>
          ) : (
            <>
              {/* Thread header */}
              <div className="p-3 border-b border-slate-800/60 flex items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-semibold text-slate-200 truncate">{thread.conversation.display_name || thread.conversation.phone}</p>
                  <p className="text-[11px] text-slate-500">{thread.conversation.phone}</p>
                </div>
                {canAssign && (
                  <div className="flex items-center gap-1.5">
                    <UserCheck className="w-3.5 h-3.5 text-slate-500" />
                    <select value={thread.conversation.assigned_user_id || ''} onChange={(e) => assign(e.target.value)}
                            className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-1 px-2 rounded-lg text-xs focus:outline-none">
                      <option value="">Unassigned</option>
                      {team.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  </div>
                )}
              </div>

              {/* Messages */}
              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                {loadingThread ? (
                  <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
                ) : thread.messages.map((m: WaMessage) => (
                  <div key={m.id} className={`flex ${m.direction === 'OUTBOUND' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[75%] rounded-2xl px-3 py-2 text-sm ${m.direction === 'OUTBOUND' ? 'bg-emerald-600/20 border border-emerald-600/30 text-slate-100' : 'bg-slate-800/70 border border-slate-700/60 text-slate-200'}`}>
                      {m.media_type && m.media_type !== 'text' && (
                        <div className="flex items-center gap-1.5 text-[11px] text-slate-400 mb-1"><MediaIcon type={m.media_type} /> {m.media_type}{m.attachments?.[0]?.url && <a href={m.attachments[0].url} target="_blank" rel="noreferrer" className="underline text-emerald-400">open</a>}</div>
                      )}
                      {m.template_name && <div className="text-[10px] text-slate-400 mb-0.5">Template · {m.template_name}</div>}
                      {m.body && <p className="whitespace-pre-wrap break-words">{m.body}</p>}
                      <div className="flex items-center justify-end gap-1 mt-0.5">
                        <span className="text-[10px] text-slate-500">{new Date(m.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        {m.direction === 'OUTBOUND' && <StatusTick status={m.wa_status} />}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* 24h window banner */}
              {!windowOpen && (
                <div className="px-4 py-2 bg-amber-500/10 border-t border-amber-500/20 text-amber-400 text-xs flex items-center gap-2">
                  <AlertTriangle className="w-3.5 h-3.5" /> 24-hour window closed — send a template to re-open the conversation.
                </div>
              )}

              {error && <div className="px-4 py-2 bg-red-500/10 border-t border-red-500/20 text-red-400 text-xs flex items-center justify-between"><span>{error}</span><button onClick={() => setError(null)}><X className="w-3.5 h-3.5" /></button></div>}

              {/* Quick replies */}
              {windowOpen && quickReplies.length > 0 && (
                <div className="px-3 pt-2 flex flex-wrap gap-1.5">
                  {quickReplies.map((q) => (
                    <button key={q.id} onClick={() => setBody(q.text)} title={q.text}
                            className="inline-flex items-center gap-1 px-2 py-1 text-[11px] rounded-md bg-slate-800/80 text-slate-300 border border-slate-700/60 hover:text-emerald-400 cursor-pointer">
                      <Zap className="w-3 h-3" /> {q.shortcut}
                    </button>
                  ))}
                </div>
              )}

              {/* Composer */}
              <form onSubmit={send} className="p-3 border-t border-slate-800/60">
                {windowOpen ? (
                  <div className="flex items-end gap-2">
                    <input type="file" ref={fileRef} onChange={onFile} className="hidden" />
                    <button type="button" onClick={() => fileRef.current?.click()} title="Attach media"
                            className="p-2 rounded-lg text-slate-400 hover:text-emerald-400 border border-slate-700/60 cursor-pointer shrink-0"><Paperclip className="w-4 h-4" /></button>
                    <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={1} placeholder="Type a message…"
                              className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm resize-none focus:outline-none focus:ring-2 focus:ring-emerald-500" />
                    <button type="submit" disabled={sending || !body.trim()}
                            className="p-2 rounded-lg bg-gradient-to-r from-emerald-500 to-teal-500 text-white disabled:opacity-40 cursor-pointer shrink-0">
                      {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                    </button>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <select onChange={(e) => e.target.value && sendTemplate(e.target.value)} value=""
                            className="flex-1 bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm focus:outline-none" disabled={sending}>
                      <option value="">Send a template to re-open…</option>
                      {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                    {sending && <Loader2 className="w-4 h-4 animate-spin text-slate-400" />}
                  </div>
                )}
              </form>
            </>
          )}
        </div>
      </div>
    </div>
  );
};
