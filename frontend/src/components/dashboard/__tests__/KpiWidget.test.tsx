// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { KpiWidget } from '../KpiWidget';
import { kpiApi } from '../../../services/kpiApi';

vi.mock('../../../services/kpiApi', () => ({ kpiApi: { dashboard: vi.fn() } }));

const DASH = {
  summary: { total: 8, on_track: 5, warning: 2, critical: 1, unknown: 0 },
  open_alerts: 3, kpis: [], by_category: {},
};

describe('KpiWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><KpiWidget /></BrowserRouter>);

  it('renders on-track ratio, critical count and open alerts', async () => {
    vi.mocked(kpiApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('KPIs')).toBeDefined());
    expect(screen.getByText('5/8')).toBeDefined();
    expect(screen.getByText('3')).toBeDefined();
  });

  it('shows an empty state when no KPIs exist', async () => {
    vi.mocked(kpiApi.dashboard).mockResolvedValue({ summary: { total: 0, on_track: 0, warning: 0, critical: 0, unknown: 0 }, open_alerts: 0, kpis: [], by_category: {} } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/Create a KPI/)).toBeDefined());
  });
});
