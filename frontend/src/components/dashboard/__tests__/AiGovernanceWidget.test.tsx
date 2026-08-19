// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { AiGovernanceWidget } from '../AiGovernanceWidget';
import { aiGovernanceApi } from '../../../services/aiGovernanceApi';

vi.mock('../../../services/aiGovernanceApi', () => ({ aiGovernanceApi: { dashboard: vi.fn() } }));

const DASH = {
  policy_enabled: true, controls_active: 4,
  controls: { pii_detection: true, injection_protection: true, content_filter: false, model_restrictions: true, role_restrictions: true, require_grounding: false },
  events_30d: 27, blocked_30d: 5, masked_30d: 19, flagged_30d: 3,
  by_type: { pii: 19, injection: 5 }, by_action: { masked: 19, blocked: 5 }, recent: [],
};

describe('AiGovernanceWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><AiGovernanceWidget /></BrowserRouter>);

  it('renders controls, masked and blocked counts', async () => {
    vi.mocked(aiGovernanceApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('4')).toBeDefined());
    expect(screen.getByText('19')).toBeDefined();
    expect(screen.getByText('5')).toBeDefined();
  });

  it('shows a fallback when the dashboard is unavailable', async () => {
    vi.mocked(aiGovernanceApi.dashboard).mockRejectedValue(new Error('403'));
    renderWidget();
    await waitFor(() => expect(screen.getByText(/No governance data/)).toBeDefined());
  });
});
