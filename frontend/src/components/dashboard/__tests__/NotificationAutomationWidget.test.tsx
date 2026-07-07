// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { NotificationAutomationWidget } from '../NotificationAutomationWidget';
import { notificationAutomationApi } from '../../../services/notificationAutomationApi';

vi.mock('../../../services/notificationAutomationApi', () => ({ notificationAutomationApi: { dashboard: vi.fn() } }));

const DASH = {
  rules: 11, active_rules: 8, deliveries: 240, delivery_rate: 93.5, pending_digest: 4, failed: 6,
  recent: [
    { id: 'd1', rule_id: 'r1', user_id: 'u1', channel: 'email', status: 'sent', attempts: 1, error: null, title: 'New lead assigned', queue_job_id: null, sent_at: null, created_at: null },
    { id: 'd2', rule_id: 'r1', user_id: 'u2', channel: 'sms', status: 'failed', attempts: 2, error: 'x', title: 'SLA breach', queue_job_id: null, sent_at: null, created_at: null },
  ],
};

describe('NotificationAutomationWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><NotificationAutomationWidget /></BrowserRouter>);

  it('renders rules/delivery-rate/failed and recent deliveries', async () => {
    vi.mocked(notificationAutomationApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Notification Rules')).toBeDefined());
    expect(screen.getByText('8/11')).toBeDefined();      // active/total
    expect(screen.getByText('93.5%')).toBeDefined();      // delivery rate
    expect(screen.getByText('6')).toBeDefined();           // failed
    expect(screen.getByText('New lead assigned')).toBeDefined();
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(notificationAutomationApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
