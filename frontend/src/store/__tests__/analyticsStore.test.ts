import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useAnalyticsStore } from '../analyticsStore';
import { analyticsApi } from '../../services/analyticsApi';

vi.mock('../../services/analyticsApi', () => ({
  analyticsApi: {
    getDashboardMetrics: vi.fn(),
    createTarget: vi.fn(),
    getTargets: vi.fn(),
  },
}));

describe('analyticsStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    useAnalyticsStore.setState({
      dashboardData: null,
      activeTargets: [],
      isLoading: false,
      error: null,
    });
  });

  it('initializes with correct defaults', () => {
    const state = useAnalyticsStore.getState();
    expect(state.dashboardData).toBeNull();
    expect(state.activeTargets).toEqual([]);
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
  });

  it('fetches dashboard metrics successfully', async () => {
    const mockDashboardData = {
      role: 'Telecaller',
      metrics: {
        calls_made: 12,
        unique_leads_contacted: 10,
        conversions: 2,
        date: '2026-06-21',
      },
    } as any;
    vi.mocked(analyticsApi.getDashboardMetrics).mockResolvedValueOnce(mockDashboardData);

    await useAnalyticsStore.getState().fetchDashboardMetrics('2026-06-21');

    expect(analyticsApi.getDashboardMetrics).toHaveBeenCalledWith('2026-06-21');
    expect(useAnalyticsStore.getState().dashboardData).toEqual(mockDashboardData);
    expect(useAnalyticsStore.getState().isLoading).toBe(false);
  });

  it('fetches performance targets successfully', async () => {
    const mockTargets = [
      {
        id: 'target-1',
        organization_id: 'org-1',
        target_type: 'DAILY',
        metric_type: 'CALLS_MADE',
        target_value: 100,
        start_date: '2026-06-21',
        end_date: '2026-06-21',
      },
    ] as any[];
    vi.mocked(analyticsApi.getTargets).mockResolvedValueOnce(mockTargets);

    await useAnalyticsStore.getState().fetchTargets();

    expect(analyticsApi.getTargets).toHaveBeenCalled();
    expect(useAnalyticsStore.getState().activeTargets).toEqual(mockTargets);
  });

  it('saves target successfully and triggers refresh', async () => {
    const targetPayload = {
      target_type: 'DAILY',
      metric_type: 'CALLS_MADE',
      target_value: 50,
      start_date: '2026-06-21',
      end_date: '2026-06-21',
    } as any;
    const createdTarget = { id: 'new-target', ...targetPayload } as any;
    
    vi.mocked(analyticsApi.createTarget).mockResolvedValueOnce(createdTarget);
    vi.mocked(analyticsApi.getTargets).mockResolvedValueOnce([createdTarget]);

    await useAnalyticsStore.getState().upsertTarget(targetPayload);

    expect(analyticsApi.createTarget).toHaveBeenCalledWith(targetPayload);
    expect(analyticsApi.getTargets).toHaveBeenCalled();
    expect(useAnalyticsStore.getState().activeTargets).toEqual([createdTarget]);
  });
});
