// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { FinancialAnalyticsWidget } from '../FinancialAnalyticsWidget';
import { financialAnalyticsApi } from '../../../services/financialAnalyticsApi';

vi.mock('../../../services/financialAnalyticsApi', () => ({
  financialAnalyticsApi: { dashboard: vi.fn() },
}));

const DASH = {
  revenue: 300000, collected: 250000, expenses: 80000, gross_profit: 220000, profit_margin: 73.3,
  outstanding: 50000, mrr: 12000, arr: 144000, churn_rate: 2.5,
};

describe('FinancialAnalyticsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><FinancialAnalyticsWidget /></BrowserRouter>);

  it('renders revenue, MRR and outstanding', async () => {
    vi.mocked(financialAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Financial Analytics')).toBeDefined());
    expect(screen.getByText('₹300,000')).toBeDefined();
    expect(screen.getByText('₹12,000')).toBeDefined();
    expect(screen.getByText('73.3%')).toBeDefined();
  });

  it('shows a loader before data resolves', async () => {
    vi.mocked(financialAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
