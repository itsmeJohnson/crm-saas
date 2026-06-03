// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { CompanyTable } from '../CompanyTable';
import { useCompanyStore } from '../../../store/companyStore';
import { useUserStore } from '../../../store/userStore';
import { CompanyResponse } from '../../../services/companyApi';

// Mock Zustand Stores
vi.mock('../../../store/companyStore', () => ({
  useCompanyStore: vi.fn(),
}));

vi.mock('../../../store/userStore', () => ({
  useUserStore: vi.fn(),
}));

describe('CompanyTable Component', () => {
  const mockCompanies: CompanyResponse[] = [
    {
      id: 'comp-1',
      organization_id: 'org-1',
      name: 'Acme Corp',
      domain: 'acme.com',
      industry: 'Software',
      website: 'https://acme.com',
      phone: '123-456',
      assigned_user_id: 'user-1',
      created_by: 'user-1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'comp-2',
      organization_id: 'org-1',
      name: 'Globex Corp',
      domain: 'globex.com',
      industry: 'Manufacturing',
      website: 'https://globex.com',
      phone: '987-654',
      assigned_user_id: 'user-2',
      created_by: 'user-1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  const mockUsers = [
    { id: 'user-1', first_name: 'Alice', last_name: 'Smith', is_active: true },
    { id: 'user-2', first_name: 'Bob', last_name: 'Jones', is_active: true },
  ];

  const mockDeleteCompany = vi.fn();
  const mockOnEditClick = vi.fn();
  const mockOnRowClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    (useCompanyStore as any).mockReturnValue({
      companies: mockCompanies,
      isLoading: false,
      error: null,
      deleteCompany: mockDeleteCompany,
    });

    (useUserStore as any).mockReturnValue({
      users: mockUsers,
      fetchUsers: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders company columns and owner names correctly', () => {
    render(<CompanyTable onEditClick={mockOnEditClick} onRowClick={mockOnRowClick} />);

    // Validate names are rendered
    expect(screen.getByText('Acme Corp')).toBeDefined();
    expect(screen.getByText('Globex Corp')).toBeDefined();

    // Validate domain
    expect(screen.getByText('acme.com')).toBeDefined();
    expect(screen.getByText('globex.com')).toBeDefined();

    // Validate industry
    expect(screen.getByText('Software')).toBeDefined();
    expect(screen.getByText('Manufacturing')).toBeDefined();

    // Validate assigned owner name mapping
    expect(screen.getByText('Alice Smith')).toBeDefined();
    expect(screen.getByText('Bob Jones')).toBeDefined();
  });

  it('calls onRowClick when clicking a row', () => {
    render(<CompanyTable onEditClick={mockOnEditClick} onRowClick={mockOnRowClick} />);

    const row = screen.getByText('Acme Corp').closest('tr');
    expect(row).not.toBeNull();
    if (row) {
      fireEvent.click(row);
      expect(mockOnRowClick).toHaveBeenCalledWith(mockCompanies[0]);
    }
  });

  it('calls deleteCompany when clicking the delete button', () => {
    vi.spyOn(window, 'confirm').mockImplementation(() => true);

    render(<CompanyTable onEditClick={mockOnEditClick} onRowClick={mockOnRowClick} />);

    const deleteButtons = screen.getAllByTitle('Delete Company');
    fireEvent.click(deleteButtons[0]);

    expect(mockDeleteCompany).toHaveBeenCalledWith('comp-1');
  });

  it('calls onEditClick when clicking edit button', () => {
    render(<CompanyTable onEditClick={mockOnEditClick} onRowClick={mockOnRowClick} />);

    const editButtons = screen.getAllByTitle('Edit Company');
    fireEvent.click(editButtons[0]);

    expect(mockOnEditClick).toHaveBeenCalledWith(mockCompanies[0]);
  });
});
