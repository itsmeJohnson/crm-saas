// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { ImportHistoryTable } from '../ImportHistoryTable';
import { useLeadImportStore } from '../../../store/leadImportStore';
import { useAuthStore } from '../../../store/authStore';

vi.mock('../../../store/leadImportStore', () => ({
  useLeadImportStore: vi.fn(),
}));

vi.mock('../../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('ImportHistoryTable Component', () => {
  const mockFetchImportHistory = vi.fn();
  const mockDownloadFailedRows = vi.fn();

  const mockHistoryData = [
    {
      id: 'job-1',
      filename: 'leads_clean.csv',
      status: 'COMPLETED',
      total_rows: 50,
      successful_rows: 50,
      failed_rows: 0,
      mapping_confidence: 1.0,
      created_at: '2026-06-04T10:00:00Z',
    },
    {
      id: 'job-2',
      filename: 'leads_broken.csv',
      status: 'PARTIAL_SUCCESS',
      total_rows: 10,
      successful_rows: 8,
      failed_rows: 2,
      mapping_confidence: 0.8,
      created_at: '2026-06-04T11:00:00Z',
    },
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders nothing when user is Employee', () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'Employee' },
    });
    (useLeadImportStore as any).mockReturnValue({
      importHistory: [],
      historyPagination: { skip: 0, limit: 10 },
      fetchImportHistory: mockFetchImportHistory,
    });

    const { container } = render(<ImportHistoryTable />);
    expect(container.firstChild).toBeNull();
  });

  it('fetches and displays history details for privileged roles', () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });
    (useLeadImportStore as any).mockReturnValue({
      importHistory: mockHistoryData,
      historyPagination: { skip: 0, limit: 10 },
      fetchImportHistory: mockFetchImportHistory,
      downloadFailedRows: mockDownloadFailedRows,
      isLoading: false,
      error: null,
    });

    render(<ImportHistoryTable />);

    expect(mockFetchImportHistory).toHaveBeenCalled();
    expect(screen.getByText('leads_clean.csv')).toBeDefined();
    expect(screen.getByText('leads_broken.csv')).toBeDefined();
    expect(screen.getByText('Completed')).toBeDefined();
    expect(screen.getByText('Partial Success')).toBeDefined();
    expect(screen.getByText('100%')).toBeDefined();
    expect(screen.getByText('80%')).toBeDefined();
    
    // Rows display
    expect(screen.getByText('50')).toBeDefined();
  });

  it('triggers error file download when clicking download button for jobs with failures', () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'Manager' },
    });
    (useLeadImportStore as any).mockReturnValue({
      importHistory: mockHistoryData,
      historyPagination: { skip: 0, limit: 10 },
      fetchImportHistory: mockFetchImportHistory,
      downloadFailedRows: mockDownloadFailedRows,
      isLoading: false,
      error: null,
    });

    window.URL.createObjectURL = vi.fn().mockReturnValue('mock-url');
    window.URL.revokeObjectURL = vi.fn();

    render(<ImportHistoryTable />);

    // Button is at index 0 (which is prev pagination page button)
    // and index 1 (next page button)
    // and index 2 (download failed rows button for job-2)
    const btn = screen.getByTitle('Download Failed Rows Report');
    fireEvent.click(btn);

    expect(mockDownloadFailedRows).toHaveBeenCalledWith('job-2');
  });
});
