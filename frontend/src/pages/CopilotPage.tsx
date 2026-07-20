import React, { useCallback, useEffect, useRef, useState } from 'react';
import { useLocation } from 'react-router-dom';
import {
  Sparkles, Loader2, Send, Plus, Mic, MicOff, Volume2, VolumeX, Check, X,
  Search, HelpCircle, FileText, Users, Calendar, ListChecks, Mail, Lightbulb,
} from 'lucide-react';
import {
  copilotApi as api, CopilotCapabilities, CopilotConversation, PendingAction,
} from '../services/copilotApi';
import { extractErrorMessage } from '../utils/errors';

const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';

interface ChatItem {
  role: 'user' | 'assistant';
  text: string;
  intent?: string;
  data?: any;
  pending?: PendingAction | null;
  done?: boolean;
}

// Web Speech API (voice-ready) — optional, guarded for unsupported browsers.
const SpeechRec: any = (typeof window !== 'undefined') &&
  ((window as any).SpeechRecognition || (window as any).webkitSpeechRecognition);

export const CopilotPage: React.FC = () => {
  const [caps, setCaps] = useState<CopilotCapabilities | null>(null);
  const [conversations, setConversations] = useState<CopilotConversation[]>([]);
  const [convoId, setConvoId] = useState<string | null>(null);
  const [items, setItems] = useState<ChatItem[]>([]);
  const [input, setInput] = useState('');
  const [busy, setBusy] = useState(false);
  const [err, setErr] = useState('');
  const [listening, setListening] = useState(false);
  const [speak, setSpeak] = useState(false);
  const recRef = useRef<any>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const seededRef = useRef(false);
  const location = useLocation();

  const loadConvos = useCallback(async () => {
    try { setConversations(await api.conversations()); } catch { /* ignore */ }
  }, []);
  useEffect(() => { api.capabilities().then(setCaps).catch(() => {}); loadConvos(); }, [loadConvos]);
  // auto-send a question passed from the Home launcher widget
  useEffect(() => {
    const seed = (location.state as any)?.seed;
    if (seed && !seededRef.current) { seededRef.current = true; ask(seed); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.state]);
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: 'smooth' }); }, [items, busy]);

  const say = (text: string) => {
    if (!speak || typeof window === 'undefined' || !window.speechSynthesis) return;
    window.speechSynthesis.cancel();
    window.speechSynthesis.speak(new SpeechSynthesisUtterance(text));
  };

  const ask = async (text: string) => {
    const q = text.trim();
    if (!q || busy) return;
    setInput(''); setErr(''); setBusy(true);
    setItems((prev) => [...prev, { role: 'user', text: q }]);
    try {
      const r = await api.ask(q, convoId);
      if (!convoId && r.conversation_id) setConvoId(r.conversation_id);
      setItems((prev) => [...prev, { role: 'assistant', text: r.reply, intent: r.intent, data: r.data, pending: r.pending_action }]);
      say(r.speech);
      await loadConvos();
    } catch (e) { setErr(extractErrorMessage(e, 'Copilot request failed')); } finally { setBusy(false); }
  };

  const confirm = async (idx: number, action: PendingAction) => {
    setBusy(true);
    try {
      const r = await api.execute(action);
      setItems((prev) => prev.map((it, i) => i === idx ? { ...it, pending: null, done: true } : it));
      setItems((prev) => [...prev, { role: 'assistant', text: r.reply }]);
      say(r.speech);
    } catch (e) { setErr(extractErrorMessage(e, 'Action failed')); } finally { setBusy(false); }
  };

  const openConvo = async (id: string) => {
    setConvoId(id);
    try {
      const msgs = await api.messages(id);
      setItems(msgs.map((m) => ({ role: m.role as any, text: m.content })));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load conversation')); }
  };

  const toggleMic = () => {
    if (!SpeechRec) { setErr('Voice input is not supported in this browser.'); return; }
    if (listening) { recRef.current?.stop(); return; }
    const rec = new SpeechRec();
    rec.lang = 'en-US'; rec.interimResults = false; rec.maxAlternatives = 1;
    rec.onresult = (e: any) => { const t = e.results[0][0].transcript; setInput(t); ask(t); };
    rec.onend = () => setListening(false);
    rec.onerror = () => setListening(false);
    recRef.current = rec; setListening(true); rec.start();
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><Sparkles className="w-6 h-6 text-brand-400" /> CRM Copilot</h1>
          <p className="text-sm text-slate-500 mt-1">Ask questions, search, summarize, draft messages and take actions — in plain language, through the AI Platform.</p>
        </div>
        <div className="flex items-center gap-2">
          <button onClick={() => setSpeak(!speak)} title={speak ? 'Mute replies' : 'Speak replies'} className={`p-2 rounded-lg cursor-pointer ${speak ? 'bg-brand-500/20 text-brand-300' : 'bg-slate-800/70 text-slate-400'}`}>{speak ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}</button>
          <button onClick={() => { setConvoId(null); setItems([]); }} className={BTN}><Plus className="w-3.5 h-3.5" /> New chat</button>
        </div>
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        <div className={`${card} h-fit`}>
          <p className="text-[11px] font-semibold text-slate-400 uppercase mb-2">Conversations</p>
          {conversations.map((c) => (
            <button key={c.id} onClick={() => openConvo(c.id)} className={`w-full text-left px-2 py-1.5 rounded-lg text-xs truncate cursor-pointer ${convoId === c.id ? 'bg-brand-500/15 text-brand-300' : 'text-slate-400 hover:bg-slate-800/60'}`}>
              {c.title} <span className="text-[9px] text-slate-600">({c.message_count})</span>
            </button>
          ))}
          {conversations.length === 0 && <p className="text-[11px] text-slate-600 px-1">No conversations yet.</p>}
        </div>

        <div className={`${card} lg:col-span-3 flex flex-col`} style={{ minHeight: 520 }}>
          <div className="flex-1 overflow-y-auto space-y-3 pr-1" style={{ maxHeight: 520 }}>
            {items.length === 0 && caps && (
              <div className="py-6">
                <p className="text-sm text-slate-400 mb-3 text-center">Try one of these:</p>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  {caps.capabilities.map((cap) => {
                    const Icon = ICONS[cap.intent] || HelpCircle;
                    return (
                      <button key={cap.intent} onClick={() => ask(cap.examples[0])} className="text-left bg-slate-950/40 border border-slate-800/60 rounded-lg p-2.5 hover:border-brand-500/40 cursor-pointer">
                        <p className="text-xs font-semibold text-slate-200 flex items-center gap-1.5"><Icon className="w-3.5 h-3.5 text-brand-400" /> {cap.label}</p>
                        <p className="text-[11px] text-slate-500 mt-0.5 italic">"{cap.examples[0]}"</p>
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            {items.map((it, i) => (
              <div key={i} className={`flex ${it.role === 'user' ? 'justify-end' : 'justify-start'}`}>
                <div className={`max-w-[85%] rounded-2xl px-3 py-2 text-sm ${it.role === 'user' ? 'bg-brand-500/20 text-brand-100' : 'bg-slate-800/70 text-slate-200'}`}>
                  <p className="whitespace-pre-wrap">{it.text}</p>
                  {it.role === 'assistant' && <IntentData intent={it.intent} data={it.data} />}
                  {it.pending && !it.done && (
                    <div className="flex items-center gap-2 mt-2">
                      <button onClick={() => confirm(i, it.pending!)} disabled={busy} className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-emerald-500/20 text-emerald-300 hover:bg-emerald-500/30 cursor-pointer flex items-center gap-1"><Check className="w-3 h-3" /> Confirm</button>
                      <button onClick={() => setItems((prev) => prev.map((x, j) => j === i ? { ...x, pending: null } : x))} className="px-2.5 py-1 rounded-lg text-[11px] font-semibold bg-slate-700/50 text-slate-300 hover:bg-slate-700 cursor-pointer flex items-center gap-1"><X className="w-3 h-3" /> Cancel</button>
                    </div>
                  )}
                  {it.done && <p className="text-[10px] text-emerald-400 mt-1 flex items-center gap-1"><Check className="w-3 h-3" /> Done</p>}
                </div>
              </div>
            ))}
            {busy && <div className="flex justify-start"><div className="bg-slate-800/70 rounded-2xl px-3 py-2"><Loader2 className="w-4 h-4 animate-spin text-slate-400" /></div></div>}
            <div ref={endRef} />
          </div>
          <div className="flex items-center gap-2 pt-3 border-t border-slate-800/60 mt-3">
            <button onClick={toggleMic} title="Voice input" className={`p-2 rounded-lg cursor-pointer shrink-0 ${listening ? 'bg-red-500/20 text-red-300 animate-pulse' : 'bg-slate-800/70 text-slate-400 hover:text-brand-300'}`}>{listening ? <MicOff className="w-4 h-4" /> : <Mic className="w-4 h-4" />}</button>
            <input value={input} onChange={(e) => setInput(e.target.value)} onKeyDown={(e) => e.key === 'Enter' && ask(input)}
                   placeholder="Ask the CRM anything…" className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
            <button onClick={() => ask(input)} disabled={busy} className={`${BTN} shrink-0`}><Send className="w-3.5 h-3.5" /> Send</button>
          </div>
        </div>
      </div>
    </div>
  );
};

const ICONS: Record<string, any> = {
  search: Search, question: HelpCircle, report: FileText, summarize: Users,
  opportunities: Lightbulb, draft: Mail, create_task: ListChecks, schedule_meeting: Calendar,
};

const IntentData: React.FC<{ intent?: string; data: any }> = ({ intent, data }) => {
  if (!data) return null;
  if (intent === 'search' && data.results?.length > 0) {
    return (
      <div className="mt-2 space-y-1">
        {data.results.slice(0, 8).map((r: any) => (
          <div key={r.id} className="text-[11px] bg-slate-950/40 rounded px-2 py-1 flex items-center justify-between gap-2">
            <span className="text-slate-200 truncate">{r.name}</span>
            <span className="text-slate-500 shrink-0">{r.status || r.industry || r.company_type || ''}{r.value ? ` · ₹${Math.round(r.value).toLocaleString()}` : ''}{r.city ? ` · ${r.city}` : ''}</span>
          </div>
        ))}
      </div>
    );
  }
  if (intent === 'opportunities' && data.hot_leads?.length > 0) {
    return (
      <div className="mt-2 space-y-1">
        {data.hot_leads.slice(0, 5).map((l: any) => (
          <div key={l.lead_id} className="text-[11px] bg-slate-950/40 rounded px-2 py-1 flex items-center justify-between gap-2">
            <span className="text-slate-200 truncate">{l.name}</span>
            <span className="text-emerald-400 shrink-0">{l.conversion_probability}% · ₹{Math.round(l.value || 0).toLocaleString()}</span>
          </div>
        ))}
      </div>
    );
  }
  if (intent === 'report' && data.rows?.length > 0) {
    const keys = (data.columns || []).map((c: any) => c.key);
    return (
      <div className="mt-2 overflow-x-auto">
        <table className="text-[11px]">
          <thead><tr className="text-slate-500">{keys.map((k: string) => <th key={k} className="text-left pr-3 pb-1">{k}</th>)}</tr></thead>
          <tbody>{data.rows.slice(0, 8).map((r: any, i: number) => (
            <tr key={i}>{keys.map((k: string) => <td key={k} className="pr-3 text-slate-300">{String(r[k] ?? '')}</td>)}</tr>
          ))}</tbody>
        </table>
      </div>
    );
  }
  return null;
};
