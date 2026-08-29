import React, { useEffect, useState } from 'react';
import { Globe, Plus, Loader2, Copy, Check, ExternalLink, Trash2, Pencil, X } from 'lucide-react';
import { landingApi, LandingPage, LandingConfig } from '../services/landingApi';
import { extractErrorMessage } from '../utils/errors';

const blankConfig = (): LandingConfig => ({
  headline: 'Grow your business with us',
  subheadline: 'Tell us what you need and our team will get back to you.',
  body: '',
  cta_text: 'Request a callback',
  theme: '#6366f1',
});

export const LandingPagesPage: React.FC = () => {
  const [items, setItems] = useState<LandingPage[]>([]);
  const [limit, setLimit] = useState(1);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState<LandingPage | 'new' | null>(null);
  const [copied, setCopied] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try { const r = await landingApi.list(); setItems(r.items); setLimit(r.website_limit); }
    catch (err: any) { setMsg(extractErrorMessage(err, 'Failed to load')); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const publicUrl = (slug: string) => `${window.location.origin}/lp/${slug}`;

  const copy = (slug: string) => { navigator.clipboard?.writeText(publicUrl(slug)); setCopied(slug); setTimeout(() => setCopied(null), 1500); };

  const togglePublish = async (p: LandingPage) => {
    try { await landingApi.update(p.id, { is_published: !p.is_published }); load(); } catch (err: any) { setMsg(extractErrorMessage(err, 'Failed')); }
  };
  const remove = async (p: LandingPage) => { if (!confirm(`Delete "${p.name}"?`)) return; try { await landingApi.remove(p.id); load(); } catch (err: any) { setMsg(extractErrorMessage(err, 'Failed')); } };

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <Globe className="w-7 h-7 text-brand-400" /> Websites
          </h1>
          <p className="text-sm text-slate-400 mt-1">Publish lead-capture landing pages that feed your CRM with UTM attribution.</p>
        </div>
        <button onClick={() => setEditing('new')} disabled={items.length >= limit}
                className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
          <Plus className="w-4 h-4" /> New Page
        </button>
      </div>

      <div className="text-xs text-slate-500">{items.length} / {limit} websites used {items.length >= limit && '— upgrade your plan to add more.'}</div>
      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}

      {loading ? (
        <div className="py-12 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : items.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-sm">No landing pages yet. Create your first one.</div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          {items.map((p) => (
            <div key={p.id} className="glass-panel border border-slate-800/85 rounded-2xl p-5 space-y-3">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <h3 className="text-sm font-semibold text-slate-200">{p.name}</h3>
                  <span className={`text-[11px] font-semibold ${p.is_published ? 'text-emerald-400' : 'text-slate-500'}`}>{p.is_published ? '● Published' : '○ Draft'}</span>
                </div>
                <div className="flex items-center gap-1">
                  <button onClick={() => setEditing(p)} title="Edit" className="p-1.5 rounded-lg text-slate-400 hover:text-brand-400 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => remove(p)} title="Delete" className="p-1.5 rounded-lg text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                </div>
              </div>
              <div className="flex items-center gap-2">
                <code className="flex-1 bg-slate-950/60 border border-slate-800 text-slate-300 py-1.5 px-2 rounded-lg text-[11px] truncate">{publicUrl(p.slug)}</code>
                <button onClick={() => copy(p.slug)} className="p-1.5 rounded-lg text-slate-400 hover:text-brand-400 border border-slate-700/60 cursor-pointer">{copied === p.slug ? <Check className="w-4 h-4 text-emerald-400" /> : <Copy className="w-4 h-4" />}</button>
                <a href={publicUrl(p.slug)} target="_blank" rel="noreferrer" className="p-1.5 rounded-lg text-slate-400 hover:text-brand-400 border border-slate-700/60"><ExternalLink className="w-4 h-4" /></a>
              </div>
              <div className="flex items-center justify-between text-xs text-slate-400">
                <span>{p.views} views · <b className="text-slate-200">{p.submissions} leads</b></span>
                <label className="flex items-center gap-1.5 cursor-pointer">
                  <input type="checkbox" checked={p.is_published} onChange={() => togglePublish(p)} className="w-3.5 h-3.5 rounded" /> Published
                </label>
              </div>
            </div>
          ))}
        </div>
      )}

      {editing && <EditModal page={editing === 'new' ? null : editing} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); load(); }} />}
    </div>
  );
};

