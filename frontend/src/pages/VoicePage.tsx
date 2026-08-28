import React, { useCallback, useEffect, useState } from 'react';
import {
  Megaphone, Send, Loader2, RefreshCw, Inbox, Upload, Mic, Radio, ChevronDown, ChevronRight,
  PhoneMissed,
} from 'lucide-react';
import { voiceApi, VoiceBroadcast, VoiceBroadcastDetail, VoiceMedia } from '../services/voiceApi';
import { extractErrorMessage } from '../utils/errors';

const VOICE_TYPES = [
  { value: '33', label: 'Transactional (30s)' },
  { value: '34', label: 'Promotional (30s)' },
  { value: '37', label: 'IVR (1 sec)' },
  { value: '35', label: 'TTS' },
];

const parseNumbers = (raw: string): string[] =>
  raw.split(/[\s,;]+/).map((s) => s.trim()).filter(Boolean);

/* ── Compose ── */
const VoiceCompose: React.FC<{ onSent: () => void }> = ({ onSent }) => {
  const [mode, setMode] = useState<'voice_note' | 'tts'>('tts');
  const [name, setName] = useState('');
  const [numbersRaw, setNumbersRaw] = useState('');
  const [voiceType, setVoiceType] = useState('33');
  const [mediaId, setMediaId] = useState('');
  const [media, setMedia] = useState<VoiceMedia[]>([]);
  const [content, setContent] = useState('');
  const [language, setLanguage] = useState('English');
  const [gender, setGender] = useState('Male');
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  useEffect(() => {
    if (mode === 'voice_note') {
      voiceApi.listMedia().then((r) => setMedia(r.success ? r.items : [])).catch(() => {});
    }
  }, [mode]);

  const send = async () => {
    const numbers = parseNumbers(numbersRaw);
    if (numbers.length === 0) { setMsg('Add at least one recipient number.'); return; }
    setBusy(true); setMsg(null);
    try {
      const payload = mode === 'tts'
        ? { mode, name: name || undefined, numbers, tts_content: content, tts_language: language, tts_gender: gender }
        : { mode, name: name || undefined, numbers, voice_type: voiceType, voice_medias_id: mediaId };
      const bc = await voiceApi.send(payload);
      setMsg(`Broadcast ${bc.status} to ${bc.total_recipients} number(s).`);
      setNumbersRaw(''); setContent('');
      onSent();
    } catch (err: any) {
      setMsg(extractErrorMessage(err, 'Failed to send broadcast'));
    } finally { setBusy(false); }
  };

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4 max-w-2xl">
      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}

      <div className="flex items-center gap-2">
        <button onClick={() => setMode('tts')}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border cursor-pointer ${mode === 'tts' ? 'bg-brand-500/20 border-brand-500/50 text-brand-300' : 'border-slate-700/60 text-slate-400'}`}>
          <Mic className="w-4 h-4" /> Text-to-Speech
        </button>
        <button onClick={() => setMode('voice_note')}
                className={`inline-flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm border cursor-pointer ${mode === 'voice_note' ? 'bg-brand-500/20 border-brand-500/50 text-brand-300' : 'border-slate-700/60 text-slate-400'}`}>
          <Radio className="w-4 h-4" /> Voice Note (OBD)
        </button>
      </div>

      <label className="space-y-1 block">
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Campaign name (optional)</span>
        <input value={name} onChange={(e) => setName(e.target.value)} placeholder="e.g. Diwali offer"
               className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
      </label>

      <label className="space-y-1 block">
        <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Recipients</span>
        <textarea value={numbersRaw} onChange={(e) => setNumbersRaw(e.target.value)} rows={3}
                  placeholder="Numbers separated by comma, space or newline"
                  className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        <span className="text-[11px] text-slate-500">{parseNumbers(numbersRaw).length} recipient(s)</span>
      </label>

      {mode === 'tts' ? (
        <>
          <label className="space-y-1 block">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Message (spoken)</span>
            <textarea value={content} onChange={(e) => setContent(e.target.value)} rows={3}
                      placeholder="Text the system will read aloud"
                      className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </label>
          <div className="grid grid-cols-2 gap-4">
            <label className="space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Language</span>
              <select value={language} onChange={(e) => setLanguage(e.target.value)}
                      className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
                <option>English</option><option>Hindi</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Voice</span>
              <select value={gender} onChange={(e) => setGender(e.target.value)}
                      className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
                <option>Male</option><option>Female</option>
              </select>
            </label>
          </div>
        </>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Voice type</span>
            <select value={voiceType} onChange={(e) => setVoiceType(e.target.value)}
                    className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
              {VOICE_TYPES.map((v) => <option key={v.value} value={v.value}>{v.label}</option>)}
            </select>
          </label>
          <label className="space-y-1">
            <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">Voice media</span>
            <select value={mediaId} onChange={(e) => setMediaId(e.target.value)}
                    className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm">
              <option value="">Select…</option>
              {media.map((m, i) => (
                <option key={i} value={m.id ?? m.voice_medias_id ?? m.announcement_id}>
                  {m.title || m.id || `Media ${i + 1}`}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}

      <button onClick={send} disabled={busy}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Send broadcast
      </button>
    </div>
  );
};

/* ── History with per-recipient DLR ── */
const StatusPill: React.FC<{ status: string }> = ({ status }) => {
  const color = status === 'answered' ? 'text-emerald-400'
    : status === 'failed' || status === 'busy' || status === 'no_answer' ? 'text-red-400'
    : status === 'sent' || status === 'scheduled' ? 'text-brand-400' : 'text-amber-400';
  return <span className={`text-xs font-semibold ${color}`}>{status}</span>;
};

const VoiceHistory: React.FC<{ refreshKey: number }> = ({ refreshKey }) => {
  const [items, setItems] = useState<VoiceBroadcast[]>([]);
  const [loading, setLoading] = useState(true);
  const [openId, setOpenId] = useState<string | null>(null);
  const [detail, setDetail] = useState<VoiceBroadcastDetail | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setItems((await voiceApi.list({ limit: 100 })).items); } catch { /* noop */ }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load, refreshKey]);

  const open = async (id: string) => {
    if (openId === id) { setOpenId(null); setDetail(null); return; }
    setOpenId(id); setDetail(null);
    try { setDetail(await voiceApi.get(id)); } catch { /* noop */ }
  };

  const refreshDlr = async (id: string) => {
    setRefreshing(true);
    try { setDetail(await voiceApi.refresh(id)); } catch { /* noop */ }
    finally { setRefreshing(false); }
  };

  if (loading) return <div className="py-12 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>;
  if (items.length === 0) return <div className="py-12 text-center text-slate-500 text-sm">No broadcasts yet.</div>;

  return (
    <div className="space-y-2">
      {items.map((b) => (
        <div key={b.id} className="glass-panel border border-slate-800/85 rounded-xl overflow-hidden">
          <button onClick={() => open(b.id)} className="w-full flex items-center gap-3 px-4 py-3 text-left cursor-pointer hover:bg-slate-800/30">
            {openId === b.id ? <ChevronDown className="w-4 h-4 text-slate-500" /> : <ChevronRight className="w-4 h-4 text-slate-500" />}
            <span className="text-sm text-slate-200 font-medium flex-1 truncate">{b.name}</span>
            <span className="text-[11px] text-slate-500 uppercase">{b.mode === 'tts' ? 'TTS' : 'OBD'}</span>
            <span className="text-xs text-slate-400">{b.total_recipients} #</span>
            <StatusPill status={b.status} />
            <span className="text-[11px] text-slate-500 whitespace-nowrap">{new Date(b.created_at).toLocaleString()}</span>
          </button>
          {openId === b.id && (
            <div className="border-t border-slate-800/60 p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-[11px] text-slate-500 uppercase tracking-wider">Delivery</span>
                <button onClick={() => refreshDlr(b.id)} disabled={refreshing}
                        className="inline-flex items-center gap-1 text-xs text-slate-400 hover:text-brand-400 cursor-pointer">
                  <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} /> Refresh DLR
                </button>
              </div>
              {!detail ? <Loader2 className="w-4 h-4 animate-spin text-slate-400" /> : (
                <div className="overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead><tr className="text-[11px] text-slate-500 uppercase">
                      <th className="text-left px-2 py-1">Number</th>
                      <th className="text-left px-2 py-1">Status</th>
                      <th className="text-left px-2 py-1">Vendor</th>
                      <th className="text-left px-2 py-1">DTMF</th>
                      <th className="text-left px-2 py-1">Duration</th>
                    </tr></thead>
                    <tbody>
                      {detail.recipients.map((r) => (
                        <tr key={r.id} className="border-t border-slate-800/40">
                          <td className="px-2 py-1.5 text-slate-300">{r.number}</td>
                          <td className="px-2 py-1.5"><StatusPill status={r.status} /></td>
                          <td className="px-2 py-1.5 text-slate-500 text-xs">{r.vendor_status || '—'}</td>
                          <td className="px-2 py-1.5 text-slate-400">{r.dtmf || '—'}</td>
                          <td className="px-2 py-1.5 text-slate-400">{r.call_duration || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
};

/* ── Media upload/list ── */
const VoiceMediaPanel: React.FC = () => {
  const [items, setItems] = useState<VoiceMedia[]>([]);
  const [msg, setMsg] = useState<string | null>(null);
  const [title, setTitle] = useState('');
  const [vendorAccountId, setVendorAccountId] = useState('');
  const [duration, setDuration] = useState('0:30');
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);

  const load = useCallback(async () => {
    try { const r = await voiceApi.listMedia(); setItems(r.success ? r.items : []); if (!r.success) setMsg(r.message || null); }
    catch (err: any) { setMsg(extractErrorMessage(err, 'Failed to load media')); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const upload = async () => {
    if (!file || !title.trim() || !vendorAccountId.trim()) { setMsg('Title, vendor account id and file are required.'); return; }
    setBusy(true); setMsg(null);
    try {
      const fd = new FormData();
      fd.append('title', title); fd.append('vendor_account_id', vendorAccountId);
      fd.append('duration', duration); fd.append('file', file);
      const r = await voiceApi.uploadMedia(fd);
      setMsg(r.success ? 'Uploaded.' : (r.message || 'Upload failed.'));
      if (r.success) { setTitle(''); setFile(null); load(); }
    } catch (err: any) { setMsg(extractErrorMessage(err, 'Upload failed')); }
    finally { setBusy(false); }
  };

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4 max-w-2xl">
      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}
      <h3 className="text-sm font-semibold text-slate-200">Upload voice media</h3>
      <div className="grid grid-cols-2 gap-4">
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title"
               className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        <input value={vendorAccountId} onChange={(e) => setVendorAccountId(e.target.value)} placeholder="Vendor account id"
               className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        <input value={duration} onChange={(e) => setDuration(e.target.value)} placeholder="Duration e.g. 0:30"
               className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        <input type="file" accept="audio/*" onChange={(e) => setFile(e.target.files?.[0] || null)}
               className="text-slate-300 text-xs" />
      </div>
      <button onClick={upload} disabled={busy}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Upload className="w-4 h-4" />} Upload
      </button>

      <div className="pt-3 border-t border-slate-800/60 space-y-1.5">
        <span className="text-[11px] text-slate-500 uppercase tracking-wider">Existing media</span>
        {items.length === 0 ? <div className="text-[11px] text-slate-500">None found.</div> : (
          <ul className="text-sm text-slate-300 space-y-1">
            {items.map((m, i) => <li key={i} className="truncate">• {m.title || m.id || `Media ${i + 1}`}</li>)}
          </ul>
        )}
      </div>
    </div>
  );
};

/* ── Missed-call alert reports ── */
const MissedCallsPanel: React.FC = () => {
  const today = new Date().toISOString().slice(0, 10);
  const [did, setDid] = useState('');
  const [start, setStart] = useState(today);
  const [end, setEnd] = useState(today);
  const [rows, setRows] = useState<any[]>([]);
  const [busy, setBusy] = useState(false);
  const [msg, setMsg] = useState<string | null>(null);

  const run = async () => {
    if (!did.trim()) { setMsg('Enter a DID number.'); return; }
    setBusy(true); setMsg(null); setRows([]);
    try {
      const r = await voiceApi.missedCalls({ did_number: did.trim(), start_date: start, end_date: end });
      setRows(r.success ? r.rows : []);
      if (!r.success) setMsg(r.message || 'No data.');
      else if (r.rows.length === 0) setMsg('No missed calls in this range.');
    } catch (err: any) { setMsg(extractErrorMessage(err, 'Failed to load report')); }
    finally { setBusy(false); }
  };

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-4 max-w-2xl">
      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}
      <div className="grid grid-cols-3 gap-3">
        <label className="space-y-1 col-span-3 sm:col-span-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">DID number</span>
          <input value={did} onChange={(e) => setDid(e.target.value)} placeholder="9876543210"
                 className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">From</span>
          <input type="date" value={start} onChange={(e) => setStart(e.target.value)}
                 className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">To</span>
          <input type="date" value={end} onChange={(e) => setEnd(e.target.value)}
                 className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
        </label>
      </div>
      <button onClick={run} disabled={busy}
              className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
        {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <PhoneMissed className="w-4 h-4" />} Fetch report
      </button>
      {rows.length > 0 && (
        <div className="overflow-x-auto pt-2 border-t border-slate-800/60">
          <table className="w-full text-sm">
            <thead><tr className="text-[11px] text-slate-500 uppercase">
              {Object.keys(rows[0]).slice(0, 5).map((k) => <th key={k} className="text-left px-2 py-1">{k}</th>)}
            </tr></thead>
            <tbody>
              {rows.map((row, i) => (
                <tr key={i} className="border-t border-slate-800/40">
                  {Object.keys(rows[0]).slice(0, 5).map((k) => (
                    <td key={k} className="px-2 py-1.5 text-slate-300">{String(row[k] ?? '—')}</td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
};

type Tab = 'compose' | 'history' | 'media' | 'missed';

export const VoicePage: React.FC = () => {
  const [tab, setTab] = useState<Tab>('compose');
  const [refreshKey, setRefreshKey] = useState(0);
  const tabs: { key: Tab; label: string; icon: any }[] = [
    { key: 'compose', label: 'Compose', icon: Send },
    { key: 'history', label: 'Broadcasts', icon: Inbox },
    { key: 'media', label: 'Media', icon: Upload },
    { key: 'missed', label: 'Missed Calls', icon: PhoneMissed },
  ];

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <Megaphone className="w-7 h-7 text-brand-400" /> Voice Broadcast
        </h1>
        <p className="text-sm text-slate-400 mt-1">Bulk OBD voice notes and text-to-speech calls with delivery tracking.</p>
      </div>

      <div className="flex items-center gap-1 border-b border-slate-800/60">
        {tabs.map((t) => (
          <button key={t.key} onClick={() => setTab(t.key)}
                  className={`inline-flex items-center gap-1.5 px-4 py-2.5 text-sm font-medium border-b-2 -mb-px transition-colors cursor-pointer ${
                    tab === t.key ? 'border-brand-500 text-brand-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}>
            <t.icon className="w-4 h-4" /> {t.label}
          </button>
        ))}
      </div>

      {tab === 'compose' && <VoiceCompose onSent={() => setRefreshKey((k) => k + 1)} />}
      {tab === 'history' && <VoiceHistory refreshKey={refreshKey} />}
      {tab === 'media' && <VoiceMediaPanel />}
      {tab === 'missed' && <MissedCallsPanel />}
    </div>
  );
};
