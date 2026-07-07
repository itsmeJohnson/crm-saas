// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { CampaignsWidget } from '../CampaignsWidget';
import { campaignApi } from '../../../services/campaignApi';

vi.mock('../../../services/campaignApi', () => ({
  campaignApi: { dashboard: vi.fn() },
}));

const DASH = {
  total: 5, running: 2, scheduled: 1, completed: 2,
  total_sent: 340, total_converted: 12, total_revenue: 12000, total_roi: 9500,
  by_status: [],
};

describe('CampaignsWidget Component', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWithRouter = (ui: React.ReactElement) => render(<BrowserRouter>{ui}</BrowserRouter>);

  it('renders campaign counts and ROI', async () => {
    vi.mocked(campaignApi.dashboard).mockResolvedValue(DASH as any);
    renderWithRouter(<CampaignsWidget />);
    await waitFor(() => expect(screen.getByText('Campaigns')).toBeDefined());
    expect(screen.getByText('2')).toBeDefined();   // running
    expect(screen.getByText('340')).toBeDefined(); // sent
    expect(screen.getByText('₹9500')).toBeDefined(); // ROI
  });

  it('shows empty state when there are no campaigns', async () => {
    vi.mocked(campaignApi.dashboard).mockResolvedValue({ ...DASH, total: 0 } as any);
    renderWithRouter(<CampaignsWidget />);
    await waitFor(() => expect(screen.getByText('No campaigns yet.')).toBeDefined());
  });
});
