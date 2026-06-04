import { create } from 'zustand';
import { 
  leadApi, 
  LeadResponse, 
  ImportPreviewResponse, 
  LeadImportProcessRequest, 
  LeadImportResponse, 
  AssignmentConfigResponse 
} from '../services/leadApi';

interface Filters {
  search: string;
  status: string;
  assigned_user_id: string;
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
  assignmentConfig: AssignmentConfigResponse | null;
  importHistory: LeadImportResponse[];
  setFilters: (filters: Partial<Filters>) => void;
  setPagination: (pagination: Partial<Pagination>) => void;
  resetFilters: () => void;
  fetchLeads: () => Promise<void>;
  createLead: (payload: Parameters<typeof leadApi.createLead>[0]) => Promise<LeadResponse>;
  updateLead: (leadId: string, payload: Parameters<typeof leadApi.updateLead>[1]) => Promise<LeadResponse>;
  deleteLead: (leadId: string) => Promise<void>;
  fetchAssignmentConfig: () => Promise<void>;
  toggleAssignmentConfig: (isActive: boolean) => Promise<void>;
  fetchImportHistory: () => Promise<void>;
  uploadImportFile: (file: File) => Promise<ImportPreviewResponse>;
  previewGoogleSheets: (url: string) => Promise<ImportPreviewResponse>;
  processImport: (payload: LeadImportProcessRequest) => Promise<LeadImportResponse>;
  downloadTemplate: (format: 'csv' | 'xlsx') => Promise<Blob>;
  downloadFailedRows: (importId: string) => Promise<Blob>;
}

export const useLeadStore = create<LeadState>((set, get) => ({
  leads: [],
  isLoading: false,
  error: null,
  filters: {
    search: '',
    status: 'All',
    assigned_user_id: 'All',
  },
  pagination: {
    skip: 0,
    limit: 20,
  },
  assignmentConfig: null,
  importHistory: [],

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
      filters: { search: '', status: 'All', assigned_user_id: 'All' },
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

      const data = await leadApi.getLeads({ skip, limit, search, status, assigned_user_id });
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

  fetchAssignmentConfig: async () => {
    set({ isLoading: true, error: null });
    try {
      const config = await leadApi.getAssignmentConfig();
      set({ assignmentConfig: config, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch assignment config',
        isLoading: false,
      });
    }
  },

  toggleAssignmentConfig: async (isActive) => {
    set({ isLoading: true, error: null });
    try {
      const config = await leadApi.updateAssignmentConfig(isActive);
      set({ assignmentConfig: config, isLoading: false });
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update assignment config';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  fetchImportHistory: async () => {
    set({ isLoading: true, error: null });
    try {
      const history = await leadApi.getImportHistory();
      set({ importHistory: history, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch import history',
        isLoading: false,
      });
    }
  },

  uploadImportFile: async (file) => {
    set({ isLoading: true, error: null });
    try {
      const res = await leadApi.uploadImportFile(file);
      set({ isLoading: false });
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to upload import file';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  previewGoogleSheets: async (url) => {
    set({ isLoading: true, error: null });
    try {
      const res = await leadApi.previewGoogleSheets(url);
      set({ isLoading: false });
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to preview Google Sheets';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  processImport: async (payload) => {
    set({ isLoading: true, error: null });
    try {
      const res = await leadApi.processImport(payload);
      set({ isLoading: false });
      await get().fetchLeads();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to process import';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  downloadTemplate: async (format) => {
    try {
      return await leadApi.downloadTemplate(format);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to download template';
      throw new Error(errorMsg);
    }
  },

  downloadFailedRows: async (importId) => {
    try {
      return await leadApi.downloadFailedRows(importId);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to download failed rows';
      throw new Error(errorMsg);
    }
  },
}));

