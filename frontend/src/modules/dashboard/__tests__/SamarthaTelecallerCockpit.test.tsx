// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { EmployeeDashboard } from '../EmployeeDashboard';
import { UploadZone } from '../../../components/leads/UploadZone';
import { useAuthStore } from '../../../store/authStore';
import { useDialerStore } from '../../../store/dialerStore';
import { attendanceApi } from '../../../services/attendanceApi';
import { dialerApi } from '../../../services/dialerApi';
import { leadImportApi } from '../../../services/leadImportApi';

// Mocks
vi.mock('../../../services/attendanceApi', () => ({
  attendanceApi: {
    myToday: vi.fn(),
    clockIn: vi.fn(),
    clockOut: vi.fn(),
    dashboard: vi.fn().mockResolvedValue(null),
  },
}));

vi.mock('../../../services/dashboardApi', () => ({
  dashboardApi: {
    getEmployeeSummary: vi.fn().mockResolvedValue({
      my_leads_total: 12,
      my_leads_converted: 4,
      my_leads_by_status: [],
      today_calls: 15,
      today_meetings_count: 0,
      today_meetings: [],
      open_tasks: 2,
      overdue_tasks: 0,
      calls_made_today: 15,
      todays_follow_ups: 3,
      overdue_follow_ups: 0,
      new_leads: 5,
      interested_leads: 2,
      meetings_today: 0,
      tasks_pending: 2,
    }),
    getWorkQueue: vi.fn().mockResolvedValue({
      generated_at: new Date().toISOString(),
      scope: 'my',
      next_action: null,
      counts: {},
      sections: [],
    }),
    getSummary: vi.fn().mockResolvedValue(null),
    getRecentActivities: vi.fn().mockResolvedValue({ items: [], total: 0, page: 1, limit: 10 }),
    getTeamStatus: vi.fn().mockResolvedValue([]),
    logFollowUp: vi.fn().mockResolvedValue({}),
  },
  FOLLOW_UP_OUTCOMES: [],
}));

vi.mock('../../../services/dialerApi', () => ({
  dialerApi: {
    getState: vi.fn(),
    getNextLead: vi.fn(),
    submitDisposition: vi.fn(),
    updateState: vi.fn(),
  },
}));

vi.mock('../../../services/leadImportApi', () => ({
  leadImportApi: {
    getBusinessTemplateTypes: vi.fn(),
    downloadTemplate: vi.fn(),
  },
}));

vi.mock('react-router-dom', () => ({
  useNavigate: () => vi.fn(),
}));

