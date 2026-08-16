// @vitest-environment happy-dom
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import { render, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import React from 'react';
import { useBrowserNotifications } from '../useBrowserNotifications';
import { notificationApi } from '../../services/notificationApi';

vi.mock('../../services/notificationApi', () => ({
  notificationApi: { list: vi.fn() },
}));

const Harness: React.FC = () => {
  useBrowserNotifications(true);
  return null;
};

let NotificationMock: any;

beforeEach(() => {
  vi.useFakeTimers();
  NotificationMock = vi.fn(function () { return { onclick: null, close: vi.fn() }; });
  NotificationMock.permission = 'granted';
  NotificationMock.requestPermission = vi.fn().mockResolvedValue('granted');
  vi.stubGlobal('Notification', NotificationMock);
});

afterEach(() => {
  cleanup();
  vi.useRealTimers();
  vi.unstubAllGlobals();
  vi.clearAllMocks();
});

describe('useBrowserNotifications', () => {
  it('primes silently on first poll, then pops only genuinely new notifications', async () => {
    const A = { id: 'a', title: 'Old reminder', body: 'was already unread', link_url: null };
    const B = { id: 'b', title: 'New reminder', body: 'Call Ramesh at 3pm', link_url: '/leads?leadId=1' };
    (notificationApi.list as any)
      .mockResolvedValueOnce([A])         // first tick → prime, no popup
      .mockResolvedValue([A, B]);         // later ticks → B is new

    render(<MemoryRouter><Harness /></MemoryRouter>);

    await vi.advanceTimersByTimeAsync(0);          // flush the priming tick
    expect(NotificationMock).not.toHaveBeenCalled();

    await vi.advanceTimersByTimeAsync(60_000);     // next poll
    expect(NotificationMock).toHaveBeenCalledTimes(1);
    expect(NotificationMock).toHaveBeenCalledWith('New reminder',
      expect.objectContaining({ body: 'Call Ramesh at 3pm', tag: 'b' }));

    // The already-seen A must never re-fire on subsequent polls.
    await vi.advanceTimersByTimeAsync(60_000);
    expect(NotificationMock).toHaveBeenCalledTimes(1);
  });

  it('does not pop when permission is not granted', async () => {
    NotificationMock.permission = 'denied';
    const B = { id: 'b', title: 'New', body: 'x', link_url: null };
    (notificationApi.list as any).mockResolvedValueOnce([]).mockResolvedValue([B]);

    render(<MemoryRouter><Harness /></MemoryRouter>);
    await vi.advanceTimersByTimeAsync(0);
    await vi.advanceTimersByTimeAsync(60_000);
    expect(NotificationMock).not.toHaveBeenCalled();
  });
});
