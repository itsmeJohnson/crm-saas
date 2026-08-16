// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AiAnalyticsWidget } from '../AiAnalyticsWidget';
import { aiAnalyticsApi } from '../../../services/aiAnalyticsApi';

vi.mock('../../../services/aiAnalyticsApi', async () => {
  const actual = await vi.importActual<any>('../../../services/aiAnalyticsApi');
  return { ...actual, aiAnalyticsApi: { dashboard: vi.fn() } };
});

const DASH = {
  days: 30, requests: 412, tokens: 91200, cost_usd: 3.42,
  success_rate: 97.6, failure_rate: 2.4, avg_latency_ms: 640, p95_latency_ms: 1800,
  quality_score: 93.1, quality_band: 'excellent', adoption_rate: 68.4, ai_users: 13,
  top_features: [], top_models: [], latency_trend: [],
};

describe('AiAnalyticsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><AiAnalyticsWidget /></BrowserRouter>);

  it('renders quality, adoption and request stats', async () => {
    vi.mocked(aiAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('AI Analytics')).toBeDefined());
    expect(screen.getByText('93.1')).toBeDefined();
    expect(screen.getByText('68.4%')).toBeDefined();
    expect(screen.getByText('412')).toBeDefined();
  });

  it('shows a fallback when analytics are unavailable', async () => {
    vi.mocked(aiAnalyticsApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No AI analytics data/)).toBeDefined());
  });
});