const EditModal: React.FC<{ page: LandingPage | null; onClose: () => void; onSaved: () => void }> = ({ page, onClose, onSaved }) => {
  const [name, setName] = useState(page?.name || 'New Landing Page');
  const [cfg, setCfg] = useState<LandingConfig>(page?.config || blankConfig());
  const [saving, setSaving] = useState(false);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (page && !page.config) { landingApi.get(page.id).then((p) => setCfg(p.config || blankConfig())).catch(() => {}); }
  }, [page]);

  const save = async () => {
    setSaving(true); setErr(null);
    try {
      if (page) await landingApi.update(page.id, { name, config: cfg });
      else await landingApi.create({ name, config: cfg, is_published: false });
      onSaved();
    } catch (e: any) { setErr(extractErrorMessage(e, 'Failed to save')); }
    finally { setSaving(false); }
  };

  const set = (k: keyof LandingConfig, v: string) => setCfg({ ...cfg, [k]: v });
  const field = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";

  return (
    <div className="fixed inset-0 z-50 bg-black/60 flex items-center justify-center p-4" onClick={onClose}>
      <div className="glass-panel border border-slate-800 rounded-2xl p-6 w-full max-w-lg space-y-4 max-h-[90vh] overflow-y-auto" onClick={(e) => e.stopPropagation()}>
        <div className="flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-100">{page ? 'Edit' : 'New'} Landing Page</h3>
          <button onClick={onClose} className="p-1.5 text-slate-400 hover:text-slate-200 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        {err && <div className="p-3 bg-red-900/30 border border-red-700/50 text-red-300 rounded-lg text-xs">{err}</div>}
        <label className="space-y-1 block"><span className="text-[11px] font-semibold text-slate-400 uppercase">Page name (internal)</span>
          <input value={name} onChange={(e) => setName(e.target.value)} className={field} /></label>
        <label className="space-y-1 block"><span className="text-[11px] font-semibold text-slate-400 uppercase">Headline</span>
          <input value={cfg.headline || ''} onChange={(e) => set('headline', e.target.value)} className={field} /></label>
        <label className="space-y-1 block"><span className="text-[11px] font-semibold text-slate-400 uppercase">Subheadline</span>
          <input value={cfg.subheadline || ''} onChange={(e) => set('subheadline', e.target.value)} className={field} /></label>
        <label className="space-y-1 block"><span className="text-[11px] font-semibold text-slate-400 uppercase">Body</span>
          <textarea rows={3} value={cfg.body || ''} onChange={(e) => set('body', e.target.value)} className={field} /></label>
        <div className="grid grid-cols-2 gap-4">
          <label className="space-y-1 block"><span className="text-[11px] font-semibold text-slate-400 uppercase">Button / CTA text</span>
            <input value={cfg.cta_text || ''} onChange={(e) => set('cta_text', e.target.value)} className={field} /></label>
          <label className="space-y-1 block"><span className="text-[11px] font-semibold text-slate-400 uppercase">Accent color</span>
            <input type="color" value={cfg.theme || '#6366f1'} onChange={(e) => set('theme', e.target.value)} className="w-full h-10 bg-slate-800/70 border border-slate-700/70 rounded-lg cursor-pointer" /></label>
        </div>
        <p className="text-[11px] text-slate-500">Form collects Name, Email, Phone, Message and captures UTM parameters automatically. Field customization coming soon.</p>
        <div className="flex justify-end gap-2 pt-2">
          <button onClick={onClose} className="px-4 py-2 rounded-lg text-sm text-slate-300 border border-slate-700/60 cursor-pointer">Cancel</button>
          <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Save
          </button>
        </div>
      </div>
    </div>
  );
};
