import { create } from 'zustand';
import { userApi, UserResponse, InvitationResponse } from '../services/userApi';

interface Filters {
  search: string;
  role: string;
  status: string;
}

interface Pagination {
  skip: number;
  limit: number;
}

interface UserState {
  users: UserResponse[];
  invitations: InvitationResponse[];
  isLoading: boolean;
  error: string | null;
  filters: Filters;
  pagination: Pagination;
  setFilters: (filters: Partial<Filters>) => void;
  setPagination: (pagination: Partial<Pagination>) => void;
  resetFilters: () => void;
  fetchUsers: () => Promise<void>;
  fetchInvitations: () => Promise<void>;
  inviteUser: (payload: { email: string; role: string }) => Promise<void>;
  updateUser: (userId: string, payload: Parameters<typeof userApi.updateUser>[1]) => Promise<void>;
  deleteUser: (userId: string) => Promise<void>;
  toggleUserStatus: (userId: string, isActive: boolean) => Promise<void>;
}

export const useUserStore = create<UserState>((set, get) => ({
  users: [],
  invitations: [],
  isLoading: false,
  error: null,
  filters: {
    search: '',
    role: 'All',
    status: 'All',
  },
  pagination: {
    skip: 0,
    limit: 20,
  },

  setFilters: (newFilters) => {
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
      pagination: { ...state.pagination, skip: 0 }, // Reset to page 1 on filter change
    }));
    get().fetchUsers();
  },

  setPagination: (newPagination) => {
    set((state) => ({
      pagination: { ...state.pagination, ...newPagination },
    }));
    get().fetchUsers();
  },

  resetFilters: () => {
    set({
      filters: { search: '', role: 'All', status: 'All' },
      pagination: { skip: 0, limit: 20 },
    });
    get().fetchUsers();
  },

  fetchUsers: async () => {
    set({ isLoading: true, error: null });
    try {
      const { skip, limit } = get().pagination;
      const querySearch = get().filters.search.trim() || undefined;

      const data = await userApi.getUsers({
        skip,
        limit,
        search: querySearch,
      });
      set({ users: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch users',
        isLoading: false,
      });
    }
  },

  fetchInvitations: async () => {
    set({ isLoading: true, error: null });
    try {
      const data = await userApi.getInvitations();
      set({ invitations: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch invitations',
        isLoading: false,
      });
    }
  },

  inviteUser: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await userApi.inviteUser(payload);
      set({ isLoading: false });
      // Refresh list of invitations
      await get().fetchInvitations();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to send invitation';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  updateUser: async (userId, payload) => {
    set({ isLoading: true, error: null });
    try {
      await userApi.updateUser(userId, payload);
      set({ isLoading: false });
      // Refresh list of users
      await get().fetchUsers();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update user';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  deleteUser: async (userId) => {
    set({ isLoading: true, error: null });
    try {
      await userApi.deleteUser(userId);
      set({ isLoading: false });
      // Refresh list of users
      await get().fetchUsers();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to delete user';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  toggleUserStatus: async (userId, isActive) => {
    set({ isLoading: true, error: null });
    try {
      await userApi.toggleUserStatus(userId, isActive);
      set({ isLoading: false });
      // Refresh list of users
      await get().fetchUsers();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to change user status';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },
}));
