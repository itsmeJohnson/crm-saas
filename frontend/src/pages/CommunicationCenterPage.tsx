import React, { useEffect, useState, useCallback } from 'react';
import { communicationApi, CommItem, Conversation, CommStats, CommTemplate } from '../services/communicationApi';
import { TemplatesModal } from '../components/communications/TemplatesModal';
import {
  Phone, MessageSquare, Mail, StickyNote, Search, Pin, Loader2, Send, FileText, LayoutTemplate,
  ArrowDownLeft, ArrowUpRight, Inbox,
} from 'lucide-react';

const CHANNEL_ICON: Record<string, any> = { Call: Phone, SMS: MessageSquare, WhatsApp: MessageSquare, Email: Mail, Note: StickyNote };
const CHANNEL_COLOR: Record<string, string> = { Call: 'text-emerald-400', SMS: 'text-sky-400', WhatsApp: 'text-green-400', Email: 'text-brand-400', Note: 'text-slate-400' };
const CHANNELS = ['Call', 'SMS', 'WhatsApp', 'Email', 'Note'];

const relativeTime = (iso?: string | null): string => {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return '—';
  const diff = Date.now() - then;
  const min = 60000;
  const hour = 3600000;
  const day = 86400000;
  if (diff < min) return 'just now';
  if (diff < hour) return `${Math.floor(diff / min)}m ago`;
  if (diff < day && new Date(iso).getDate() === new Date().getDate()) {
    return new Date(iso).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }
  const days = Math.floor(diff / day);
  if (days <= 0) return 'Today';
  if (days === 1) return 'Yesterday';
  if (days < 30) return `${days}d ago`;
  return new Date(iso).toLocaleDateString([], { month: 'short', day: 'numeric' });
};

const getCallOutcomeBadge = (subject?: string) => {
  if (!subject) return null;
  const s = subject.toLowerCase();
  if (s.includes('pick') || s.includes('connect') || (s.includes('answer') && !s.includes('no answer') && !s.includes('not answer'))) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-status-success-bg text-status-success-fg border border-status-success-fg/20">
        Picked
      </span>
    );
  }
  if (s.includes('miss')) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-status-danger-bg text-status-danger-fg border border-status-danger-fg/20">
        Missed
      </span>
    );
  }
  if (s.includes('not answer') || s.includes('no answer') || s.includes('busy') || s.includes('fail')) {
    return (
      <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-semibold bg-status-warning-bg text-status-warning-fg border border-status-warning-fg/20">
        Not answered
      </span>
    );
  }
  return (
    <span className="inline-flex items-center px-1.5 py-0.5 rounded text-[10px] font-medium bg-subtle text-muted border border-default truncate max-w-[150px]">
      {subject}
    </span>
  );
};

const getContactDisplayName = (c: Conversation) => {
  if (c.name && !c.name.toLowerCase().startsWith('call:')) return c.name;
  return `Contact #${c.entity_id?.slice(0, 8) || 'Unknown'}`;
};

