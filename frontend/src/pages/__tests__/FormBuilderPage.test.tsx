// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { FormBuilderPage } from '../FormBuilderPage';
import { metadataApi } from '../../services/metadataApi';
import { formApi } from '../../services/formApi';

vi.mock('../../services/metadataApi', async (orig) => {
  const actual: any = await orig();
  return { ...actual, metadataApi: { listCustomFields: vi.fn() } };
});
vi.mock('../../services/formApi', async (orig) => {
  const actual: any = await orig();
  return { ...actual, formApi: { listForms: vi.fn(), createForm: vi.fn().mockResolvedValue({}), deleteForm: vi.fn(), updateForm: vi.fn() } };
});
vi.mock('../../store/metadataStore', () => ({
  useMetadataStore: () => ({ customObjects: [] }),
}));

const def = (key: string) => ({
  id: key, organization_id: 'o', entity_type: 'lead', key, label: key.toUpperCase(),
  field_type: 'text', options: null, placeholder: null, description: null, default_value: null,
  validation_rules: null, section: null, is_active: true, read_only: false, visible: true,
  searchable: true, filterable: true, exportable: true, importable: true, created_at: '', updated_at: '',
});

beforeEach(() => {
  vi.clearAllMocks();
});
afterEach(cleanup);

describe('FormBuilderPage', () => {
  it('builds a form schema from selected fields and creates it', async () => {
    (metadataApi.listCustomFields as any).mockResolvedValue([def('budget'), def('notes')]);
    (formApi.listForms as any).mockResolvedValue([]);
    render(<FormBuilderPage />);

    await waitFor(() => expect(screen.getByText('+ BUDGET')).toBeTruthy());
    fireEvent.click(screen.getByText('+ BUDGET'));            // add field to layout
    fireEvent.change(screen.getByPlaceholderText('key (e.g. create_form)'), { target: { value: 'Lead Form' } });
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: 'Lead Form' } });
    fireEvent.click(screen.getByText('Create Form'));

    await waitFor(() => expect(formApi.createForm).toHaveBeenCalled());
    const [entity, payload] = (formApi.createForm as any).mock.calls[0];
    expect(entity).toBe('lead');
    expect(payload.key).toBe('lead_form');                    // sanitized
    expect(payload.schema.sections[0].fields[0].key).toBe('budget');
  });

  it('surfaces a server validation error', async () => {
    (metadataApi.listCustomFields as any).mockResolvedValue([def('budget')]);
    (formApi.listForms as any).mockResolvedValue([]);
    (formApi.createForm as any).mockRejectedValueOnce({ response: { data: { detail: "Unknown or inactive field 'x'" } } });
    render(<FormBuilderPage />);
    await waitFor(() => expect(screen.getByText('+ BUDGET')).toBeTruthy());
    fireEvent.click(screen.getByText('+ BUDGET'));
    fireEvent.change(screen.getByPlaceholderText('key (e.g. create_form)'), { target: { value: 'lf' } });
    fireEvent.change(screen.getByPlaceholderText('Name'), { target: { value: 'LF' } });
    fireEvent.click(screen.getByText('Create Form'));
    await waitFor(() => expect(screen.getByText(/Unknown or inactive field/)).toBeTruthy());
  });
});
