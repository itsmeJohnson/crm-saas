// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { HistoryWidget } from '../HistoryWidget';
import { historyApi } from '../../../services/historyApi';

vi.mock('../../../services/historyApi', () => ({ historyApi: { dashboard: vi.fn() } }));

const DASH = {
  days_covered: 45, metrics_tracked: 28, archived_rows: 12, last_capture: '2026-07-17',
  top_movers: [], sparklines: {},
  settings: { retention_days: 730, archive_enabled: true, capture_enabled: true },
};

describe('HistoryWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><HistoryWidget /></BrowserRouter>);

  it('renders coverage, metric and archive counts', async () => {
    vi.mocked(historyApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Historical Analytics')).toBeDefined());
    expect(screen.getByText('45')).toBeDefined();
    expect(screen.getByText('28')).toBeDefined();
    expect(screen.getByText('12')).toBeDefined();
  });

  it('shows an empty state when no snapshots exist', async () => {
    vi.mocked(historyApi.dashboard).mockResolvedValue({ ...DASH, days_covered: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/Capture a snapshot/)).toBeDefined());
  });
});
