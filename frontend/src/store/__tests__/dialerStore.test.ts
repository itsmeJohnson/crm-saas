import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { useDialerStore } from '../dialerStore';
import { dialerApi } from '../../services/dialerApi';

vi.mock('../../services/dialerApi', () => ({
  dialerApi: {
    getNextLead: vi.fn(),
    updateState: vi.fn(),
    getState: vi.fn(),
    submitDisposition: vi.fn(),
  },
}));

describe('dialerStore', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.clearAllMocks();
    useDialerStore.getState().resetStore();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('initializes with correct defaults', () => {
    const state = useDialerStore.getState();
    expect(state.agentState).toBe('IDLE');
    expect(state.currentLead).toBeNull();
    expect(state.breakReason).toBeNull();
    expect(state.callDuration).toBe(0);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('fetches current state successfully', async () => {
    vi.mocked(dialerApi.getState).mockResolvedValueOnce({
      state: 'BREAK',
      timestamp: '...',
      metadata: { break_reason: 'Lunch' },
    });

    await useDialerStore.getState().fetchCurrentState();

    const state = useDialerStore.getState();
    expect(state.agentState).toBe('BREAK');
    expect(state.breakReason).toBe('Lunch');
    expect(state.isLoading).toBe(false);
  });

  it('starts calling successfully, updates lead, and runs active call timer', async () => {
    const mockLead = {
      id: 'lead-123',
      first_name: 'John',
      last_name: 'Doe',
      phone: '+91********10',
    } as any;
    vi.mocked(dialerApi.getNextLead).mockResolvedValueOnce(mockLead);

    await useDialerStore.getState().startCalling(true);

    const stateAfterCall = useDialerStore.getState();
    expect(stateAfterCall.currentLead).toEqual(mockLead);
    expect(stateAfterCall.agentState).toBe('ACTIVE_CALLING');
    expect(stateAfterCall.callDuration).toBe(0);

    // Advance timers by 5 seconds
    vi.advanceTimersByTime(5000);
    expect(useDialerStore.getState().callDuration).toBe(5);
  });

  it('submits disposition successfully, stops timer, and resets state to IDLE', async () => {
    const mockLead = {
      id: 'lead-123',
      first_name: 'John',
      last_name: 'Doe',
      phone: '+91********10',
    } as any;
    
    // Setup store with active call
    useDialerStore.setState({
      currentLead: mockLead,
      agentState: 'ACTIVE_CALLING',
      callDuration: 5,
    });
    
    // Mock disposition submission
    vi.mocked(dialerApi.submitDisposition).mockResolvedValueOnce({} as any);

    await useDialerStore.getState().submitDisposition({
      status: 'Busy',
      remarks: 'No answer',
    });

    expect(dialerApi.submitDisposition).toHaveBeenCalledWith('lead-123', {
      status: 'Busy',
      remarks: 'No answer',
    });

    const state = useDialerStore.getState();
    expect(state.currentLead).toBeNull();
    expect(state.callDuration).toBe(0);
    expect(state.agentState).toBe('IDLE');
  });

  it('handles goOnBreak and endBreak successfully', async () => {
    vi.mocked(dialerApi.updateState).mockResolvedValue({} as any);

    // 1. Go on break
    await useDialerStore.getState().goOnBreak('Tea');
    expect(dialerApi.updateState).toHaveBeenCalledWith({
      state: 'BREAK',
      metadata: { break_reason: 'Tea' },
    });
    expect(useDialerStore.getState().agentState).toBe('BREAK');
    expect(useDialerStore.getState().breakReason).toBe('Tea');

    // 2. End break
    await useDialerStore.getState().endBreak();
    expect(dialerApi.updateState).toHaveBeenCalledWith({
      state: 'IDLE',
    });
    expect(useDialerStore.getState().agentState).toBe('IDLE');
    expect(useDialerStore.getState().breakReason).toBeNull();
  });
});
