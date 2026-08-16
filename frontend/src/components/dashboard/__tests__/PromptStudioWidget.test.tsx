// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { PromptStudioWidget } from '../PromptStudioWidget';
import { promptStudioApi } from '../../../services/promptStudioApi';

vi.mock('../../../services/promptStudioApi', () => ({ promptStudioApi: { dashboard: vi.fn() } }));

const DASH = { prompts: 18, active: 12, pending_review: 3, total_usage: 274, categories: 7 };

describe('PromptStudioWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><PromptStudioWidget /></BrowserRouter>);

  it('renders prompt, pending and usage stats', async () => {
    vi.mocked(promptStudioApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Prompt Studio')).toBeDefined());
    expect(screen.getByText('18')).toBeDefined();
    expect(screen.getByText('3')).toBeDefined();
    expect(screen.getByText('274')).toBeDefined();
  });

  it('shows a fallback when the dashboard is unavailable', async () => {
    vi.mocked(promptStudioApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No prompt data/)).toBeDefined());
  });
});
