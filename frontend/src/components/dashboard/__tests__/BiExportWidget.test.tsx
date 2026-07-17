// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { BiExportWidget } from '../BiExportWidget';
import { biApi } from '../../../services/biApi';

vi.mock('../../../services/biApi', () => ({ biApi: { dashboard: vi.fn() } }));

const DASH = {
  active_tokens: 2, active_syncs: 3, exports: 42, failed: 1,
  success_rate: 97.6, by_kind: { download: 30, webhook: 6, cloud: 3, sync: 3 }, recent: [],
};

describe('BiExportWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><BiExportWidget /></BrowserRouter>);

  it('renders export, token and sync counts', async () => {
    vi.mocked(biApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Export & BI')).toBeDefined());
    expect(screen.getByText('42')).toBeDefined();
    expect(screen.getByText('2')).toBeDefined();
    expect(screen.getByText('3')).toBeDefined();
  });

  it('shows an empty state when nothing is configured', async () => {
    vi.mocked(biApi.dashboard).mockResolvedValue({ ...DASH, exports: 0, active_tokens: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/create a BI feed token/i)).toBeDefined());
  });
});
