import { create } from 'zustand';
import { companyApi, CompanyResponse } from '../services/companyApi';

interface Filters {
  search: string;
}

interface Pagination {
  skip: number;
  limit: number;
}

interface CompanyState {
  companies: CompanyResponse[];
  isLoading: boolean;
  error: string | null;
  filters: Filters;
  pagination: Pagination;
  setFilters: (filters: Partial<Filters>) => void;
  setPagination: (pagination: Partial<Pagination>) => void;
  resetFilters: () => void;
  fetchCompanies: () => Promise<void>;
  createCompany: (payload: Parameters<typeof companyApi.createCompany>[0]) => Promise<CompanyResponse>;
  updateCompany: (companyId: string, payload: Parameters<typeof companyApi.updateCompany>[1]) => Promise<CompanyResponse>;
  deleteCompany: (companyId: string) => Promise<void>;
}

export const useCompanyStore = create<CompanyState>((set, get) => ({
  companies: [],
  isLoading: false,
  error: null,
  filters: {
    search: '',
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
    get().fetchCompanies();
  },

  setPagination: (newPagination) => {
    set((state) => ({
      pagination: { ...state.pagination, ...newPagination },
    }));
    get().fetchCompanies();
  },

  resetFilters: () => {
    set({
      filters: { search: '' },
      pagination: { skip: 0, limit: 20 },
    });
    get().fetchCompanies();
  },

  fetchCompanies: async () => {
    set({ isLoading: true, error: null });
    try {
      const { skip, limit } = get().pagination;
      const search = get().filters.search.trim() || undefined;

      const data = await companyApi.getCompanies({ skip, limit, search });
      set({ companies: data, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch companies',
        isLoading: false,
      });
    }
  },

  createCompany: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await companyApi.createCompany(payload);
      set({ isLoading: false });
      await get().fetchCompanies();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to create company';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  updateCompany: async (companyId, payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await companyApi.updateCompany(companyId, payload);
      set({ isLoading: false });
      await get().fetchCompanies();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update company';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  deleteCompany: async (companyId) => {
    set({ isLoading: true, error: null });
    try {
      await companyApi.deleteCompany(companyId);
      set({ isLoading: false });
      await get().fetchCompanies();
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to delete company';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },
}));
