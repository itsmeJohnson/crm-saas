// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { PredictionEngineWidget } from '../PredictionEngineWidget';
import { predictionEngineApi } from '../../../services/predictionEngineApi';

vi.mock('../../../services/predictionEngineApi', () => ({
  predictionEngineApi: { dashboard: vi.fn() },
}));

const DASH = {
  engine_version: 'prediction_engine_v1', algorithm: 'heuristic_v1', models_active: 8,
  sales: { open_deals: 4, weighted_expected_value: 32000, win_rate: 50, confidence: 62 },
  revenue: { total_forecast: 120000, trend: 'up', backtest_accuracy: 82, confidence: 74 },
  tasks: { open: 9, at_risk: 3, top: [] },
  campaigns: { count: 2, top: [] },
  customers_at_risk: [],
};

describe('PredictionEngineWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><PredictionEngineWidget /></BrowserRouter>);

  it('renders pipeline, at-risk and revenue-confidence stats', async () => {
    vi.mocked(predictionEngineApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Prediction Engine')).toBeDefined());
    expect(screen.getByText('₹32k')).toBeDefined();
    expect(screen.getByText('3')).toBeDefined();
    expect(screen.getByText('74%')).toBeDefined();
  });

  it('shows a fallback when the dashboard is unavailable', async () => {
    vi.mocked(predictionEngineApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No prediction data/)).toBeDefined());
  });
});
