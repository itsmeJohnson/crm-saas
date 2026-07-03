import React, { useCallback, useEffect, useState } from 'react';
import {
  PhoneCall, PhoneIncoming, PhoneOutgoing, PhoneMissed, Loader2, Search,
  Tag, Play, Pause, Users, ChevronLeft, ChevronRight, X, Check,
} from 'lucide-react';
import { callingApi, CallItem, CallQueue } from '../services/callingApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const PAGE_SIZE = 25;

const DISPOSITIONS = [
  'RNR', 'Switch Off', 'Busy', 'Not Exist', 'Out of Service', 'Picked',
  'Answered / Resolved', 'Callback Requested', 'Interested', 'Not Interested', 'Spam / Junk',
];

const formatDuration = (seconds: number | null): string => {
  if (!seconds) return '—';
  const mins = Math.floor(seconds / 60);
  const secs = seconds % 60;
  return `${mins}:${secs.toString().padStart(2, '0')}`;
};

const DirectionIcon: React.FC<{ item: CallItem }> = ({ item }) => {
  if (item.status === 'Missed') return <PhoneMissed className="w-4 h-4 text-red-400" />;
  if (item.direction === 'INBOUND') return <PhoneIncoming className="w-4 h-4 text-sky-400" />;
  return <PhoneOutgoing className="w-4 h-4 text-emerald-400" />;
};

