// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { WorkflowAssistantWidget } from '../WorkflowAssistantWidget';
import { workflowAssistantApi } from '../../../services/workflowAssistantApi';

vi.mock('../../../services/workflowAssistantApi', () => ({
  workflowAssistantApi: { insights: vi.fn(), suggestions: vi.fn(), bottlenecks: vi.fn() },
}));

const INSIGHTS = {
  window_days: 30, totals: { runs: 42, failed: 3, success_rate: 92.9 },
  workflows: [], trend: [],
};

describe('WorkflowAssistantWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><WorkflowAssistantWidget /></BrowserRouter>);

  it('renders suggestion, bottleneck and success stats', async () => {
    vi.mocked(workflowAssistantApi.insights).mockResolvedValue(INSIGHTS as any);
    vi.mocked(workflowAssistantApi.suggestions).mockResolvedValue({ suggestions: [], count: 4, signals: {} } as any);
    vi.mocked(workflowAssistantApi.bottlenecks).mockResolvedValue({ bottlenecks: [], count: 2, areas: [] } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Workflow Assistant')).toBeDefined());
    expect(screen.getByText('4')).toBeDefined();
    expect(screen.getByText('2')).toBeDefined();
    expect(screen.getByText('92.9%')).toBeDefined();
  });

  it('shows a fallback when the assistant is unavailable', async () => {
    vi.mocked(workflowAssistantApi.insights).mockRejectedValue(new Error('403'));
    vi.mocked(workflowAssistantApi.suggestions).mockRejectedValue(new Error('403'));
    vi.mocked(workflowAssistantApi.bottlenecks).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No assistant data/)).toBeDefined());
  });
});
