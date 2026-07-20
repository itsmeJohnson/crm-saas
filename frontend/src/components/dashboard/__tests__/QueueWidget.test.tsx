// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { QueueWidget } from '../QueueWidget';
import { queueApi } from '../../../services/queueApi';

vi.mock('../../../services/queueApi', () => ({ queueApi: { dashboard: vi.fn() } }));

const DASH = {
  pending: 17, running: 2, succeeded: 340, failed: 4, dead_letter: 6, workers: 1,
  recent: [
    { id: 'j1', queue: 'ai', job_type: 'ai_task', priority: 5, status: 'succeeded', attempts: 1, max_attempts: 3, payload: null, result: null, error: null, run_at: null, started_at: null, finished_at: null, duration_ms: 12, created_at: null },
    { id: 'j2', queue: 'email', job_type: 'send_email', priority: 5, status: 'dead_letter', attempts: 3, max_attempts: 3, payload: null, result: null, error: 'x', run_at: null, started_at: null, finished_at: null, duration_ms: 8, created_at: null },
  ],
};

describe('QueueWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><QueueWidget /></BrowserRouter>);

  it('renders pending/workers/dlq and recent jobs', async () => {
    vi.mocked(queueApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Background Queue')).toBeDefined());
    expect(screen.getByText('17')).toBeDefined();      // pending
    expect(screen.getByText('6')).toBeDefined();         // dlq
    expect(screen.getByText(/ai task/)).toBeDefined();   // recent job type
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(queueApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
