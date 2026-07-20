// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { TargetsWidget } from '../TargetsWidget';
import { targetApi } from '../../../services/targetApi';

vi.mock('../../../services/targetApi', () => ({ targetApi: { dashboard: vi.fn() } }));

const DASH = {
  total: 10, achieved: 4, on_track: 3, at_risk: 2, missed: 1, avg_attainment: 78.5,
  by_scope: { individual: 5, team: 3, department: 2 }, by_period: { monthly: 8, weekly: 2 },
  at_risk_targets: [{ id: 't1', scope: 'team', scope_name: 'Alpha', name: 'Q3 Sales', attainment: 40 }],
};

describe('TargetsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><TargetsWidget /></BrowserRouter>);

  it('renders achieved/total, avg attainment and at-risk targets', async () => {
    vi.mocked(targetApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Targets')).toBeDefined());
    expect(screen.getByText('/10')).toBeDefined();           // achieved/total
    expect(screen.getByText('78.5%')).toBeDefined();          // avg attainment
    expect(screen.getByText(/2 target\(s\) at risk/i)).toBeDefined();
    expect(screen.getByText(/Alpha · Q3 Sales/)).toBeDefined();
  });

  it('shows empty state when no targets', async () => {
    vi.mocked(targetApi.dashboard).mockResolvedValue({ ...DASH, total: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('No targets set.')).toBeDefined());
  });
});
