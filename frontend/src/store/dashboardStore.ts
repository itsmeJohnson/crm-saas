import { create } from 'zustand';
import { dashboardApi, DashboardSummaryResponse, RecentActivityItem } from '../services/dashboardApi';

interface DashboardState {
  summary: DashboardSummaryResponse | null;
  recentActivities: RecentActivityItem[];
  totalRecent: number;
  page: number;
  limit: number;
  isLoadingSummary: boolean;
  isLoadingActivities: boolean;
  error: string | null;
  fetchSummary: () => Promise<void>;
  fetchRecentActivities: () => Promise<void>;
  setPage: (page: number) => void;
  setLimit: (limit: number) => void;
}

export const useDashboardStore = create<DashboardState>((set, get) => ({
  summary: null,
  recentActivities: [],
  totalRecent: 0,
  page: 1,
  limit: 10,
  isLoadingSummary: false,
  isLoadingActivities: false,
  error: null,

  fetchSummary: async () => {
    set({ isLoadingSummary: true, error: null });
    try {
      const data = await dashboardApi.getSummary();
      set({ summary: data, isLoadingSummary: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch dashboard summary',
        isLoadingSummary: false,
      });
    }
  },

  fetchRecentActivities: async () => {
    set({ isLoadingActivities: true, error: null });
    try {
      const { page, limit } = get();
      const data = await dashboardApi.getRecentActivities({ page, limit });
      set({
        recentActivities: data.items,
        totalRecent: data.total,
        isLoadingActivities: false,
      });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch recent activities',
        isLoadingActivities: false,
      });
    }
  },

  setPage: (page: number) => {
    set({ page });
    get().fetchRecentActivities();
  },

  setLimit: (limit: number) => {
    set({ limit, page: 1 });
    get().fetchRecentActivities();
  },
}));
