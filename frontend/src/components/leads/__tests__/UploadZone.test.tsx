// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { UploadZone } from '../UploadZone';

describe('UploadZone Component', () => {
  const mockSetSourceType = vi.fn();
  const mockSetSelectedFile = vi.fn();
  const mockSetSheetsUrl = vi.fn();
  const mockOnDownloadTemplate = vi.fn();
  const mockSetErrorMsg = vi.fn();
  const mockSetTemplateVertical = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders upload tabs and default drag drop area', () => {
    render(
      <UploadZone
        sourceType="file"
        setSourceType={mockSetSourceType}
        selectedFile={null}
        setSelectedFile={mockSetSelectedFile}
        sheetsUrl=""
        setSheetsUrl={mockSetSheetsUrl}
        onDownloadTemplate={mockOnDownloadTemplate}
        setErrorMsg={mockSetErrorMsg}
        templateVertical=""
        setTemplateVertical={mockSetTemplateVertical}
      />
    );

    expect(screen.getByText('Local File Upload')).toBeDefined();
    expect(screen.getByText('Google Sheets Link')).toBeDefined();
    expect(screen.getByText('Choose a file or drag it here')).toBeDefined();
    expect(screen.getByText('CSV Template')).toBeDefined();
    expect(screen.getByText('Excel Template')).toBeDefined();
  });

  it('renders Google Sheets input when sourceType is google_sheets', () => {
    render(
      <UploadZone
        sourceType="google_sheets"
        setSourceType={mockSetSourceType}
        selectedFile={null}
        setSelectedFile={mockSetSelectedFile}
        sheetsUrl="https://docs.google.com/spreadsheets/d/123/edit"
        setSheetsUrl={mockSetSheetsUrl}
        onDownloadTemplate={mockOnDownloadTemplate}
        setErrorMsg={mockSetErrorMsg}
        templateVertical=""
        setTemplateVertical={mockSetTemplateVertical}
      />
    );

    expect(screen.getByText('Google Sheets Public Export Link')).toBeDefined();
    const input = screen.getByPlaceholderText('https://docs.google.com/spreadsheets/d/your-spreadsheet-id/edit?usp=sharing') as HTMLInputElement;
    expect(input.value).toBe('https://docs.google.com/spreadsheets/d/123/edit');
  });

  it('calls setSourceType when clicking tabs', () => {
    render(
      <UploadZone
        sourceType="file"
        setSourceType={mockSetSourceType}
        selectedFile={null}
        setSelectedFile={mockSetSelectedFile}
        sheetsUrl=""
        setSheetsUrl={mockSetSheetsUrl}
        onDownloadTemplate={mockOnDownloadTemplate}
        setErrorMsg={mockSetErrorMsg}
        templateVertical=""
        setTemplateVertical={mockSetTemplateVertical}
      />
    );

    const sheetsTab = screen.getByText('Google Sheets Link');
    fireEvent.click(sheetsTab);
    expect(mockSetSourceType).toHaveBeenCalledWith('google_sheets');
  });

  it('calls onDownloadTemplate when clicking template buttons', () => {
    render(
      <UploadZone
        sourceType="file"
        setSourceType={mockSetSourceType}
        selectedFile={null}
        setSelectedFile={mockSetSelectedFile}
        sheetsUrl=""
        setSheetsUrl={mockSetSheetsUrl}
        onDownloadTemplate={mockOnDownloadTemplate}
        setErrorMsg={mockSetErrorMsg}
        templateVertical=""
        setTemplateVertical={mockSetTemplateVertical}
      />
    );

    const csvBtn = screen.getByText('CSV Template');
    fireEvent.click(csvBtn);
    expect(mockOnDownloadTemplate).toHaveBeenCalledWith('csv');

    const xlsxBtn = screen.getByText('Excel Template');
    fireEvent.click(xlsxBtn);
    expect(mockOnDownloadTemplate).toHaveBeenCalledWith('xlsx');
  });
});
