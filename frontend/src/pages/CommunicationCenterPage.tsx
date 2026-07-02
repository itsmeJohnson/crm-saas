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
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-slate-800/60 pb-5">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent">Communication Center</h1>
          <p className="text-sm text-slate-400 mt-1">Every customer interaction — calls, SMS, WhatsApp, email &amp; notes — in one place.</p>
        </div>
        <div className="flex items-center gap-3">
          {stats && (
            <div className="flex items-center gap-3 text-xs text-slate-400">
              <span className="flex items-center gap-1"><Inbox className="w-3.5 h-3.5" /> {stats.unread} unread</span>
              <span>{stats.this_week} this week</span>
            </div>
          )}
          <button onClick={() => setTemplatesOpen(true)} className="flex items-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-sm font-semibold text-slate-300 cursor-pointer">
            <LayoutTemplate className="w-4 h-4" /> Templates
          </button>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-[320px_1fr] gap-4 h-[calc(100vh-220px)]">
        {/* Sidebar */}
        <div className="glass-panel rounded-2xl border border-slate-800/80 flex flex-col overflow-hidden">
          <div className="p-3 border-b border-slate-800/70">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input value={convoSearch} onChange={(e) => setConvoSearch(e.target.value)} placeholder="Search conversations…" className="w-full pl-9 pr-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50" />
            </div>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loadingConvos ? <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
              : convos.length === 0 ? <p className="p-4 text-xs text-slate-500">No conversations yet.</p>
              : convos.map((c) => {
                const Icon = CHANNEL_ICON[c.last_channel] || MessageSquare;
                return (
                  <button key={`${c.entity_type}-${c.entity_id}`} onClick={() => openConvo(c)} className={`w-full text-left px-3 py-3 border-b border-slate-800/50 hover:bg-slate-900/40 cursor-pointer ${selected?.entity_id === c.entity_id ? 'bg-slate-900/60' : ''}`}>
                    <div className="flex items-center gap-2">
                      {c.pinned && <Pin className="w-3 h-3 text-amber-400 shrink-0" />}
                      <Icon className={`w-3.5 h-3.5 shrink-0 ${CHANNEL_COLOR[c.last_channel] || 'text-slate-400'}`} />
                      <span className="text-sm font-medium text-slate-200 truncate flex-1">{c.name}</span>
                      {c.unread_count > 0 && <span className="shrink-0 min-w-5 h-5 px-1.5 rounded-full bg-brand-500 text-[10px] font-black text-white flex items-center justify-center">{c.unread_count}</span>}
                    </div>
                    <p className="text-[11px] text-slate-500 truncate mt-0.5 ml-5">{c.last_subject}</p>
                  </button>
                );
              })}
          </div>
        </div>

        {/* Thread */}
        <div className="glass-panel rounded-2xl border border-slate-800/80 flex flex-col overflow-hidden">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">Select a conversation.</div>
          ) : (
            <>
              <div className="p-3 border-b border-slate-800/70 flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-200 mr-auto">{selected.name}</span>
                <select value={channelF} onChange={(e) => setChannelF(e.target.value)} className="px-2 py-1.5 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200">
                  {['All', ...CHANNELS].map((c) => <option key={c} value={c}>{c === 'All' ? 'All channels' : c}</option>)}
                </select>
                <button onClick={() => setUnreadOnly(!unreadOnly)} className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer ${unreadOnly ? 'bg-brand-500/15 border-brand-500/30 text-brand-300' : 'bg-slate-950/40 border-slate-800 text-slate-400'}`}>Unread</button>
                <button onClick={() => setPinnedOnly(!pinnedOnly)} className={`px-2.5 py-1.5 rounded-lg text-xs font-semibold border cursor-pointer ${pinnedOnly ? 'bg-amber-500/15 border-amber-500/30 text-amber-300' : 'bg-slate-950/40 border-slate-800 text-slate-400'}`}>Pinned</button>
                <div className="relative">
                  <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2 pointer-events-none" />
                  <input value={feedSearch} onChange={(e) => setFeedSearch(e.target.value)} placeholder="Search…" className="w-36 pl-8 pr-2 py-1.5 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50" />
                </div>
              </div>

              <div className="flex-1 overflow-y-auto p-4 space-y-2">
                {loadingFeed ? <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
                  : feed.length === 0 ? <p className="text-xs text-slate-500 text-center py-8">No messages.</p>
                  : feed.map((it) => {
                    const Icon = CHANNEL_ICON[it.channel] || MessageSquare;
                    const inbound = it.direction === 'INBOUND';
                    return (
                      <div key={it.id} className={`flex ${inbound ? 'justify-start' : it.internal ? 'justify-center' : 'justify-end'}`}>
                        <div className={`max-w-[75%] rounded-xl border px-3 py-2 ${it.internal ? 'bg-amber-500/5 border-amber-500/20' : inbound ? 'bg-slate-950/50 border-slate-800' : 'bg-brand-500/10 border-brand-500/20'} ${!it.is_read ? 'ring-1 ring-brand-500/40' : ''}`}>
                          <div className="flex items-center gap-1.5 mb-0.5">
                            <Icon className={`w-3 h-3 ${CHANNEL_COLOR[it.channel]}`} />
                            <span className="text-[10px] font-semibold text-slate-400">{it.internal ? 'Internal note' : it.channel}</span>
                            {!it.internal && (inbound ? <ArrowDownLeft className="w-3 h-3 text-slate-500" /> : <ArrowUpRight className="w-3 h-3 text-slate-500" />)}
                            <button onClick={() => togglePin(it)} className="ml-1 cursor-pointer"><Pin className={`w-3 h-3 ${it.is_pinned ? 'text-amber-400' : 'text-slate-600 hover:text-slate-400'}`} /></button>
                          </div>
                          {!it.internal && <p className="text-xs font-medium text-slate-200">{it.subject}</p>}
                          {it.body && <p className="text-xs text-slate-300 whitespace-pre-wrap mt-0.5">{it.body}</p>}
                          {it.recording_url && <a href={it.recording_url} target="_blank" rel="noreferrer" className="text-[11px] text-brand-400 hover:text-brand-300 mt-1 inline-block">▶ Recording</a>}
                          {it.attachments && it.attachments.length > 0 && (
                            <div className="mt-1 space-y-0.5">{it.attachments.map((a: any) => <a key={a.filename} href={a.url} target="_blank" rel="noreferrer" className="flex items-center gap-1 text-[11px] text-brand-400 hover:text-brand-300"><FileText className="w-3 h-3" />{a.filename}</a>)}</div>
                          )}
                          <p className="text-[10px] text-slate-500 mt-1">{it.actor_name}{it.actor_name ? ' · ' : ''}{new Date(it.timestamp).toLocaleString()}</p>
                        </div>
                      </div>
                    );
                  })}
              </div>

              {/* Compose / quick actions */}
              <div className="p-3 border-t border-slate-800/70 space-y-2">
                <div className="flex items-center gap-2 flex-wrap">
                  <select value={composeChannel} onChange={(e) => setComposeChannel(e.target.value)} className="px-2 py-1.5 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200">
                    {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
                  </select>
                  {composeChannel !== 'Note' && (
                    <select value={composeDir} onChange={(e) => setComposeDir(e.target.value)} className="px-2 py-1.5 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200">
                      <option value="OUTBOUND">Outbound</option>
                      <option value="INBOUND">Inbound</option>
                    </select>
                  )}
                  {templates.length > 0 && (
                    <select value="" onChange={(e) => applyTemplate(e.target.value)} className="px-2 py-1.5 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200">
                      <option value="">Template…</option>
                      {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
                    </select>
                  )}
                </div>
                {composeChannel !== 'Note' && <input value={composeSubject} onChange={(e) => setComposeSubject(e.target.value)} placeholder="Subject" className="w-full px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50" />}
                <div className="flex gap-2">
                  <textarea value={composeBody} onChange={(e) => setComposeBody(e.target.value)} placeholder={composeChannel === 'Note' ? 'Internal note…' : 'Message body…'} rows={2} className="flex-1 px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50" />
                  <button onClick={() => { if (composeChannel === 'Note') setComposeSubject('note'); doLog(); }} disabled={sending} className="px-4 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-lg text-sm font-semibold cursor-pointer flex items-center gap-1.5">
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
