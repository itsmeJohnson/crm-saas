// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ForecastingWidget } from '../ForecastingWidget';
import { forecastingApi } from '../../../services/forecastingApi';

vi.mock('../../../services/forecastingApi', () => ({
  forecastingApi: { dashboard: vi.fn() },
}));

const DASH = {
  revenue: { next_month: 42000, history_avg: 38000, direction: 'up' },
  sales: { next_month: 30000, history_avg: 28000, direction: 'up' },
  leads: { next_month: 120, history_avg: 110, direction: 'up' },
  collections: { next_month: 35000, history_avg: 33000, direction: 'flat' },
  pipeline_expected_close: 88000, goals_on_track: 3, goals_total: 5,
};

describe('ForecastingWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><ForecastingWidget /></BrowserRouter>);

  it('renders next-month revenue, pipeline and goals', async () => {
    vi.mocked(forecastingApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Forecasting')).toBeDefined());
    expect(screen.getByText(/42,000/)).toBeDefined();
    expect(screen.getByText(/88,000/)).toBeDefined();
    expect(screen.getByText('3/5')).toBeDefined();
  });

  it('shows a loader before data resolves', async () => {
    vi.mocked(forecastingApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
