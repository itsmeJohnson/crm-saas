// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { ImportModal } from '../ImportModal';
import { useLeadImportStore } from '../../../store/leadImportStore';
import { useAuthStore } from '../../../store/authStore';
import { userApi } from '../../../services/userApi';

vi.mock('../../../store/leadImportStore', () => ({
  useLeadImportStore: vi.fn().mockReturnValue({
    clearError: vi.fn(),
  }),
}));

vi.mock('../../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../../../services/userApi', () => ({
  userApi: {
    getUsers: vi.fn(),
  },
}));

describe('ImportModal Component', () => {
  const mockUploadImportFile = vi.fn();
  const mockPreviewGoogleSheets = vi.fn();
  const mockProcessImport = vi.fn();
  const mockDownloadTemplate = vi.fn();
  const mockDownloadFailedRows = vi.fn();
  const mockClearError = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useLeadImportStore as any).mockReturnValue({
      uploadImportFile: mockUploadImportFile,
      previewGoogleSheets: mockPreviewGoogleSheets,
      processImport: mockProcessImport,
      downloadTemplate: mockDownloadTemplate,
      downloadFailedRows: mockDownloadFailedRows,
      clearError: mockClearError,
    });
    (userApi.getUsers as any).mockResolvedValue([]);
  });

  afterEach(() => {
    cleanup();
  });

  it('renders nothing when isOpen is false', () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });

    const { container } = render(
      <ImportModal isOpen={false} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders nothing when user is Employee', () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'Employee' },
    });

    const { container } = render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders layout and handles template downloads for privileged roles', () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });

    render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    expect(screen.getByText('Bulk Import Leads')).toBeDefined();
    expect(screen.getByText('Local File Upload')).toBeDefined();
    expect(screen.getByText('Google Sheets Link')).toBeDefined();

    mockDownloadTemplate.mockResolvedValue(new Blob(['First Name,Last Name'], { type: 'text/csv' }));
    window.URL.createObjectURL = vi.fn().mockReturnValue('mock-url');
    window.URL.revokeObjectURL = vi.fn();

    const csvBtn = screen.getByText('CSV Template');
    fireEvent.click(csvBtn);

    expect(mockDownloadTemplate).toHaveBeenCalledWith('csv');
  });

  it('transitions to mapping step on successful upload', async () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });

    const mockPreviewResponse = {
      file_token: 'token-123',
      headers: ['First Name', 'Last Name', 'Email', 'Job Title'],
      suggested_mapping: {
        first_name: { column: 'First Name', confidence: 1.0 },
        last_name: { column: 'Last Name', confidence: 1.0 },
        email: { column: 'Email', confidence: 1.0 },
        title: { column: 'Job Title', confidence: 1.0 },
      },
      preview_rows: [
        { 'First Name': 'John', 'Last Name': 'Doe', 'Email': 'john@test.com', 'Job Title': 'Developer' }
      ]
    };
    
    mockUploadImportFile.mockResolvedValue(mockPreviewResponse);

    render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    const file = new File(['John,Doe,john@test.com,Developer'], 'leads.csv', { type: 'text/csv' });
    const fileInput = document.querySelector('input[type="file"]');
    expect(fileInput).not.toBeNull();
    
    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }

    const nextBtn = screen.getByText('Next');
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(mockUploadImportFile).toHaveBeenCalled();
      expect(screen.getByText('Map File Headers to Lead Properties')).toBeDefined();
      expect(screen.getByText('Source Data Preview')).toBeDefined();
    });
  });

  it('displays validation error if required fields are missing during mapping', async () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });

    const mockPreviewResponse = {
      file_token: 'token-123',
      headers: ['First Name', 'Last Name'],
      suggested_mapping: {
        first_name: { column: 'First Name', confidence: 1.0 },
        last_name: { column: 'Last Name', confidence: 1.0 },
      },
      preview_rows: [
        { 'First Name': 'John', 'Last Name': 'Doe' }
      ]
    };
    
    mockUploadImportFile.mockResolvedValue(mockPreviewResponse);

    render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    // Skip to Step 2
    const file = new File(['John,Doe'], 'leads.csv', { type: 'text/csv' });
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }
    const nextBtn = screen.getByText('Next');
    fireEvent.click(nextBtn);

    await waitFor(() => {
      expect(screen.getByText('Map File Headers to Lead Properties')).toBeDefined();
    });

    // Try processing mapping (missing Job Title/title)
    const processBtn = screen.getByText('Process Mapping');
    fireEvent.click(processBtn);

    await waitFor(() => {
      expect(screen.getByText(/Job Title\/Lead Title is a required field and is missing/)).toBeDefined();
      expect(mockProcessImport).not.toHaveBeenCalled();
    });
  });

  it('completes the import flow and supports resetting to import another file', async () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });

    const mockPreviewResponse = {
      file_token: 'token-123',
      headers: ['First Name', 'Last Name', 'Email', 'Job Title'],
      suggested_mapping: {
        first_name: { column: 'First Name', confidence: 1.0 },
        last_name: { column: 'Last Name', confidence: 1.0 },
        email: { column: 'Email', confidence: 1.0 },
        title: { column: 'Job Title', confidence: 1.0 },
      },
      preview_rows: [
        { 'First Name': 'John', 'Last Name': 'Doe', 'Email': 'john@test.com', 'Job Title': 'Developer' }
      ]
    };

    const mockImportResponse = {
      id: 'import-id-456',
      organization_id: 'org-id',
      filename: 'leads.csv',
      status: 'COMPLETED',
      total_rows: 1,
      successful_rows: 1,
      failed_rows: 0,
      mapping_confidence: 1.0,
      error_summary: [],
      failed_rows_file_path: null,
      created_by: 'user-id',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    mockUploadImportFile.mockResolvedValue(mockPreviewResponse);
    mockProcessImport.mockResolvedValue(mockImportResponse);

    render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    // Step 1: Upload file
    const file = new File(['John,Doe,john@test.com,Developer'], 'leads.csv', { type: 'text/csv' });
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }
    fireEvent.click(screen.getByText('Next'));

    // Step 2: Preview Mapping and Process Mapping
    await waitFor(() => {
      expect(screen.getByText('Map File Headers to Lead Properties')).toBeDefined();
    });

    fireEvent.click(screen.getByText('Process Mapping'));

    // Step 3: Summary screen
    await waitFor(() => {
      expect(screen.getByText('Import Batch Processed')).toBeDefined();
      expect(screen.getByText('Import Another File')).toBeDefined();
      expect(screen.getByText('Close')).toBeDefined();
    });

    // Test clicking "Import Another File" resets the flow
    fireEvent.click(screen.getByText('Import Another File'));

    await waitFor(() => {
      expect(screen.getByText('Local File Upload')).toBeDefined();
      expect(screen.queryByText('Import Batch Processed')).toBeNull();
    });
  });

  it('calls onSuccess and onClose when Close button is clicked on summary step', async () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });

    const mockPreviewResponse = {
      file_token: 'token-123',
      headers: ['First Name', 'Last Name', 'Email', 'Job Title'],
      suggested_mapping: {
        first_name: { column: 'First Name', confidence: 1.0 },
        last_name: { column: 'Last Name', confidence: 1.0 },
        email: { column: 'Email', confidence: 1.0 },
        title: { column: 'Job Title', confidence: 1.0 },
      },
      preview_rows: [
        { 'First Name': 'John', 'Last Name': 'Doe', 'Email': 'john@test.com', 'Job Title': 'Developer' }
      ]
    };

    const mockImportResponse = {
      id: 'import-id-456',
      organization_id: 'org-id',
      filename: 'leads.csv',
      status: 'COMPLETED',
      total_rows: 1,
      successful_rows: 1,
      failed_rows: 0,
      mapping_confidence: 1.0,
      error_summary: [],
      failed_rows_file_path: null,
      created_by: 'user-id',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString()
    };

    mockUploadImportFile.mockResolvedValue(mockPreviewResponse);
    mockProcessImport.mockResolvedValue(mockImportResponse);

    render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    // Step 1: Upload file
    const file = new File(['John,Doe,john@test.com,Developer'], 'leads.csv', { type: 'text/csv' });
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }
    fireEvent.click(screen.getByText('Next'));

    // Step 2: Process Mapping
    await waitFor(() => {
      expect(screen.getByText('Map File Headers to Lead Properties')).toBeDefined();
    });
    fireEvent.click(screen.getByText('Process Mapping'));

    // Step 3: Summary screen
    await waitFor(() => {
      expect(screen.getByText('Import Batch Processed')).toBeDefined();
    });

    // Click Close
    fireEvent.click(screen.getByText('Close'));
    expect(mockOnSuccess).toHaveBeenCalled();
    expect(mockOnClose).toHaveBeenCalled();
  });

  it('resets all state on close/unmount and clears Zustand error', async () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });

    const { rerender } = render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    expect(screen.getByText('Bulk Import Leads')).toBeDefined();

    // Rerender with isOpen = false
    rerender(<ImportModal isOpen={false} onClose={mockOnClose} onSuccess={mockOnSuccess} />);

    // Verify Zustand clearError was called
    expect(mockClearError).toHaveBeenCalled();
  });

  it('fetches active employees when opened and handles dropdown states', async () => {
    (useAuthStore as any).mockReturnValue({
      user: { role: 'OrgAdmin' },
    });

    const mockEmployeesList = [
      {
        id: 'emp-99',
        email: 'employee99@tenant.com',
        first_name: 'David',
        last_name: 'Employee',
        role: 'Employee',
        is_active: true,
        is_verified: true,
        is_invited: false,
        organization_id: 'org-1',
        created_at: '',
        updated_at: ''
      }
    ];

    (userApi.getUsers as any).mockResolvedValue(mockEmployeesList);

    const mockPreviewResponse = {
      file_token: 'token-123',
      headers: ['First Name', 'Last Name', 'Email', 'Job Title'],
      suggested_mapping: {
        first_name: { column: 'First Name', confidence: 1.0 },
        last_name: { column: 'Last Name', confidence: 1.0 },
        email: { column: 'Email', confidence: 1.0 },
        title: { column: 'Job Title', confidence: 1.0 },
      },
      preview_rows: [
        { 'First Name': 'John', 'Last Name': 'Doe', 'Email': 'john@test.com', 'Job Title': 'Developer' }
      ]
    };
    mockUploadImportFile.mockResolvedValue(mockPreviewResponse);

    render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    // Should fetch active employees on open
    await waitFor(() => {
      expect(userApi.getUsers).toHaveBeenCalledWith({ limit: 100, role: 'Employee', is_active: true });
    });

    // Advance to step 2 (preview_mapping)
    const file = new File(['John,Doe,john@test.com,Developer'], 'leads.csv', { type: 'text/csv' });
    const fileInput = document.querySelector('input[type="file"]');
    if (fileInput) {
      fireEvent.change(fileInput, { target: { files: [file] } });
    }
    fireEvent.click(screen.getByText('Next'));

    await waitFor(() => {
      expect(screen.getByText('Map File Headers to Lead Properties')).toBeDefined();
    });

    // Toggle specific user mode radio
    const radio = screen.getByDisplayValue('SPECIFIC_USER');
    fireEvent.click(radio);

    // Dropdown should render and contain the mock employee
    await waitFor(() => {
      expect(screen.getByText('Select Assignee')).toBeDefined();
      expect(screen.getByText('David Employee (employee99@tenant.com)')).toBeDefined();
    });
  });
});

