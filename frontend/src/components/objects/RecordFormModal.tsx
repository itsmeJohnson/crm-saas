import React, { useEffect, useState } from 'react';
import { X, Loader2 } from 'lucide-react';
import { metadataApi, CustomFieldDefinition } from '../../services/metadataApi';
import { objectApi, CustomObjectRecord } from '../../services/objectApi';
import { formApi, FormDefinition, pickForm } from '../../services/formApi';
import { FormRenderer } from '../forms/FormRenderer';

interface Props {
  objectKey: string;
  objectLabel: string;
  record?: CustomObjectRecord | null;
  isOpen: boolean;
  onClose: () => void;
  onSaved: () => void;
}

/** Create/edit a custom-object record. The form is the SHARED DynamicCustomFields
 *  renderer driven by the object's own field definitions (loaded lazily). */
export const RecordFormModal: React.FC<Props> = ({ objectKey, objectLabel, record, isOpen, onClose, onSaved }) => {
  const [definitions, setDefinitions] = useState<CustomFieldDefinition[]>([]);
  const [form, setForm] = useState<FormDefinition | null>(null);
  const [values, setValues] = useState<Record<string, any>>({});
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [error, setError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isOpen) return;
    setValues(record?.data ?? {});
    setError(null);
    setErrors({});
    metadataApi.listCustomFields(objectKey).then((d) => setDefinitions(d.filter((f) => f.is_active))).catch(() => {});
    // Use a Dynamic Form when one is configured; otherwise fall back to the
    // default layout (all visible+active fields). Failure to load = fallback.
    formApi.listForms(objectKey).then((forms) => setForm(pickForm(forms))).catch(() => setForm(null));
  }, [isOpen, objectKey, record]);

  if (!isOpen) return null;

  const save = async () => {
    setSaving(true);
    setError(null);
    try {
      if (record) await objectApi.updateRecord(objectKey, record.id, values);
      else await objectApi.createRecord(objectKey, values);
      onSaved();
      onClose();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to save record');
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-lg font-bold text-slate-100">{record ? 'Edit' : 'New'} {objectLabel}</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
        </div>

        {definitions.length === 0 ? (
          <p className="text-xs text-slate-500">No fields defined for this object yet. Add fields first.</p>
        ) : (
          <FormRenderer
            definitions={definitions}
            form={form}
            values={values}
            errors={errors}
            onChange={(k, v) => setValues((p) => ({ ...p, [k]: v }))}
          />
        )}

        {error && <p className="text-xs text-red-400">{error}</p>}

        <div className="flex justify-end gap-3 pt-4 border-t border-slate-800">
          <button onClick={onClose} className="px-5 py-2.5 border border-slate-800 hover:border-slate-700 rounded-xl text-sm font-semibold text-slate-300">Cancel</button>
          <button
            onClick={save}
            disabled={saving || definitions.length === 0}
            className="flex items-center gap-2 px-5 py-2.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-xl text-sm font-semibold"
          >
            {saving && <Loader2 className="w-4 h-4 animate-spin" />}
            Save
          </button>
        </div>
      </div>
    </div>
  );
};
