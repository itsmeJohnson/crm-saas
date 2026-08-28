import React from 'react';
import { CustomFieldDefinition } from '../../services/metadataApi';
import { FormDefinition } from '../../services/formApi';
import { DynamicCustomFields } from '../crm/DynamicCustomFields';

interface Props {
  /** All active field definitions for the entity (the field catalog). */
  definitions: CustomFieldDefinition[];
  /** The form to apply. When null/undefined, falls back to the default layout. */
  form?: FormDefinition | null;
  values: Record<string, any>;
  onChange: (key: string, value: any) => void;
  errors?: Record<string, string>;
}

/**
 * Runtime renderer for a Dynamic Form. It does NOT re-implement field rendering —
 * it reorders/regroups the entity's field definitions per the form schema and
 * applies per-form overrides (required / hidden / read_only), then hands the
 * result to the SHARED DynamicCustomFields renderer.
 *
 * When no form is supplied, it renders the definitions unchanged — preserving the
 * exact pre-Dynamic-Forms behavior (backward compatible).
 */
export const FormRenderer: React.FC<Props> = ({ definitions, form, values, onChange, errors }) => {
  const laidOut = React.useMemo(
    () => (form ? applyForm(definitions, form) : definitions),
    [definitions, form],
  );
  return <DynamicCustomFields definitions={laidOut} values={values} onChange={onChange} errors={errors} />;
};

/** Build an ordered, section-grouped, override-applied definition list from a form. */
export function applyForm(
  definitions: CustomFieldDefinition[],
  form: FormDefinition,
): CustomFieldDefinition[] {
  const byKey = new Map(definitions.map((d) => [d.key, d]));
  const out: CustomFieldDefinition[] = [];
  const sections = form.schema?.sections ?? [];
  for (const section of sections) {
    for (const entry of section.fields ?? []) {
      const base = byKey.get(entry.key);
      if (!base) continue; // key not (or no longer) an active field — skip safely
      if (entry.hidden) continue; // per-form hide
      out.push({
        ...base,
        section: section.title ?? base.section ?? null,
        read_only: entry.read_only ?? base.read_only,
        validation_rules:
          entry.required != null
            ? { ...(base.validation_rules ?? {}), required: entry.required }
            : base.validation_rules,
      });
    }
  }
  return out;
}
