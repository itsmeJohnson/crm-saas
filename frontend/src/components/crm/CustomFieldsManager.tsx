import React, { useEffect, useState } from 'react';
import { contactApi, CustomFieldDefinition } from '../../services/contactApi';
import { X, Plus, Trash2 } from 'lucide-react';

const FIELD_TYPES = ['text', 'number', 'date', 'select', 'checkbox'];

export const CustomFieldsManager: React.FC<{ isOpen: boolean; onClose: () => void }> = ({ isOpen, onClose }) => {
  const [defs, setDefs] = useState<CustomFieldDefinition[]>([]);
  const [key, setKey] = useState('');
  const [label, setLabel] = useState('');
  const [fieldType, setFieldType] = useState('text');
  const [options, setOptions] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setDefs(await contactApi.listCustomFields());
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
    try {
      await contactApi.createCustomField({
        key: key.trim(),
        label: label.trim(),
        field_type: fieldType,
        options: fieldType === 'select' ? options.split(',').map((o) => o.trim()).filter(Boolean) : undefined,
      });
      setKey('');
      setLabel('');
      setOptions('');
      await load();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to create field');
    }
  };

  const handleDelete = async (id: string) => {
    await contactApi.deleteCustomField(id);
    await load();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-5">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-lg font-bold text-slate-100">Contact Custom Fields</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
        </div>

        <div className="space-y-2 p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
          <div className="grid grid-cols-2 gap-2">
            <input value={key} onChange={(e) => setKey(e.target.value.replace(/[^a-zA-Z0-9_]/g, '_'))} placeholder="key (e.g. loyalty)" className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200" />
            <input value={label} onChange={(e) => setLabel(e.target.value)} placeholder="Label" className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200" />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <select value={fieldType} onChange={(e) => setFieldType(e.target.value)} className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200">
              {FIELD_TYPES.map((t) => <option key={t} value={t}>{t}</option>)}
            </select>
            {fieldType === 'select' && (
              <input value={options} onChange={(e) => setOptions(e.target.value)} placeholder="comma,options" className="px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200" />
            )}
          </div>
          <button onClick={handleCreate} className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold cursor-pointer">
            <Plus className="w-3.5 h-3.5" /> Add Field
          </button>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>

        {defs.length === 0 ? (
          <p className="text-xs text-slate-500">No custom fields defined.</p>
        ) : (
          <ul className="space-y-2 max-h-60 overflow-y-auto">
            {defs.map((d) => (
              <li key={d.id} className="flex items-center justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">
                <span className="text-xs text-slate-200 truncate">
                  {d.label} <span className="text-slate-500">({d.key} · {d.field_type})</span>
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
