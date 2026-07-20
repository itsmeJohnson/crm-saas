import React, { useCallback, useEffect, useState } from 'react';
import {
  MessagesSquare, Loader2, Download, LayoutDashboard, Wand2, FileText, Languages,
  Smile, Frown, Meh, ListChecks, Play,
} from 'lucide-react';
import {
  commIntelligenceApi as api, CommIntelDashboard, TextAnalysis,
} from '../services/commIntelligenceApi';
import { extractErrorMessage } from '../utils/errors';

const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';
const SENT_ICON: Record<string, any> = { positive: Smile, neutral: Meh, negative: Frown };
const SENT_TONE: Record<string, string> = { positive: 'text-emerald-400', neutral: 'text-slate-400', negative: 'text-red-400' };

const downloadText = (name: string, text: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(new Blob([text], { type: 'text/csv' }));
  a.download = name; a.click(); URL.revokeObjectURL(a.href);
};

export const CommIntelligencePage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'analyze' | 'meeting'>('dashboard');
  const [dash, setDash] = useState<CommIntelDashboard | null>(null);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try { if (tab === 'dashboard') setDash(await api.dashboard()); }
    catch (e) { setErr(extractErrorMessage(e, 'Failed to load communication intelligence.')); } finally { setLoading(false); }
  }, [tab]);
  useEffect(() => { load(); }, [load]);

  return (
    <div className="space-y-5">
      <div className="flex items-center justify-between gap-3 flex-wrap">
        <div>
          <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><MessagesSquare className="w-6 h-6 text-brand-400" /> Communication Intelligence</h1>
          <p className="text-sm text-slate-500 mt-1">Sentiment, intent, action items, language & AI summaries across calls, email, WhatsApp and SMS.</p>
        </div>
        {tab === 'dashboard' && <button onClick={async () => { try { downloadText('comm-intelligence.csv', await api.exportCsv()); } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } }} className={BTN}><Download className="w-3.5 h-3.5" /> Export CSV</button>}
      </div>

      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['analyze', 'Analyze / Transcript', Wand2], ['meeting', 'Meeting Summary', FileText]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {tab === 'dashboard' ? (
        loading ? <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div> :
        dash ? (
          <div className="space-y-4">
            <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Comms (30d)</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.total}</p></div>
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Smile className="w-3 h-3 text-emerald-400" /> Positive</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.sentiment.positive}</p></div>
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><Frown className="w-3 h-3 text-red-400" /> Negative</p><p className="text-xl font-bold text-red-400 mt-1">{dash.sentiment.negative}</p></div>
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Positive rate</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.positive_rate}%</p></div>
              <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase flex items-center gap-1"><ListChecks className="w-3 h-3" /> Action items</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.action_items}</p></div>
            </div>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
              <div className={card}>
                <p className="text-xs font-semibold text-slate-400 uppercase mb-2">Top intents</p>
                {dash.by_intent.slice(0, 6).map((i) => <div key={i.intent} className="flex items-center justify-between py-1 text-sm"><span className="text-slate-300 capitalize">{i.intent}</span><span className="text-slate-100 font-semibold">{i.count}</span></div>)}
                {dash.by_intent.length === 0 && <p className="text-xs text-slate-500">No data.</p>}
              </div>
              <div className={card}>
                <p className="text-xs font-semibold text-slate-400 uppercase mb-2">By channel</p>
                {Object.entries(dash.by_channel).map(([c, n]) => <div key={c} className="flex items-center justify-between py-1 text-sm"><span className="text-slate-300">{c}</span><span className="text-slate-100 font-semibold">{n}</span></div>)}
              </div>
              <div className={card}>
                <p className="text-xs font-semibold text-slate-400 uppercase mb-2 flex items-center gap-1.5"><Languages className="w-3.5 h-3.5" /> Languages</p>
                {dash.languages.map((l) => <div key={l.code} className="flex items-center justify-between py-1 text-sm"><span className="text-slate-300 uppercase">{l.code}</span><span className="text-slate-100 font-semibold">{l.count}</span></div>)}
              </div>
            </div>
          </div>
        ) : null
      ) : tab === 'analyze' ? (
        <AnalyzeTab setErr={setErr} />
      ) : (
        <MeetingTab setErr={setErr} />
      )}
    </div>
  );
};

