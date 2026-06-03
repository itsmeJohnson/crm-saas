// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { RecentActivitiesWidget } from '../RecentActivitiesWidget';
import { RecentActivityItem } from '../../../services/dashboardApi';

describe('RecentActivitiesWidget Component', () => {
  afterEach(() => {
    cleanup();
  });

  const mockActivities: RecentActivityItem[] = [
    {
      id: 'act-1',
      activity_type: 'Call',
      subject: 'Call Acme',
      description: 'Discuss deal details',
      due_date: null,
      status: 'Completed',
      assigned_user_id: 'user-1',
      assigned_user_name: 'Alice Smith',
      created_at: new Date().toISOString()
    },
    {
      id: 'act-2',
      activity_type: 'Meeting',
      subject: 'Sync with Globex',
      description: null,
      due_date: null,
      status: 'Planned',
      assigned_user_id: null,
      assigned_user_name: 'Unassigned',
      created_at: new Date().toISOString()
    }
  ];

  const mockOnPageChange = vi.fn();

  it('renders activities list correctly', () => {
    render(
      <RecentActivitiesWidget
        activities={mockActivities}
        total={2}
        page={1}
        limit={10}
        isLoading={false}
        onPageChange={mockOnPageChange}
      />
    );

    expect(screen.getByText('Call Acme')).toBeDefined();
    expect(screen.getByText('Discuss deal details')).toBeDefined();
    expect(screen.getByText('Alice Smith')).toBeDefined();
    expect(screen.getByText('Sync with Globex')).toBeDefined();
    expect(screen.getByText('Unassigned')).toBeDefined();
  });

  it('shows empty state when no activities are present', () => {
    render(
      <RecentActivitiesWidget
        activities={[]}
        total={0}
        page={1}
        limit={10}
        isLoading={false}
        onPageChange={mockOnPageChange}
      />
    );

    expect(screen.getByText('No recent activities')).toBeDefined();
  });

  it('shows pagination controls and handles clicks when total exceeds limit', () => {
    render(
      <RecentActivitiesWidget
        activities={mockActivities}
        total={15}
        page={1}
        limit={10}
        isLoading={false}
        onPageChange={mockOnPageChange}
      />
    );

    const buttons = screen.getAllByRole('button');
    expect(buttons[0].hasAttribute('disabled')).toBe(true);
    expect(buttons[1].hasAttribute('disabled')).toBe(false);

    fireEvent.click(buttons[1]);
    expect(mockOnPageChange).toHaveBeenCalledWith(2);
  });
});
