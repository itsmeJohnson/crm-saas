// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { DepartmentsWidget } from '../DepartmentsWidget';
import { departmentApi } from '../../../services/departmentApi';

vi.mock('../../../services/departmentApi', () => ({
  departmentApi: { dashboard: vi.fn() },
}));

const DASH = {
  total: 5, active: 4, archived: 1, total_budget: 120000, unassigned_members: 3,
  largest: [{ id: 'd1', name: 'Sales', member_count: 12 }, { id: 'd2', name: 'Support', member_count: 8 }],
};

describe('DepartmentsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><DepartmentsWidget /></BrowserRouter>);

  it('renders active count, budget, unassigned and largest departments', async () => {
    vi.mocked(departmentApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Departments')).toBeDefined());
    expect(screen.getByText('/5')).toBeDefined();      // active/total
    expect(screen.getByText('Sales')).toBeDefined();
    expect(screen.getByText(/3 unassigned member/i)).toBeDefined();
  });

  it('shows empty state when there are no departments', async () => {
    vi.mocked(departmentApi.dashboard).mockResolvedValue({ ...DASH, total: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('No departments yet.')).toBeDefined());
  });
});
