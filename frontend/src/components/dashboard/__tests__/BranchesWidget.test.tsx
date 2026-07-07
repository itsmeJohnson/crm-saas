// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { BranchesWidget } from '../BranchesWidget';
import { branchApi } from '../../../services/branchApi';

vi.mock('../../../services/branchApi', () => ({
  branchApi: { dashboard: vi.fn() },
}));

const DASH = {
  total_branches: 5, active_branches: 4, archived_branches: 1, total_territories: 8,
  mapped_pincodes: 120, unmapped_leads: 7,
  top_branches: [
    { id: 'b1', name: 'Mumbai', lead_count: 40 },
    { id: 'b2', name: 'Pune', lead_count: 22 },
  ],
};

describe('BranchesWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><BranchesWidget /></BrowserRouter>);

  it('renders active count, mapped PINs, unmapped leads and top branches', async () => {
    vi.mocked(branchApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Branches')).toBeDefined());
    expect(screen.getByText('/5')).toBeDefined();          // active/total
    expect(screen.getByText('120')).toBeDefined();          // mapped PINs
    expect(screen.getByText(/7 lead/i)).toBeDefined();      // unmapped leads
    expect(screen.getByText('Mumbai')).toBeDefined();
  });

  it('shows empty state when there are no branches', async () => {
    vi.mocked(branchApi.dashboard).mockResolvedValue({ ...DASH, total_branches: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('No branches yet.')).toBeDefined());
  });
});
