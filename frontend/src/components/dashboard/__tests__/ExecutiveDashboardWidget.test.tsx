// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ExecutiveDashboardWidget } from '../ExecutiveDashboardWidget';
import { executiveDashboardApi } from '../../../services/executiveDashboardApi';

vi.mock('../../../services/executiveDashboardApi', () => ({
  executiveDashboardApi: { dashboard: vi.fn() },
}));

const DASH = {
  persona: 'ceo', scope: 'organization', from: '2026-06-01', to: '2026-07-01',
  generated_at: new Date().toISOString(), widgets: ['revenue', 'forecast', 'sla_compliance', 'ai_insights'],
  blocks: {
    revenue: { revenue: 250000 },
    forecast: { projected_total: 400000 },
    sla_compliance: { compliance_rate: 92 },
    ai_insights: { ai_ready: true, insights: [{ severity: 'warning', title: 'Low conversion', detail: 'Conversion is 15%.' }] },
  },
};

describe('ExecutiveDashboardWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><ExecutiveDashboardWidget /></BrowserRouter>);

  it('renders headline executive KPIs and the top AI insight', async () => {
    vi.mocked(executiveDashboardApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Executive')).toBeDefined());
    expect(screen.getByText('₹250,000')).toBeDefined();
    expect(screen.getByText('₹400,000')).toBeDefined();
    expect(screen.getByText('92%')).toBeDefined();
    expect(screen.getByText(/Low conversion/)).toBeDefined();
  });

  it('shows a loader before data resolves', async () => {
    vi.mocked(executiveDashboardApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
