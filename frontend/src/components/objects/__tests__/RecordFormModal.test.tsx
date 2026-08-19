// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { RecordFormModal } from '../RecordFormModal';
import { metadataApi } from '../../../services/metadataApi';
import { objectApi } from '../../../services/objectApi';

vi.mock('../../../services/metadataApi', async (orig) => {
  const actual: any = await orig();
  return { ...actual, metadataApi: { listCustomFields: vi.fn() } };
});
vi.mock('../../../services/objectApi', () => ({
  objectApi: { createRecord: vi.fn().mockResolvedValue({}), updateRecord: vi.fn().mockResolvedValue({}) },
}));

const def = (over: any) => ({
  id: 'd1', organization_id: 'o', entity_type: 'property', key: 'city', label: 'City',
  field_type: 'text', options: null, placeholder: null, description: null, default_value: null,
  validation_rules: null, section: null, is_active: true, read_only: false, visible: true,
  searchable: true, filterable: true, exportable: true, importable: true,
  created_at: '2026-01-01', updated_at: '2026-01-01', ...over,
});

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(cleanup);

describe('RecordFormModal', () => {
  it('loads object field definitions and creates a record on save', async () => {
    (metadataApi.listCustomFields as any).mockResolvedValue([def({})]);
    const onSaved = vi.fn();
    render(
      <RecordFormModal objectKey="property" objectLabel="Property" isOpen onClose={vi.fn()} onSaved={onSaved} />,
    );
    // waits for the lazily-loaded field to render
    await waitFor(() => expect(screen.getByText('City')).toBeTruthy());
    fireEvent.change(screen.getByRole('textbox'), { target: { value: 'Bangalore' } });
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(objectApi.createRecord).toHaveBeenCalledWith('property', { city: 'Bangalore' }));
    await waitFor(() => expect(onSaved).toHaveBeenCalled());
  });

  it('shows a server validation error and does not close', async () => {
    (metadataApi.listCustomFields as any).mockResolvedValue([def({})]);
    (objectApi.createRecord as any).mockRejectedValueOnce({ response: { data: { detail: 'City is required' } } });
    render(
      <RecordFormModal objectKey="property" objectLabel="Property" isOpen onClose={vi.fn()} onSaved={vi.fn()} />,
    );
    await waitFor(() => expect(screen.getByText('City')).toBeTruthy());
    fireEvent.click(screen.getByText('Save'));
    await waitFor(() => expect(screen.getByText('City is required')).toBeTruthy());
  });
});
