import { create } from 'zustand';
import { contactApi, ContactResponse } from '../services/contactApi';

interface Filters {
  search: string;
  company_id: string;
}

interface Pagination {
  skip: number;
  limit: number;
}

interface ContactState {
  contacts: ContactResponse[];
  isLoading: boolean;
  error: string | null;
  filters: Filters;
  pagination: Pagination;
  setFilters: (filters: Partial<Filters>) => void;
  setPagination: (pagination: Partial<Pagination>) => void;
  resetFilters: () => void;
  fetchContacts: () => Promise<void>;
  createContact: (payload: Parameters<typeof contactApi.createContact>[0]) => Promise<ContactResponse>;
  updateContact: (contactId: string, payload: Parameters<typeof contactApi.updateContact>[1]) => Promise<ContactResponse>;
  deleteContact: (contactId: string) => Promise<void>;
}

export const useContactStore = create<ContactState>((set, get) => ({
  contacts: [],
  isLoading: false,
  error: null,
  filters: {
    search: '',
    company_id: 'All',
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
    get().fetchContacts();
  },

  setPagination: (newPagination) => {
    set((state) => ({
      pagination: { ...state.pagination, ...newPagination },
    }));
    get().fetchContacts();
  },

  resetFilters: () => {
    set({
      filters: { search: '', company_id: 'All' },
      pagination: { skip: 0, limit: 20 },
    });
    get().fetchContacts();
  },

  fetchContacts: async () => {
    set({ isLoading: true, error: null });
    try {
      const { skip, limit } = get().pagination;
      const search = get().filters.search.trim() || undefined;
      const company_id = get().filters.company_id === 'All' ? undefined : get().filters.company_id;

      const data = await contactApi.getContacts({ skip, limit, search, company_id });
      set({ contacts: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch contacts',
        isLoading: false,
      });
    }
  },

  createContact: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await contactApi.createContact(payload);
      set({ isLoading: false });
      await get().fetchContacts();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to create contact';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  updateContact: async (contactId, payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await contactApi.updateContact(contactId, payload);
      set({ isLoading: false });
      await get().fetchContacts();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update contact';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  deleteContact: async (contactId) => {
    set({ isLoading: true, error: null });
    try {
      await contactApi.deleteContact(contactId);
      set({ isLoading: false });
      await get().fetchContacts();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to delete contact';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },
}));
