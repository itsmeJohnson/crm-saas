// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AutomationWidget } from '../AutomationWidget';
import { automationApi } from '../../../services/automationApi';

vi.mock('../../../services/automationApi', () => ({ automationApi: { dashboard: vi.fn() } }));

const DASH = {
  jobs: 10, enabled: 8, success_rate: 91.5, open_breaches: 3, active_reports: 2,
  recent: [
    { id: 'r1', job_key: 'sla_scan', status: 'success', triggered_by: 'schedule', items_processed: 4, retry_count: 0, error: null, duration_ms: 12, started_at: null, finished_at: null },
    { id: 'r2', job_key: 'email_sync', status: 'failed', triggered_by: 'manual', items_processed: 0, retry_count: 1, error: 'x', duration_ms: 5, started_at: null, finished_at: null },
  ],
};

describe('AutomationWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><AutomationWidget /></BrowserRouter>);

  it('renders jobs/success/breaches and recent runs', async () => {
    vi.mocked(automationApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Automation')).toBeDefined());
    expect(screen.getByText('8/10')).toBeDefined();     // enabled/jobs
    expect(screen.getByText('91.5%')).toBeDefined();     // success rate
    expect(screen.getByText('3')).toBeDefined();          // open breaches
    expect(screen.getByText('sla scan')).toBeDefined();
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(automationApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