const ResultCard: React.FC<{ r: TextAnalysis }> = ({ r }) => {
  const SIcon = SENT_ICON[r.sentiment.label] || Meh;
  return (
    <div className={`${card} space-y-3`}>
      <div className="flex items-center gap-4 flex-wrap">
        <span className={`flex items-center gap-1.5 text-sm font-semibold ${SENT_TONE[r.sentiment.label]}`}><SIcon className="w-4 h-4" /> {r.sentiment.label} ({r.sentiment.score})</span>
        <span className="text-xs text-slate-400 flex items-center gap-1"><Languages className="w-3.5 h-3.5" /> {r.language.name} ({r.language.code})</span>
        {r.translation_ready && <span className="text-[10px] px-1.5 py-0.5 rounded bg-amber-500/10 text-amber-300">translation-ready</span>}
      </div>
      {r.intents.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {r.intents.map((i) => <span key={i} className="text-[10px] px-2 py-0.5 rounded-full bg-brand-500/10 text-brand-300 capitalize">{i}</span>)}
        </div>
      )}
      {r.action_items.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase mb-1 flex items-center gap-1.5"><ListChecks className="w-3.5 h-3.5" /> Action items</p>
          {r.action_items.map((a, i) => <p key={i} className="text-xs text-slate-300 py-0.5">• {a}</p>)}
        </div>
      )}
      {r.follow_up_suggestions.length > 0 && (
        <div>
          <p className="text-[11px] font-semibold text-slate-400 uppercase mb-1">Follow-up suggestions</p>
          {r.follow_up_suggestions.map((s, i) => <p key={i} className="text-xs text-slate-400 py-0.5">→ {s}</p>)}
        </div>
      )}
    </div>
  );
};

const AnalyzeTab: React.FC<{ setErr: (s: string) => void }> = ({ setErr }) => {
  const [text, setText] = useState('');
  const [asTranscript, setAsTranscript] = useState(false);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<TextAnalysis | null>(null);
  const run = async () => {
    if (!text.trim()) return;
    setBusy(true); setErr('');
    try { setResult(asTranscript ? await api.transcript(text) : await api.analyze(text)); }
    catch (e) { setErr(extractErrorMessage(e, 'Analysis failed')); } finally { setBusy(false); }
  };
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className={`${card} space-y-2`}>
        <p className="text-xs font-semibold text-slate-400 uppercase">Paste a message or call transcript</p>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={10} placeholder="Paste an email, WhatsApp/SMS thread, or a call transcript…" className={F} />
        <div className="flex items-center justify-between">
          <label className="flex items-center gap-1.5 text-xs text-slate-300"><input type="checkbox" checked={asTranscript} onChange={(e) => setAsTranscript(e.target.checked)} /> Treat as call transcript</label>
          <button onClick={run} disabled={busy} className={BTN}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />} Analyze</button>
        </div>
      </div>
      {result ? <ResultCard r={result} /> : <div className={`${card} flex items-center justify-center text-sm text-slate-500`}>Analysis appears here.</div>}
    </div>
  );
};

const MeetingTab: React.FC<{ setErr: (s: string) => void }> = ({ setErr }) => {
  const [notes, setNotes] = useState('');
  const [busy, setBusy] = useState(false);
  const [res, setRes] = useState<any>(null);
  const run = async () => {
    if (!notes.trim()) return;
    setBusy(true); setErr('');
    try { setRes(await api.meetingSummary(notes)); }
    catch (e) { setErr(extractErrorMessage(e, 'Summary failed')); } finally { setBusy(false); }
  };
  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className={`${card} space-y-2`}>
        <p className="text-xs font-semibold text-slate-400 uppercase">Meeting notes / transcript</p>
        <textarea value={notes} onChange={(e) => setNotes(e.target.value)} rows={10} placeholder="Paste meeting notes or a transcript…" className={F} />
        <button onClick={run} disabled={busy} className={BTN}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />} Summarize meeting</button>
      </div>
      {res ? (
        <div className={`${card} space-y-3`}>
          <div><p className="text-[11px] font-semibold text-slate-400 uppercase mb-1">Summary</p><p className="text-sm text-slate-200 whitespace-pre-wrap">{res.summary}</p></div>
          {res.action_items?.length > 0 && (
            <div><p className="text-[11px] font-semibold text-slate-400 uppercase mb-1 flex items-center gap-1.5"><ListChecks className="w-3.5 h-3.5" /> Action items</p>
              {res.action_items.map((a: string, i: number) => <p key={i} className="text-xs text-slate-300 py-0.5">• {a}</p>)}</div>
          )}
        </div>
      ) : <div className={`${card} flex items-center justify-center text-sm text-slate-500`}>Meeting summary appears here.</div>}
    </div>
  );
};
