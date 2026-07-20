// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { EmailWidget } from '../EmailWidget';
import { emailApi } from '../../../services/emailApi';

vi.mock('../../../services/emailApi', () => ({
  emailApi: { reports: vi.fn() },
}));

const REPORT = {
  total: 9, sent: 6, inbound: 3, drafts: 1, failed: 0, opened: 4, clicked: 2,
  open_rate: 66.7, click_rate: 33.3, by_status: [], by_direction: [], by_day: [],
};

describe('EmailWidget Component', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWithRouter = (ui: React.ReactElement) => render(<BrowserRouter>{ui}</BrowserRouter>);

  it('renders today email stats from the reports endpoint', async () => {
    vi.mocked(emailApi.reports).mockResolvedValue(REPORT as any);
    renderWithRouter(<EmailWidget />);
    await waitFor(() => expect(screen.getByText('Email Today')).toBeDefined());
    expect(screen.getByText('6')).toBeDefined(); // sent
    expect(screen.getByText('3')).toBeDefined(); // received
    expect(screen.getByText('66.7%')).toBeDefined(); // open rate
    expect(screen.getByText('33.3%')).toBeDefined(); // click rate
    expect(vi.mocked(emailApi.reports).mock.calls[0][0]).toHaveProperty('date_from');
  });

  it('shows empty state when there are no emails today', async () => {
    vi.mocked(emailApi.reports).mockResolvedValue({ ...REPORT, total: 0 } as any);
    renderWithRouter(<EmailWidget />);
    await waitFor(() => expect(screen.getByText('No emails today.')).toBeDefined());
  });
});
