import { create } from 'zustand';
import { leadApi, LeadResponse } from '../services/leadApi';

interface Filters {
  search: string;
  status: string;
  assigned_user_id: string;
  name: string;
  city: string;
  source: string;
  priority: string;
  min_value: string;
  max_value: string;
  include_archived: boolean;
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
  archiveLead: (leadId: string) => Promise<void>;
  restoreLead: (leadId: string) => Promise<void>;
  bulkUpdate: (payload: Parameters<typeof leadApi.bulkUpdate>[0]) => Promise<void>;
  exportLeads: (format: 'csv' | 'xlsx') => Promise<void>;
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
    source: '',
    priority: 'All',
    min_value: '',
    max_value: '',
    include_archived: false,
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
      filters: {
        search: '', status: 'All', assigned_user_id: 'All', name: '', city: '',
        source: '', priority: 'All', min_value: '', max_value: '', include_archived: false,
      },
      pagination: { skip: 0, limit: 20 },
    });
    get().fetchLeads();
  },

  fetchLeads: async () => {
    set({ isLoading: true, error: null });
    try {
      const { skip, limit } = get().pagination;
      const f = get().filters;
      const params = {
        skip,
        limit,
        search: f.search.trim() || undefined,
        status: f.status === 'All' ? undefined : f.status,
        assigned_user_id: f.assigned_user_id === 'All' ? undefined : f.assigned_user_id,
        name: f.name.trim() || undefined,
        city: f.city.trim() || undefined,
        source: f.source.trim() || undefined,
        priority: f.priority === 'All' ? undefined : f.priority,
        min_value: f.min_value !== '' ? Number(f.min_value) : undefined,
        max_value: f.max_value !== '' ? Number(f.max_value) : undefined,
        include_archived: f.include_archived || undefined,
      };
      const data = await leadApi.getLeads(params);
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

  archiveLead: async (leadId) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.archiveLead(leadId);
      set({ isLoading: false });
      await get().fetchLeads();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to archive lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  restoreLead: async (leadId) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.restoreLead(leadId);
      set({ isLoading: false });
      await get().fetchLeads();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to restore lead';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  bulkUpdate: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await leadApi.bulkUpdate(payload);
      set({ isLoading: false });
      await get().fetchLeads();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed bulk update';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  exportLeads: async (format) => {
    const f = get().filters;
    const params = {
      format,
      search: f.search.trim() || undefined,
      status: f.status === 'All' ? undefined : f.status,
      assigned_user_id: f.assigned_user_id === 'All' ? undefined : f.assigned_user_id,
      name: f.name.trim() || undefined,
      city: f.city.trim() || undefined,
      source: f.source.trim() || undefined,
      priority: f.priority === 'All' ? undefined : f.priority,
      min_value: f.min_value !== '' ? Number(f.min_value) : undefined,
      max_value: f.max_value !== '' ? Number(f.max_value) : undefined,
      include_archived: f.include_archived || undefined,
    };
    const blob = await leadApi.exportLeads(params);
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `leads_export.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
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
