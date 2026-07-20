// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { LeadIntelligenceWidget } from '../LeadIntelligenceWidget';
import { leadIntelligenceApi } from '../../../services/leadIntelligenceApi';

vi.mock('../../../services/leadIntelligenceApi', () => ({ leadIntelligenceApi: { dashboard: vi.fn() } }));

const DASH = {
  total: 40, by_temperature: { hot: 7, warm: 20, cold: 13 }, by_quality: { A: 5, B: 15, C: 12, D: 8 },
  avg_score: 48.5, avg_completeness: 72.1, avg_conversion_probability: 41.3,
  hot_leads: [], at_risk_leads: [], needs_enrichment: [],
};

describe('LeadIntelligenceWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><LeadIntelligenceWidget /></BrowserRouter>);

  it('renders hot/cold counts and average conversion', async () => {
    vi.mocked(leadIntelligenceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Lead Intelligence')).toBeDefined());
    expect(screen.getByText('7')).toBeDefined();
    expect(screen.getByText('13')).toBeDefined();
    expect(screen.getByText('41.3%')).toBeDefined();
  });

  it('shows an empty state when there are no leads', async () => {
    vi.mocked(leadIntelligenceApi.dashboard).mockResolvedValue({ ...DASH, total: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No leads to analyze/)).toBeDefined());
  });
});
