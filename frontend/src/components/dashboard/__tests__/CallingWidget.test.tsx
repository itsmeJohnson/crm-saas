// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { CallingWidget } from '../CallingWidget';
import { callingApi } from '../../../services/callingApi';

vi.mock('../../../services/callingApi', () => ({
  callingApi: {
    reports: vi.fn(),
  },
}));

const REPORT = {
  total: 12,
  missed: 2,
  avg_duration: 95,
  connect_rate: 60.0,
  connected: 6,
  dispositioned: 10,
  by_direction: [
    { label: 'OUTBOUND', count: 9 },
    { label: 'INBOUND', count: 3 },
  ],
  by_disposition: [],
  by_agent: [],
  by_day: [],
};

describe('CallingWidget Component', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement) => render(<BrowserRouter>{ui}</BrowserRouter>);

  it('renders today call stats from the reports endpoint', async () => {
    vi.mocked(callingApi.reports).mockResolvedValue(REPORT as any);
    renderWithRouter(<CallingWidget />);

    await waitFor(() => expect(screen.getByText('Calling Today')).toBeDefined());
    expect(screen.getByText('9')).toBeDefined(); // outbound
    expect(screen.getByText('3')).toBeDefined(); // inbound
    expect(screen.getByText('60%')).toBeDefined(); // connect rate
    expect(screen.getByText('2')).toBeDefined(); // missed
    // requested a today-scoped report
    expect(vi.mocked(callingApi.reports).mock.calls[0][0]).toHaveProperty('date_from');
  });

  it('shows empty state when there are no calls today', async () => {
    vi.mocked(callingApi.reports).mockResolvedValue({ ...REPORT, total: 0 } as any);
    renderWithRouter(<CallingWidget />);
    await waitFor(() => expect(screen.getByText('No calls logged today.')).toBeDefined());
  });
});
