// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { WhatsAppWidget } from '../WhatsAppWidget';
import { whatsappApi } from '../../../services/whatsappApi';

vi.mock('../../../services/whatsappApi', () => ({
  whatsappApi: { reports: vi.fn(), conversations: vi.fn() },
}));

const REPORT = {
  total: 10, outbound: 7, inbound: 3, delivered: 6, read: 4, failed: 1,
  delivery_rate: 85.7, read_rate: 57.1, by_status: [], by_direction: [], by_media_type: [], by_day: [],
};

describe('WhatsAppWidget Component', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });

  const renderWithRouter = (ui: React.ReactElement) => render(<BrowserRouter>{ui}</BrowserRouter>);

  it('renders today WhatsApp stats and unread count', async () => {
    vi.mocked(whatsappApi.reports).mockResolvedValue(REPORT as any);
    vi.mocked(whatsappApi.conversations).mockResolvedValue([{ unread_count: 3 }, { unread_count: 2 }] as any);
    renderWithRouter(<WhatsAppWidget />);

    await waitFor(() => expect(screen.getByText('WhatsApp Today')).toBeDefined());
    expect(screen.getByText('7')).toBeDefined(); // sent
    expect(screen.getByText('57.1%')).toBeDefined(); // read rate
    expect(screen.getByText('85.7%')).toBeDefined(); // delivery rate
    // unread total 5 shown (3 + 2)
    await waitFor(() => expect(screen.getByText(/unread message/i)).toBeDefined());
    expect(screen.getByText('5')).toBeDefined();
    expect(vi.mocked(whatsappApi.reports).mock.calls[0][0]).toHaveProperty('date_from');
  });

  it('shows empty state when there are no messages today', async () => {
    vi.mocked(whatsappApi.reports).mockResolvedValue({ ...REPORT, total: 0 } as any);
    vi.mocked(whatsappApi.conversations).mockResolvedValue([] as any);
    renderWithRouter(<WhatsAppWidget />);
    await waitFor(() => expect(screen.getByText('No messages today.')).toBeDefined());
  });
});
