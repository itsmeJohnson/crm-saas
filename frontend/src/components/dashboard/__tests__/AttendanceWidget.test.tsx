// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AttendanceWidget } from '../AttendanceWidget';
import { attendanceApi } from '../../../services/attendanceApi';

vi.mock('../../../services/attendanceApi', () => ({
  attendanceApi: { myToday: vi.fn(), dashboard: vi.fn(), clockIn: vi.fn(), clockOut: vi.fn() },
}));

const DASH = {
  work_date: '2026-07-04', headcount: 10, present: 7, absent: 3, late: 2,
  on_break: 1, clocked_out: 2, still_working: 5, pending_corrections: 4,
};

describe('AttendanceWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><AttendanceWidget /></BrowserRouter>);

  it('shows clock-in prompt and org present/late/pending stats when not clocked in', async () => {
    vi.mocked(attendanceApi.myToday).mockResolvedValue({ work_date: '2026-07-04', record: null, shift: null, on_break: false } as any);
    vi.mocked(attendanceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Attendance')).toBeDefined());
    expect(screen.getByText('Not clocked in')).toBeDefined();
    expect(screen.getByText('Clock in')).toBeDefined();
    expect(screen.getByText('7/10')).toBeDefined();  // present/headcount
    expect(screen.getByText('2')).toBeDefined();      // late
  });

  it('shows clock-out when already clocked in', async () => {
    vi.mocked(attendanceApi.myToday).mockResolvedValue({
      work_date: '2026-07-04',
      record: { clock_in_at: '2026-07-04T09:00:00Z', clock_out_at: null, status: 'present' },
      shift: null, on_break: false,
    } as any);
    vi.mocked(attendanceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Clocked in')).toBeDefined());
    expect(screen.getByText('Clock out')).toBeDefined();
  });
});
