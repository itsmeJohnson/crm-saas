// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NotificationCenterPage } from '../NotificationCenterPage';
import { notificationApi } from '../../services/notificationApi';
import { useAuthStore } from '../../store/authStore';

vi.mock('../../services/notificationApi', () => ({
  notificationApi: {
    list: vi.fn(),
    categories: vi.fn(),
    markAllRead: vi.fn(),
    bulkRead: vi.fn(),
    dismiss: vi.fn(),
    markRead: vi.fn(),
    getPreferences: vi.fn(),
    stats: vi.fn(),
  },
}));
vi.mock('../../store/authStore', () => ({ useAuthStore: vi.fn() }));

const NOTIFS = [
  { id: 'n1', category: 'lead', title: 'Hot lead', body: 'A new hot lead', link_url: null, is_read: false,
    read_at: null, action_metadata: null, priority: 'urgent', is_dismissed: false, actions: null, channels_sent: ['in_app'], created_at: new Date().toISOString() },
  { id: 'n2', category: 'task', title: 'Task due', body: 'Do it', link_url: null, is_read: true,
    read_at: null, action_metadata: null, priority: 'normal', is_dismissed: false, actions: null, channels_sent: ['in_app'], created_at: new Date().toISOString() },
];

describe('NotificationCenterPage', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderPage = () => render(<BrowserRouter><NotificationCenterPage /></BrowserRouter>);

  it('renders the inbox with priority badges and a broadcast button for admins', async () => {
    vi.mocked(useAuthStore).mockReturnValue({ user: { role: 'OrgAdmin' } } as any);
    vi.mocked(notificationApi.list).mockResolvedValue(NOTIFS as any);
    vi.mocked(notificationApi.categories).mockResolvedValue(['lead', 'task']);
    renderPage();

    await waitFor(() => expect(screen.getByText('Hot lead')).toBeDefined());
    expect(screen.getByText('Task due')).toBeDefined();
    // 'urgent' appears as both a priority badge and a filter option
    expect(screen.getAllByText('urgent').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText('Broadcast')).toBeDefined();
  });

  it('hides broadcast for non-privileged users', async () => {
    vi.mocked(useAuthStore).mockReturnValue({ user: { role: 'Employee' } } as any);
    vi.mocked(notificationApi.list).mockResolvedValue([] as any);
    vi.mocked(notificationApi.categories).mockResolvedValue([]);
    renderPage();
    await waitFor(() => expect(screen.getByText("You're all caught up.")).toBeDefined());
    expect(screen.queryByText('Broadcast')).toBeNull();
  });

  it('marks all read', async () => {
    vi.mocked(useAuthStore).mockReturnValue({ user: { role: 'Employee' } } as any);
    vi.mocked(notificationApi.list).mockResolvedValue(NOTIFS as any);
    vi.mocked(notificationApi.categories).mockResolvedValue(['lead', 'task']);
    vi.mocked(notificationApi.markAllRead).mockResolvedValue({ marked_read: 1 } as any);
    renderPage();
    await waitFor(() => expect(screen.getByText('Hot lead')).toBeDefined());
    fireEvent.click(screen.getByText('Mark all read'));
    await waitFor(() => expect(vi.mocked(notificationApi.markAllRead)).toHaveBeenCalled());
  });
});
