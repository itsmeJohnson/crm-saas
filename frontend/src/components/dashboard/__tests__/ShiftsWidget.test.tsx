// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ShiftsWidget } from '../ShiftsWidget';
import { shiftApi } from '../../../services/shiftApi';

vi.mock('../../../services/shiftApi', () => ({ shiftApi: { dashboard: vi.fn() } }));

const DASH = {
  total_shifts: 5, flexible_shifts: 1, night_shifts: 2, active_rotations: 3,
  by_type: { morning: 1, evening: 1, night: 2, flexible: 1 },
  my_shift_today: { id: 's1', name: 'Morning Shift', start_time: '06:00', end_time: '14:00' },
};

describe('ShiftsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><ShiftsWidget /></BrowserRouter>);

  it("renders today's shift, total/night/rotation counts", async () => {
    vi.mocked(shiftApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/Morning Shift/)).toBeDefined());
    expect(screen.getByText('5')).toBeDefined();  // total shifts
    expect(screen.getByText('3')).toBeDefined();  // rotations
  });

  it('shows "No shift" when none assigned today', async () => {
    vi.mocked(shiftApi.dashboard).mockResolvedValue({ ...DASH, my_shift_today: null } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('No shift')).toBeDefined());
  });
});
