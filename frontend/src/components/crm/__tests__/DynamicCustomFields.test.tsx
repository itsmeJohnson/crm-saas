// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { DynamicCustomFields } from '../DynamicCustomFields';
import { CustomFieldDefinition } from '../../../services/metadataApi';

afterEach(cleanup);

const def = (over: Partial<CustomFieldDefinition>): CustomFieldDefinition => ({
  id: over.key || 'id-' + Math.random(),
  organization_id: 'org-1',
  entity_type: 'lead',
  key: 'field',
  label: 'Field',
  field_type: 'text',
  options: null,
  placeholder: null,
  description: null,
  default_value: null,
  validation_rules: null,
  section: null,
  is_active: true,
  read_only: false,
  visible: true,
  searchable: true,
  filterable: true,
  exportable: true,
  importable: true,
  created_at: '2026-01-01',
  updated_at: '2026-01-01',
  ...over,
});

const renderOne = (d: CustomFieldDefinition, extra: any = {}) =>
  render(<DynamicCustomFields definitions={[d]} values={{}} onChange={vi.fn()} {...extra} />);

describe('DynamicCustomFields renderer', () => {
  it('renders nothing when there are no visible/active fields', () => {
    const { container } = render(
      <DynamicCustomFields definitions={[def({ is_active: false })]} values={{}} onChange={vi.fn()} />,
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders a text input', () => {
    renderOne(def({ key: 'city', label: 'City', field_type: 'text' }));
    expect(screen.getByText('City')).toBeTruthy();
    expect(screen.getByRole('textbox')).toBeTruthy();
  });

  it('renders a textarea for textarea type', () => {
    const { container } = renderOne(def({ field_type: 'textarea' }));
    expect(container.querySelector('textarea')).toBeTruthy();
  });

  it('renders number/currency/percentage as numeric inputs', () => {
    for (const t of ['number', 'currency', 'percentage'] as const) {
      cleanup();
      const { container } = renderOne(def({ field_type: t }));
      expect(container.querySelector('input[type="number"]')).toBeTruthy();
    }
  });

  it('renders date and datetime pickers', () => {
    let c = renderOne(def({ field_type: 'date' })).container;
    expect(c.querySelector('input[type="date"]')).toBeTruthy();
    cleanup();
    c = renderOne(def({ field_type: 'datetime' })).container;
    expect(c.querySelector('input[type="datetime-local"]')).toBeTruthy();
  });

  it('renders email/phone/url with the right input types', () => {
    let c = renderOne(def({ field_type: 'email' })).container;
    expect(c.querySelector('input[type="email"]')).toBeTruthy();
    cleanup();
    c = renderOne(def({ field_type: 'phone' })).container;
    expect(c.querySelector('input[type="tel"]')).toBeTruthy();
    cleanup();
    c = renderOne(def({ field_type: 'url' })).container;
    expect(c.querySelector('input[type="url"]')).toBeTruthy();
  });

  it('renders boolean and legacy checkbox as a checkbox', () => {
    let c = renderOne(def({ field_type: 'boolean' })).container;
    expect(c.querySelector('input[type="checkbox"]')).toBeTruthy();
    cleanup();
    c = renderOne(def({ field_type: 'checkbox' })).container;
    expect(c.querySelector('input[type="checkbox"]')).toBeTruthy();
  });

  it('renders a select and coerces legacy string options', () => {
    renderOne(def({ field_type: 'select', options: ['gold', 'silver'] as any }));
    expect(screen.getByRole('combobox')).toBeTruthy();
    expect(screen.getByRole('option', { name: 'gold' })).toBeTruthy();
    expect(screen.getByRole('option', { name: 'silver' })).toBeTruthy();
  });

  it('renders {value,label} select options with labels', () => {
    renderOne(def({
      field_type: 'select',
      options: [{ value: 'apartment', label: 'Apartment' }] as any,
    }));
    expect(screen.getByRole('option', { name: 'Apartment' })).toBeTruthy();
  });

  it('renders multiselect as toggle buttons and reports selections', () => {
    const onChange = vi.fn();
    render(
      <DynamicCustomFields
        definitions={[def({ key: 'tags', field_type: 'multiselect', options: ['x', 'y'] as any })]}
        values={{ tags: [] }}
        onChange={onChange}
      />,
    );
    fireEvent.click(screen.getByRole('button', { name: 'x' }));
    expect(onChange).toHaveBeenCalledWith('tags', ['x']);
  });

  it('marks required fields with an asterisk', () => {
    renderOne(def({ label: 'Budget', validation_rules: { required: true } }));
    expect(screen.getByText('*')).toBeTruthy();
  });

  it('shows a validation error message', () => {
    renderOne(def({ key: 'budget', label: 'Budget' }), { errors: { budget: 'Budget must be at least 100000' } });
    expect(screen.getByText('Budget must be at least 100000')).toBeTruthy();
  });

  it('disables read-only fields', () => {
    const { container } = renderOne(def({ field_type: 'text', read_only: true }));
    expect(container.querySelector('input')?.disabled).toBe(true);
  });

  it('fires onChange when typing in a text field', () => {
    const onChange = vi.fn();
    render(
      <DynamicCustomFields definitions={[def({ key: 'city', field_type: 'text' })]} values={{}} onChange={onChange} />,
    );
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bangalore' } });
    expect(onChange).toHaveBeenCalledWith('city', 'Bangalore');
  });
});
