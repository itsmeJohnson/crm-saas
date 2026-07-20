// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { SchedulerWidget } from '../SchedulerWidget';
import { schedulerApi } from '../../../services/schedulerApi';

vi.mock('../../../services/schedulerApi', () => ({ schedulerApi: { dashboard: vi.fn() } }));

const DASH = {
  total: 12, active: 9, success_rate: 94.5, failed: 3, skipped: 7,
  upcoming: [
    { id: 's1', name: 'Nightly SLA scan', next_run_at: '2026-07-07T02:00:00Z' },
    { id: 's2', name: 'Weekly leads report', next_run_at: '2026-07-08T09:00:00Z' },
  ],
  recent: [],
};

describe('SchedulerWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><SchedulerWidget /></BrowserRouter>);

  it('renders active/success/skipped and upcoming schedules', async () => {
    vi.mocked(schedulerApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Scheduler')).toBeDefined());
    expect(screen.getByText('9/12')).toBeDefined();      // active/total
    expect(screen.getByText('94.5%')).toBeDefined();      // success rate
    expect(screen.getByText('7')).toBeDefined();           // skipped
    expect(screen.getByText('Nightly SLA scan')).toBeDefined();
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(schedulerApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
