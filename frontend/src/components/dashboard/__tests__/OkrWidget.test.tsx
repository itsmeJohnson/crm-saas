// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { OkrWidget } from '../OkrWidget';
import { okrApi } from '../../../services/okrApi';

vi.mock('../../../services/okrApi', () => ({ okrApi: { dashboard: vi.fn() } }));

const DASH = {
  total: 6, achieved: 2, on_track: 3, at_risk: 1, missed: 0,
  avg_progress: 58.3, by_level: { company: 2, individual: 4 }, reviews: 5, at_risk_objectives: [],
};

describe('OkrWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><OkrWidget /></BrowserRouter>);

  it('renders achieved ratio, at-risk count and average progress', async () => {
    vi.mocked(okrApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Goals & OKRs')).toBeDefined());
    expect(screen.getByText('2/6')).toBeDefined();
    expect(screen.getByText('1')).toBeDefined();
    expect(screen.getByText('58.3%')).toBeDefined();
  });

  it('shows an empty state when no objectives exist', async () => {
    vi.mocked(okrApi.dashboard).mockResolvedValue({ ...DASH, total: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/Create an objective/)).toBeDefined());
  });
});
