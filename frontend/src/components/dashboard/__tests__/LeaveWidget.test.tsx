// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { LeaveWidget } from '../LeaveWidget';
import { leaveApi } from '../../../services/leaveApi';

vi.mock('../../../services/leaveApi', () => ({ leaveApi: { dashboard: vi.fn() } }));
vi.mock('../../../store/authStore', () => ({ useAuthStore: () => ({ user: { role: 'Manager' } }) }));

const DASH = {
  my_pending: 1, my_available_days: 14.5, pending_approvals: 3,
  on_leave_today: [{ user_id: 'u1', name: 'Asha' }, { user_id: 'u2', name: 'Ravi' }],
};

describe('LeaveWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><LeaveWidget /></BrowserRouter>);

  it('renders available days, approvals for a manager, and who is on leave', async () => {
    vi.mocked(leaveApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Leave')).toBeDefined());
    expect(screen.getByText('14.5')).toBeDefined();       // available days
    expect(screen.getByText('To approve')).toBeDefined();  // manager label
    expect(screen.getByText('3')).toBeDefined();           // pending approvals
    expect(screen.getByText('Asha')).toBeDefined();
  });

  it('shows empty leave-today gracefully', async () => {
    vi.mocked(leaveApi.dashboard).mockResolvedValue({ ...DASH, on_leave_today: [] } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Leave')).toBeDefined());
    expect(screen.queryByText('On leave today')).toBeNull();
  });
});
