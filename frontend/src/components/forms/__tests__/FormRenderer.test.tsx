// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { FormRenderer, applyForm } from '../FormRenderer';
import { CustomFieldDefinition } from '../../../services/metadataApi';
import { FormDefinition } from '../../../services/formApi';

afterEach(cleanup);

const def = (key: string, over: Partial<CustomFieldDefinition> = {}): CustomFieldDefinition => ({
  id: key, organization_id: 'o', entity_type: 'property', key, label: key.toUpperCase(),
  field_type: 'text', options: null, placeholder: null, description: null, default_value: null,
  validation_rules: null, section: null, is_active: true, read_only: false, visible: true,
  searchable: true, filterable: true, exportable: true, importable: true,
  created_at: '', updated_at: '', ...over,
});

const form = (over: Partial<FormDefinition> = {}): FormDefinition => ({
  id: 'f', organization_id: 'o', entity_type: 'property', key: 'pf', name: 'PF',
  description: null, is_active: true, is_default: true, created_at: '', updated_at: '',
  schema: { sections: [] }, ...over,
});

describe('applyForm (Dynamic Form transform)', () => {
  const defs = [def('a'), def('b'), def('c')];

  it('orders fields per the form schema', () => {
    const f = form({ schema: { sections: [{ title: 'S', fields: [{ key: 'c' }, { key: 'a' }] }] } });
    expect(applyForm(defs, f).map((d) => d.key)).toEqual(['c', 'a']);
  });

  it('drops hidden fields', () => {
    const f = form({ schema: { sections: [{ fields: [{ key: 'a' }, { key: 'b', hidden: true }] }] } });
    expect(applyForm(defs, f).map((d) => d.key)).toEqual(['a']);
  });

  it('applies required + read_only + section overrides', () => {
    const f = form({ schema: { sections: [{ title: 'Basics', fields: [{ key: 'a', required: true, read_only: true }] }] } });
    const [out] = applyForm(defs, f);
    expect(out.validation_rules?.required).toBe(true);
    expect(out.read_only).toBe(true);
    expect(out.section).toBe('Basics');
  });

  it('skips keys not in the field catalog (safe)', () => {
    const f = form({ schema: { sections: [{ fields: [{ key: 'a' }, { key: 'ghost' }] }] } });
    expect(applyForm(defs, f).map((d) => d.key)).toEqual(['a']);
  });
});

describe('FormRenderer', () => {
  const defs = [def('a', { label: 'Alpha' }), def('b', { label: 'Beta' })];

  it('renders the form layout (ordered, hidden dropped)', () => {
    const f = form({ schema: { sections: [{ title: 'S', fields: [{ key: 'b' }, { key: 'a', required: true }] }] } });
    render(<FormRenderer definitions={defs} form={f} values={{}} onChange={vi.fn()} />);
    expect(screen.getByText('Beta')).toBeTruthy();
    expect(screen.getByText('Alpha')).toBeTruthy();
    expect(screen.getByText('*')).toBeTruthy(); // required override marker
  });

  it('falls back to all definitions when no form is set (backward compatible)', () => {
    render(<FormRenderer definitions={defs} form={null} values={{}} onChange={vi.fn()} />);
    expect(screen.getByText('Alpha')).toBeTruthy();
    expect(screen.getByText('Beta')).toBeTruthy();
  });
});
