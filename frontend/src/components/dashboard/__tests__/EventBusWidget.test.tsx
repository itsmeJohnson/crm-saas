// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { EventBusWidget } from '../EventBusWidget';
import { eventApi } from '../../../services/eventApi';

vi.mock('../../../services/eventApi', () => ({ eventApi: { dashboard: vi.fn() } }));

const DASH = {
  total_events: 274, success_rate: 98.2, dead_letter: 5, subscriptions: 3,
  recent: [
    { id: 'e1', event_type: 'lead.converted', entity_type: 'lead', entity_id: 'x', source: 'trigger', status: 'published', subscriber_count: 2, delivered_count: 2, failed_count: 0, duration_ms: 8, published_at: null },
    { id: 'e2', event_type: 'payment.received', entity_type: 'customer', entity_id: 'y', source: 'trigger', status: 'published', subscriber_count: 1, delivered_count: 1, failed_count: 0, duration_ms: 4, published_at: null },
  ],
};

describe('EventBusWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><EventBusWidget /></BrowserRouter>);

  it('renders events/success/dlq and recent event types', async () => {
    vi.mocked(eventApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Event Bus')).toBeDefined());
    expect(screen.getByText('274')).toBeDefined();       // total events
    expect(screen.getByText('98.2%')).toBeDefined();      // success rate
    expect(screen.getByText('5')).toBeDefined();           // dlq
    expect(screen.getByText('lead.converted')).toBeDefined();
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(eventApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
