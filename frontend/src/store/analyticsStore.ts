import { create } from 'zustand';
import {
  analyticsApi,
  UnifiedDashboardResponse,
  PerformanceTarget,
  PerformanceTargetCreate,
} from '../services/analyticsApi';

interface AnalyticsState {
  dashboardData: UnifiedDashboardResponse | null;
  activeTargets: PerformanceTarget[];
  isLoading: boolean;
  error: string | null;
  
  fetchDashboardMetrics: (targetDate?: string) => Promise<void>;
  fetchTargets: () => Promise<void>;
  upsertTarget: (targetData: PerformanceTargetCreate) => Promise<void>;
}

export const useAnalyticsStore = create<AnalyticsState>((set, get) => ({
  dashboardData: null,
  activeTargets: [],
  isLoading: false,
  error: null,

  fetchDashboardMetrics: async (targetDate) => {
    set({ isLoading: true, error: null });
    try {
      const data = await analyticsApi.getDashboardMetrics(targetDate);
      set({ dashboardData: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch dashboard metrics',
        isLoading: false,
      });
    }
  },

  fetchTargets: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await analyticsApi.getTargets();
      set({ activeTargets: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch targets',
        isLoading: false,
      });
    }
  },

  upsertTarget: async (targetData) => {
    set({ isLoading: true, error: null });
    try {
      await analyticsApi.createTarget(targetData);
      set({ isLoading: false });
      await get().fetchTargets();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to save target';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },
}));
