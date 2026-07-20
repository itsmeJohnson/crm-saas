// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { KnowledgeWidget } from '../KnowledgeWidget';
import { knowledgeApi } from '../../../services/knowledgeApi';

vi.mock('../../../services/knowledgeApi', () => ({ knowledgeApi: { dashboard: vi.fn() } }));

const DASH = {
  totals: {
    articles: 12, by_status: { published: 8, pending_review: 2, draft: 2 },
    by_type: { article: 9, faq: 3 }, categories: 4, chunks: 41, indexed: 12,
    indexed_pct: 100, total_views: 250,
  },
  helpful_rate: 92.5, events_30d: { view: 40, search: 12 },
  recent_searches: [], unanswered_queries: [], top_articles: [],
  embedding_model: 'hash_embed_v1',
};

describe('KnowledgeWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><KnowledgeWidget /></BrowserRouter>);

  it('renders published, pending and indexed stats', async () => {
    vi.mocked(knowledgeApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Knowledge Base')).toBeDefined());
    expect(screen.getByText('8')).toBeDefined();
    expect(screen.getByText('2')).toBeDefined();
    expect(screen.getByText('100%')).toBeDefined();
  });

  it('shows a fallback when the dashboard is unavailable', async () => {
    vi.mocked(knowledgeApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No knowledge data/)).toBeDefined());
  });
});
