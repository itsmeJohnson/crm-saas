import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  MessageCircle, Send, Loader2, Search, Check, CheckCheck, Clock, Paperclip,
  FileText, Image as ImageIcon, Video, Mic, Zap, AlertTriangle, X,
  Lock, Unlock, Tag, UserPlus, Eye, ArrowLeft
} from 'lucide-react';
import { useSearchParams } from 'react-router-dom';
import { whatsappApi, WaConversation, WaThread, WaMessage, QuickReply, WaLabel } from '../services/whatsappApi';
import { communicationApi, CommTemplate } from '../services/communicationApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { whatsappRealtime } from '../services/whatsappRealtime';
import { extractErrorMessage } from '../utils/errors';

const SLA_TIME_MINUTES = 15;

const StatusTick: React.FC<{ status: string }> = ({ status }) => {
  if (status === 'read') return <CheckCheck className="w-3.5 h-3.5 text-sky-400" />;
  if (status === 'delivered') return <CheckCheck className="w-3.5 h-3.5 text-slate-400" />;
  if (status === 'sent') return <Check className="w-3.5 h-3.5 text-slate-400" />;
  if (status === 'failed') return <AlertTriangle className="w-3.5 h-3.5 text-red-400" />;
  return <Clock className="w-3.5 h-3.5 text-slate-500" />;
};

