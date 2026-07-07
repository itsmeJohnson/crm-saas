// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ReportBuilderWidget } from '../ReportBuilderWidget';
import { reportBuilderApi } from '../../../services/reportBuilderApi';

vi.mock('../../../services/reportBuilderApi', () => ({
  reportBuilderApi: { dashboard: vi.fn() },
}));

describe('ReportBuilderWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><ReportBuilderWidget /></BrowserRouter>);

  it('renders pinned reports with their row counts', async () => {
    vi.mocked(reportBuilderApi.dashboard).mockResolvedValue({
      reports: [{ id: '1', name: 'Leads by status', total: 42 }, { id: '2', name: 'Overdue invoices', total: 7 }],
    } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Pinned Reports')).toBeDefined());
    expect(screen.getByText('Leads by status')).toBeDefined();
    expect(screen.getByText('42')).toBeDefined();
  });

  it('shows an empty state when nothing is pinned', async () => {
    vi.mocked(reportBuilderApi.dashboard).mockResolvedValue({ reports: [] } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/Pin a report/)).toBeDefined());
  });
});
