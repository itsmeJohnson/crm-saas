import React, { useState, useEffect, useMemo } from 'react';
import { Stethoscope, Plus, Edit2, Trash2, X, Loader2, Search, RefreshCw } from 'lucide-react';
import { api } from '../../services/api';

interface Item {
  id: string;
  name: string;
  category: string | null;
  code: string | null;
  price: number;
  tax_percent: number;
  duration_minutes: number | null;
  description: string | null;
  is_active: boolean;
}

const money = (n: number) => `₹${Number(n || 0).toLocaleString('en-IN')}`;

export const TreatmentCatalogPage: React.FC = () => {
  const [items, setItems] = useState<Item[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<Item | null>(null);

  const fetchItems = async () => {
    setLoading(true);
    try { setItems((await api.get('/treatment-catalog/')).data || []); }
    catch (e) { console.error(e); }
    finally { setLoading(false); }
  };
  useEffect(() => { fetchItems(); }, []);

  const filtered = useMemo(() => items.filter((i) =>
    (i.name + (i.category || '') + (i.code || '')).toLowerCase().includes(search.toLowerCase())), [items, search]);

  const grouped = useMemo(() => {
    const g: Record<string, Item[]> = {};
    filtered.forEach((i) => { const k = i.category || 'Uncategorised'; (g[k] ||= []).push(i); });
    return Object.entries(g).sort(([a], [b]) => a.localeCompare(b));
  }, [filtered]);

  const remove = async (i: Item) => {
    if (!confirm(`Delete "${i.name}" from the price list?`)) return;
    await api.delete(`/treatment-catalog/${i.id}`);
    fetchItems();
  };

  return (
    <div className="space-y-6 select-none">
      <div className="bento-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-violet-500 to-fuchsia-500 flex items-center justify-center text-white shadow-lg shadow-violet-500/25 flex-shrink-0">
            <Stethoscope className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-100">Treatment &amp; Price Master</h1>
            <p className="text-xs text-slate-400 mt-0.5">Your clinic's procedure catalogue &amp; pricing — used across treatment plans &amp; invoices.</p>
          </div>
        </div>
        <div className="flex items-center gap-2.5">
          <button onClick={fetchItems} className="neo-btn px-3.5 py-2.5 text-xs flex items-center gap-2 text-slate-300"><RefreshCw className="w-4 h-4" /> Refresh</button>
          <button onClick={() => { setEditing(null); setModalOpen(true); }} className="neo-btn-primary px-4 py-2.5 text-xs flex items-center gap-2"><Plus className="w-4 h-4" /> Add Treatment</button>
        </div>
      </div>

      <div className="bento-card p-5">
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search treatments, category or code…" className="neo-input w-full pl-10 pr-4 py-2.5 text-xs" />
        </div>
      </div>

      {loading ? (
        <div className="bento-card p-10 flex items-center justify-center text-slate-400 text-sm"><Loader2 className="w-5 h-5 animate-spin mr-2" /> Loading price list…</div>
      ) : items.length === 0 ? (
        <div className="bento-card p-10 text-center">
          <Stethoscope className="w-10 h-10 text-slate-600 mx-auto mb-3" />
          <p className="text-slate-300 font-semibold">No treatments yet</p>
          <p className="text-slate-500 text-xs mt-1">Add your procedures and prices so staff can pick them when billing.</p>
          <button onClick={() => { setEditing(null); setModalOpen(true); }} className="neo-btn-primary px-4 py-2.5 text-xs inline-flex items-center gap-2 mt-4"><Plus className="w-4 h-4" /> Add your first treatment</button>
        </div>
      ) : (
        <div className="space-y-5">
          {grouped.map(([cat, rows]) => (
            <div key={cat} className="bento-card p-0 overflow-hidden">
              <div className="px-5 py-3 bg-[var(--bg-inset)] border-b border-slate-800/40 text-[11px] font-bold uppercase tracking-wider text-slate-400">{cat} · {rows.length}</div>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead><tr className="text-slate-400 uppercase tracking-wider text-[10px] border-b border-slate-800/40">
                    <th className="px-5 py-3">Treatment</th><th className="px-4 py-3">Code</th>
                    <th className="px-4 py-3 text-right">Price</th><th className="px-4 py-3 text-right">Tax %</th>
                    <th className="px-4 py-3 text-right">Duration</th><th className="px-4 py-3">Status</th><th className="px-5 py-3 text-right">Actions</th>
                  </tr></thead>
                  <tbody className="divide-y divide-slate-800/30">
                    {rows.map((i) => (
                      <tr key={i.id} className="hover:bg-[var(--bg-card-hover)]">
                        <td className="px-5 py-3 font-semibold text-slate-100">{i.name}{i.description && <span className="block text-[11px] text-slate-500 font-normal">{i.description}</span>}</td>
                        <td className="px-4 py-3 font-mono text-slate-400">{i.code || '—'}</td>
                        <td className="px-4 py-3 text-right font-bold text-slate-100">{money(i.price)}</td>
                        <td className="px-4 py-3 text-right text-slate-300">{Number(i.tax_percent) || 0}%</td>
                        <td className="px-4 py-3 text-right text-slate-400">{i.duration_minutes ? `${i.duration_minutes}m` : '—'}</td>
                        <td className="px-4 py-3">
                          <span className={`px-2 py-0.5 rounded-full text-[10px] font-bold ${i.is_active ? 'bg-emerald-500/15 text-emerald-300 [.light_&]:text-emerald-700' : 'bg-slate-500/15 text-slate-400'}`}>{i.is_active ? 'Active' : 'Inactive'}</span>
                        </td>
                        <td className="px-5 py-3 text-right">
                          <div className="flex items-center justify-end gap-1.5">
                            <button onClick={() => { setEditing(i); setModalOpen(true); }} className="neo-btn p-1.5 text-slate-300" title="Edit"><Edit2 className="w-3.5 h-3.5" /></button>
                            <button onClick={() => remove(i)} className="neo-btn p-1.5 text-rose-400" title="Delete"><Trash2 className="w-3.5 h-3.5" /></button>
                          </div>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ))}
        </div>
      )}

      {modalOpen && <TreatmentModal item={editing} onClose={() => setModalOpen(false)} onSaved={() => { setModalOpen(false); fetchItems(); }} />}
    </div>
  );
};

const TreatmentModal: React.FC<{ item: Item | null; onClose: () => void; onSaved: () => void }> = ({ item, onClose, onSaved }) => {
  const [f, setF] = useState({
    name: item?.name || '', category: item?.category || '', code: item?.code || '',
    price: item?.price ?? 0, tax_percent: item?.tax_percent ?? 0,
    duration_minutes: item?.duration_minutes ?? '', description: item?.description || '',
    is_active: item?.is_active ?? true,
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const set = (k: string, v: any) => setF((p) => ({ ...p, [k]: v }));

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!f.name.trim()) { setError('Name is required.'); return; }
    setSaving(true); setError('');
    const body: any = {
      name: f.name.trim(), category: f.category.trim() || null, code: f.code.trim() || null,
      price: Number(f.price) || 0, tax_percent: Number(f.tax_percent) || 0,
      duration_minutes: f.duration_minutes === '' ? null : Number(f.duration_minutes),
      description: f.description.trim() || null, is_active: f.is_active,
    };
    try {
      if (item) await api.patch(`/treatment-catalog/${item.id}`, body);
      else await api.post('/treatment-catalog/', body);
      onSaved();
    } catch (err: any) { setError(err.response?.data?.detail || 'Could not save.'); }
    finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-950/80 backdrop-blur-md">
      <div className="relative w-full max-w-md bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl overflow-hidden flex flex-col max-h-[92vh]">
        <div className="p-5 bg-slate-950/60 border-b border-slate-800 flex items-center justify-between flex-shrink-0">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-xl bg-violet-500/15 border border-violet-500/25 flex items-center justify-center text-violet-400"><Stethoscope className="w-5 h-5" /></div>
            <h3 className="text-sm font-bold text-slate-100">{item ? 'Edit Treatment' : 'Add Treatment'}</h3>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-300"><X className="w-5 h-5" /></button>
        </div>
        <form onSubmit={submit} className="p-5 space-y-4 overflow-y-auto">
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Treatment name</label>
            <input value={f.name} onChange={(e) => set('name', e.target.value)} placeholder="e.g. Root Canal Therapy" className="neo-input w-full px-3.5 py-2.5 text-xs" />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div><label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Category</label>
              <input value={f.category} onChange={(e) => set('category', e.target.value)} placeholder="e.g. Endodontics" className="neo-input w-full px-3.5 py-2.5 text-xs" /></div>
            <div><label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Code</label>
              <input value={f.code} onChange={(e) => set('code', e.target.value)} placeholder="e.g. RCT" className="neo-input w-full px-3.5 py-2.5 text-xs" /></div>
          </div>
          <div className="grid grid-cols-3 gap-3">
            <div><label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Price (₹)</label>
              <input type="number" min={0} value={f.price} onChange={(e) => set('price', e.target.value)} className="neo-input w-full px-3 py-2.5 text-xs" /></div>
            <div><label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Tax %</label>
              <input type="number" min={0} max={100} value={f.tax_percent} onChange={(e) => set('tax_percent', e.target.value)} className="neo-input w-full px-3 py-2.5 text-xs" /></div>
            <div><label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Mins</label>
              <input type="number" min={0} value={f.duration_minutes} onChange={(e) => set('duration_minutes', e.target.value)} className="neo-input w-full px-3 py-2.5 text-xs" /></div>
          </div>
          <div>
            <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-400 mb-1.5">Description</label>
            <input value={f.description} onChange={(e) => set('description', e.target.value)} placeholder="Optional" className="neo-input w-full px-3.5 py-2.5 text-xs" />
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
            <input type="checkbox" checked={f.is_active} onChange={(e) => set('is_active', e.target.checked)} /> Active (selectable when billing)
          </label>
          {error && <p className="text-xs text-rose-400">{error}</p>}
          <div className="flex items-center gap-2 pt-1">
            <button type="button" onClick={onClose} className="neo-btn px-4 py-2.5 text-xs text-slate-300 flex-1">Cancel</button>
            <button type="submit" disabled={saving} className="neo-btn-primary px-4 py-2.5 text-xs flex-1 flex items-center justify-center gap-2">{saving ? <><Loader2 className="w-4 h-4 animate-spin" /> Saving…</> : (item ? 'Save changes' : 'Add treatment')}</button>
          </div>
        </form>
      </div>
    </div>
  );
};