const MediaIcon: React.FC<{ type: string }> = ({ type }) => {
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
  const isManagerOrAdmin = !!user && ['SuperAdmin', 'OrgAdmin', 'Manager'].includes(user.role);

  const [conversations, setConversations] = useState<WaConversation[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [search, setSearch] = useState('');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [labelFilter, setLabelFilter] = useState<string>('');
  const [settingsFilter, setSettingsFilter] = useState<string>('');

  const [activeId, setActiveId] = useState<string | null>(null);
  const [thread, setThread] = useState<WaThread | null>(null);
  const [loadingThread, setLoadingThread] = useState(false);

  const [body, setBody] = useState('');
  const [isInternal, setIsInternal] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [templates, setTemplates] = useState<CommTemplate[]>([]);
  const [quickReplies, setQuickReplies] = useState<QuickReply[]>([]);
  const [allLabels, setAllLabels] = useState<WaLabel[]>([]);
  const [team, setTeam] = useState<{ id: string; name: string }[]>([]);
  const [settingsList, setSettingsList] = useState<{ id: string; number: string }[]>([]);
  const fileRef = useRef<HTMLInputElement>(null);

  const [assigneeId, setAssigneeId] = useState('');

  const loadList = useCallback(async () => {
    setLoadingList(true);
    try {
      const data = await whatsappApi.conversations({
        search: search || undefined,
        unread_only: unreadOnly || undefined,
        label_id: labelFilter || undefined,
        settings_id: settingsFilter || undefined
      });
      setConversations(data);
    } finally {
      setLoadingList(false);
    }
  }, [search, unreadOnly, labelFilter, settingsFilter]);

  // Initial load
  useEffect(() => {
    whatsappApi.listQuickReplies().then(setQuickReplies).catch(() => {});
    whatsappApi.listLabels().then(setAllLabels).catch(() => {});
    whatsappApi.listSettings().then((list) =>
      setSettingsList(list.map((s) => ({ id: s.id, number: s.sender_number || s.phone_number_id || 'Mock' })))
    ).catch(() => {});
    
    if (isManagerOrAdmin) {
      userApi.getUsers({ is_active: true, limit: 100 }).then((u) =>
        setTeam(u.map((x: any) => ({ id: x.id, name: `${x.first_name || ''} ${x.last_name || ''}`.trim() || x.email })))
      ).catch(() => {});
    }
  }, [isManagerOrAdmin]);

  useEffect(() => {
    const t = setTimeout(loadList, search ? 300 : 0);
    return () => clearTimeout(t);
  }, [loadList, search]);

  // Deep-link / notifier auto-open: open the conversation named in the URL
  // (?conversationId=...), e.g. when the user clicks the global inbound popup.
  const [searchParams] = useSearchParams();
  useEffect(() => {
    const cid = searchParams.get('conversationId');
    if (cid && cid !== activeId) {
      openConversation(cid);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);

  // Real-time updates via the shared WhatsApp WebSocket (one connection,
  // multiplexed to this page and the global inbound notifier).
  useEffect(() => {
    if (!user) return;
    whatsappRealtime.connect(user.id);

    const unsubscribe = whatsappRealtime.subscribe((data) => {
        try {
          if (data.type === 'whatsapp_message') {
            const newMsg = data.message;
            if (activeId === data.conversation_id) {
              setThread((prev) => {
                if (!prev) return null;
                // Avoid duplicates
                if (prev.messages.some(m => m.id === newMsg.id)) return prev;
                return {
                  ...prev,
                  messages: [...prev.messages, newMsg]
                };
              });
            }
            
            // Refresh conversation list to bump/update latest text
            loadList();
          }
          
          else if (data.type === 'whatsapp_message_status') {
            if (activeId === data.conversation_id) {
              setThread((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  messages: prev.messages.map(m => m.id === data.message_id ? { ...m, wa_status: data.status, error: data.error } : m)
                };
              });
            }
          }
          
          else if (data.type === 'whatsapp_lock_change') {
            if (activeId === data.conversation_id) {
              setThread((prev) => {
                if (!prev) return null;
                const isLocked = !!data.locked_by_user_id;
                return {
                  ...prev,
                  conversation: {
                    ...prev.conversation,
                    locked_by_user_id: data.locked_by_user_id,
                    locked_by_user_name: data.locked_by_name,
                    lock_expires_at: data.lock_expires_at,
                    is_locked: isLocked
                  }
                };
              });
            }
            loadList();
          }

          else if (data.type === 'whatsapp_conversation_status') {
            if (activeId === data.conversation_id) {
              setThread((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  conversation: { ...prev.conversation, status: data.status }
                };
              });
            }
            loadList();
          }
          
          else if (data.type === 'whatsapp_conversation_assigned') {
            if (activeId === data.conversation_id) {
              setThread((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  conversation: {
                    ...prev.conversation,
                    assigned_user_id: data.assigned_user_id,
                    assigned_user_name: data.assigned_user_name
                  }
                };
              });
            }
            loadList();
          }

          else if (data.type === 'whatsapp_attachment_ready') {
            if (activeId === data.conversation_id) {
              setThread((prev) => {
                if (!prev) return null;
                return {
                  ...prev,
                  messages: prev.messages.map(m => m.id === data.message_id ? { ...m, attachments: [data.attachment] } : m)
                };
              });
            }
          }
        } catch (e) {
          console.error("Failed to parse websocket message", e);
        }
    });

    return () => {
      unsubscribe();
    };
  }, [activeId, user, loadList]);

  const openConversation = async (id: string) => {
    setActiveId(id);
    setLoadingThread(true);
    setError(null);
    try {
      const data = await whatsappApi.thread(id);
      setThread(data);
      setAssigneeId(data.conversation.assigned_user_id || '');
      setConversations((prev) => prev.map((c) => (c.id === id ? { ...c, unread_count: 0 } : c)));
      
      // Auto pre-fill active settings filter if selected
      setTemplates([]);
      Promise.all([
        communicationApi.listTemplates().catch(() => []),
        whatsappApi.listTemplates().catch(() => []),
      ]).then(([commList, waList]) => {
        const commWhatsApp = (commList || []).filter((x) => x.channel === 'WhatsApp');
        const waConverted = (waList || []).map((w) => ({
          id: w.id,
          organization_id: w.organization_id,
          name: w.name,
          channel: 'WhatsApp',
          subject: null,
          body: w.body_text,
          created_at: '',
          language: w.language,
        }));
        const combined = [...commWhatsApp];
        waConverted.forEach((w) => {
          if (!combined.some((c) => c.name.toLowerCase() === w.name.toLowerCase())) {
            combined.push(w);
          }
        });
        setTemplates(combined);
      }).catch(() => {});
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to load thread'));
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
      await whatsappApi.sendText({
        conversation_id: thread.conversation.id,
        body,
        is_internal: isInternal
      });
      setBody('');
      setIsInternal(false);
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
      setAssigneeId(userId);
      loadList();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to assign conversation'));
    }
  };

  const changeStatus = async (status: string) => {
    if (!thread) return;
    try {
      const updated = await whatsappApi.changeStatus(thread.conversation.id, status);
      setThread({ ...thread, conversation: updated });
      loadList();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to update status'));
    }
  };

  const toggleLock = async () => {
    if (!thread) return;
    try {
      let updated;
      if (thread.conversation.is_locked) {
        updated = await whatsappApi.unlock(thread.conversation.id);
      } else {
        updated = await whatsappApi.lock(thread.conversation.id);
      }
      setThread({ ...thread, conversation: updated });
      loadList();
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to toggle composer lock lease'));
    }
  };

  const promoteToLead = async () => {
    if (!thread || !thread.conversation.whatsapp_contact_id) return;
    try {
      const res = await whatsappApi.promoteContact(thread.conversation.whatsapp_contact_id);
      await refreshThread();
      loadList();
      setError(`Contact promoted to Lead: ${res.title}`);
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to promote contact'));
    }
  };

  const assignTag = async (labelId: string) => {
    if (!thread) return;
    try {
      const updated = await whatsappApi.assignLabel(thread.conversation.id, labelId);
      setThread({ ...thread, conversation: updated });
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to assign label'));
    }
  };

  const removeTag = async (labelId: string) => {
    if (!thread) return;
    try {
      const updated = await whatsappApi.removeLabel(thread.conversation.id, labelId);
      setThread({ ...thread, conversation: updated });
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to remove label'));
    }
  };

  const windowOpen = thread?.conversation.window_open;
  const isLocked = thread?.conversation.is_locked;
  const lockOwner = thread?.conversation.locked_by_user_id === user?.id;

  return (
    <div className="space-y-4">
      <div className="border-b border-default pb-4 flex flex-wrap justify-between items-center gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-strong flex items-center gap-3">
            <MessageCircle className="w-7 h-7 text-[#25D366]" /> WhatsApp Conversations
          </h1>
          <p className="text-sm text-muted mt-1">Unified omnichannel team inbox with response SLA guarantees and locking.</p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4 h-[calc(100vh-220px)] min-h-[580px]">
        {/* Sidebar Filters & List */}
        <div className={`bg-card border border-default rounded-2xl flex flex-col overflow-hidden shadow-xs ${activeId ? 'hidden lg:flex' : 'flex'}`}>
          <div className="p-3 border-b border-default space-y-2.5">
            <div className="relative">
              <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search number or name..."
                     className="w-full bg-card border border-default text-strong py-2 pl-9 pr-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500/20 placeholder:text-muted" />
            </div>
            
            <div className="grid grid-cols-2 gap-2">
              <select value={settingsFilter} onChange={(e) => setSettingsFilter(e.target.value)}
                      className="bg-card border border-default text-strong py-1.5 px-2 rounded-lg text-xs focus:outline-none">
                <option value="">All Numbers</option>
                {settingsList.map(s => <option key={s.id} value={s.id}>{s.number}</option>)}
              </select>
              <select value={labelFilter} onChange={(e) => setLabelFilter(e.target.value)}
                      className="bg-card border border-default text-strong py-1.5 px-2 rounded-lg text-xs focus:outline-none">
                <option value="">All Labels</option>
                {allLabels.map(l => <option key={l.id} value={l.id}>{l.name}</option>)}
              </select>
            </div>

            <label className="flex items-center gap-1.5 text-xs text-muted cursor-pointer select-none">
              <input type="checkbox" checked={unreadOnly} onChange={(e) => setUnreadOnly(e.target.checked)} className="w-3.5 h-3.5 rounded border-default text-[#25D366] focus:ring-indigo-500" /> Unread messages only
            </label>
          </div>
          
          <div className="flex-1 overflow-y-auto divide-y divide-default">
            {loadingList ? (
              <div className="py-12 text-center text-muted"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
            ) : conversations.length === 0 ? (
              <p className="py-12 text-center text-xs text-muted">No active threads matching filters.</p>
            ) : conversations.map((c) => {
              const isBreached = c.sla_status === 'breached';
              return (
                <button key={c.id} onClick={() => openConversation(c.id)}
                        className={`w-full text-left px-4 py-3 hover:bg-hover transition cursor-pointer flex flex-col gap-1 ${activeId === c.id ? 'bg-selected border-l-2 border-[#25D366]' : 'bg-card'}`}>
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-sm font-semibold text-strong truncate">{c.display_name || c.phone}</span>
                    <span className="text-[10px] text-muted shrink-0">{timeAgo(c.last_message_at)}</span>
                  </div>
                  
                  <div className="flex items-center justify-between gap-2">
                    <span className="text-xs text-muted truncate">{c.assigned_user_name || 'Unassigned'}</span>
                    <div className="flex items-center gap-1.5 shrink-0">
                      {isBreached && (
                        <span className="px-1.5 py-0.5 rounded bg-status-danger-bg text-status-danger-fg border border-status-danger-fg/20 text-[9px] font-black uppercase tracking-wider">SLA Overdue</span>
                      )}
                      {c.is_locked && <Lock className="w-3 h-3 text-status-warning-fg" />}
                      {!c.window_open && <span title="24h customer window closed" className="text-[9px] text-status-warning-fg font-bold uppercase">closed</span>}
                      {c.unread_count > 0 && <span className="min-w-4 h-4 px-1 rounded-full bg-[#25D366] text-[10px] font-black text-white flex items-center justify-center">{c.unread_count}</span>}
                    </div>
                  </div>

                  {c.labels.length > 0 && (
                    <div className="flex flex-wrap gap-1 mt-1">
                      {c.labels.slice(0, 2).map(l => (
                        <span key={l.id} className="text-[9px] font-bold px-1.5 py-0.5 rounded border uppercase tracking-wider" style={{ color: l.color, borderColor: `${l.color}20`, backgroundColor: `${l.color}08` }}>{l.name}</span>
                      ))}
                    </div>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {/* Central Chat Thread Panel */}
        <div className={`lg:col-span-3 bg-card border border-default rounded-2xl flex flex-col overflow-hidden shadow-xs ${!activeId ? 'hidden lg:flex' : 'flex'}`}>
          {!thread ? (
            <div className="flex-1 flex items-center justify-center bg-subtle p-8">
              <div className="text-center max-w-sm space-y-3">
                <MessageCircle className="w-12 h-12 mx-auto text-muted stroke-1" />
                <h3 className="text-sm font-semibold text-strong">No conversation selected</h3>
                <p className="text-xs text-muted">Choose a client conversation from the list to view WhatsApp messages, respond, or send broadcast templates.</p>
              </div>
            </div>
          ) : (
            <>
              {/* Thread header */}
              <div className="p-3 sm:p-4 border-b border-default flex flex-wrap items-center justify-between gap-3 bg-subtle">
                <div className="flex items-center gap-2 min-w-0">
                  <button
                    onClick={() => { setActiveId(null); setThread(null); }}
                    className="lg:hidden p-1.5 -ml-1 rounded-lg text-muted hover:text-strong hover:bg-hover"
                    title="Back to conversations"
                  >
                    <ArrowLeft className="w-4 h-4 text-[#25D366]" />
                  </button>
                  <div className="min-w-0">
                    <div className="flex items-center gap-2 flex-wrap">
                      <p className="text-sm font-semibold text-strong truncate">{thread.conversation.display_name || thread.conversation.phone}</p>
                      {thread.conversation.whatsapp_contact_id && (
                        <button onClick={promoteToLead} className="inline-flex items-center gap-1 px-2 py-0.5 rounded bg-status-success-bg text-status-success-fg border border-status-success-fg/20 text-[9px] font-black uppercase tracking-wider hover:opacity-90 transition cursor-pointer">
                          <UserPlus className="w-3 h-3" /> Promote to Lead
                        </button>
                      )}
                    </div>
                    <p className="text-[11px] text-muted">{thread.conversation.phone}</p>
                  </div>
                </div>
                
                {/* Actions: lock compose, tag, assign, status */}
                <div className="flex flex-wrap items-center gap-2">
                  {/* Status Dropdown */}
                  <select value={thread.conversation.status} onChange={(e) => changeStatus(e.target.value)}
                          className="bg-card border border-default text-body py-1 px-2.5 rounded-xl text-xs focus:outline-none focus:ring-1 focus:ring-indigo-500 cursor-pointer">
                    <option value="open">Open</option>
                    <option value="pending">Pending</option>
                    <option value="resolved">Resolved</option>
                    <option value="closed">Closed</option>
                  </select>

                  {/* Lock Thread button */}
                  <button onClick={toggleLock} title={isLocked ? "Unlock compose lease" : "Lock compose lease"}
                          className={`p-1.5 rounded-xl border transition cursor-pointer ${
                            isLocked
                              ? 'bg-status-warning-bg border-status-warning-fg/30 text-status-warning-fg'
                              : 'bg-card border-default text-muted hover:text-strong hover:bg-hover'
                          }`}>
                    {isLocked ? <Lock className="w-4 h-4" /> : <Unlock className="w-4 h-4" />}
                  </button>

                  {/* Assign dropdown */}
                  {isManagerOrAdmin ? (
                    <select value={assigneeId} onChange={(e) => assign(e.target.value)}
                            className="bg-card border border-default text-body py-1 px-2 rounded-xl text-xs focus:outline-none cursor-pointer">
                      <option value="">Unassigned</option>
                      {team.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  ) : (
                    <span className="text-xs text-muted px-2">Assigned to: {thread.conversation.assigned_user_name || 'None'}</span>
                  )}
                </div>
              </div>

              {/* Tags/Labels Area */}
              <div className="px-4 py-2 border-b border-default bg-card flex flex-wrap items-center gap-1.5">
                <Tag className="w-3.5 h-3.5 text-muted shrink-0" />
                <span className="text-[10px] font-bold text-muted uppercase tracking-wider mr-1">Tags:</span>
                {thread.conversation.labels.map(l => (
                  <span key={l.id} className="inline-flex items-center gap-1 text-[9px] font-bold px-2 py-0.5 rounded border uppercase tracking-wider" style={{ color: l.color, borderColor: `${l.color}25`, backgroundColor: `${l.color}08` }}>
                    {l.name}
                    <button onClick={() => removeTag(l.id)} className="hover:text-red-400 ml-0.5"><X className="w-2.5 h-2.5" /></button>
                  </span>
                ))}
                
                {/* Add Tag Dropdown */}
                <select value="" onChange={(e) => e.target.value && assignTag(e.target.value)}
                        className="bg-subtle border border-default text-[10px] text-body py-0.5 px-2 rounded-lg focus:outline-none cursor-pointer">
                  <option value="">+ Add Tag</option>
                  {allLabels.filter(al => !thread.conversation.labels.some(tl => tl.id === al.id)).map(al => (
                    <option key={al.id} value={al.id}>{al.name}</option>
                  ))}
                </select>
              </div>

              {/* SLA Banner */}
              {thread.conversation.sla_due_at && (
                <div className={`px-4 py-2 border-b text-xs flex items-center justify-between ${
                  thread.conversation.sla_status === 'breached'
                    ? 'bg-status-danger-bg border-status-danger-fg/20 text-status-danger-fg'
                    : 'bg-status-warning-bg border-status-warning-fg/10 text-status-warning-fg'
                }`}>
                  <span className="flex items-center gap-2 font-medium">
                    <Clock className="w-3.5 h-3.5" />
                    {thread.conversation.sla_status === 'breached'
                      ? 'SLA Response Time Breached! Action overdue.'
                      : `SLA Response Due in: ${timeAgo(thread.conversation.sla_due_at)}`}
                  </span>
                  <span className="text-[10px] font-bold opacity-60">Limit: {SLA_TIME_MINUTES} mins</span>
                </div>
              )}

              {/* Chat Message Logs */}
              <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-subtle">
                {loadingThread ? (
                  <div className="py-12 text-center text-muted"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
                ) : thread.messages.length === 0 ? (
                  <p className="text-center text-xs text-muted py-10">No messages in this chat thread.</p>
                ) : thread.messages.map((m: WaMessage) => (
                  <div key={m.id} className={`flex ${m.direction === 'OUTBOUND' ? 'justify-end' : 'justify-start'}`}>
                    <div className={`max-w-[70%] rounded-2xl px-4 py-2.5 text-sm border flex flex-col gap-1 transition ${
                      m.is_internal
                        ? 'bg-status-warning-bg border-status-warning-fg/30 text-status-warning-fg'
                        : m.direction === 'OUTBOUND'
                        ? 'bg-indigo-50 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800 text-strong shadow-xs'
                        : 'bg-card border-default text-strong shadow-xs'
                    }`}>
                      {m.is_internal && (
                        <div className="text-[9px] font-extrabold uppercase tracking-widest text-status-warning-fg flex items-center gap-1 mb-0.5"><Eye className="w-3 h-3" /> Internal team note</div>
                      )}
                      
                      {m.media_type && m.media_type !== 'text' && (
                        <div className="flex items-center gap-1.5 text-[10px] text-muted font-bold uppercase tracking-wider mb-1 border-b border-default pb-1">
                          <MediaIcon type={m.media_type} /> {m.media_type}
                          {m.attachments?.[0]?.media_url && (
                            <a href={m.attachments[0].media_url} target="_blank" rel="noreferrer" className="underline text-indigo-600 dark:text-indigo-400 font-extrabold lowercase ml-auto">Download</a>
                          )}
                        </div>
                      )}
                      {m.template_name && <div className="text-[10px] text-muted font-bold uppercase tracking-wider mb-0.5">Approved Broadcast Template · {m.template_name}</div>}
                      {m.body && <p className="whitespace-pre-wrap break-words leading-relaxed">{m.body}</p>}
                      
                      {/* AI Sentiment Analysis diagnostics */}
                      {(m.ai_sentiment || m.ai_intent) && (
                        <div className="flex flex-wrap gap-1 mt-1 pt-1.5 border-t border-default/50">
                          {m.ai_sentiment && <span className="text-[8px] font-bold px-1.5 py-0.2 bg-status-success-bg text-status-success-fg border border-status-success-fg/20 rounded uppercase tracking-wider">AI: {m.ai_sentiment}</span>}
                          {m.ai_intent && <span className="text-[8px] font-bold px-1.5 py-0.2 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 rounded uppercase tracking-wider">Intent: {m.ai_intent}</span>}
                        </div>
                      )}

                      <div className="flex items-center justify-end gap-1.5 mt-1 border-t border-default/30 pt-0.5">
                        <span className="text-[9px] text-muted">{new Date(m.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
                        {m.direction === 'OUTBOUND' && !m.is_internal && <StatusTick status={m.wa_status} />}
                      </div>
                    </div>
                  </div>
                ))}
              </div>

              {/* Lock Warning Banner */}
              {isLocked && !lockOwner && (
                <div className="px-4 py-2 bg-status-warning-bg border-t border-status-warning-fg/20 text-status-warning-fg text-xs flex items-center gap-2">
                  <Lock className="w-3.5 h-3.5" /> Thread locked by {thread.conversation.locked_by_user_name || 'another agent'}. You cannot send replies at this time.
                </div>
              )}

              {/* 24h customer window banner */}
              {!windowOpen && (
                <div className="px-4 py-2 bg-status-warning-bg border-t border-status-warning-fg/20 text-status-warning-fg text-xs flex items-center gap-2">
                  <AlertTriangle className="w-3.5 h-3.5" /> 24-hour response window closed — select and send a Template below to re-open.
                </div>
              )}

              {error && <div className="px-4 py-2 bg-status-danger-bg border-t border-status-danger-fg/20 text-status-danger-fg text-xs flex items-center justify-between"><span>{error}</span><button onClick={() => setError(null)}><X className="w-3.5 h-3.5" /></button></div>}

              {/* Canned Quick reply recommendations */}
              {windowOpen && (!isLocked || lockOwner) && quickReplies.length > 0 && (
                <div className="px-4 pt-2 flex flex-wrap gap-1.5 bg-card border-t border-default">
                  {quickReplies.map((q) => (
                    <button key={q.id} onClick={() => setBody(q.text)} title={q.text}
                            className="inline-flex items-center gap-1 px-2.5 py-1 text-[10px] font-bold rounded-lg bg-subtle text-body border border-default hover:text-indigo-600 hover:border-indigo-500/30 cursor-pointer transition">
                      <Zap className="w-3 h-3 text-indigo-500" /> {q.shortcut}
                    </button>
                  ))}
                </div>
              )}

              {/* Composer */}
              <form onSubmit={send} className="p-3 border-t border-default bg-card">
                {windowOpen ? (
                  <div className="space-y-2">
                    <div className="flex items-end gap-2">
                      <input type="file" ref={fileRef} onChange={onFile} className="hidden" />
                      <button type="button" onClick={() => fileRef.current?.click()} title="Attach media file" disabled={sending || (isLocked && !lockOwner)}
                              className="p-2.5 rounded-xl text-muted hover:text-strong border border-default bg-card hover:bg-hover cursor-pointer shrink-0 disabled:opacity-30"><Paperclip className="w-4 h-4" /></button>
                      <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={2} placeholder="Compose message..." disabled={sending || (isLocked && !lockOwner)}
                                className="flex-1 bg-subtle border border-default text-strong py-2 px-3 rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:ring-indigo-500/20 disabled:opacity-40 placeholder:text-muted" />
                      <button type="submit" disabled={sending || !body.trim() || (isLocked && !lockOwner)}
                              className="p-2.5 rounded-xl bg-indigo-600 hover:bg-indigo-700 text-white font-bold disabled:opacity-40 cursor-pointer shrink-0 transition shadow-xs">
                        {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
                      </button>
                    </div>
                    <div className="flex items-center gap-2 pl-12 text-xs">
                      <label className="flex items-center gap-1.5 text-muted cursor-pointer select-none">
                        <input type="checkbox" checked={isInternal} onChange={(e) => setIsInternal(e.target.checked)} className="w-3.5 h-3.5 rounded border-default bg-card text-amber-500 focus:ring-amber-500" disabled={isLocked && !lockOwner} />
                        Send as internal team note (yellow log; will not transmit to client)
                      </label>
                    </div>
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <select onChange={(e) => e.target.value && sendTemplate(e.target.value)} value=""
                            className="flex-1 bg-subtle border border-default text-strong py-2.5 px-3.5 rounded-xl text-sm focus:outline-none cursor-pointer" disabled={sending || (isLocked && !lockOwner)}>
                      <option value="">Send approved Meta broadcast template to contact...</option>
                      {templates.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.language})</option>)}
                    </select>
                    {sending && <Loader2 className="w-4 h-4 animate-spin text-muted" />}
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
