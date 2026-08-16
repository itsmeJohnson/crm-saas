// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AiDeveloperWidget } from '../AiDeveloperWidget';
import { aiDeveloperApi } from '../../../services/aiDeveloperApi';

vi.mock('../../../services/aiDeveloperApi', () => ({ aiDeveloperApi: { portal: vi.fn() } }));

const PORTAL = {
  base_url: 'https://crm.test/api/v1/ai-api', current_version: 'v1',
  versions: [{ version: 'v1', status: 'stable', released: '2026-07-23', sunset: null, notes: '' }],
  keys_total: 5, keys_active: 3,
  webhooks_total: 2, webhooks_active: 2,
  requests_30d: 148, failed_30d: 4, throttled_30d: 1,
  tokens_30d: 91234, cost_30d: 1.42, success_rate: 97.3,
  dead_letter_deliveries: 0,
  sdk_languages: [], scopes: [], webhook_events: [], keys: [],
};

describe('AiDeveloperWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><AiDeveloperWidget /></BrowserRouter>);

  it('renders active keys, 30-day calls and active webhooks', async () => {
    vi.mocked(aiDeveloperApi.portal).mockResolvedValue(PORTAL as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('AI API & SDK')).toBeDefined());
    expect(screen.getByText('3')).toBeDefined();
    expect(screen.getByText('148')).toBeDefined();
    expect(screen.getByText('2')).toBeDefined();
  });

  it('shows a fallback when the portal is unavailable', async () => {
    vi.mocked(aiDeveloperApi.portal).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No developer API data/)).toBeDefined());
  });
});
