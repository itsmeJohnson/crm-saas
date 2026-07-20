// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { OrgHealthWidget } from '../OrgHealthWidget';
import { orgAnalyticsApi } from '../../../services/orgAnalyticsApi';

vi.mock('../../../services/orgAnalyticsApi', () => ({ orgAnalyticsApi: { health: vi.fn() } }));

const HEALTH = {
  score: 74.5, rating: 'Good',
  components: [
    { name: 'Attendance', score: 90, weight: 1 },
    { name: 'Target attainment', score: 60, weight: 2 },
    { name: 'Task completion', score: 80, weight: 1 },
    { name: 'Lead conversion', score: 70, weight: 2 },
  ],
};

describe('OrgHealthWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><OrgHealthWidget /></BrowserRouter>);

  it('renders the composite score, rating and components', async () => {
    vi.mocked(orgAnalyticsApi.health).mockResolvedValue(HEALTH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Org Health')).toBeDefined());
    expect(screen.getByText('74.5%')).toBeDefined();
    expect(screen.getByText('Good')).toBeDefined();
    expect(screen.getByText('Attendance')).toBeDefined();
    expect(screen.getByText('Lead conversion')).toBeDefined();
  });

  it('shows a loader before data resolves', async () => {
    vi.mocked(orgAnalyticsApi.health).mockResolvedValue(HEALTH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
