// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { TemplatesWidget } from '../TemplatesWidget';
import { templateApi } from '../../../services/templateApi';

vi.mock('../../../services/templateApi', () => ({
  templateApi: { reports: vi.fn() },
}));

const REPORT = {
  total: 7, total_usage: 12, pending_approval: 2, approved: 4, drafts: 1,
  by_channel: [], by_status: [], by_category: [],
  most_used: [{ id: 't1', name: 'Welcome Email', channel: 'Email', usage_count: 8 }],
};

describe('TemplatesWidget Component', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWithRouter = (ui: React.ReactElement) => render(<BrowserRouter>{ui}</BrowserRouter>);

  it('renders approval counts and most-used templates', async () => {
    vi.mocked(templateApi.reports).mockResolvedValue(REPORT as any);
    renderWithRouter(<TemplatesWidget />);
    await waitFor(() => expect(screen.getByText('Templates')).toBeDefined());
    expect(screen.getByText('4')).toBeDefined(); // approved
    expect(screen.getByText('2')).toBeDefined(); // pending
    expect(screen.getByText('Welcome Email')).toBeDefined();
    expect(screen.getByText('8×')).toBeDefined();
  });

  it('shows empty state when there are no templates', async () => {
    vi.mocked(templateApi.reports).mockResolvedValue({ ...REPORT, total: 0 } as any);
    renderWithRouter(<TemplatesWidget />);
    await waitFor(() => expect(screen.getByText('No templates yet.')).toBeDefined());
  });
});
