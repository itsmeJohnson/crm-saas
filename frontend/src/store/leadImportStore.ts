import { create } from 'zustand';
import { 
  leadImportApi, 
  ImportPreviewResponse, 
  LeadImportProcessRequest, 
  LeadImportResponse, 
  AssignmentConfigResponse 
} from '../services/leadImportApi';

interface HistoryPagination {
  skip: number;
  limit: number;
}

interface LeadImportState {
  importHistory: LeadImportResponse[];
  assignmentConfig: AssignmentConfigResponse | null;
  isLoading: boolean;
  error: string | null;
  historyPagination: HistoryPagination;
  
  setHistoryPagination: (pagination: Partial<HistoryPagination>) => Promise<void>;
  fetchImportHistory: () => Promise<void>;
  fetchAssignmentConfig: () => Promise<void>;
  toggleAssignmentConfig: (isActive: boolean) => Promise<void>;
  uploadImportFile: (file: File) => Promise<ImportPreviewResponse>;
  previewGoogleSheets: (url: string) => Promise<ImportPreviewResponse>;
  processImport: (payload: LeadImportProcessRequest) => Promise<LeadImportResponse>;
  downloadTemplate: (format: 'csv' | 'xlsx', vertical?: string | null) => Promise<Blob>;
  downloadFailedRows: (importId: string) => Promise<Blob>;
  clearError: () => void;
}

export const useLeadImportStore = create<LeadImportState>((set, get) => ({
  importHistory: [],
  assignmentConfig: null,
  isLoading: false,
  error: null,
  historyPagination: {
    skip: 0,
    limit: 10,
  },

  setHistoryPagination: async (newPagination) => {
    set((state) => ({
      historyPagination: { ...state.historyPagination, ...newPagination },
    }));
    await get().fetchImportHistory();
  },

  fetchImportHistory: async () => {
    set({ isLoading: true, error: null });
    try {
      const { skip, limit } = get().historyPagination;
      const history = await leadImportApi.getImportHistory({ skip, limit });
      set({ importHistory: history, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch import history',
        isLoading: false,
      });
    }
  },

  fetchAssignmentConfig: async () => {
    set({ isLoading: true, error: null });
    try {
      const config = await leadImportApi.getAssignmentConfig();
      set({ assignmentConfig: config, isLoading: false });
    } catch (err: any) {
      set({
        error: err.response?.data?.detail || 'Failed to fetch assignment config',
        isLoading: false,
      });
    }
  },

  toggleAssignmentConfig: async (isActive) => {
    // Save current config for potential rollback
    const previousConfig = get().assignmentConfig;
    
    // Optimistic Update
    if (previousConfig) {
      set({
        assignmentConfig: { ...previousConfig, is_active: isActive },
        error: null,
      });
    }

    try {
      const config = await leadImportApi.updateAssignmentConfig(isActive);
      set({ assignmentConfig: config, isLoading: false });
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to update assignment config';
      
      // Rollback on failure
      set({ 
        assignmentConfig: previousConfig,
        error: errorMsg, 
        isLoading: false 
      });
      throw new Error(errorMsg);
    }
  },

  uploadImportFile: async (file) => {
    set({ isLoading: true, error: null });
    try {
      const res = await leadImportApi.uploadImportFile(file);
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
      const res = await leadImportApi.previewGoogleSheets(url);
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
      const res = await leadImportApi.processImport(payload);
      set({ isLoading: false });
      // Optimistic refresh of import history list
      await get().fetchImportHistory();
      return res;
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to process import';
      set({ error: errorMsg, isLoading: false });
      throw new Error(errorMsg);
    }
  },

  downloadTemplate: async (format, vertical) => {
    try {
      return await leadImportApi.downloadTemplate(format, vertical);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to download template';
      throw new Error(errorMsg);
    }
  },

  downloadFailedRows: async (importId) => {
    try {
      return await leadImportApi.downloadFailedRows(importId);
    } catch (err: any) {
      const errorMsg = err.response?.data?.detail || 'Failed to download failed rows';
      throw new Error(errorMsg);
    }
  },

  clearError: () => set({ error: null }),
}));
