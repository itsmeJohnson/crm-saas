// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { AssignmentToggle } from '../AssignmentToggle';
import { useLeadStore } from '../../../store/leadStore';
import { useAuthStore } from '../../../store/authStore';

vi.mock('../../../store/leadStore', () => ({
  useLeadStore: vi.fn(),
}));

vi.mock('../../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('AssignmentToggle Component', () => {
  const mockFetchAssignmentConfig = vi.fn();
  const mockToggleAssignmentConfig = vi.fn();

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    cleanup();
  });

  it('renders nothing if user is an Employee', () => {
    (useAuthStore as any).mockReturnValue({
      user: { id: 'u1', role: 'Employee' },
    });

    (useLeadStore as any).mockReturnValue({
      assignmentConfig: null,
      fetchAssignmentConfig: mockFetchAssignmentConfig,
      toggleAssignmentConfig: mockToggleAssignmentConfig,
      isLoading: false,
    });

    const { container } = render(<AssignmentToggle />);
    expect(container.firstChild).toBeNull();
    expect(mockFetchAssignmentConfig).not.toHaveBeenCalled();
  });

  it('renders and fetches config if user is OrgAdmin', () => {
    (useAuthStore as any).mockReturnValue({
      user: { id: 'u1', role: 'OrgAdmin' },
    });

    (useLeadStore as any).mockReturnValue({
      assignmentConfig: { is_active: false, organization_id: 'org-1' },
      fetchAssignmentConfig: mockFetchAssignmentConfig,
      toggleAssignmentConfig: mockToggleAssignmentConfig,
      isLoading: false,
    });

    render(<AssignmentToggle />);
    expect(screen.getByText('Auto Assignment')).toBeDefined();
    expect(mockFetchAssignmentConfig).toHaveBeenCalled();
  });

  it('calls toggleAssignmentConfig when clicking the toggle switch', async () => {
    (useAuthStore as any).mockReturnValue({
      user: { id: 'u1', role: 'OrgAdmin' },
    });

    (useLeadStore as any).mockReturnValue({
      assignmentConfig: { is_active: false, organization_id: 'org-1' },
      fetchAssignmentConfig: mockFetchAssignmentConfig,
      toggleAssignmentConfig: mockToggleAssignmentConfig,
      isLoading: false,
    });

    render(<AssignmentToggle />);
    const button = screen.getByRole('button');
    fireEvent.click(button);
    expect(mockToggleAssignmentConfig).toHaveBeenCalledWith(true);
  });
});
