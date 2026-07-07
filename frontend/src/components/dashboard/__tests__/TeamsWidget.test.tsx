// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { TeamsWidget } from '../TeamsWidget';
import { teamApi } from '../../../services/teamApi';

vi.mock('../../../services/teamApi', () => ({
  teamApi: { dashboard: vi.fn() },
}));

const DASH = {
  total: 4, active: 3, archived: 1, total_members: 22, capacity_utilization: 73.5,
  largest: [
    { id: 't1', name: 'Alpha', member_count: 10, capacity: 12 },
    { id: 't2', name: 'Bravo', member_count: 6, capacity: null },
  ],
};

describe('TeamsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><TeamsWidget /></BrowserRouter>);

  it('renders active count, capacity utilization and largest teams', async () => {
    vi.mocked(teamApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Teams')).toBeDefined());
    expect(screen.getByText('/4')).toBeDefined();          // active/total
    expect(screen.getByText('73.5%')).toBeDefined();       // capacity utilization
    expect(screen.getByText('Alpha')).toBeDefined();
    expect(screen.getByText(/22 member/i)).toBeDefined();
  });

  it('shows empty state when there are no teams', async () => {
    vi.mocked(teamApi.dashboard).mockResolvedValue({ ...DASH, total: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('No teams yet.')).toBeDefined());
  });
});
