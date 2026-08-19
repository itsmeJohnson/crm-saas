import React from 'react';
import { CustomFieldDefinition, normalizeFieldOptions } from '../../services/metadataApi';

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

    const options = normalizeFieldOptions(def.options);
    const isBoolean = def.field_type === 'boolean' || def.field_type === 'checkbox';
    // HTML input `type` for the simple textual variants.
    const textInputType: Record<string, string> = {
      email: 'email',
      phone: 'tel',
      url: 'url',
      datetime: 'datetime-local',
    };

    let control: React.ReactNode;
    switch (def.field_type) {
      case 'boolean':
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
      case 'textarea':
        control = (
          <textarea
            value={val ?? ''}
            disabled={disabled}
            rows={3}
            placeholder={def.placeholder || ''}
            onChange={(e) => onChange(def.key, e.target.value)}
            className={`${inputCls} resize-y ${err ? 'border-red-500/50' : ''}`}
          />
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
            {options.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </select>
        );
        break;
      case 'multiselect': {
        const selected: string[] = Array.isArray(val) ? val : val ? [val] : [];
        const toggle = (optValue: string) => {
          const next = selected.includes(optValue)
            ? selected.filter((v) => v !== optValue)
            : [...selected, optValue];
          onChange(def.key, next);
        };
        control = (
          <div className="flex flex-wrap gap-2">
            {options.map((opt) => {
              const active = selected.includes(opt.value);
              return (
                <button
                  type="button"
                  key={opt.value}
                  disabled={disabled}
                  onClick={() => toggle(opt.value)}
                  className={`px-3 py-1.5 rounded-lg text-xs border transition ${
                    active
                      ? 'bg-brand-500/20 border-brand-500/60 text-brand-200'
                      : 'bg-slate-900 border-slate-800 text-slate-300 hover:border-slate-600'
                  }`}
                >
                  {opt.label}
                </button>
              );
            })}
          </div>
        );
        break;
      }
      case 'number':
      case 'currency':
      case 'percentage':
        control = (
          <div className="relative">
            {def.field_type === 'currency' && (
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">₹</span>
            )}
            <input
              type="number"
              step="any"
              value={val ?? ''}
              disabled={disabled}
              placeholder={def.placeholder || ''}
              onChange={(e) => onChange(def.key, e.target.value === '' ? null : Number(e.target.value))}
              className={`${inputCls} ${def.field_type === 'currency' ? 'pl-8' : ''} ${
                def.field_type === 'percentage' ? 'pr-8' : ''
              } ${err ? 'border-red-500/50' : ''}`}
            />
            {def.field_type === 'percentage' && (
              <span className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-500 text-sm">%</span>
            )}
          </div>
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
        // text, textarea handled above; email/phone/url/datetime + text fall here.
        control = (
          <input
            type={textInputType[def.field_type] || 'text'}
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
        {!isBoolean && (
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
