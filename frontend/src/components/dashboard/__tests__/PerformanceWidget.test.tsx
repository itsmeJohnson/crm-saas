// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { PerformanceWidget } from '../PerformanceWidget';
import { performanceApi } from '../../../services/performanceApi';

vi.mock('../../../services/performanceApi', () => ({ performanceApi: { dashboard: vi.fn() } }));

const DASH = {
  my_metrics: { sales_revenue: 125000, calls_made: 40, leads_converted: 6 },
  my_composite_score: 82.5, my_open_goals: 3, my_achievements: 4,
  top_sales: [{ rank: 1, user_id: 'u1', name: 'Asha', value: 200000 }],
};

describe('PerformanceWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><PerformanceWidget /></BrowserRouter>);

  it('renders composite score, revenue, open goals and achievements', async () => {
    vi.mocked(performanceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Performance')).toBeDefined());
    expect(screen.getByText('82.5%')).toBeDefined();     // composite score
    expect(screen.getByText('3')).toBeDefined();          // open goals
    expect(screen.getByText('4')).toBeDefined();          // achievements
  });

  it('shows a dash when there is no composite score', async () => {
    vi.mocked(performanceApi.dashboard).mockResolvedValue({ ...DASH, my_composite_score: null } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Performance')).toBeDefined());
    expect(screen.getByText('—')).toBeDefined();
  });
});
