// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { CustomFieldsManager } from '../CustomFieldsManager';
import { contactApi } from '../../../services/contactApi';

vi.mock('../../../services/contactApi', () => ({
  contactApi: {
    listCustomFields: vi.fn().mockResolvedValue([]),
    createCustomField: vi.fn().mockResolvedValue({}),
    deleteCustomField: vi.fn().mockResolvedValue({}),
  },
}));

afterEach(cleanup);
beforeEach(() => {
  vi.clearAllMocks();
});

const ALL_TYPES = [
  'text', 'textarea', 'number', 'currency', 'percentage', 'date', 'datetime',
  'boolean', 'email', 'phone', 'url', 'select', 'multiselect',
];

describe('CustomFieldsManager (admin builder)', () => {
  it('offers all 13 field types', async () => {
    render(<CustomFieldsManager isOpen onClose={vi.fn()} />);
    for (const t of ALL_TYPES) {
      expect(screen.getByRole('option', { name: t })).toBeTruthy();
    }
  });

  it('shows the options editor only for select/multiselect', () => {
    render(<CustomFieldsManager isOpen onClose={vi.fn()} />);
    const typeSelect = screen.getByRole('combobox');
    // default 'text' → no options input
    expect(screen.queryByPlaceholderText('comma,options')).toBeNull();
    fireEvent.change(typeSelect, { target: { value: 'select' } });
    expect(screen.getByPlaceholderText('comma,options')).toBeTruthy();
    fireEvent.change(typeSelect, { target: { value: 'multiselect' } });
    expect(screen.getByPlaceholderText('comma,options')).toBeTruthy();
    fireEvent.change(typeSelect, { target: { value: 'boolean' } });
    expect(screen.queryByPlaceholderText('comma,options')).toBeNull();
  });

  it('creates a select field with a normalized options array and lowercased key', async () => {
    render(<CustomFieldsManager isOpen onClose={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('key (e.g. loyalty)'), { target: { value: 'Property Type' } });
    fireEvent.change(screen.getByPlaceholderText('Label'), { target: { value: 'Property Type' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'select' } });
    fireEvent.change(screen.getByPlaceholderText('comma,options'), { target: { value: 'apartment, villa' } });
    fireEvent.click(screen.getByText('Add Field'));

    await waitFor(() => expect(contactApi.createCustomField).toHaveBeenCalled());
    const payload = (contactApi.createCustomField as any).mock.calls[0][0];
    expect(payload.key).toBe('property_type'); // sanitized to lowercase snake_case
    expect(payload.field_type).toBe('select');
    expect(payload.options).toEqual(['apartment', 'villa']);
  });

  it('omits options for non-option field types', async () => {
    render(<CustomFieldsManager isOpen onClose={vi.fn()} />);
    fireEvent.change(screen.getByPlaceholderText('key (e.g. loyalty)'), { target: { value: 'budget' } });
    fireEvent.change(screen.getByPlaceholderText('Label'), { target: { value: 'Budget' } });
    fireEvent.change(screen.getByRole('combobox'), { target: { value: 'currency' } });
    fireEvent.click(screen.getByText('Add Field'));

    await waitFor(() => expect(contactApi.createCustomField).toHaveBeenCalled());
    const payload = (contactApi.createCustomField as any).mock.calls[0][0];
    expect(payload.field_type).toBe('currency');
    expect(payload.options).toBeUndefined();
  });
});
