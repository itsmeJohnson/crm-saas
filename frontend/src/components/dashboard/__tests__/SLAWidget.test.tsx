// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { SLAWidget } from '../SLAWidget';
import { slaApi } from '../../../services/slaApi';

vi.mock('../../../services/slaApi', () => ({ slaApi: { dashboard: vi.fn() } }));

const DASH = {
  policies: 5, active: 4, compliance_rate: 88.5, open_breaches: 7, at_risk: 3, running: 24, recent_breaches: [],
};

describe('SLAWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><SLAWidget /></BrowserRouter>);

  it('renders compliance/running/at-risk and open breaches', async () => {
    vi.mocked(slaApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('SLA')).toBeDefined());
    expect(screen.getByText('88.5%')).toBeDefined();     // compliance
    expect(screen.getByText('24')).toBeDefined();         // running
    expect(screen.getByText('3')).toBeDefined();           // at risk
    expect(screen.getByText('7')).toBeDefined();           // open breaches
  });

  it('shows a loader before data resolves', () => {
    vi.mocked(slaApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
