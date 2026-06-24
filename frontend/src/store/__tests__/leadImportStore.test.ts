import { describe, it, expect, vi, beforeEach } from 'vitest';
import { useLeadImportStore } from '../leadImportStore';
import { leadImportApi } from '../../services/leadImportApi';

vi.mock('../../services/leadImportApi', () => ({
  leadImportApi: {
    getImportHistory: vi.fn(),
    getAssignmentConfig: vi.fn(),
    updateAssignmentConfig: vi.fn(),
    uploadImportFile: vi.fn(),
    previewGoogleSheets: vi.fn(),
    processImport: vi.fn(),
    downloadTemplate: vi.fn(),
    downloadFailedRows: vi.fn(),
  },
}));

describe('leadImportStore', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    // Reset Zustand store state before each test
    useLeadImportStore.setState({
      importHistory: [],
      assignmentConfig: null,
      isLoading: false,
      error: null,
      historyPagination: {
        skip: 0,
        limit: 10,
      },
    });
  });

  it('initializes with correct defaults', () => {
    const state = useLeadImportStore.getState();
    expect(state.importHistory).toEqual([]);
    expect(state.assignmentConfig).toBeNull();
    expect(state.isLoading).toBe(false);
    expect(state.error).toBeNull();
    expect(state.historyPagination).toEqual({ skip: 0, limit: 10 });
  });

  it('updates pagination and triggers a fetch history call', async () => {
    const mockHistory = [{ id: '1', filename: 'test.csv' }] as any[];
    vi.mocked(leadImportApi.getImportHistory).mockResolvedValueOnce(mockHistory);

    const store = useLeadImportStore.getState();
    await store.setHistoryPagination({ skip: 10 });

    expect(useLeadImportStore.getState().historyPagination.skip).toBe(10);
    expect(leadImportApi.getImportHistory).toHaveBeenCalledWith({ skip: 10, limit: 10 });
    expect(useLeadImportStore.getState().importHistory).toEqual(mockHistory);
  });

  it('fetches import history successfully', async () => {
    const mockHistory = [
      { id: '1', filename: 'leads.csv', status: 'COMPLETED' },
    ] as any[];
    vi.mocked(leadImportApi.getImportHistory).mockResolvedValueOnce(mockHistory);

    await useLeadImportStore.getState().fetchImportHistory();

    expect(useLeadImportStore.getState().isLoading).toBe(false);
    expect(useLeadImportStore.getState().importHistory).toEqual(mockHistory);
  });

  it('handles import history fetch failure', async () => {
    const errorMsg = 'Network Error';
    vi.mocked(leadImportApi.getImportHistory).mockRejectedValueOnce({
      response: { data: { detail: errorMsg } },
    });

    await useLeadImportStore.getState().fetchImportHistory();

    expect(useLeadImportStore.getState().isLoading).toBe(false);
    expect(useLeadImportStore.getState().error).toBe(errorMsg);
  });

  it('fetches assignment config successfully', async () => {
    const mockConfig = { organization_id: 'org-123', is_active: true, last_assigned_user_id: null };
    vi.mocked(leadImportApi.getAssignmentConfig).mockResolvedValueOnce(mockConfig);

    await useLeadImportStore.getState().fetchAssignmentConfig();

    expect(useLeadImportStore.getState().assignmentConfig).toEqual(mockConfig);
  });

  it('performs optimistic updates on assignment config toggle and rolls back on failure', async () => {
    const initialConfig = { organization_id: 'org-123', is_active: false, last_assigned_user_id: null };
    useLeadImportStore.setState({ assignmentConfig: initialConfig });

    // Mock API failure
    const errorMsg = 'Failed to save config';
    vi.mocked(leadImportApi.updateAssignmentConfig).mockRejectedValueOnce({
      response: { data: { detail: errorMsg } },
    });

    const store = useLeadImportStore.getState();
    
    // Call toggle with true, which should update state optimistically first, then fail and rollback
    const togglePromise = store.toggleAssignmentConfig(true);
    
    // Check optimistic update
    expect(useLeadImportStore.getState().assignmentConfig?.is_active).toBe(true);

    // Wait for the async process to fail
    await expect(togglePromise).rejects.toThrow(errorMsg);

    // Assert rollback happened
    expect(useLeadImportStore.getState().assignmentConfig?.is_active).toBe(false);
    expect(useLeadImportStore.getState().error).toBe(errorMsg);
  });

  it('successfully uploads file and returns preview', async () => {
    const mockFile = new File(['test'], 'test.csv');
    const mockPreview = { file_token: 'tok-123', headers: [], preview_rows: [] } as any;
    vi.mocked(leadImportApi.uploadImportFile).mockResolvedValueOnce(mockPreview);

    const result = await useLeadImportStore.getState().uploadImportFile(mockFile);

    expect(leadImportApi.uploadImportFile).toHaveBeenCalledWith(mockFile);
    expect(result).toEqual(mockPreview);
  });

  it('processes import and refreshes history', async () => {
    const processPayload = {
      file_token: 'tok-123',
      source_type: 'file',
      column_mapping: {},
      auto_assign: true,
    };
    const mockResult = { id: 'job-123', total_rows: 10, successful_rows: 10 } as any;
    vi.mocked(leadImportApi.processImport).mockResolvedValueOnce(mockResult);
    vi.mocked(leadImportApi.getImportHistory).mockResolvedValueOnce([]);

    const result = await useLeadImportStore.getState().processImport(processPayload);

    expect(leadImportApi.processImport).toHaveBeenCalledWith(processPayload);
    expect(leadImportApi.getImportHistory).toHaveBeenCalled();
    expect(result).toEqual(mockResult);
  });
});
