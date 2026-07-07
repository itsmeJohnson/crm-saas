// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { NotificationBell } from '../NotificationBell';
import { useNotificationStore } from '../../../store/notificationStore';

vi.mock('../../../store/notificationStore', () => ({
  useNotificationStore: vi.fn(),
}));

describe('NotificationBell Component', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement) => render(<BrowserRouter>{ui}</BrowserRouter>);

  const baseState = {
    notifications: [],
    unreadCount: 0,
    isLoading: false,
    fetchNotifications: vi.fn(),
    fetchUnreadCount: vi.fn(),
    markRead: vi.fn(),
    markAllRead: vi.fn(),
  };

  it('shows no badge when unreadCount is 0', () => {
    vi.mocked(useNotificationStore).mockReturnValue(baseState as any);
    renderWithRouter(<NotificationBell />);
    expect(screen.queryByText('0')).toBeNull();
  });

  it('shows an unread badge count', () => {
    vi.mocked(useNotificationStore).mockReturnValue({ ...baseState, unreadCount: 3 } as any);
    renderWithRouter(<NotificationBell />);
    expect(screen.getByText('3')).toBeDefined();
  });

  it('caps the badge display at 99+', () => {
    vi.mocked(useNotificationStore).mockReturnValue({ ...baseState, unreadCount: 150 } as any);
    renderWithRouter(<NotificationBell />);
    expect(screen.getByText('99+')).toBeDefined();
  });

  it('opens the dropdown and shows an empty state when there are no notifications', async () => {
    vi.mocked(useNotificationStore).mockReturnValue(baseState as any);
    renderWithRouter(<NotificationBell />);
    fireEvent.click(screen.getByTitle('Notifications'));
    await waitFor(() => {
      expect(screen.getByText("You're all caught up.")).toBeDefined();
    });
  });

  it('renders notification titles when present and marks read on click', async () => {
    const markRead = vi.fn();
    vi.mocked(useNotificationStore).mockReturnValue({
      ...baseState,
      unreadCount: 1,
      notifications: [
        {
          id: 'n1',
          category: 'lead',
          title: 'New lead assigned to you',
          body: 'Test lead was assigned to you.',
          link_url: null,
          is_read: false,
          read_at: null,
          action_metadata: null,
          created_at: new Date().toISOString(),
        },
      ],
      markRead,
    } as any);

    renderWithRouter(<NotificationBell />);
    fireEvent.click(screen.getByTitle('Notifications'));
    await waitFor(() => {
      expect(screen.getByText('New lead assigned to you')).toBeDefined();
    });
    fireEvent.click(screen.getByText('New lead assigned to you'));
    expect(markRead).toHaveBeenCalledWith('n1');
  });
});
