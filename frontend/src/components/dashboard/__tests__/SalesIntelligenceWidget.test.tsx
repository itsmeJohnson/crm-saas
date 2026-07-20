// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { SalesIntelligenceWidget } from '../SalesIntelligenceWidget';
import { salesIntelligenceApi } from '../../../services/salesIntelligenceApi';

vi.mock('../../../services/salesIntelligenceApi', () => ({ salesIntelligenceApi: { dashboard: vi.fn() } }));

const DASH = {
  open_deals: 18, open_pipeline_value: 900000, weighted_pipeline_value: 320000,
  avg_win_probability: 44.2, by_health: { strong: 5, moderate: 9, at_risk: 4 },
  top_deals: [], at_risk_deals: [], revenue_forecast_next3: [],
};

describe('SalesIntelligenceWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><SalesIntelligenceWidget /></BrowserRouter>);

  it('renders deals, weighted pipeline and at-risk count', async () => {
    vi.mocked(salesIntelligenceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Sales Intelligence')).toBeDefined());
    expect(screen.getByText('18')).toBeDefined();
    expect(screen.getByText('₹320,000')).toBeDefined();
    expect(screen.getByText('4')).toBeDefined();
  });

  it('shows an empty state when there are no open deals', async () => {
    vi.mocked(salesIntelligenceApi.dashboard).mockResolvedValue({ ...DASH, open_deals: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No open deals to analyze/)).toBeDefined());
  });
});
