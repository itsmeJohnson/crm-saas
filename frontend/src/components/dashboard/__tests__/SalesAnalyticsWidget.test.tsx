// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { SalesAnalyticsWidget } from '../SalesAnalyticsWidget';
import { salesAnalyticsApi } from '../../../services/salesAnalyticsApi';

vi.mock('../../../services/salesAnalyticsApi', () => ({
  salesAnalyticsApi: { dashboard: vi.fn() },
}));

const DASH = {
  revenue: 125000, win_rate: 48.5, conversion_rate: 32, avg_deal_size: 5000,
  sales_velocity: 8200, pipeline_value: 300000, won: 25, open: 40,
};

describe('SalesAnalyticsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><SalesAnalyticsWidget /></BrowserRouter>);

  it('renders revenue, win rate and velocity', async () => {
    vi.mocked(salesAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Sales Analytics')).toBeDefined());
    expect(screen.getByText('₹125,000')).toBeDefined();
    expect(screen.getByText('48.5%')).toBeDefined();
    expect(screen.getByText('₹8,200')).toBeDefined();
  });

  it('shows a loader before data resolves', async () => {
    vi.mocked(salesAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
