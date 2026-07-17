// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ScheduledReportsWidget } from '../ScheduledReportsWidget';
import { scheduledReportsApi } from '../../../services/scheduledReportsApi';

vi.mock('../../../services/scheduledReportsApi', () => ({ scheduledReportsApi: { dashboard: vi.fn() } }));

const DASH = {
  schedules: 4, active: 3, deliveries: 20,
  by_status: { success: 17, partial: 1, failed: 2 },
  success_rate: 85.0, upcoming: [],
};

describe('ScheduledReportsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><ScheduledReportsWidget /></BrowserRouter>);

  it('renders active ratio, success rate and failed count', async () => {
    vi.mocked(scheduledReportsApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Scheduled Reports')).toBeDefined());
    expect(screen.getByText('3/4')).toBeDefined();
    expect(screen.getByText('85%')).toBeDefined();
    expect(screen.getByText('2')).toBeDefined();
  });

  it('shows an empty state when no schedules exist', async () => {
    vi.mocked(scheduledReportsApi.dashboard).mockResolvedValue({ ...DASH, schedules: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/Create a schedule/)).toBeDefined());
  });
});
