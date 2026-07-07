import React, { useCallback, useEffect, useState } from 'react';
import { announcementApi, Announcement, ANNOUNCEMENT_AUDIENCES } from '../../services/announcementApi';
import { useAuthStore } from '../../store/authStore';
import { Megaphone, Pin, Loader2, Plus, X, Check, Trash2 } from 'lucide-react';
import { extractErrorMessage } from '../../utils/errors';

export const AnnouncementsWidget: React.FC = () => {
  const { user } = useAuthStore();
  const canManage = user?.role === 'OrgAdmin' || user?.role === 'Manager';
  const [items, setItems] = useState<Announcement[] | null>(null);
  const [adding, setAdding] = useState(false);
  const [f, setF] = useState<any>({ title: '', body: '', audience: 'all', is_pinned: false });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => {
    announcementApi.list(canManage ? 'all' : 'mine').then(setItems).catch(() => setItems([]));
  }, [canManage]);
  useEffect(() => { load(); }, [load]);

  const create = async () => {
    if (!f.title.trim() || !f.body.trim()) { setError('Title and body are required'); return; }
    setError(null);
    try {
      await announcementApi.create({ title: f.title, body: f.body, audience: f.audience, is_pinned: f.is_pinned });
      setF({ title: '', body: '', audience: 'all', is_pinned: false }); setAdding(false); load();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to post')); }
  };

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Megaphone className="w-4 h-4 text-brand-400" /> Announcements</h3>
        {canManage && !adding && <button onClick={() => setAdding(true)} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer inline-flex items-center gap-1"><Plus className="w-3.5 h-3.5" /> New</button>}
      </div>
      {error && <div className="p-2 mb-2 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      {adding && (
        <div className="p-2 mb-3 bg-slate-950/40 border border-slate-800/60 rounded-lg space-y-2">
          <input value={f.title} onChange={(e) => setF({ ...f, title: e.target.value })} placeholder="Title" className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs" />
          <textarea value={f.body} onChange={(e) => setF({ ...f, body: e.target.value })} rows={2} placeholder="Message" className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs" />
          <div className="flex items-center gap-2">
            <select value={f.audience} onChange={(e) => setF({ ...f, audience: e.target.value })} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1 px-1.5 rounded-md text-[11px]">
              {ANNOUNCEMENT_AUDIENCES.map((a) => <option key={a} value={a}>{a}</option>)}
            </select>
            <label className="text-[11px] text-slate-400 flex items-center gap-1 cursor-pointer"><input type="checkbox" checked={f.is_pinned} onChange={(e) => setF({ ...f, is_pinned: e.target.checked })} /> Pin</label>
            <button onClick={create} className="ml-auto text-xs text-emerald-400 cursor-pointer inline-flex items-center gap-1"><Check className="w-3.5 h-3.5" /> Post</button>
            <button onClick={() => { setAdding(false); setError(null); }} className="text-slate-500 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
          </div>
        </div>
      )}
      {!items ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : items.length === 0 ? (
        <p className="text-xs text-slate-500">No announcements.</p>
      ) : (
        <ul className="space-y-2">
          {items.slice(0, 5).map((a) => (
            <li key={a.id} className="p-2.5 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <div className="flex items-start justify-between gap-2">
                <p className="text-xs font-semibold text-slate-200 flex items-center gap-1.5">
                  {a.is_pinned && <Pin className="w-3 h-3 text-amber-400 shrink-0" />} {a.title}
                  {canManage && a.audience !== 'all' && <span className="text-[9px] text-slate-600">({a.audience})</span>}
                </p>
                {canManage && <button onClick={async () => { await announcementApi.remove(a.id); load(); }} className="text-slate-600 hover:text-red-400 cursor-pointer shrink-0"><Trash2 className="w-3 h-3" /></button>}
              </div>
              <p className="text-[11px] text-slate-400 mt-0.5 line-clamp-2">{a.body}</p>
              <p className="text-[10px] text-slate-600 mt-1">{a.author_name}{a.published_at ? ` · ${new Date(a.published_at).toLocaleDateString()}` : ''}{a.is_active ? '' : ' · inactive'}</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