describe('Samartha Sankalpa Telecaller Workflow & Agent Cockpit', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useDialerStore.setState({
      agentState: 'IDLE',
      currentLead: null,
      breakReason: null,
      callDuration: 0,
      stateTimestamp: null,
      isLoading: false,
      error: null,
      callDirection: null,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('1. shows attendance required when telecaller is not clocked in, and unlocks cockpit on clock in', async () => {
    // Agent is initially not clocked in
    (attendanceApi.myToday as any).mockResolvedValue({
      work_date: '2026-10-17',
      record: null,
      shift: null,
      on_break: false,
    });

    useAuthStore.setState({
      user: {
        id: 'user-telecaller-1',
        first_name: 'John',
        last_name: 'B',
        email: 'johnsonsoftwares8@gmail.com',
        role: 'Employee',
      } as any,
      organization: {
        id: 'org-samartha',
        name: 'Samartha Sankalpa',
        slug: 'samartha-sankalpa',
      } as any,
    });

    render(<EmployeeDashboard />);

    // Shows attendance required state
    expect(await screen.findByText('Clock-In Required to Call')).toBeDefined();
    expect(screen.getByText('Calling Cockpit is Paused')).toBeDefined();
    const clockInBtn = screen.getByText('Mark Attendance & Start Calling');
    expect(clockInBtn).toBeDefined();

    // Now agent clocks in
    (attendanceApi.clockIn as any).mockResolvedValue({
      id: 'att-1',
      clock_in_at: '2026-10-17T09:00:00Z',
      clock_out_at: null,
      status: 'present',
    });
    (attendanceApi.myToday as any).mockResolvedValue({
      work_date: '2026-10-17',
      record: {
        clock_in_at: '2026-10-17T09:00:00Z',
        clock_out_at: null,
        status: 'present',
      },
      shift: null,
      on_break: false,
    });

    fireEvent.click(clockInBtn);

    await waitFor(() => {
      expect(attendanceApi.clockIn).toHaveBeenCalledTimes(1);
    });

    // Calling cockpit unlocks with verified attendance
    expect(await screen.findByText('Active • Attendance Verified')).toBeDefined();
    expect(screen.getByText('Start Dialing Session')).toBeDefined();
    expect(screen.getByText('Power Dialer (auto-dial next lead)')).toBeDefined();
  });

  it('2. allows telecaller to start calling, dispositions call, and automatically prepares the next lead', async () => {
    (attendanceApi.myToday as any).mockResolvedValue({
      work_date: '2026-10-17',
      record: {
        clock_in_at: '2026-10-17T09:00:00Z',
        clock_out_at: null,
        status: 'present',
      },
      shift: null,
      on_break: false,
    });

    const mockLead1 = {
      id: 'lead-101',
      first_name: 'Pooja',
      last_name: 'Sharma',
      phone: '9876543210',
      email: 'pooja.sharma@example.com',
      company_name: 'Samartha Sankalpa Agency',
      title: 'Inbound Campaign Lead',
      status: 'New',
    };

    (dialerApi.getNextLead as any).mockResolvedValue(mockLead1);
    (dialerApi.submitDisposition as any).mockResolvedValue({ success: true });

    render(<EmployeeDashboard />);

    // Click Start Dialing Session
    const startDialingBtn = await screen.findByRole('button', { name: /Start Dialing Session/i });
    fireEvent.click(startDialingBtn);

    await waitFor(() => {
      expect(dialerApi.getNextLead).toHaveBeenCalledTimes(1);
    });

    // Active Calling Screen shows lead information
    expect(await screen.findByText('Active Lead Context')).toBeDefined();
    expect(screen.getByText('Pooja Sharma')).toBeDefined();
    expect(screen.getByText('Call Disposition Status')).toBeDefined();

    // Telecaller selects status (e.g. Busy)
    const busyBtn = screen.getByRole('button', { name: 'Busy' });
    fireEvent.click(busyBtn);

    // Enter remarks
    const remarksInput = screen.getByPlaceholderText(/Enter mandatory call notes/i);
    fireEvent.change(remarksInput, { target: { value: 'Candidate line was busy, will retry.' } });

    // Submit disposition
    const submitBtn = screen.getByRole('button', { name: /Submit Disposition Outcome/i });
    fireEvent.click(submitBtn);

    await waitFor(() => {
      expect(dialerApi.submitDisposition).toHaveBeenCalledWith('lead-101', expect.objectContaining({
        status: 'Busy',
        remarks: 'Candidate line was busy, will retry.',
      }));
    });

    // Auto-dial countdown activates immediately for the next lead
    await waitFor(() => {
      expect(screen.getByText(/Power dialer: next call in/i)).toBeDefined();
    });
  });

  it('3. telecaller can take a break (e.g. Lunch/Tea) and resume when ready', async () => {
    (attendanceApi.myToday as any).mockResolvedValue({
      work_date: '2026-10-17',
      record: {
        clock_in_at: '2026-10-17T09:00:00Z',
        clock_out_at: null,
        status: 'present',
      },
      shift: null,
      on_break: false,
    });

    (dialerApi.updateState as any).mockResolvedValue({
      state: 'BREAK',
      metadata: { break_reason: 'Lunch' },
      timestamp: new Date().toISOString(),
    });

    render(<EmployeeDashboard />);

    // Click Request Break dropdown button
    const breakBtn = await screen.findByRole('button', { name: /Request Break/i });
    fireEvent.click(breakBtn);

    // Click Lunch Break option
    const lunchOption = screen.getByRole('button', { name: /Lunch Break/i });
    fireEvent.click(lunchOption);

    await waitFor(() => {
      expect(dialerApi.updateState).toHaveBeenCalledWith(expect.objectContaining({
        state: 'BREAK',
        metadata: { break_reason: 'Lunch' },
      }));
    });

    // Screen enters BREAK state
    expect(await screen.findByText('Lunch Break')).toBeDefined();
    expect(screen.getByRole('button', { name: /End Break/i })).toBeDefined();

    // Now telecaller ends break
    (dialerApi.updateState as any).mockResolvedValue({
      state: 'IDLE',
      timestamp: new Date().toISOString(),
    });

    const endBreakBtn = screen.getByRole('button', { name: /End Break/i });
    fireEvent.click(endBreakBtn);

    await waitFor(() => {
      expect(dialerApi.updateState).toHaveBeenCalledWith(expect.objectContaining({
        state: 'IDLE',
      }));
    });

    // Returns to ready state
    expect(await screen.findByText('Start Dialing Session')).toBeDefined();
  });

  it('4. import template for Samartha Sankalpa agency strictly restricts templates to Samartha Sankalpa agency', async () => {
    (leadImportApi.getBusinessTemplateTypes as any).mockResolvedValue([
      { key: 'samartha_sankalpa', label: 'Samartha Sankalpa Telecalling Agency' },
      { key: 'real_estate', label: 'Real Estate' },
      { key: 'logistics', label: 'Logistics' },
    ]);

    useAuthStore.setState({
      organization: {
        id: 'org-samartha',
        name: 'Samartha Sankalpa',
        slug: 'samartha-sankalpa',
      } as any,
    });

    const mockDownload = vi.fn();
    const mockSetVertical = vi.fn();

    render(
      <UploadZone
        sourceType="file"
        setSourceType={vi.fn()}
        selectedFile={null}
        setSelectedFile={vi.fn()}
        sheetsUrl=""
        setSheetsUrl={vi.fn()}
        onDownloadTemplate={mockDownload}
        setErrorMsg={vi.fn()}
        templateVertical="samartha_sankalpa"
        setTemplateVertical={mockSetVertical}
      />
    );

    // Only Samartha Sankalpa Telecalling Agency is shown in the template selector
    await waitFor(() => {
      expect(screen.getByText('Samartha Sankalpa Telecalling Agency')).toBeDefined();
    });

    // Real Estate and Logistics should NOT be rendered for Samartha Sankalpa tenant
    expect(screen.queryByText('Real Estate')).toBeNull();
    expect(screen.queryByText('Logistics')).toBeNull();

    // Trigger CSV template download
    const csvBtn = screen.getByText('CSV Template');
    fireEvent.click(csvBtn);
    expect(mockDownload).toHaveBeenCalledWith('csv');
  });
});