export const CommunicationCenterPage: React.FC = () => {
  const [convos, setConvos] = useState<Conversation[]>([]);
  const [stats, setStats] = useState<CommStats | null>(null);
  const [selected, setSelected] = useState<Conversation | null>(null);
  const [feed, setFeed] = useState<CommItem[]>([]);
  const [convoSearch, setConvoSearch] = useState('');
  const [feedSearch, setFeedSearch] = useState('');
  const [channelF, setChannelF] = useState('All');
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [pinnedOnly, setPinnedOnly] = useState(false);
  const [loadingConvos, setLoadingConvos] = useState(true);
  const [loadingFeed, setLoadingFeed] = useState(false);
  const [templatesOpen, setTemplatesOpen] = useState(false);

  // compose
  const [composeChannel, setComposeChannel] = useState('Email');
  const [composeDir, setComposeDir] = useState('OUTBOUND');
  const [composeSubject, setComposeSubject] = useState('');
  const [composeBody, setComposeBody] = useState('');
  const [templates, setTemplates] = useState<CommTemplate[]>([]);
  const [sending, setSending] = useState(false);

  const entityParams = (c: Conversation | null) => c ? { [`${c.entity_type}_id`]: c.entity_id } : {};

  const loadConvos = useCallback(async () => {
    setLoadingConvos(true);
    try { const [cv, st] = await Promise.all([communicationApi.conversations(convoSearch || undefined), communicationApi.stats().catch(() => null)]); setConvos(cv); setStats(st); }
    catch { /* */ } finally { setLoadingConvos(false); }
  }, [convoSearch]);

  const loadFeed = useCallback(async () => {
    if (!selected) { setFeed([]); return; }
    setLoadingFeed(true);
    try {
      setFeed(await communicationApi.feed({
        ...entityParams(selected),
        channel: channelF === 'All' ? undefined : channelF,
        search: feedSearch.trim() || undefined,
        unread_only: unreadOnly || undefined,
        pinned_only: pinnedOnly || undefined,
      }));
    } catch { /* */ } finally { setLoadingFeed(false); }
  }, [selected, channelF, feedSearch, unreadOnly, pinnedOnly]);

  useEffect(() => { loadConvos(); communicationApi.listTemplates().then(setTemplates).catch(() => {}); }, [loadConvos]);
  useEffect(() => { loadFeed(); }, [loadFeed]);

  const openConvo = async (c: Conversation) => {
    setSelected(c);
    if (c.unread_count > 0) { await communicationApi.markAllRead(entityParams(c)); loadConvos(); }
  };

  const applyTemplate = async (id: string) => {
    if (!id || !selected) return;
    const rendered = await communicationApi.renderTemplate(id, entityParams(selected));
    if (rendered.subject) setComposeSubject(rendered.subject);
    setComposeBody(rendered.body);
  };

  const doLog = async () => {
    if (!selected || !composeSubject.trim()) return;
    setSending(true);
    try {
      await communicationApi.log({ channel: composeChannel, direction: composeChannel === 'Note' ? 'OUTBOUND' : composeDir, subject: composeSubject, body: composeBody || undefined, ...entityParams(selected) });
      setComposeSubject(''); setComposeBody('');
      loadFeed(); loadConvos();
    } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } finally { setSending(false); }
  };

  const togglePin = async (it: CommItem) => { await communicationApi.togglePin(it.id); loadFeed(); loadConvos(); };

  return (
    <div className="space-y-4">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-default pb-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-strong">Communication Center</h1>
          <p className="text-sm text-muted mt-1">Every customer interaction — calls, SMS, WhatsApp, email &amp; notes — in one place.</p>
        </div>
        <div className="flex items-center gap-3">
          {stats && (
            <div className="flex items-center gap-3 text-xs text-muted">
              <span className="flex items-center gap-1"><Inbox className="w-3.5 h-3.5" /> {stats.unread} unread</span>
              <span>{stats.this_week} this week</span>
            </div>
          )}
          <button onClick={() => setTemplatesOpen(true)} className="flex items-center gap-2 px-4 py-2.5 bg-card border border-default hover:bg-hover rounded-xl text-sm font-semibold text-strong cursor-pointer shadow-xs">
            <LayoutTemplate className="w-4 h-4" /> Templates
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[340px_1fr] gap-4 h-[calc(100vh-220px)]">
        {/* Sidebar */}
        <div className="bg-card rounded-2xl border border-default flex flex-col overflow-hidden shadow-card">
          <div className="p-3 border-b border-default">
            <div className="relative">
              <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input value={convoSearch} onChange={(e) => setConvoSearch(e.target.value)} placeholder="Search conversations…" className="w-full pl-9 pr-3 py-2 bg-card border border-default rounded-lg text-xs text-strong focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500/20 placeholder:text-muted" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loadingConvos ? (
              <div className="py-10 text-center text-muted"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
            ) : convos.length === 0 ? (
              <div className="p-8 text-center">
                <Inbox className="w-8 h-8 text-muted mx-auto mb-2 opacity-50" />
                <p className="text-xs font-semibold text-strong">No conversations found</p>
                <p className="text-[11px] text-muted mt-0.5">Start communicating with contacts to populate feed.</p>
              </div>
            ) : convos.map((c) => {
              const Icon = CHANNEL_ICON[c.last_channel] || MessageSquare;
              const isSelected = selected?.entity_id === c.entity_id;
              return (
                <button
                  key={`${c.entity_type}-${c.entity_id}`}
                  onClick={() => openConvo(c)}
                  className={`w-full text-left px-3.5 py-3 border-b border-default cursor-pointer transition ${
                    isSelected ? 'bg-selected font-semibold' : 'bg-card hover:bg-hover'
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <div className="flex items-center gap-2 min-w-0">
                      {c.pinned && <Pin className="w-3 h-3 text-amber-500 shrink-0" />}
                      <Icon className={`w-3.5 h-3.5 shrink-0 ${CHANNEL_COLOR[c.last_channel] || 'text-muted'}`} />
                      <span className="text-sm font-semibold text-strong truncate">{getContactDisplayName(c)}</span>
                    </div>
                    <span className="text-[11px] text-muted shrink-0">{relativeTime(c.last_at)}</span>
                  </div>
                  <div className="flex items-center justify-between gap-2 mt-1.5 ml-5">
                    {getCallOutcomeBadge(c.last_subject)}
                    {c.unread_count > 0 && (
                      <span className="shrink-0 min-w-5 h-5 px-1.5 rounded-full bg-brand-500 text-[10px] font-black text-white flex items-center justify-center">
                        {c.unread_count}
                      </span>
                    )}
                  </div>
                </button>
              );
            })}
          </div>
        </div>

        {/* Thread */}
        <div className="bg-card rounded-2xl border border-default flex flex-col overflow-hidden shadow-card">
          {!selected ? (
            <div className="flex-1 flex flex-col items-center justify-center text-center p-8 bg-subtle">
              <div className="w-12 h-12 rounded-xl bg-card border border-default text-muted flex items-center justify-center mb-3 shadow-xs">
                <MessageSquare className="w-6 h-6" />
              </div>
              <p className="text-sm font-bold text-strong">Select a conversation to view details</p>
              <p className="text-xs text-muted mt-1 max-w-sm">Choose an active interaction from the conversation list on the left to read full transcript logs and reply.</p>
            </div>
          ) : (
            <>
              <div className="p-3 border-b border-default flex items-center gap-2 flex-wrap bg-subtle">
                <span className="text-sm font-semibold text-strong mr-auto">{selected.name}</span>
                <select value={channelF} onChange={(e) => setChannelF(e.target.value)} className="px-2 py-1.5 bg-card border border-default rounded-lg text-xs text-strong">
                  {['All', ...CHANNELS].map((c) => <option key={c} value={c}>{c === 'All' ? 'All channels' : c}</option>)}
                </select>
                <button onClick={() => setUnreadOnly(!unreadOnly)} className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer ${unreadOnly ? 'bg-brand-500/15 border-brand-500/30 text-brand-600 dark:text-brand-300' : 'bg-card border-default text-muted hover:bg-hover'}`}>Unread</button>
                <button onClick={() => setPinnedOnly(!pinnedOnly)} className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer ${pinnedOnly ? 'bg-amber-500/15 border-amber-500/30 text-amber-600 dark:text-amber-300' : 'bg-card border-default text-muted hover:bg-hover'}`}>Pinned</button>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-muted absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input value={feedSearch} onChange={(e) => setFeedSearch(e.target.value)} placeholder="Search…" className="w-36 pl-8 pr-2 py-1.5 bg-card border border-default rounded-lg text-xs text-strong focus:outline-none focus:border-brand-500" />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-2 bg-card">
                {loadingFeed ? <div className="py-10 text-center text-muted"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
                  : feed.length === 0 ? <p className="text-xs text-muted text-center py-8">No messages in this conversation.</p>
                  : feed.map((it) => {
                    const Icon = CHANNEL_ICON[it.channel] || MessageSquare;
                    const inbound = it.direction === 'INBOUND';
                    return (
                      <div key={it.id} className={`flex ${inbound ? 'justify-start' : it.internal ? 'justify-center' : 'justify-end'}`}>
                        <div className={`max-w-[75%] rounded-xl border px-3 py-2 ${it.internal ? 'bg-amber-500/10 border-amber-500/20 text-amber-900 dark:text-amber-200' : inbound ? 'bg-subtle border-default text-strong' : 'bg-indigo-50 dark:bg-brand-500/10 border-indigo-200 dark:border-brand-500/20 text-strong'} ${!it.is_read ? 'ring-1 ring-brand-500/40' : ''}`}>
                          <div className="flex items-center gap-1.5 mb-0.5">
                            <Icon className={`w-3 h-3 ${CHANNEL_COLOR[it.channel]}`} />
                            <span className="text-[10px] font-semibold text-muted">{it.internal ? 'Internal note' : it.channel}</span>
                            {!it.internal && (inbound ? <ArrowDownLeft className="w-3 h-3 text-muted" /> : <ArrowUpRight className="w-3 h-3 text-muted" />)}
                            <button onClick={() => togglePin(it)} className="ml-1 cursor-pointer"><Pin className={`w-3 h-3 ${it.is_pinned ? 'text-amber-500' : 'text-muted hover:text-strong'}`} /></button>
                          </div>
                          {!it.internal && <p className="text-xs font-semibold text-strong">{it.subject}</p>}
                          {it.body && <p className="text-xs text-body whitespace-pre-wrap mt-0.5">{it.body}</p>}
                          {it.recording_url && <a href={it.recording_url} target="_blank" rel="noreferrer" className="text-[11px] text-indigo-600 dark:text-brand-400 hover:underline mt-1 inline-block">▶ Recording</a>}
                          {it.attachments && it.attachments.length > 0 && (
                            <div className="mt-1 space-y-0.5">{it.attachments.map((a: any) => <a key={a.filename} href={a.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] text-indigo-600 dark:text-brand-400 hover:underline"><FileText className="w-3 h-3" />{a.filename}</a>)}</div>
                          )}
                          <p className="text-[10px] text-muted mt-1">{it.actor_name}{it.actor_name ? ' · ' : ''}{new Date(it.timestamp).toLocaleString()}</p>
                        </div>
                      </div>
                    );
                  })}
              </div>

              {/* Compose / quick actions */}
              <div className="p-3 border-t border-default space-y-2 bg-subtle">
                <div className="flex items-center gap-2 flex-wrap">
                  <select value={composeChannel} onChange={(e) => setComposeChannel(e.target.value)} className="px-2 py-1.5 bg-card border border-default rounded-lg text-xs text-strong">
                    {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  {composeChannel !== 'Note' && (
                    <select value={composeDir} onChange={(e) => setComposeDir(e.target.value)} className="px-2 py-1.5 bg-card border border-default rounded-lg text-xs text-strong">
                      <option value="OUTBOUND">Outbound</option>
                      <option value="INBOUND">Inbound</option>
                    </select>
                  )}
                  {templates.length > 0 && (
                    <select value="" onChange={(e) => applyTemplate(e.target.value)} className="px-2 py-1.5 bg-card border border-default rounded-lg text-xs text-strong">
                      <option value="">Template…</option>
                      {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  )}
                </div>
                {composeChannel !== 'Note' && <input value={composeSubject} onChange={(e) => setComposeSubject(e.target.value)} placeholder="Subject" className="w-full px-3 py-2 bg-card border border-default rounded-lg text-xs text-strong focus:outline-none focus:border-brand-500 placeholder:text-muted" />}
                <div className="flex gap-2">
                  <textarea value={composeBody} onChange={(e) => setComposeBody(e.target.value)} placeholder={composeChannel === 'Note' ? 'Internal note…' : 'Message body…'} rows={2} className="flex-1 px-3 py-2 bg-card border border-default rounded-lg text-xs text-strong focus:outline-none focus:border-brand-500 placeholder:text-muted" />
                  <button onClick={() => { if (composeChannel === 'Note') setComposeSubject('note'); doLog(); }} disabled={sending} className="px-4 bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white rounded-lg text-sm font-semibold cursor-pointer flex items-center gap-1.5 shadow-xs">
                    {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Log
                  </button>
                </div>
              </div>
            </>
          )}
        </div>
      </div>

      {templatesOpen && <TemplatesModal onClose={() => { setTemplatesOpen(false); communicationApi.listTemplates().then(setTemplates).catch(() => {}); }} />}
    </div>
  );
};
