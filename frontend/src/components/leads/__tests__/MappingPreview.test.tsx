// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MappingPreview } from '../MappingPreview';
import { ImportPreviewResponse } from '../../../services/leadImportApi';
import { UserResponse } from '../../../services/userApi';

describe('MappingPreview Component', () => {
  const mockOnMappingChange = vi.fn();
  const mockSetAssignmentMode = vi.fn();
  const mockSetAssignedUserId = vi.fn();

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

  const mockEmployees: UserResponse[] = [
    {
      id: 'emp-123',
      email: 'emp1@test.com',
      first_name: 'Bob',
      last_name: 'Employee',
      role: 'Employee',
      is_active: true,
      is_verified: true,
      is_invited: false,
      organization_id: 'org-123',
      created_at: '',
      updated_at: ''
    }
  ];

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders standard layout fields, column mappings, and assignment mode options', () => {
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
        assignmentMode="NONE"
        setAssignmentMode={mockSetAssignmentMode}
        assignedUserId={null}
        setAssignedUserId={mockSetAssignedUserId}
        assignedUserIds={[]}
        setAssignedUserIds={vi.fn()}
        employees={mockEmployees}
        isLoadingEmployees={false}
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

    // Check assignment mode options
    expect(screen.getByText('Unassigned')).toBeDefined();
    expect(screen.getByText('Round Robin')).toBeDefined();
    expect(screen.getByText('Assign to User')).toBeDefined();
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
        assignmentMode="NONE"
        setAssignmentMode={mockSetAssignmentMode}
        assignedUserId={null}
        setAssignedUserId={mockSetAssignedUserId}
        assignedUserIds={[]}
        setAssignedUserIds={vi.fn()}
        employees={mockEmployees}
        isLoadingEmployees={false}
      />
    );

    const selects = screen.getAllByRole('combobox');
    
    // Field 'title' (Job Title / Lead Title) is config[0], 'last_name' is config[1]
    fireEvent.change(selects[1], { target: { value: 'Last Name' } });
    expect(mockOnMappingChange).toHaveBeenCalledWith('last_name', 'Last Name');
  });

  it('triggers assignment mode changes when a radio is clicked', () => {
    const columnMapping = {};
    render(
      <MappingPreview
        previewData={mockPreviewData}
        columnMapping={columnMapping}
        onMappingChange={mockOnMappingChange}
        assignmentMode="NONE"
        setAssignmentMode={mockSetAssignmentMode}
        assignedUserId={null}
        setAssignedUserId={mockSetAssignedUserId}
        assignedUserIds={[]}
        setAssignedUserIds={vi.fn()}
        employees={mockEmployees}
        isLoadingEmployees={false}
      />
    );

    const roundRobinRadio = screen.getByDisplayValue('AUTO');
    fireEvent.click(roundRobinRadio);
    expect(mockSetAssignmentMode).toHaveBeenCalledWith('AUTO');
  });

  it('renders employee dropdown and handles selection when assignmentMode is SPECIFIC_USER', () => {
    const columnMapping = {};
    render(
      <MappingPreview
        previewData={mockPreviewData}
        columnMapping={columnMapping}
        onMappingChange={mockOnMappingChange}
        assignmentMode="SPECIFIC_USER"
        setAssignmentMode={mockSetAssignmentMode}
        assignedUserId={null}
        setAssignedUserId={mockSetAssignedUserId}
        assignedUserIds={[]}
        setAssignedUserIds={vi.fn()}
        employees={mockEmployees}
        isLoadingEmployees={false}
      />
    );

    expect(screen.getByText('Select Assignee')).toBeDefined();
    const selects = screen.getAllByRole('combobox');
    const select = selects[selects.length - 1] as HTMLSelectElement;
    fireEvent.change(select, { target: { value: 'emp-123' } });
    expect(mockSetAssignedUserId).toHaveBeenCalledWith('emp-123');
  });
});
