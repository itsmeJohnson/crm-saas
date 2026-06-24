// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { AssignmentSettings } from '../AssignmentSettings';
import { useLeadImportStore } from '../../../store/leadImportStore';
import { useAuthStore } from '../../../store/authStore';

vi.mock('../../../store/leadImportStore', () => ({
  useLeadImportStore: vi.fn(),
}));

vi.mock('../../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('AssignmentSettings Component', () => {
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

    (useLeadImportStore as any).mockReturnValue({
      assignmentConfig: null,
      fetchAssignmentConfig: mockFetchAssignmentConfig,
      toggleAssignmentConfig: mockToggleAssignmentConfig,
      isLoading: false,
    });

    const { container } = render(<AssignmentSettings />);
    expect(container.firstChild).toBeNull();
    expect(mockFetchAssignmentConfig).not.toHaveBeenCalled();
  });

  it('renders and fetches config if user is Manager', () => {
    (useAuthStore as any).mockReturnValue({
      user: { id: 'u1', role: 'Manager' },
    });

    (useLeadImportStore as any).mockReturnValue({
      assignmentConfig: { is_active: false, organization_id: 'org-1' },
      fetchAssignmentConfig: mockFetchAssignmentConfig,
      toggleAssignmentConfig: mockToggleAssignmentConfig,
      isLoading: false,
    });

    render(<AssignmentSettings />);
    expect(screen.getByText('Auto Assignment')).toBeDefined();
    expect(mockFetchAssignmentConfig).toHaveBeenCalled();
  });

  it('calls toggleAssignmentConfig when clicking the toggle switch', async () => {
    (useAuthStore as any).mockReturnValue({
      user: { id: 'u1', role: 'OrgAdmin' },
    });

    (useLeadImportStore as any).mockReturnValue({
      assignmentConfig: { is_active: false, organization_id: 'org-1' },
      fetchAssignmentConfig: mockFetchAssignmentConfig,
      toggleAssignmentConfig: mockToggleAssignmentConfig,
      isLoading: false,
    });

    render(<AssignmentSettings />);
    const button = screen.getByRole('button');
    fireEvent.click(button);
    expect(mockToggleAssignmentConfig).toHaveBeenCalledWith(true);
  });
});
