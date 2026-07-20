// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { CommAnalyticsWidget } from '../CommAnalyticsWidget';
import { commAnalyticsApi } from '../../../services/commAnalyticsApi';

vi.mock('../../../services/commAnalyticsApi', () => ({
  commAnalyticsApi: { overview: vi.fn(), responseTime: vi.fn() },
}));

const OV = { total: 40, outbound: 30, inbound: 10, delivered: 27, failed: 3, delivery_rate: 90, by_channel: [], by_direction: [] };
const RT = { avg_response_seconds: 180, median_response_seconds: 120, sample_size: 12 };

describe('CommAnalyticsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><CommAnalyticsWidget /></BrowserRouter>);

  it('renders cross-channel volume and avg reply', async () => {
    vi.mocked(commAnalyticsApi.overview).mockResolvedValue(OV as any);
    vi.mocked(commAnalyticsApi.responseTime).mockResolvedValue(RT as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Comm Analytics')).toBeDefined());
    expect(screen.getByText('30')).toBeDefined();  // outbound
    expect(screen.getByText('10')).toBeDefined();  // inbound
    expect(screen.getByText('90%')).toBeDefined(); // delivery
    expect(screen.getByText('3m')).toBeDefined();  // avg reply 180s
  });

  it('shows empty state when there are no comms', async () => {
    vi.mocked(commAnalyticsApi.overview).mockResolvedValue({ ...OV, total: 0 } as any);
    vi.mocked(commAnalyticsApi.responseTime).mockResolvedValue(RT as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No communications in the last 30 days/i)).toBeDefined());
  });
});
