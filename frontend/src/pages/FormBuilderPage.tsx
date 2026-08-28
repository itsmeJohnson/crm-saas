import React, { useEffect, useState, useCallback } from 'react';
import { Plus, Trash2, ChevronUp, ChevronDown, LayoutList, Loader2, Star } from 'lucide-react';
import { metadataApi, CustomFieldDefinition } from '../services/metadataApi';
import { formApi, FormDefinition, FormFieldEntry } from '../services/formApi';
import { useMetadataStore } from '../store/metadataStore';

interface Row extends FormFieldEntry { section: string; }

const CORE_ENTITIES = ['lead', 'contact'];

export const FormBuilderPage: React.FC = () => {
  const { customObjects } = useMetadataStore();
  const entities = [...CORE_ENTITIES, ...customObjects.filter((o) => o.is_active).map((o) => o.key)];

  const [entity, setEntity] = useState('lead');
  const [defs, setDefs] = useState<CustomFieldDefinition[]>([]);
  const [forms, setForms] = useState<FormDefinition[]>([]);
  const [editing, setEditing] = useState<FormDefinition | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // editor state
  const [formKey, setFormKey] = useState('');
  const [formName, setFormName] = useState('');
  const [isDefault, setIsDefault] = useState(false);
  const [rows, setRows] = useState<Row[]>([]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDefs((await metadataApi.listCustomFields(entity)).filter((d) => d.is_active));
      setForms(await formApi.listForms(entity, true));
    } catch { /* silent */ } finally { setLoading(false); }
  }, [entity]);

  useEffect(() => { load(); resetEditor(); }, [load]);

  const resetEditor = () => {
    setEditing(null); setFormKey(''); setFormName(''); setIsDefault(false); setRows([]);
  };

  const startEdit = (f: FormDefinition) => {
    setEditing(f); setFormKey(f.key); setFormName(f.name); setIsDefault(f.is_default);
    const r: Row[] = [];
    for (const s of f.schema?.sections ?? []) {
      for (const fld of s.fields ?? []) {
        r.push({ key: fld.key, section: s.title ?? '', required: fld.required ?? false, hidden: fld.hidden ?? false, read_only: fld.read_only ?? false });
      }
    }
    setRows(r);
  };

  const addedKeys = new Set(rows.map((r) => r.key));
  const available = defs.filter((d) => !addedKeys.has(d.key));

  const addField = (key: string) => setRows((p) => [...p, { key, section: '', required: false, hidden: false, read_only: false }]);
  const removeRow = (i: number) => setRows((p) => p.filter((_, idx) => idx !== i));
  const move = (i: number, dir: -1 | 1) => setRows((p) => {
    const j = i + dir; if (j < 0 || j >= p.length) return p;
    const n = [...p]; [n[i], n[j]] = [n[j], n[i]]; return n;
  });
  const patch = (i: number, k: keyof Row, v: any) => setRows((p) => p.map((r, idx) => (idx === i ? { ...r, [k]: v } : r)));

  const buildSchema = () => {
    // Group rows by section label, preserving first-seen order and field order.
    const order: string[] = [];
    const map = new Map<string, FormFieldEntry[]>();
    for (const r of rows) {
      const s = r.section.trim() || 'General';
      if (!map.has(s)) { map.set(s, []); order.push(s); }
      map.get(s)!.push({ key: r.key, required: r.required || undefined, hidden: r.hidden || undefined, read_only: r.read_only || undefined });
    }
    return { sections: order.map((title) => ({ title, fields: map.get(title)! })) };
  };

  const save = async () => {
    if (!formKey.trim() || !formName.trim()) return;
    setError(null);
    try {
      const payload = { name: formName.trim(), is_default: isDefault, schema: buildSchema() };
      if (editing) await formApi.updateForm(editing.id, payload);
      else await formApi.createForm(entity, { key: formKey.trim().toLowerCase(), ...payload });
      resetEditor();
      await load();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to save form');
    }
  };

  const del = async (f: FormDefinition) => {
    await formApi.deleteForm(f.id);
    if (editing?.id === f.id) resetEditor();
    await load();
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <LayoutList className="w-6 h-6 text-brand-400" />
        <h1 className="text-2xl font-bold text-slate-100">Dynamic Forms</h1>
      </div>

      <div className="flex items-center gap-3">
        <label className="text-xs text-slate-400 uppercase tracking-wider">Entity</label>
        <select value={entity} onChange={(e) => setEntity(e.target.value)}
                className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-sm text-slate-200">
          {entities.map((en) => <option key={en} value={en}>{en}</option>)}
        </select>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* existing forms */}
        <div className="space-y-2">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Forms for {entity}</p>
          {loading && <Loader2 className="w-4 h-4 animate-spin text-slate-500" />}
          {forms.length === 0 && !loading && <p className="text-xs text-slate-500">No forms yet.</p>}
          {forms.map((f) => (
            <div key={f.id} className="flex items-center justify-between gap-2 p-3 rounded-xl bg-slate-900 border border-slate-800">
              <button onClick={() => startEdit(f)} className="text-left flex-1">
                <span className="text-sm text-slate-200">{f.name}</span>{' '}
                <span className="text-xs text-slate-500">({f.key})</span>
                {f.is_default && <Star className="inline w-3 h-3 ml-1 text-amber-400" />}
              </button>
              <button onClick={() => del(f)} className="p-1 text-slate-500 hover:text-red-400"><Trash2 className="w-3.5 h-3.5" /></button>
            </div>
          ))}
          <button onClick={resetEditor} className="w-full mt-2 flex items-center justify-center gap-1.5 px-3 py-2 border border-slate-800 hover:border-slate-700 text-slate-300 rounded-lg text-xs font-semibold">
            <Plus className="w-3.5 h-3.5" /> New Form
          </button>
        </div>

        {/* editor */}
        <div className="lg:col-span-2 p-4 bg-slate-900 border border-slate-800 rounded-2xl space-y-4">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">{editing ? 'Edit Form' : 'New Form'}</p>
          <div className="grid grid-cols-2 gap-2">
            <input value={formKey} disabled={!!editing} onChange={(e) => setFormKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
                   placeholder="key (e.g. create_form)" className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 disabled:opacity-50" />
            <input value={formName} onChange={(e) => setFormName(e.target.value)}
                   placeholder="Name" className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200" />
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-300">
            <input type="checkbox" checked={isDefault} onChange={(e) => setIsDefault(e.target.checked)} className="accent-brand-500" />
            Default form for this entity
          </label>

          {/* available fields */}
          <div>
            <p className="text-[11px] text-slate-500 mb-1">Available fields</p>
            <div className="flex flex-wrap gap-1.5">
              {available.length === 0 && <span className="text-xs text-slate-600">All fields added.</span>}
              {available.map((d) => (
                <button key={d.id} onClick={() => addField(d.key)}
                        className="px-2 py-1 rounded bg-slate-800/60 hover:bg-slate-700 text-[11px] text-slate-300">+ {d.label}</button>
              ))}
            </div>
          </div>

          {/* layout rows */}
          <div className="space-y-2">
            {rows.length === 0 && <p className="text-xs text-slate-500">Add fields to build the form.</p>}
            {rows.map((r, i) => (
              <div key={r.key} className="flex flex-wrap items-center gap-2 p-2 bg-slate-950/60 border border-slate-800 rounded-lg">
                <span className="text-xs text-slate-200 w-28 truncate">{r.key}</span>
                <input value={r.section} onChange={(e) => patch(i, 'section', e.target.value)} placeholder="section"
                       className="px-2 py-1 bg-slate-900 border border-slate-800 rounded text-[11px] text-slate-200 w-24" />
                <label className="text-[11px] text-slate-400 flex items-center gap-1"><input type="checkbox" checked={!!r.required} onChange={(e) => patch(i, 'required', e.target.checked)} className="accent-brand-500" />req</label>
                <label className="text-[11px] text-slate-400 flex items-center gap-1"><input type="checkbox" checked={!!r.hidden} onChange={(e) => patch(i, 'hidden', e.target.checked)} className="accent-brand-500" />hide</label>
                <label className="text-[11px] text-slate-400 flex items-center gap-1"><input type="checkbox" checked={!!r.read_only} onChange={(e) => patch(i, 'read_only', e.target.checked)} className="accent-brand-500" />ro</label>
                <div className="ml-auto flex items-center gap-0.5">
                  <button onClick={() => move(i, -1)} className="p-1 text-slate-500 hover:text-slate-200"><ChevronUp className="w-3.5 h-3.5" /></button>
                  <button onClick={() => move(i, 1)} className="p-1 text-slate-500 hover:text-slate-200"><ChevronDown className="w-3.5 h-3.5" /></button>
                  <button onClick={() => removeRow(i)} className="p-1 text-slate-500 hover:text-red-400"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
            ))}
          </div>

          <button onClick={save} className="flex items-center gap-1.5 px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold">
            <Plus className="w-3.5 h-3.5" /> {editing ? 'Save Changes' : 'Create Form'}
          </button>
        </div>
      </div>
    </div>
  );
};
