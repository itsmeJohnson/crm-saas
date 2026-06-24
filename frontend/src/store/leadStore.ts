import { create } from 'zustand';
import { leadApi, LeadResponse } from '../services/leadApi';

interface Filters {
  search: string;
  status: string;
  assigned_user_id: string;
  name: string;
  city: string;
}

interface Pagination {
  skip: number;
  limit: number;
}

interface LeadState {
  leads: LeadResponse[];
  isLoading: boolean;
  error: string | null;
  filters: Filters;
  pagination: Pagination;
  setFilters: (filters: Partial<Filters>) => void;
  setPagination: (pagination: Partial<Pagination>) => void;
  resetFilters: () => void;
  fetchLeads: () => Promise<void>;
  createLead: (payload: Parameters<typeof leadApi.createLead>[0]) => Promise<LeadResponse>;
  updateLead: (leadId: string, payload: Parameters<typeof leadApi.updateLead>[1]) => Promise<LeadResponse>;
  deleteLead: (leadId: string) => Promise<void>;
  assignLeadsBulk: (payload: Parameters<typeof leadApi.assignLeadsBulk>[0]) => Promise<void>;
  transferLeads: (payload: Parameters<typeof leadApi.transferLeads>[0]) => Promise<void>;
}

export const useLeadStore = create<LeadState>((set, get) => ({
  leads: [],
  isLoading: false,
  error: null,
  filters: {
    search: '',
    status: 'All',
    assigned_user_id: 'All',
    name: '',
    city: '',
  },
  pagination: {
    skip: 0,
    limit: 20,
  },

  setFilters: (newFilters) => {
    set((state) => ({
      filters: { ...state.filters, ...newFilters },
      pagination: { ...state.pagination, skip: 0 },
    }));
    get().fetchLeads();
  },

  setPagination: (newPagination) => {
    set((state) => ({
      pagination: { ...state.pagination, ...newPagination },
    }));
    get().fetchLeads();
  },

  resetFilters: () => {
    set({
      filters: { search: '', status: 'All', assigned_user_id: 'All', name: '', city: '' },
      pagination: { skip: 0, limit: 20 },
    });
    get().fetchLeads();
  },

  fetchLeads: async () => {
    set({ isLoading: true, error: null });
    try {
      const { skip, limit } = get().pagination;
      const search = get().filters.search.trim() || undefined;
      const status = get().filters.status === 'All' ? undefined : get().filters.status;
      const assigned_user_id = get().filters.assigned_user_id === 'All' ? undefined : get().filters.assigned_user_id;
      const name = get().filters.name.trim() || undefined;
      const city = get().filters.city.trim() || undefined;

      const data = await leadApi.getLeads({ skip, limit, search, status, assigned_user_id, name, city });
      set({ leads: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch leads',
        isLoading: false,
      });
    }
  },

  createLead: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await leadApi.createLead(payload);
      set({ isLoading: false });
      await get().fetchLeads();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to create lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  updateLead: async (leadId, payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await leadApi.updateLead(leadId, payload);
      set({ isLoading: false });
      await get().fetchLeads();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  deleteLead: async (leadId) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.deleteLead(leadId);
      set({ isLoading: false });
      await get().fetchLeads();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to delete lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  assignLeadsBulk: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.assignLeadsBulk(payload);
      set({ isLoading: false });
      await get().fetchLeads();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed bulk assignment';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  transferLeads: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.transferLeads(payload);
      set({ isLoading: false });
      await get().fetchLeads();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed lead transfer';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },
}));
