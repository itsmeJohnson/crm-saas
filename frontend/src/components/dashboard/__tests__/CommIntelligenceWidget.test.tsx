// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { CommIntelligenceWidget } from '../CommIntelligenceWidget';
import { commIntelligenceApi } from '../../../services/commIntelligenceApi';

vi.mock('../../../services/commIntelligenceApi', () => ({ commIntelligenceApi: { dashboard: vi.fn() } }));

const DASH = {
  days: 30, total: 84, sentiment: { positive: 50, neutral: 24, negative: 10 },
  positive_rate: 59.5, action_items: 33, by_intent: [], by_channel: {}, languages: [],
};

describe('CommIntelligenceWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><CommIntelligenceWidget /></BrowserRouter>);

  it('renders positive rate, negative count and action items', async () => {
    vi.mocked(commIntelligenceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Comm Intelligence')).toBeDefined());
    expect(screen.getByText('59.5%')).toBeDefined();
    expect(screen.getByText('10')).toBeDefined();
    expect(screen.getByText('33')).toBeDefined();
  });

  it('shows an empty state when there are no communications', async () => {
    vi.mocked(commIntelligenceApi.dashboard).mockResolvedValue({ ...DASH, total: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No communications to analyze/)).toBeDefined());
  });
});
