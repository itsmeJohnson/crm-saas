import React, { useEffect, useState } from 'react';
import { CalendarClock, Plus, Loader2, Copy, Check, ExternalLink, Trash2, X } from 'lucide-react';
import { bookingApi, BookingLink } from '../services/bookingApi';
import { extractErrorMessage } from '../utils/errors';

const blank = () => ({ title: 'Book a meeting', slot_minutes: 30, buffer_minutes: 0, advance_days: 14 });

export const BookingLinksPage: React.FC = () => {
  const [items, setItems] = useState<BookingLink[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);
  const [form, setForm] = useState(blank());
  const [saving, setSaving] = useState(false);
  const [copied, setCopied] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try { setItems(await bookingApi.list()); }
    catch (err: any) { setMsg(extractErrorMessage(err, 'Failed to load booking links')); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const publicUrl = (slug: string) => `${window.location.origin}/book/${slug}`;
  const copy = (slug: string) => { navigator.clipboard?.writeText(publicUrl(slug)); setCopied(slug); setTimeout(() => setCopied(null), 1500); };

  const create = async () => {
    if (!form.title.trim()) { setMsg('A title is required'); return; }
    setSaving(true); setMsg(null);
    try {
      await bookingApi.create(form);
      setCreating(false); setForm(blank()); load();
    } catch (err: any) { setMsg(extractErrorMessage(err, 'Failed to create')); }
    finally { setSaving(false); }
  };

  const toggle = async (b: BookingLink) => {
    try { await bookingApi.update(b.id, { is_active: !b.is_active }); load(); }
    catch (err: any) { setMsg(extractErrorMessage(err, 'Failed')); }
  };
  const remove = async (b: BookingLink) => {
    if (!confirm(`Delete "${b.title}"? Its public link will stop working.`)) return;
    try { await bookingApi.remove(b.id); load(); } catch (err: any) { setMsg(extractErrorMessage(err, 'Failed')); }
  };

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <CalendarClock className="w-7 h-7 text-brand-400" /> Booking Links
          </h1>
          <p className="text-sm text-slate-400 mt-1">Share a link and let prospects book open slots on your calendar. Each booking creates an appointment and a lead.</p>
        </div>
        <button onClick={() => { setCreating(true); setForm(blank()); }}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm cursor-pointer">
          <Plus className="w-4 h-4" /> New Link
        </button>
      </div>

      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}

      {creating && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200">New booking link</h2>
            <button onClick={() => setCreating(false)} className="text-slate-400 hover:text-slate-200"><X className="w-4 h-4" /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Title</span>
              <input value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })}
                className="mt-1 w-full px-3 py-2 rounded-lg glass-input" placeholder="Sales demo" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Slot length (min)</span>
              <input type="number" min={5} max={480} value={form.slot_minutes}
                onChange={(e) => setForm({ ...form, slot_minutes: Number(e.target.value) })}
                className="mt-1 w-full px-3 py-2 rounded-lg glass-input" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Buffer between (min)</span>
              <input type="number" min={0} max={240} value={form.buffer_minutes}
                onChange={(e) => setForm({ ...form, buffer_minutes: Number(e.target.value) })}
                className="mt-1 w-full px-3 py-2 rounded-lg glass-input" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Bookable days ahead</span>
              <input type="number" min={1} max={120} value={form.advance_days}
                onChange={(e) => setForm({ ...form, advance_days: Number(e.target.value) })}
                className="mt-1 w-full px-3 py-2 rounded-lg glass-input" />
            </label>
          </div>
          <p className="text-xs text-slate-500">Availability follows your organization’s working hours and skips holidays and times you’re already booked.</p>
          <div className="flex justify-end gap-2">
            <button onClick={() => setCreating(false)} className="px-4 py-2 rounded-lg text-sm text-slate-300 border border-slate-700 hover:bg-slate-800">Cancel</button>
            <button onClick={create} disabled={saving}
              className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-brand-500 text-white disabled:opacity-50">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />} Create
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : items.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-sm">No booking links yet. Create your first one to start taking appointments.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((b) => (
            <div key={b.id} className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-semibold text-slate-100 truncate">{b.title}</h3>
                  <p className="text-xs text-slate-500 mt-0.5">{b.slot_minutes} min · up to {b.advance_days} days ahead · {b.bookings_count} booked</p>
                </div>
                <span className={`text-[10px] px-2 py-0.5 rounded-full border ${b.is_active ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-slate-400 border-slate-700 bg-slate-800/60'}`}>
                  {b.is_active ? 'Active' : 'Paused'}
                </span>
              </div>
              <div className="mt-3 flex items-center gap-2 text-xs">
                <code className="flex-1 truncate bg-slate-950/60 border border-slate-800 rounded px-2 py-1 text-slate-400">{publicUrl(b.slug)}</code>
                <button onClick={() => copy(b.slug)} title="Copy link" className="p-1.5 rounded border border-slate-700 text-slate-300 hover:bg-slate-800">
                  {copied === b.slug ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />}
                </button>
                <a href={publicUrl(b.slug)} target="_blank" rel="noopener noreferrer" title="Open" className="p-1.5 rounded border border-slate-700 text-slate-300 hover:bg-slate-800">
                  <ExternalLink className="w-3.5 h-3.5" />
                </a>
              </div>
              <div className="mt-3 flex items-center gap-2">
                <button onClick={() => toggle(b)} className="text-xs px-3 py-1.5 rounded border border-slate-700 text-slate-300 hover:bg-slate-800">
                  {b.is_active ? 'Pause' : 'Activate'}
                </button>
                <button onClick={() => remove(b)} className="text-xs px-3 py-1.5 rounded border border-slate-800 text-red-400 hover:bg-red-500/10 hover:border-red-500/30 inline-flex items-center gap-1">
                  <Trash2 className="w-3.5 h-3.5" /> Delete
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default BookingLinksPage;
