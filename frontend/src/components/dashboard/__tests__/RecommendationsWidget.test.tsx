// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { RecommendationsWidget } from '../RecommendationsWidget';
import { recommendationApi } from '../../../services/recommendationApi';

vi.mock('../../../services/recommendationApi', () => ({
  recommendationApi: { dashboard: vi.fn() },
}));

const DASH = {
  top_recommendations: [
    { rec_type: 'next_best_action', rec_key: 'k1', title: 'Push to close: HotCo', reason: '', priority: 'high', score: 70, target_type: 'lead', target_id: 'l1', payload: {} },
    { rec_type: 'follow_up', rec_key: 'k2', title: 'Follow up with Stale Lead', reason: '', priority: 'medium', score: 45, target_type: 'lead', target_id: 'l2', payload: {} },
  ],
  types_present: ['next_best_action', 'follow_up'], total: 7, my_pending: 5, my_accepted: 2,
};

describe('RecommendationsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><RecommendationsWidget /></BrowserRouter>);

  it('renders top recommendations and counts', async () => {
    vi.mocked(recommendationApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Recommendations')).toBeDefined());
    expect(screen.getByText('Push to close: HotCo')).toBeDefined();
    expect(screen.getByText(/7 live · 5 pending · 2 accepted/)).toBeDefined();
  });

  it('shows a caught-up message when there are no recommendations', async () => {
    vi.mocked(recommendationApi.dashboard).mockResolvedValue({
      top_recommendations: [], types_present: [], total: 0, my_pending: 0, my_accepted: 0 } as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText(/all caught up/)).toBeDefined());
  });
});
