// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ApprovalsWidget } from '../ApprovalsWidget';
import { approvalApi } from '../../../services/approvalApi';

vi.mock('../../../services/approvalApi', () => ({ approvalApi: { dashboard: vi.fn() } }));

const DASH = { my_pending: 2, awaiting_my_action: 5, total: 20, approved: 12, rejected: 3, pending: 5 };

describe('ApprovalsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><ApprovalsWidget /></BrowserRouter>);

  it('renders awaiting-action, my-pending and the status summary', async () => {
    vi.mocked(approvalApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Approvals')).toBeDefined());
    expect(screen.getByText('5')).toBeDefined();   // awaiting my action
    expect(screen.getByText('2')).toBeDefined();   // my pending
    expect(screen.getByText(/12 approved · 3 rejected · 5 pending/)).toBeDefined();
  });

  it('shows a loader then content', async () => {
    vi.mocked(approvalApi.dashboard).mockResolvedValue({ ...DASH, awaiting_my_action: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('To action')).toBeDefined());
  });
});
