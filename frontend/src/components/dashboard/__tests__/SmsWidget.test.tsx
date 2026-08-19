// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { SmsWidget } from '../SmsWidget';
import { smsApi } from '../../../services/smsApi';

vi.mock('../../../services/smsApi', () => ({
  smsApi: { reports: vi.fn() },
}));

const REPORT = {
  total: 8,
  outbound: 6,
  inbound: 2,
  delivered: 5,
  failed: 1,
  segments: 9,
  delivery_rate: 83.3,
  by_status: [],
  by_direction: [],
  by_day: [],
};

describe('SmsWidget Component', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement) => render(<BrowserRouter>{ui}</BrowserRouter>);

  it('renders today SMS stats from the reports endpoint', async () => {
    vi.mocked(smsApi.reports).mockResolvedValue(REPORT as any);
    renderWithRouter(<SmsWidget />);

    await waitFor(() => expect(screen.getByText('6')).toBeDefined()); // sent
    expect(screen.getByText('2')).toBeDefined(); // received
    expect(screen.getByText('83.3%')).toBeDefined(); // delivery rate
    expect(screen.getByText('1')).toBeDefined(); // failed
    expect(vi.mocked(smsApi.reports).mock.calls[0][0]).toHaveProperty('date_from');
  });

  it('shows empty state when there are no messages today', async () => {
    vi.mocked(smsApi.reports).mockResolvedValue({ ...REPORT, total: 0 } as any);
    renderWithRouter(<SmsWidget />);
    await waitFor(() => expect(screen.getByText('No messages today.')).toBeDefined());
  });
});
