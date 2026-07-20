// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AutomationAnalyticsWidget } from '../AutomationAnalyticsWidget';
import { automationAnalyticsApi } from '../../../services/automationAnalyticsApi';

vi.mock('../../../services/automationAnalyticsApi', () => ({
  automationAnalyticsApi: { dashboard: vi.fn() },
}));

const DASH = {
  workflow_runs: 12, workflow_success_rate: 83.3, workflow_failed: 2, queue_failed: 1,
  sla_compliance_rate: 90.0, open_breaches: 1, escalations: 3, approvals_pending: 4,
};

describe('AutomationAnalyticsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><AutomationAnalyticsWidget /></BrowserRouter>);

  it('renders the headline automation metrics', async () => {
    vi.mocked(automationAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Automation Analytics')).toBeDefined());
    expect(screen.getByText('83.3%')).toBeDefined();
    expect(screen.getByText('90%')).toBeDefined();
    expect(screen.getByText('4')).toBeDefined();
  });

  it('shows a loader before data resolves', async () => {
    vi.mocked(automationAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
