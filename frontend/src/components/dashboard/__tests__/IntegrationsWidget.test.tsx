// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { IntegrationsWidget } from '../IntegrationsWidget';
import { integrationApi } from '../../../services/integrationApi';

vi.mock('../../../services/integrationApi', () => ({ integrationApi: { dashboard: vi.fn() } }));

const DASH = {
  total: 12, active: 8, managed_elsewhere: 4,
  healthy: 9, degraded: 2, down: 1, unconfigured: 0,
  categories_used: 6, categories_available: 17, connectors_available: 60,
  by_category: {},
  calls_7d: 340, failures_7d: 11, retries_7d: 5, fallbacks_7d: 2,
  success_rate: 96.8, needs_attention: [],
};

describe('IntegrationsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><IntegrationsWidget /></BrowserRouter>);

  it('renders totals and sums degraded + down into one issues count', async () => {
    vi.mocked(integrationApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Integrations')).toBeDefined());
    expect(screen.getByText('12')).toBeDefined();
    expect(screen.getByText('9')).toBeDefined();
    expect(screen.getByText('3')).toBeDefined(); // 2 degraded + 1 down
  });

  it('shows a fallback when the dashboard is unavailable', async () => {
    vi.mocked(integrationApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No integration data/)).toBeDefined());
  });
});
