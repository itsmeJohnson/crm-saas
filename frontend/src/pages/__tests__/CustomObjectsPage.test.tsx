// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { CustomObjectsPage } from '../CustomObjectsPage';
import { objectApi } from '../../services/objectApi';

vi.mock('../../services/objectApi', () => ({
  objectApi: {
    listObjects: vi.fn().mockResolvedValue([]),
    createObject: vi.fn().mockResolvedValue({}),
    deleteObject: vi.fn().mockResolvedValue({}),
    listRecords: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, page_size: 50 }),
  },
}));
vi.mock('../../store/metadataStore', () => ({
  useMetadataStore: () => ({ refresh: vi.fn().mockResolvedValue(undefined) }),
}));

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(cleanup);

describe('CustomObjectsPage', () => {
  it('lists objects and creates a new object with a lowercased key', async () => {
    (objectApi.listObjects as any).mockResolvedValue([
      { id: 'o1', key: 'property', label: 'Property', is_active: true, is_system: false,
        label_plural: null, description: null, icon: null, color: null, display_field_key: null,
        organization_id: 'org', created_at: '', updated_at: '' },
    ]);
    render(<CustomObjectsPage />);
    await waitFor(() => expect(screen.getByText(/Property/)).toBeTruthy());

    fireEvent.change(screen.getByPlaceholderText('key (e.g. property)'), { target: { value: 'Policy' } });
    fireEvent.change(screen.getByPlaceholderText('Label (e.g. Property)'), { target: { value: 'Policy' } });
    fireEvent.click(screen.getByText('Create Object'));

    await waitFor(() => expect(objectApi.createObject).toHaveBeenCalledWith({ key: 'policy', label: 'Policy' }));
  });

  it('surfaces a delete-protection error from the API', async () => {
    (objectApi.listObjects as any).mockResolvedValue([
      { id: 'o1', key: 'property', label: 'Property', is_active: true, is_system: false,
        label_plural: null, description: null, icon: null, color: null, display_field_key: null,
        organization_id: 'org', created_at: '', updated_at: '' },
    ]);
    (objectApi.deleteObject as any).mockRejectedValueOnce({
      response: { data: { detail: "Cannot delete object 'Property': it still has 3 record(s)." } },
    });
    render(<CustomObjectsPage />);
    await waitFor(() => expect(screen.getByText(/Property/)).toBeTruthy());
    // delete button lives inside the object's row, next to its label
    const row = screen.getByText(/Property/).closest('div')!;
    const trash = row.querySelector('button')!;
    fireEvent.click(trash);
    await waitFor(() => expect(screen.getByText(/still has 3 record/)).toBeTruthy());
  });
});
