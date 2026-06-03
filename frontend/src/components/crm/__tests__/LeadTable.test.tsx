// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { LeadTable } from '../LeadTable';
import { useLeadStore } from '../../../store/leadStore';
import { useUserStore } from '../../../store/userStore';
import { LeadResponse } from '../../../services/leadApi';

// Mock Zustand Stores
vi.mock('../../../store/leadStore', () => ({
  useLeadStore: vi.fn(),
}));

vi.mock('../../../store/userStore', () => ({
  useUserStore: vi.fn(),
}));

describe('LeadTable Component', () => {
  const mockLeads: LeadResponse[] = [
    {
      id: 'lead-1',
      organization_id: 'org-1',
      first_name: 'John',
      last_name: 'Doe',
      email: 'john.doe@lead.com',
      phone: '111-222',
      company_name: 'Doe Corp',
      title: 'Acme Enterprise Deal',
      status: 'Qualified',
      source: 'Cold Outreach',
      value: 120000.0,
      assigned_user_id: 'user-1',
      created_by: 'user-1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: 'lead-2',
      organization_id: 'org-1',
      first_name: null,
      last_name: 'Smith',
      email: 'smith@lead.com',
      phone: '333-444',
      company_name: null,
      title: 'Small business lead',
      status: 'New',
      source: 'Website',
      value: 5000.0,
      assigned_user_id: null,
      created_by: 'user-1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  const mockUsers = [
    { id: 'user-1', first_name: 'Alice', last_name: 'Smith', is_active: true },
  ];

  const mockDeleteLead = vi.fn();
  const mockOnEditClick = vi.fn();
  const mockOnRowClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    (useLeadStore as any).mockReturnValue({
      leads: mockLeads,
      isLoading: false,
      error: null,
      deleteLead: mockDeleteLead,
    });

    (useUserStore as any).mockReturnValue({
      users: mockUsers,
      fetchUsers: vi.fn(),
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders lead columns, formatted currency value, status badges, and owners correctly', () => {
    render(<LeadTable onEditClick={mockOnEditClick} onRowClick={mockOnRowClick} />);

    // Validate titles are rendered
    expect(screen.getByText('Acme Enterprise Deal')).toBeDefined();
    expect(screen.getByText('Small business lead')).toBeDefined();

    // Validate values are formatted in USD
    expect(screen.getByText('$120,000')).toBeDefined();
    expect(screen.getByText('$5,000')).toBeDefined();

    // Validate status badges
    expect(screen.getByText('Qualified')).toBeDefined();
    expect(screen.getByText('New')).toBeDefined();

    // Validate mapped owner name and unassigned mapping
    expect(screen.getByText('Alice Smith')).toBeDefined();
    expect(screen.getByText('Unassigned')).toBeDefined();
  });

  it('calls onRowClick when clicking a row', () => {
    render(<LeadTable onEditClick={mockOnEditClick} onRowClick={mockOnRowClick} />);

    const row = screen.getByText('Acme Enterprise Deal').closest('tr');
    expect(row).not.toBeNull();
    if (row) {
      fireEvent.click(row);
      expect(mockOnRowClick).toHaveBeenCalledWith(mockLeads[0]);
    }
  });

  it('calls deleteLead when clicking the delete button', () => {
    vi.spyOn(window, 'confirm').mockImplementation(() => true);

    render(<LeadTable onEditClick={mockOnEditClick} onRowClick={mockOnRowClick} />);

    const deleteButtons = screen.getAllByTitle('Delete Lead');
    fireEvent.click(deleteButtons[0]);

    expect(mockDeleteLead).toHaveBeenCalledWith('lead-1');
  });

  it('calls onEditClick when clicking edit button', () => {
    render(<LeadTable onEditClick={mockOnEditClick} onRowClick={mockOnRowClick} />);

    const editButtons = screen.getAllByTitle('Edit Lead');
    fireEvent.click(editButtons[0]);

    expect(mockOnEditClick).toHaveBeenCalledWith(mockLeads[0]);
  });
});
