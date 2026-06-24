// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { UserTable } from '../UserTable';
import { useUserStore } from '../../../store/userStore';
import { useAuthStore } from '../../../store/authStore';
import { UserResponse } from '../../../services/userApi';

// Mock Zustand Stores
vi.mock('../../../store/userStore', () => ({
  useUserStore: vi.fn(),
}));

vi.mock('../../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('UserTable Component', () => {
  const mockUsers: UserResponse[] = [
    {
      id: '1',
      email: 'admin@org.com',
      first_name: 'Admin',
      last_name: 'User',
      role: 'OrgAdmin',
      is_active: true,
      is_verified: true,
      is_invited: false,
      organization_id: 'org1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
    {
      id: '2',
      email: 'employee@org.com',
      first_name: 'Employee',
      last_name: 'User',
      role: 'Employee',
      is_active: true,
      is_verified: true,
      is_invited: false,
      organization_id: 'org1',
      created_at: new Date().toISOString(),
      updated_at: new Date().toISOString(),
    },
  ];

  const mockToggleStatus = vi.fn();
  const mockDeleteUser = vi.fn();
  const mockOnEditClick = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();

    // Mock store values
    (useUserStore as any).mockReturnValue({
      users: mockUsers,
      isLoading: false,
      error: null,
      filters: { role: 'All', status: 'All', search: '' },
      toggleUserStatus: mockToggleStatus,
      deleteUser: mockDeleteUser,
    });

    // Mock auth store by default as OrgAdmin
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          id: '1',
          email: 'admin@org.com',
          first_name: 'Admin',
          last_name: 'User',
          role: 'OrgAdmin',
        }
      };
      return selector ? selector(state) : state;
    });
  });

  afterEach(() => {
    cleanup();
  });

  it('renders user details and role badges correctly', () => {
    render(<UserTable onEditClick={mockOnEditClick} />);

    // Check names are rendered
    expect(screen.getByText('Admin User')).toBeDefined();
    expect(screen.getByText('Employee User')).toBeDefined();

    // Check emails are rendered
    expect(screen.getByText('admin@org.com')).toBeDefined();
    expect(screen.getByText('employee@org.com')).toBeDefined();

    // Check role badges
    expect(screen.getByText('Admin')).toBeDefined();
    expect(screen.getByText('Employee')).toBeDefined();
  });

  it('allows OrgAdmin to deactivate and delete other users but not themselves', () => {
    render(<UserTable onEditClick={mockOnEditClick} />);

    // OrgAdmin should see actions on employee (deactivate, edit, delete)
    // In our implementation, buttons are visible based on helpers.
    // Let's assert buttons exist
    const editButtons = screen.getAllByTitle('Edit User Details');
    expect(editButtons.length).toBe(2); // Can edit self and employee

    const deactivateButtons = screen.getAllByTitle('Deactivate User');
    expect(deactivateButtons.length).toBe(1); // Can deactivate Employee, not self

    const deleteButtons = screen.getAllByTitle('Delete User');
    expect(deleteButtons.length).toBe(1); // Can delete Employee, not self
  });

  it('restricts Employee users from deactivating or deleting any users', () => {
    // Current user is Employee User (id: '2')
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          id: '2',
          email: 'employee@org.com',
          first_name: 'Employee',
          last_name: 'User',
          role: 'Employee',
        }
      };
      return selector ? selector(state) : state;
    });

    render(<UserTable onEditClick={mockOnEditClick} />);

    // Employee cannot deactivate or delete anyone
    expect(screen.queryByTitle('Deactivate User')).toBeNull();
    expect(screen.queryByTitle('Delete User')).toBeNull();

    // Employee should only be able to edit themselves
    const editButtons = screen.getAllByTitle('Edit User Details');
    expect(editButtons.length).toBe(1);
  });
});
