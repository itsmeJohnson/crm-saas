// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { PredictiveWidget } from '../PredictiveWidget';
import { predictiveApi } from '../../../services/predictiveApi';

vi.mock('../../../services/predictiveApi', () => ({ predictiveApi: { dashboard: vi.fn() } }));

const DASH = {
  method: 'heuristic_v1', ai_ready: true, datasets: {},
  open_leads: 12, expected_pipeline_value: 480000, customers_tracked: 30,
  customers_at_high_churn_risk: 4, open_invoices: 9, invoices_at_collection_risk: 2,
  recommendations: 17, hot_leads: [], at_risk_customers: [], top_recommendations: [],
};

describe('PredictiveWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><PredictiveWidget /></BrowserRouter>);

  it('renders pipeline, churn-risk and recommendation counts', async () => {
    vi.mocked(predictiveApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Predictive Analytics')).toBeDefined());
    expect(screen.getByText('₹480,000')).toBeDefined();
    expect(screen.getByText('4')).toBeDefined();
    expect(screen.getByText('17')).toBeDefined();
  });

  it('shows a fallback when the API is unavailable', async () => {
    vi.mocked(predictiveApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No data/)).toBeDefined());
  });
});
