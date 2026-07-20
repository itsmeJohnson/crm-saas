// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { ComplianceWidget } from '../ComplianceWidget';
import { complianceApi } from '../../../services/complianceApi';

vi.mock('../../../services/complianceApi', () => ({ complianceApi: { dashboard: vi.fn() } }));

const DASH = {
  counts: { last_24h: 4, last_7d: 31, last_30d: 120 },
  by_category: [], failed_logins_30d: 2,
  top_actors: [{ user_id: 'u1', name: 'Ad Min', events: 80 }],
  recent_sensitive: [],
};

describe('ComplianceWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><ComplianceWidget /></BrowserRouter>);

  it('renders event, failed-login and actor counts', async () => {
    vi.mocked(complianceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Audit & Compliance')).toBeDefined());
    expect(screen.getByText('31')).toBeDefined();
    expect(screen.getByText('2')).toBeDefined();
    expect(screen.getByText('1')).toBeDefined();
  });

  it('shows a fallback when the API is unavailable', async () => {
    vi.mocked(complianceApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No audit data/)).toBeDefined());
  });
});
