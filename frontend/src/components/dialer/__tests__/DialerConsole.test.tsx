// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { DialerConsole } from '../DialerConsole';
import { useDialerStore } from '../../../store/dialerStore';
import { usePipelineStore } from '../../../store/pipelineStore';

// Mock Zustand Stores
vi.mock('../../../store/dialerStore', () => ({
  useDialerStore: vi.fn(),
}));

vi.mock('../../../store/pipelineStore', () => ({
  usePipelineStore: vi.fn(),
}));

describe('DialerConsole Component', () => {
  const mockFetchCurrentState = vi.fn().mockResolvedValue(undefined);
  const mockFetchStages = vi.fn().mockResolvedValue(undefined);
  const mockStartCalling = vi.fn().mockResolvedValue(undefined);
  const mockSubmitDisposition = vi.fn().mockResolvedValue(undefined);
  const mockGoOnBreak = vi.fn().mockResolvedValue(undefined);
  const mockEndBreak = vi.fn().mockResolvedValue(undefined);

  const mockStages = [
    { id: 'stage-1', name: 'Fresh Leads' },
    { id: 'stage-2', name: 'Contacted' },
    { id: 'stage-3', name: 'Followup' },
    { id: 'stage-dropped', name: 'Dropped' },
  ];

  beforeEach(() => {
    vi.clearAllMocks();

    (usePipelineStore as any).mockReturnValue({
      stages: mockStages,
      fetchStages: mockFetchStages,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders IDLE state controls by default and starts call session', () => {
    (useDialerStore as any).mockReturnValue({
      agentState: 'IDLE',
      currentLead: null,
      breakReason: null,
      callDuration: 0,
      isLoading: false,
      error: null,
      fetchCurrentState: mockFetchCurrentState,
      startCalling: mockStartCalling,
      submitDisposition: mockSubmitDisposition,
      goOnBreak: mockGoOnBreak,
      endBreak: mockEndBreak,
    });

    render(<DialerConsole />);

    // Verify initial setup calls
    expect(mockFetchCurrentState).toHaveBeenCalled();
    expect(mockFetchStages).toHaveBeenCalled();

    // Verify controls
    expect(screen.getByText('Start Dialing Session')).toBeDefined();
    expect(screen.getByText('Request Break')).toBeDefined();

    // Click start session
    fireEvent.click(screen.getByText('Start Dialing Session'));
    expect(mockStartCalling).toHaveBeenCalledWith(false);
  });

  it('renders BREAK state details and ends break', () => {
    (useDialerStore as any).mockReturnValue({
      agentState: 'BREAK',
      currentLead: null,
      breakReason: 'Tea',
      callDuration: 0,
      isLoading: false,
      error: null,
      fetchCurrentState: mockFetchCurrentState,
      startCalling: mockStartCalling,
      submitDisposition: mockSubmitDisposition,
      goOnBreak: mockGoOnBreak,
      endBreak: mockEndBreak,
    });

    render(<DialerConsole />);

    expect(screen.getByText('Tea Break')).toBeDefined();
    expect(screen.getByText('End Break')).toBeDefined();

    // Click end break
    fireEvent.click(screen.getByText('End Break'));
    expect(mockEndBreak).toHaveBeenCalled();
  });

  it('renders ACTIVE_CALLING state details, showing active lead and call timer', () => {
    const mockLead = {
      id: 'lead-1',
      first_name: 'Jane',
      last_name: 'Doe',
      title: 'VP of Sales',
      company_name: 'Acme Inc',
      phone: '+91********12',
    } as any;

    (useDialerStore as any).mockReturnValue({
      agentState: 'ACTIVE_CALLING',
      currentLead: mockLead,
      breakReason: null,
      callDuration: 102, // 1 minute 42 seconds
      isLoading: false,
      error: null,
      fetchCurrentState: mockFetchCurrentState,
      startCalling: mockStartCalling,
      submitDisposition: mockSubmitDisposition,
      goOnBreak: mockGoOnBreak,
      endBreak: mockEndBreak,
    });

    render(<DialerConsole />);

    // Verify lead name and meta details
    expect(screen.getByText('Jane Doe')).toBeDefined();
    expect(screen.getByText('VP of Sales at Acme Inc')).toBeDefined();

    // Verify duration string "01:42"
    expect(screen.getByText('01:42')).toBeDefined();

    // Verify masked phone number
    expect(screen.getByText('+91********12')).toBeDefined();
  });

  it('submits disposition successfully when inputs are valid', () => {
    const mockLead = {
      id: 'lead-1',
      first_name: 'Jane',
      last_name: 'Doe',
      title: 'VP of Sales',
      company_name: 'Acme Inc',
      phone: '+91********12',
    } as any;

    (useDialerStore as any).mockReturnValue({
      agentState: 'ACTIVE_CALLING',
      currentLead: mockLead,
      breakReason: null,
      callDuration: 10,
      isLoading: false,
      error: null,
      fetchCurrentState: mockFetchCurrentState,
      startCalling: mockStartCalling,
      submitDisposition: mockSubmitDisposition,
      goOnBreak: mockGoOnBreak,
      endBreak: mockEndBreak,
    });

    render(<DialerConsole />);

    const submitBtn = screen.getByText('Submit Disposition Outcome') as HTMLButtonElement;
    expect(submitBtn.disabled).toBe(true);

    // Click Busy status
    fireEvent.click(screen.getByText('Busy'));

    // Type notes
    const notesArea = screen.getByPlaceholderText(/Enter mandatory call notes/i);
    fireEvent.change(notesArea, { target: { value: 'User hung up immediately' } });

    // Submit button should now be enabled
    expect(submitBtn.disabled).toBe(false);

    // Click Submit
    fireEvent.click(submitBtn);
    expect(mockSubmitDisposition).toHaveBeenCalledWith({
      status: 'Busy',
      remarks: 'User hung up immediately',
      custom_pipeline_stage_id: undefined,
    });
  });

  it('shows pipeline stage dropdown when status is Picked', () => {
    const mockLead = {
      id: 'lead-1',
      first_name: 'Jane',
      last_name: 'Doe',
      title: 'VP of Sales',
      company_name: 'Acme Inc',
      phone: '+91********12',
    } as any;

    (useDialerStore as any).mockReturnValue({
      agentState: 'ACTIVE_CALLING',
      currentLead: mockLead,
      breakReason: null,
      callDuration: 10,
      isLoading: false,
      error: null,
      fetchCurrentState: mockFetchCurrentState,
      startCalling: mockStartCalling,
      submitDisposition: mockSubmitDisposition,
      goOnBreak: mockGoOnBreak,
      endBreak: mockEndBreak,
    });

    render(<DialerConsole />);

    // Initially pipeline dropdown is hidden
    expect(screen.queryByLabelText(/Advance Lead to Pipeline Stage/i)).toBeNull();

    // Click Picked status
    fireEvent.click(screen.getByText('Picked'));

    // Now dropdown label is visible
    expect(screen.getByText('Advance Lead to Pipeline Stage')).toBeDefined();

    // Select contacted stage
    const dropdown = screen.getByRole('combobox') as HTMLSelectElement;
    fireEvent.change(dropdown, { target: { value: 'stage-2' } });

    // Type notes
    const notesArea = screen.getByPlaceholderText(/Enter mandatory call notes/i);
    fireEvent.change(notesArea, { target: { value: 'Good conversation' } });

    // Click Submit
    const submitBtn = screen.getByText('Submit Disposition Outcome');
    fireEvent.click(submitBtn);
    
    expect(mockSubmitDisposition).toHaveBeenCalledWith({
      status: 'Picked',
      remarks: 'Good conversation',
      custom_pipeline_stage_id: 'stage-2',
    });
  });
});
