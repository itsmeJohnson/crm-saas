// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { RulesWidget } from '../RulesWidget';
import { ruleApi } from '../../../services/ruleApi';

vi.mock('../../../services/ruleApi', () => ({ ruleApi: { dashboard: vi.fn() } }));

const DASH = {
  total: 9, active: 6, match_rate: 72.5, evaluations: 88,
  top: [
    { id: 'r1', name: 'High-value hot lead', entity_type: 'lead', priority: 200, match_count: 41 },
    { id: 'r2', name: 'Stale lead escalation', entity_type: 'lead', priority: 150, match_count: 12 },
  ],
};

describe('RulesWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><RulesWidget /></BrowserRouter>);

  it('renders rules/active/match-rate and top rules', async () => {
    vi.mocked(ruleApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Rule Engine')).toBeDefined());
    expect(screen.getByText('9')).toBeDefined();        // total
    expect(screen.getByText('6')).toBeDefined();         // active
    expect(screen.getByText('72.5%')).toBeDefined();     // match rate
    expect(screen.getByText('High-value hot lead')).toBeDefined();
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(ruleApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
