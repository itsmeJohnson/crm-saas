// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MappingPreview } from '../MappingPreview';
import { ImportPreviewResponse } from '../../../services/leadImportApi';

describe('MappingPreview Component', () => {
  const mockOnMappingChange = vi.fn();
  const mockSetAutoAssign = vi.fn();

  const mockPreviewData: ImportPreviewResponse = {
    file_token: 'token-abc',
    headers: ['First Name', 'Last Name', 'Email Address', 'Job Title'],
    suggested_mapping: {
      first_name: { column: 'First Name', confidence: 1.0 },
      last_name: { column: 'Last Name', confidence: 1.0 },
      email: { column: 'Email Address', confidence: 0.8 },
      title: { column: 'Job Title', confidence: 0.6 },
    },
    preview_rows: [
      { 'First Name': 'Alice', 'Last Name': 'Green', 'Email Address': 'alice@test.com', 'Job Title': 'CEO' },
    ],
  };

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders standard layout fields, column mappings, and auto assignment checkbox', () => {
    const columnMapping = {
      first_name: 'First Name',
      last_name: 'Last Name',
      email: 'Email Address',
      title: 'Job Title',
    };

    render(
      <MappingPreview
        previewData={mockPreviewData}
        columnMapping={columnMapping}
        onMappingChange={mockOnMappingChange}
        autoAssign={true}
        setAutoAssign={mockSetAutoAssign}
      />
    );

    expect(screen.getByText('Map File Headers to Lead Properties')).toBeDefined();
    expect(screen.getByText('Source Data Preview')).toBeDefined();
    
    // Check confidence badges
    expect(screen.getAllByText('Exact (100%)').length).toBe(2);
    expect(screen.getByText('Alias (80%)')).toBeDefined();
    expect(screen.getByText('Fuzzy (60%)')).toBeDefined();

    // Check preview rows content
    expect(screen.getByText('Alice')).toBeDefined();
    expect(screen.getByText('Green')).toBeDefined();

    // Check checkbox
    const checkbox = screen.getByLabelText('Trigger Auto Assignment Logic') as HTMLInputElement;
    expect(checkbox.checked).toBe(true);
  });

  it('triggers mapping changes when another column is selected', () => {
    const columnMapping = {
      first_name: '',
      last_name: '',
      email: '',
      title: '',
    };

    render(
      <MappingPreview
        previewData={mockPreviewData}
        columnMapping={columnMapping}
        onMappingChange={mockOnMappingChange}
        autoAssign={true}
        setAutoAssign={mockSetAutoAssign}
      />
    );

    // Let's trigger a select change on 'Last Name' mapping selector
    // Field Last Name is labeled 'Last Name *' or has ID
    // We can select the dropdowns by finding them
    const selects = screen.getAllByRole('combobox');
    
    // Field 'title' (Job Title / Lead Title) is config[0], 'last_name' is config[1]
    fireEvent.change(selects[1], { target: { value: 'Last Name' } });
    expect(mockOnMappingChange).toHaveBeenCalledWith('last_name', 'Last Name');
  });

  it('toggles auto assign checkbox state', () => {
    const columnMapping = {};
    render(
      <MappingPreview
        previewData={mockPreviewData}
        columnMapping={columnMapping}
        onMappingChange={mockOnMappingChange}
        autoAssign={true}
        setAutoAssign={mockSetAutoAssign}
      />
    );

    const checkbox = screen.getByLabelText('Trigger Auto Assignment Logic');
    fireEvent.click(checkbox);
    expect(mockSetAutoAssign).toHaveBeenCalledWith(false);
  });
});
