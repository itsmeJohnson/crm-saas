import React from 'react';
import { CustomFieldDefinition } from '../../services/metadataApi';

interface DynamicCustomFieldsProps {
  definitions: CustomFieldDefinition[];
  values: Record<string, any>;
  onChange: (key: string, value: any) => void;
  errors?: Record<string, string>;
  /** Only render fields flagged importable/filterable/etc. Defaults to visible+active. */
  filter?: (def: CustomFieldDefinition) => boolean;
}

const labelCls = 'block text-xs font-semibold text-slate-300 uppercase tracking-wider mb-2';
const inputCls = 'w-full px-4 py-3 rounded-xl glass-input';
const selectCls =
  'w-full px-4 py-3 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50';

const isRequired = (def: CustomFieldDefinition) => def.validation_rules?.required === true;

export const DynamicCustomFields: React.FC<DynamicCustomFieldsProps> = ({
  definitions,
  values,
  onChange,
  errors = {},
  filter,
}) => {
  const visible = definitions.filter(
    (d) => d.is_active && d.visible && (filter ? filter(d) : true),
  );

  if (visible.length === 0) return null;

  // Group by section so tenant-defined layouts stay coherent.
  const sections = new Map<string, CustomFieldDefinition[]>();
  for (const def of visible) {
    const key = def.section || '';
    if (!sections.has(key)) sections.set(key, []);
    sections.get(key)!.push(def);
  }

  const renderField = (def: CustomFieldDefinition) => {
    const val = values[def.key];
    const err = errors[def.key];
    const required = isRequired(def);
    const disabled = def.read_only;

    let control: React.ReactNode;
    switch (def.field_type) {
      case 'checkbox':
        control = (
          <label className="inline-flex items-center gap-2 cursor-pointer select-none">
            <input
              type="checkbox"
              checked={!!val}
              disabled={disabled}
              onChange={(e) => onChange(def.key, e.target.checked)}
              className="w-4 h-4 rounded border-slate-700 bg-slate-900 text-brand-500 focus:ring-brand-500/50"
            />
            <span className="text-sm text-slate-300">{def.placeholder || def.label}</span>
          </label>
        );
        break;
      case 'select':
        control = (
          <select
            value={val ?? ''}
            disabled={disabled}
            onChange={(e) => onChange(def.key, e.target.value || null)}
            className={selectCls}
          >
            <option value="">{def.placeholder || 'Select…'}</option>
            {(def.options || []).map((opt) => (
              <option key={opt} value={opt}>
                {opt}
              </option>
            ))}
          </select>
        );
        break;
      case 'number':
        control = (
          <input
            type="number"
            step="any"
            value={val ?? ''}
            disabled={disabled}
            placeholder={def.placeholder || ''}
            onChange={(e) => onChange(def.key, e.target.value === '' ? null : Number(e.target.value))}
            className={`${inputCls} ${err ? 'border-red-500/50' : ''}`}
          />
        );
        break;
      case 'date':
        control = (
          <input
            type="date"
            value={val ?? ''}
            disabled={disabled}
            onChange={(e) => onChange(def.key, e.target.value || null)}
            className={`${inputCls} ${err ? 'border-red-500/50' : ''}`}
          />
        );
        break;
      default:
        control = (
          <input
            type="text"
            value={val ?? ''}
            disabled={disabled}
            placeholder={def.placeholder || ''}
            onChange={(e) => onChange(def.key, e.target.value)}
            className={`${inputCls} ${err ? 'border-red-500/50' : ''} ${disabled ? 'opacity-60 cursor-not-allowed' : ''}`}
          />
        );
    }

    return (
      <div key={def.id}>
        {def.field_type !== 'checkbox' && (
          <label className={labelCls}>
            {def.label} {required && <span className="text-red-400">*</span>}
          </label>
        )}
        {control}
        {def.description && !err && <p className="mt-1.5 text-xs text-slate-500">{def.description}</p>}
        {err && <p className="mt-1.5 text-xs text-red-400">{err}</p>}
      </div>
    );
  };

  return (
    <div className="space-y-5">
      {Array.from(sections.entries()).map(([section, defs]) => (
        <div key={section || '_default'} className="space-y-4">
          {section && (
            <h4 className="text-[11px] font-bold text-slate-400 uppercase tracking-wider pt-2 border-t border-slate-800/70">
              {section}
            </h4>
          )}
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">{defs.map(renderField)}</div>
        </div>
      ))}
    </div>
  );
};