/* ── Live queue monitor (Manager / TL / OrgAdmin) ── */
const QueueMonitor: React.FC = () => {
  const [queue, setQueue] = useState<CallQueue | null>(null);
  const [visible, setVisible] = useState(true);

  const load = useCallback(() => {
    callingApi.queue().then(setQueue).catch(() => setVisible(false));
  }, []);

  useEffect(() => {
    load();
    const interval = setInterval(load, 15000);
    return () => clearInterval(interval);
  }, [load]);

  if (!visible || !queue) return null;

  const active = queue.agents.filter((a) => a.state === 'ACTIVE_CALLING');
  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <Users className="w-4 h-4 text-brand-400" />
          Live Queue Monitor
        </h3>
        <div className="flex items-center gap-4 text-xs">
          <span className="text-slate-400">Pending queue: <span className="font-bold text-slate-200">{queue.pending_queue}</span></span>
          <span className="text-slate-400">On call: <span className="font-bold text-amber-400">{active.length}</span></span>
        </div>
      </div>
      {queue.agents.length === 0 ? (
        <p className="text-xs text-slate-500">No agents in your downline.</p>
      ) : (
        <ul className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2">
          {queue.agents.map((a) => (
            <li key={a.user_id} className="flex items-center gap-2.5 p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <span className={`w-2 h-2 rounded-full flex-shrink-0 ${
                a.state === 'ACTIVE_CALLING' ? 'bg-amber-400 animate-pulse' :
                a.state === 'BREAK' ? 'bg-blue-400' : 'bg-emerald-400'
              }`} />
              <div className="min-w-0 flex-1">
                <p className="text-xs font-semibold text-slate-200 truncate">{a.user_name}</p>
                <p className="text-[11px] text-slate-500 truncate">
                  {a.state === 'ACTIVE_CALLING' && a.current_call
                    ? `On call · ${a.current_call.lead_title || 'Unknown lead'}`
                    : a.state}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

/* ── Inline tag editor ── */
const TagEditor: React.FC<{ item: CallItem; onSaved: (updated: CallItem) => void }> = ({ item, onSaved }) => {
  const [editing, setEditing] = useState(false);
  const [value, setValue] = useState('');
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const tags = value.split(',').map((t) => t.trim()).filter(Boolean);
      const updated = await callingApi.setTags(item.id, tags);
      onSaved(updated);
      setEditing(false);
    } catch (e) {
      // keep the editor open so the user can retry
    } finally {
      setSaving(false);
    }
  };

  if (!editing) {
    return (
      <div className="flex items-center gap-1 flex-wrap">
        {item.tags.map((t) => (
          <span key={t} className="px-1.5 py-0.5 text-[10px] font-semibold rounded-md bg-brand-500/10 text-brand-400 border border-brand-500/20">{t}</span>
        ))}
        <button
          title="Edit tags"
          onClick={() => { setValue(item.tags.join(', ')); setEditing(true); }}
          className="p-1 rounded text-slate-500 hover:text-brand-400 cursor-pointer"
        >
          <Tag className="w-3.5 h-3.5" />
        </button>
      </div>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <input
        autoFocus
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter') save(); if (e.key === 'Escape') setEditing(false); }}
        placeholder="tag1, tag2"
        className="w-32 bg-slate-800 border border-slate-700 text-slate-200 py-1 px-2 rounded-md text-xs focus:outline-none focus:ring-1 focus:ring-brand-500"
      />
      <button onClick={save} disabled={saving} className="p-1 text-emerald-400 hover:text-emerald-300 cursor-pointer"><Check className="w-3.5 h-3.5" /></button>
      <button onClick={() => setEditing(false)} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
    </div>
  );
};

/* ── Recording playback ── */
const RecordingCell: React.FC<{ url: string | null }> = ({ url }) => {
  const [open, setOpen] = useState(false);
  if (!url) return <span className="text-slate-600 text-xs">—</span>;
  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        title="Play recording"
        className="inline-flex items-center gap-1 px-2 py-1 text-[11px] font-semibold rounded-md bg-slate-800/80 text-slate-300 border border-slate-700/60 hover:text-brand-400 hover:border-brand-500/40 cursor-pointer"
      >
        <Play className="w-3 h-3" /> Play
      </button>
    );
  }
  return (
    <div className="flex items-center gap-1">
      <audio controls autoPlay src={url} className="h-8 max-w-[220px]" />
      <button onClick={() => setOpen(false)} title="Hide player" className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><Pause className="w-3.5 h-3.5" /></button>
    </div>
  );
};

export const CallingPage: React.FC = () => {
  const { user } = useAuthStore();
  const canMonitor = !!user && (['SuperAdmin', 'OrgAdmin', 'Manager'].includes(user.role) || !!user.is_team_leader);

  const [items, setItems] = useState<CallItem[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(0);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [search, setSearch] = useState('');
  const [direction, setDirection] = useState('');
  const [disposition, setDisposition] = useState('');
  const [tag, setTag] = useState('');
  const [missedOnly, setMissedOnly] = useState(false);
  const [recordedOnly, setRecordedOnly] = useState(false);
  const [allTags, setAllTags] = useState<string[]>([]);

  const load = useCallback(async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await callingApi.history({
        search: search || undefined,
        direction: direction || undefined,
        disposition: disposition || undefined,
        tag: tag || undefined,
        missed_only: missedOnly || undefined,
        has_recording: recordedOnly || undefined,
        skip: page * PAGE_SIZE,
        limit: PAGE_SIZE,
      });
      setItems(data.items);
      setTotal(data.total);
    } catch (err: any) {
      setError(extractErrorMessage(err, 'Failed to load call history'));
    } finally {
      setIsLoading(false);
    }
  }, [search, direction, disposition, tag, missedOnly, recordedOnly, page]);

  useEffect(() => {
    const t = setTimeout(load, search ? 300 : 0);
    return () => clearTimeout(t);
  }, [load, search]);

  useEffect(() => {
    callingApi.listTags().then(setAllTags).catch(() => {});
  }, []);

  const onTagsSaved = (updated: CallItem) => {
    setItems((prev) => prev.map((i) => (i.id === updated.id ? { ...i, tags: updated.tags } : i)));
    callingApi.listTags().then(setAllTags).catch(() => {});
  };

  const totalPages = Math.max(1, Math.ceil(total / PAGE_SIZE));

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6">
        <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
          <PhoneCall className="w-7 h-7 text-brand-400" />
          Calling
        </h1>
        <p className="text-sm text-slate-400 mt-1">Call history, recordings, tags, and the live dialing queue.</p>
      </div>

      {canMonitor && <QueueMonitor />}

      {/* Filters */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl p-4 flex flex-wrap items-center gap-3">
        <div className="relative flex-1 min-w-[180px]">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input
            value={search}
            onChange={(e) => { setSearch(e.target.value); setPage(0); }}
            placeholder="Search calls…"
            className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 pl-9 pr-3 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500"
          />
        </div>
        <select value={direction} onChange={(e) => { setDirection(e.target.value); setPage(0); }}
                className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm focus:outline-none">
          <option value="">All directions</option>
          <option value="INBOUND">Inbound</option>
          <option value="OUTBOUND">Outbound</option>
        </select>
        <select value={disposition} onChange={(e) => { setDisposition(e.target.value); setPage(0); }}
                className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm focus:outline-none">
          <option value="">All dispositions</option>
          {DISPOSITIONS.map((d) => <option key={d} value={d}>{d}</option>)}
        </select>
        <select value={tag} onChange={(e) => { setTag(e.target.value); setPage(0); }}
                className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm focus:outline-none">
          <option value="">All tags</option>
          {allTags.map((t) => <option key={t} value={t}>{t}</option>)}
        </select>
        <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer select-none">
          <input type="checkbox" checked={missedOnly} onChange={(e) => { setMissedOnly(e.target.checked); setPage(0); }}
                 className="w-3.5 h-3.5 rounded" />
          Missed only
        </label>
        <label className="flex items-center gap-1.5 text-xs text-slate-300 cursor-pointer select-none">
          <input type="checkbox" checked={recordedOnly} onChange={(e) => { setRecordedOnly(e.target.checked); setPage(0); }}
                 className="w-3.5 h-3.5 rounded" />
          With recording
        </label>
      </div>

      {error && <div className="p-4 bg-red-500/10 border border-red-500/20 text-red-400 rounded-xl text-sm">{error}</div>}

      {/* History table */}
      <div className="glass-panel border border-slate-800/85 rounded-2xl overflow-hidden">
        {isLoading ? (
          <div className="py-24 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
        ) : items.length === 0 ? (
          <div className="py-24 text-center">
            <PhoneCall className="w-10 h-10 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-400 text-sm">No calls match the current filters.</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800/80 text-left text-[11px] uppercase tracking-wider text-slate-500">
                  <th className="px-4 py-3 font-semibold">Call</th>
                  <th className="px-4 py-3 font-semibold">Lead</th>
                  <th className="px-4 py-3 font-semibold">Agent</th>
                  <th className="px-4 py-3 font-semibold">Disposition</th>
                  <th className="px-4 py-3 font-semibold">Duration</th>
                  <th className="px-4 py-3 font-semibold">Tags</th>
                  <th className="px-4 py-3 font-semibold">Recording</th>
                  <th className="px-4 py-3 font-semibold">When</th>
                </tr>
              </thead>
              <tbody>
                {items.map((item) => (
                  <tr key={item.id} className="border-b border-slate-800/40 hover:bg-slate-900/40">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <DirectionIcon item={item} />
                        <span className="text-slate-300 truncate max-w-[200px]" title={item.subject}>{item.subject}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-slate-300">{item.lead_title || '—'}</td>
                    <td className="px-4 py-3 text-slate-400">{item.agent_name || '—'}</td>
                    <td className="px-4 py-3">
                      {item.status === 'Missed' ? (
                        <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-red-500/10 text-red-400 border border-red-500/20">Missed</span>
                      ) : item.disposition ? (
                        <span className="px-2 py-0.5 text-[11px] font-semibold rounded-md bg-slate-800/80 text-slate-300 border border-slate-700/60">{item.disposition}</span>
                      ) : (
                        <span className="text-slate-600 text-xs">{item.status}</span>
                      )}
                    </td>
                    <td className="px-4 py-3 text-slate-400 font-mono text-xs">{formatDuration(item.duration)}</td>
                    <td className="px-4 py-3"><TagEditor item={item} onSaved={onTagsSaved} /></td>
                    <td className="px-4 py-3"><RecordingCell url={item.recording_url} /></td>
                    <td className="px-4 py-3 text-slate-500 text-xs whitespace-nowrap">{new Date(item.timestamp).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        {!isLoading && total > PAGE_SIZE && (
          <div className="flex items-center justify-between px-4 py-3 border-t border-slate-800/60">
            <span className="text-xs text-slate-500">{total} calls · page {page + 1} of {totalPages}</span>
            <div className="flex items-center gap-1">
              <button disabled={page === 0} onClick={() => setPage((p) => p - 1)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 disabled:opacity-30 cursor-pointer">
                <ChevronLeft className="w-4 h-4" />
              </button>
              <button disabled={page + 1 >= totalPages} onClick={() => setPage((p) => p + 1)}
                      className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 disabled:opacity-30 cursor-pointer">
                <ChevronRight className="w-4 h-4" />
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
