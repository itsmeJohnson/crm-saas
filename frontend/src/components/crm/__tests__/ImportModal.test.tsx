// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup, waitFor } from '@testing-library/react';
import { ImportModal } from '../ImportModal';
import { useLeadStore } from '../../../store/leadStore';

vi.mock('../../../store/leadStore', () => ({
  useLeadStore: vi.fn(),
}));

describe('ImportModal Component', () => {
  const mockUploadImportFile = vi.fn();
  const mockPreviewGoogleSheets = vi.fn();
  const mockProcessImport = vi.fn();
  const mockDownloadTemplate = vi.fn();
  const mockDownloadFailedRows = vi.fn();
  const mockOnClose = vi.fn();
  const mockOnSuccess = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
    (useLeadStore as any).mockReturnValue({
      uploadImportFile: mockUploadImportFile,
      previewGoogleSheets: mockPreviewGoogleSheets,
      processImport: mockProcessImport,
      downloadTemplate: mockDownloadTemplate,
      downloadFailedRows: mockDownloadFailedRows,
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders nothing when isOpen is false', () => {
    const { container } = render(
      <ImportModal isOpen={false} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );
    expect(container.firstChild).toBeNull();
  });

  it('renders standard options and handles template downloads', () => {
    render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    expect(screen.getByText('Bulk Import Leads')).toBeDefined();
    expect(screen.getByText('Local File Upload')).toBeDefined();
    expect(screen.getByText('Google Sheets Link')).toBeDefined();

    // Trigger CSV template download
    mockDownloadTemplate.mockResolvedValue(new Blob(['First Name,Last Name'], { type: 'text/csv' }));
    window.URL.createObjectURL = vi.fn().mockReturnValue('mock-url');
    window.URL.revokeObjectURL = vi.fn();

    const csvBtn = screen.getByText('CSV Template');
    fireEvent.click(csvBtn);

    expect(mockDownloadTemplate).toHaveBeenCalledWith('csv');
  });

  it('transitions to mapping step on successful file parse', async () => {
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
        { 'First Name': 'John', 'Last Name': 'Doe', 'Email': 'john@test.com', 'Job Title': 'Dev' }
      ]
    };
    
    mockUploadImportFile.mockResolvedValue(mockPreviewResponse);

    render(
      <ImportModal isOpen={true} onClose={mockOnClose} onSuccess={mockOnSuccess} />
    );

    // Mock file input interaction
    const file = new File(['John,Doe,john@test.com,Dev'], 'leads.csv', { type: 'text/csv' });
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
});
