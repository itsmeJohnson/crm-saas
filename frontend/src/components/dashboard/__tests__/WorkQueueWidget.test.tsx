// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor, within } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { WorkQueueWidget } from '../WorkQueueWidget';
import { dashboardApi } from '../../../services/dashboardApi';

vi.mock('../../../services/dashboardApi', () => ({ dashboardApi: { getWorkQueue: vi.fn() } }));

const QUEUE = {
  generated_at: '2026-07-23T00:00:00Z', scope: 'Manager',
  next_action: { type: 'follow_up', id: 't1', lead_id: 'l1', title: 'Follow up: Rahul Mehta' },
  counts: { overdue_follow_ups: 3, todays_follow_ups: 5, meetings: 2, hot_leads: 4, new_leads: 9 },
  sections: [
    { key: 'overdue_follow_ups', order: 1, label: 'Overdue Follow Ups', count: 3, items: [] },
    { key: 'todays_follow_ups', order: 2, label: 'Todays Follow Ups', count: 5, items: [] },
    { key: 'meetings', order: 3, label: 'Meetings', count: 2, items: [] },
    { key: 'hot_leads', order: 5, label: 'Hot Leads', count: 4, items: [] },
    { key: 'new_leads', order: 7, label: 'New Leads', count: 9, items: [] },
  ],
};

describe('WorkQueueWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><WorkQueueWidget /></BrowserRouter>);

  it('renders overdue/today counts and the next action', async () => {
    vi.mocked(dashboardApi.getWorkQueue).mockResolvedValue(QUEUE as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('My Work Queue')).toBeDefined());
    // "3" (overdue) and "5" (today) appear in both the stat boxes and section rows
    expect(screen.getAllByText('3').length).toBeGreaterThanOrEqual(1);
    expect(screen.getAllByText('5').length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText(/Follow up: Rahul Mehta/)).toBeDefined();
    const overdueRow = screen.getByText('Overdue Follow Ups').closest('div')!;
    expect(within(overdueRow).getByText('3')).toBeDefined();
  });

  it('shows a fallback when the queue is unavailable', async () => {
    vi.mocked(dashboardApi.getWorkQueue).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No work-queue data/)).toBeDefined());
  });
});
