// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AiPlatformWidget } from '../AiPlatformWidget';
import { aiApi } from '../../../services/aiApi';

vi.mock('../../../services/aiApi', () => ({ aiApi: { usage: vi.fn() } }));

const DASH = {
  days: 30, requests: 128, failed: 3, cached: 40, fallbacks: 2, tokens: 90000,
  cost_usd: 4.27, error_rate: 2.3, cache_hit_rate: 31.3, avg_latency_ms: 640,
  by_provider: {}, by_task: {}, by_day: [],
  budget: { monthly_budget_usd: 100, spent_this_month_usd: 4.27, daily_request_limit: 1000 },
};

describe('AiPlatformWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><AiPlatformWidget /></BrowserRouter>);

  it('renders request, cost and cache-hit stats', async () => {
    vi.mocked(aiApi.usage).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('AI Platform')).toBeDefined());
    expect(screen.getByText('128')).toBeDefined();
    expect(screen.getByText('$4.27')).toBeDefined();
    expect(screen.getByText('31.3%')).toBeDefined();
  });

  it('shows a fallback when usage is unavailable', async () => {
    vi.mocked(aiApi.usage).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No AI usage data/)).toBeDefined());
  });
});
