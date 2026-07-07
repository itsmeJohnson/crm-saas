// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { WorkflowsWidget } from '../WorkflowsWidget';
import { workflowApi } from '../../../services/workflowApi';

vi.mock('../../../services/workflowApi', () => ({ workflowApi: { dashboard: vi.fn() } }));

const DASH = {
  published: 4, enabled: 3, total_runs: 120, success_rate: 96.5, failed: 4,
  recent: [
    { id: 'e1', workflow_name: 'New Lead flow', status: 'completed' },
    { id: 'e2', workflow_name: 'Payment thanks', status: 'failed' },
  ],
};

describe('WorkflowsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><WorkflowsWidget /></BrowserRouter>);

  it('renders live/runs/success and recent executions', async () => {
    vi.mocked(workflowApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Workflows')).toBeDefined());
    expect(screen.getByText('3')).toBeDefined();       // enabled
    expect(screen.getByText('120')).toBeDefined();      // runs
    expect(screen.getByText('96.5%')).toBeDefined();    // success rate
    expect(screen.getByText('New Lead flow')).toBeDefined();
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(workflowApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
