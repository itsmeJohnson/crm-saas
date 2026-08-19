import React, { useEffect, useState } from 'react';
import { metadataApi, CustomFieldDefinition } from '../../services/metadataApi';
import { useMetadataStore } from '../../store/metadataStore';
import { X, Plus, Trash2, Loader2 } from 'lucide-react';

const FIELD_TYPES = [
  'text', 'textarea', 'number', 'currency', 'percentage', 'date', 'datetime',
  'boolean', 'email', 'phone', 'url', 'select', 'multiselect',
];
const OPTION_TYPES = ['select', 'multiselect'];

export const LeadCustomFieldsManager: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const { refresh } = useMetadataStore();
  const [defs, setDefs] = useState<CustomFieldDefinition[]>([]);
  const [key, setKey] = useState('');
  const [label, setLabel] = useState('');
  const [fieldType, setFieldType] = useState('text');
  const [options, setOptions] = useState('');
  const [required, setRequired] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setDefs(await metadataApi.listCustomFields('lead'));
    } catch {
      /* silent */
    }
  };

  useEffect(() => {
    if (isOpen) load();
  }, [isOpen]);

  if (!isOpen) return null;

  const handleCreate = async () => {
    if (!key.trim() || !label.trim()) return;
    setError(null);
    setSaving(true);
    try {
      await metadataApi.createCustomField(
        {
          key: key.trim().toLowerCase(),
          label: label.trim(),
          field_type: fieldType,
          options: OPTION_TYPES.includes(fieldType) ? options.split(',').map((o) => o.trim()).filter(Boolean) : undefined,
          validation_rules: required ? { required: true } : undefined,
        },
        'lead',
      );
      setKey('');
      setLabel('');
      setOptions('');
      setRequired(false);
      await load();
      await refresh(); // propagate new field into forms/filters/kanban immediately
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to create field');
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async (id: string) => {
    await metadataApi.deleteCustomField(id);
    await load();
    await refresh();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-lg font-bold text-slate-100">Lead Custom Fields</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
        </div>

        <p className="text-xs text-slate-400">
          Fields you define here appear automatically on the lead form, import mapping, filters, and export for your organization.
        </p>

        <div className="space-y-2 p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
          <div className="grid grid-cols-2 gap-2">
            <input value={key} onChange={(e) => setKey(e.target.value.replace(/[^a-zA-Z0-9_]/g, '_').toLowerCase())} placeholder="key (e.g. doctor)" className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200" />
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label (e.g. Doctor)" className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <select value={fieldType} onChange={(e) => setFieldType(e.target.value)} className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200">
              {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            {OPTION_TYPES.includes(fieldType) && (
              <input value={options} onChange={(e) => setOptions(e.target.value)} placeholder="comma,separated,options" className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200" />
            )}
          </div>
          <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer select-none">
            <input type="checkbox" checked={required} onChange={(e) => setRequired(e.target.checked)} className="accent-brand-500" />
            Required field
          </label>
          <button onClick={handleCreate} disabled={saving || !key.trim() || !label.trim()} className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-lg text-xs font-semibold cursor-pointer">
            {saving ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Plus className="w-3.5 h-3.5" />} Add Field
          </button>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>

        {defs.length === 0 ? (
          <p className="text-xs text-slate-500">No custom fields defined yet.</p>
        ) : (
          <ul className="space-y-2 max-h-60 overflow-y-auto">
            {defs.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">
                <span className="text-xs text-slate-200 truncate">
                  {d.label} <span className="text-slate-500">({d.key} · {d.field_type}{d.validation_rules?.required ? ' · required' : ''})</span>
                </span>
                <button onClick={() => handleDelete(d.id)} className="p-1 text-slate-500 hover:text-red-400 cursor-pointer shrink-0"><Trash2 className="w-3.5 h-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
