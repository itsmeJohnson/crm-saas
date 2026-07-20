import { create } from 'zustand';
import { contactApi, ContactResponse } from '../services/contactApi';

interface Filters {
  search: string;
  company_id: string;
  assigned_user_id: string;
  tag: string;
  has_email: string; // 'All' | 'yes' | 'no'
}

interface Pagination {
  skip: number;
  limit: number;
}

const buildParams = (f: Filters) => ({
  search: f.search.trim() || undefined,
  company_id: f.company_id === 'All' ? undefined : f.company_id,
  assigned_user_id: f.assigned_user_id === 'All' ? undefined : f.assigned_user_id,
  tag: f.tag.trim() || undefined,
  has_email: f.has_email === 'All' ? undefined : f.has_email === 'yes',
});

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
  bulkUpdate: (payload: Parameters<typeof contactApi.bulkUpdate>[0]) => Promise<void>;
  bulkDelete: (contactIds: string[]) => Promise<void>;
  exportContacts: (format: 'csv' | 'xlsx') => Promise<void>;
}

export const useContactStore = create<ContactState>((set, get) => ({
  contacts: [],
  isLoading: false,
  error: null,
  filters: {
    search: '',
    company_id: 'All',
    assigned_user_id: 'All',
    tag: '',
    has_email: 'All',
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
      filters: { search: '', company_id: 'All', assigned_user_id: 'All', tag: '', has_email: 'All' },
      pagination: { skip: 0, limit: 20 },
    });
    get().fetchContacts();
  },

  fetchContacts: async () => {
    set({ isLoading: true, error: null });
    try {
      const { skip, limit } = get().pagination;
      const data = await contactApi.getContacts({ skip, limit, ...buildParams(get().filters) });
      set({ contacts: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch contacts',
        isLoading: false,
      });
    }
  },

  bulkUpdate: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      await contactApi.bulkUpdate(payload);
      set({ isLoading: false });
      await get().fetchContacts();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Bulk update failed';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  bulkDelete: async (contactIds) => {
    set({ isLoading: true, error: null });
    try {
      await contactApi.bulkDelete(contactIds);
      set({ isLoading: false });
      await get().fetchContacts();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Bulk delete failed';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  exportContacts: async (format) => {
    const blob = await contactApi.exportContacts({ format, ...buildParams(get().filters) });
    const url = window.URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `contacts_export.${format}`;
    document.body.appendChild(a);
    a.click();
    a.remove();
    window.URL.revokeObjectURL(url);
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
