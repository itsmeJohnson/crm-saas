// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { VizWidget } from '../VizWidget';
import { vizApi } from '../../../services/vizApi';

vi.mock('../../../services/vizApi', () => ({ vizApi: { dashboard: vi.fn() } }));

const PINNED = {
  count: 1,
  pinned: [{
    id: 'v1', name: 'Leads by status', viz_type: 'funnel', dataset: 'leads',
    config: { dimension: 'status' }, filters: null, visibility: 'organization', is_pinned: true,
    created_at: null,
    data: { stages: [{ label: 'New', value: 6, pct_of_first: 100, drop_pct: 0 }], measure_label: 'count' },
  }],
};

describe('VizWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><VizWidget /></BrowserRouter>);

  it('renders pinned visualizations from the studio', async () => {
    vi.mocked(vizApi.dashboard).mockResolvedValue(PINNED as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Visualizations')).toBeDefined());
    expect(screen.getByText('Leads by status')).toBeDefined();
    expect(screen.getByText('New')).toBeDefined(); // funnel stage rendered
  });

  it('shows an empty state when nothing is pinned', async () => {
    vi.mocked(vizApi.dashboard).mockResolvedValue({ count: 0, pinned: [] } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/Pin a visualization/)).toBeDefined());
  });
});
