// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup, waitFor } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { EmployeeAnalyticsWidget } from '../EmployeeAnalyticsWidget';
import { employeeAnalyticsApi } from '../../../services/employeeAnalyticsApi';

vi.mock('../../../services/employeeAnalyticsApi', () => ({
  employeeAnalyticsApi: { dashboard: vi.fn() },
}));

const DASH = {
  headcount: 12, avg_productivity: 64.5, avg_attendance: 91.2, avg_training_score: 78,
  top_performer: { name: 'Emp One', productivity_score: 88 },
};

describe('EmployeeAnalyticsWidget', () => {
  afterEach(() => { cleanup(); vi.clearAllMocks(); });
  const renderWidget = () => render(<BrowserRouter><EmployeeAnalyticsWidget /></BrowserRouter>);

  it('renders workforce KPIs and the top performer', async () => {
    vi.mocked(employeeAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    renderWidget();
    await waitFor(() => expect(screen.getByText('Employee Analytics')).toBeDefined());
    expect(screen.getByText('64.5')).toBeDefined();
    expect(screen.getByText('91.2%')).toBeDefined();
    expect(screen.getByText(/Emp One/)).toBeDefined();
  });

  it('shows a loader before data resolves', async () => {
    vi.mocked(employeeAnalyticsApi.dashboard).mockResolvedValue(DASH as any);
    const { container } = renderWidget();
    expect(container.querySelector('.animate-spin')).not.toBeNull();
  });
});
