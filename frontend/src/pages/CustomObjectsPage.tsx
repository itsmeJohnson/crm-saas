import React, { useEffect, useState, useCallback } from 'react';
import { Plus, Trash2, Database, Pencil, Loader2 } from 'lucide-react';
import { objectApi, CustomObjectDefinition, CustomObjectRecord } from '../services/objectApi';
import { metadataApi, CustomFieldDefinition } from '../services/metadataApi';
import { useMetadataStore } from '../store/metadataStore';
import { RecordFormModal } from '../components/objects/RecordFormModal';

const FIELD_TYPES = [
  'text', 'textarea', 'number', 'currency', 'percentage', 'date', 'datetime',
  'boolean', 'email', 'phone', 'url', 'select', 'multiselect', 'entity_reference',
];
const OPTION_TYPES = ['select', 'multiselect'];

export const CustomObjectsPage: React.FC = () => {
  const { refresh } = useMetadataStore();
  const [objects, setObjects] = useState<CustomObjectDefinition[]>([]);
  const [selected, setSelected] = useState<CustomObjectDefinition | null>(null);
  const [error, setError] = useState<string | null>(null);

  // new object form
  const [newKey, setNewKey] = useState('');
  const [newLabel, setNewLabel] = useState('');

  const loadObjects = useCallback(async () => {
    try {
      setObjects(await objectApi.listObjects());
    } catch { /* silent */ }
  }, []);

  useEffect(() => { loadObjects(); }, [loadObjects]);

  const createObject = async () => {
    if (!newKey.trim() || !newLabel.trim()) return;
    setError(null);
    try {
      await objectApi.createObject({ key: newKey.trim().toLowerCase(), label: newLabel.trim() });
      setNewKey(''); setNewLabel('');
      await loadObjects();
      await refresh();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to create object');
    }
  };

  const deleteObject = async (obj: CustomObjectDefinition) => {
    setError(null);
    try {
      await objectApi.deleteObject(obj.id);
      if (selected?.id === obj.id) setSelected(null);
      await loadObjects();
      await refresh();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to delete object');
    }
  };

  return (
    <div className="p-6 space-y-6">
      <div className="flex items-center gap-3">
        <Database className="w-6 h-6 text-brand-400" />
        <h1 className="text-2xl font-bold text-slate-100">Custom Objects</h1>
      </div>
      {error && <p className="text-sm text-red-400">{error}</p>}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Object list + create */}
        <div className="space-y-4">
          <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">New Object</p>
            <input value={newKey} onChange={(e) => setNewKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))}
                   placeholder="key (e.g. property)" className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200" />
            <input value={newLabel} onChange={(e) => setNewLabel(e.target.value)}
                   placeholder="Label (e.g. Property)" className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200" />
            <button onClick={createObject} className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold">
              <Plus className="w-3.5 h-3.5" /> Create Object
            </button>
          </div>

          <div className="space-y-2">
            {objects.length === 0 && <p className="text-xs text-slate-500">No custom objects yet.</p>}
            {objects.map((o) => (
              <div key={o.id}
                   className={`flex items-center justify-between gap-2 p-3 rounded-xl border cursor-pointer transition ${
                     selected?.id === o.id ? 'bg-brand-500/10 border-brand-500/50' : 'bg-slate-900 border-slate-800 hover:border-slate-700'
                   }`}
                   onClick={() => setSelected(o)}>
                <span className="text-sm text-slate-200">{o.label} <span className="text-slate-500 text-xs">({o.key})</span></span>
                <button onClick={(e) => { e.stopPropagation(); deleteObject(o); }} className="p-1 text-slate-500 hover:text-red-400"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>
        </div>

        {/* Selected object detail */}
        <div className="lg:col-span-2">
          {selected ? <ObjectDetail object={selected} /> : (
            <div className="h-full flex items-center justify-center text-sm text-slate-500 border border-dashed border-slate-800 rounded-2xl p-10">
              Select an object to manage its fields and records.
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

// ── Selected object: fields manager + records table ─────────────────────────────

const ObjectDetail: React.FC<{ object: CustomObjectDefinition }> = ({ object }) => {
  const [defs, setDefs] = useState<CustomFieldDefinition[]>([]);
  const [records, setRecords] = useState<CustomObjectRecord[]>([]);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<CustomObjectRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  // field creator
  const [fKey, setFKey] = useState('');
  const [fLabel, setFLabel] = useState('');
  const [fType, setFType] = useState('text');
  const [fOptions, setFOptions] = useState('');

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setDefs((await metadataApi.listCustomFields(object.key)).filter((d) => d.is_active));
      const res = await objectApi.listRecords(object.key, { pageSize: 50 });
      setRecords(res.items);
    } catch { /* silent */ } finally { setLoading(false); }
  }, [object.key]);

  useEffect(() => { load(); }, [load]);

  const addField = async () => {
    if (!fKey.trim() || !fLabel.trim()) return;
    setError(null);
    try {
      await metadataApi.createCustomField({
        key: fKey.trim().toLowerCase(),
        label: fLabel.trim(),
        field_type: fType,
        options: OPTION_TYPES.includes(fType) ? fOptions.split(',').map((o) => o.trim()).filter(Boolean) : undefined,
      }, object.key);
      setFKey(''); setFLabel(''); setFOptions('');
      await load();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to add field');
    }
  };

  const deleteRecord = async (rec: CustomObjectRecord) => {
    await objectApi.deleteRecord(object.key, rec.id);
    await load();
  };

  return (
    <div className="space-y-5">
      <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
        <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Fields — {object.label}</p>
        <div className="flex flex-wrap gap-2 items-center">
          <input value={fKey} onChange={(e) => setFKey(e.target.value.toLowerCase().replace(/[^a-z0-9_]/g, '_'))} placeholder="key" className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 w-28" />
          <input value={fLabel} onChange={(e) => setFLabel(e.target.value)} placeholder="Label" className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 w-32" />
          <select value={fType} onChange={(e) => setFType(e.target.value)} className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200">
            {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
          </select>
          {OPTION_TYPES.includes(fType) && (
            <input value={fOptions} onChange={(e) => setFOptions(e.target.value)} placeholder="comma,options" className="px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 w-40" />
          )}
          <button onClick={addField} className="flex items-center gap-1 px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold"><Plus className="w-3.5 h-3.5" /> Field</button>
        </div>
        <div className="flex flex-wrap gap-2">
          {defs.map((d) => <span key={d.id} className="text-[11px] px-2 py-1 rounded bg-slate-800/60 text-slate-300">{d.label} · {d.field_type}</span>)}
        </div>
        {error && <p className="text-xs text-red-400">{error}</p>}
      </div>

      <div className="p-4 bg-slate-900 border border-slate-800 rounded-2xl space-y-3">
        <div className="flex items-center justify-between">
          <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Records</p>
          <button onClick={() => { setEditing(null); setFormOpen(true); }} disabled={defs.length === 0}
                  className="flex items-center gap-1 px-3 py-1.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-40 text-white rounded-lg text-xs font-semibold">
            <Plus className="w-3.5 h-3.5" /> Add Record
          </button>
        </div>
        {loading ? <Loader2 className="w-4 h-4 animate-spin text-slate-500" /> : records.length === 0 ? (
          <p className="text-xs text-slate-500">No records yet.</p>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-xs">
              <thead>
                <tr className="text-slate-500 text-left">
                  {defs.map((d) => <th key={d.id} className="px-2 py-1.5 font-semibold">{d.label}</th>)}
                  <th className="px-2 py-1.5"></th>
                </tr>
              </thead>
              <tbody>
                {records.map((r) => (
                  <tr key={r.id} className="border-t border-slate-800/60 text-slate-300">
                    {defs.map((d) => <td key={d.id} className="px-2 py-1.5">{formatCell(r.data?.[d.key])}</td>)}
                    <td className="px-2 py-1.5 text-right whitespace-nowrap">
                      <button onClick={() => { setEditing(r); setFormOpen(true); }} className="p-1 text-slate-500 hover:text-brand-400"><Pencil className="w-3.5 h-3.5" /></button>
                      <button onClick={() => deleteRecord(r)} className="p-1 text-slate-500 hover:text-red-400"><Trash2 className="w-3.5 h-3.5" /></button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      <RecordFormModal
        objectKey={object.key}
        objectLabel={object.label}
        record={editing}
        isOpen={formOpen}
        onClose={() => setFormOpen(false)}
        onSaved={load}
      />
    </div>
  );
};

function formatCell(v: any): string {
  if (v === null || v === undefined || v === '') return '—';
  if (Array.isArray(v)) return v.join(', ');
  if (typeof v === 'boolean') return v ? 'Yes' : 'No';
  return String(v);
}
