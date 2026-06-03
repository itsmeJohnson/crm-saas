// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { LeadStatusChart } from '../LeadStatusChart';
import { DashboardSummaryResponse } from '../../../services/dashboardApi';

// Mock ResponsiveContainer to render properly in virtual DOM
vi.mock('recharts', async () => {
  const original = await vi.importActual('recharts') as any;
  return {
    ...original,
    ResponsiveContainer: ({ children }: any) => (
      <div style={{ width: '800px', height: '600px' }}>{children}</div>
    )
  };
});

describe('LeadStatusChart Component', () => {
  afterEach(() => {
    cleanup();
  });

  const mockSummary: DashboardSummaryResponse = {
    total_leads: 10,
    contacts_count: 5,
    companies_count: 3,
    activities_count: 12,
    user_count: 2,
    leads_by_status: {
      New: 3,
      Contacted: 2,
      Qualified: 4,
      Lost: 1
    },
    assigned_leads_breakdown: []
  };

  it('renders lead status distribution chart correctly', () => {
    render(<LeadStatusChart summary={mockSummary} isLoading={false} />);

    expect(screen.getByText('Lead Status Distribution')).toBeDefined();
    expect(screen.getByText('10')).toBeDefined();
  });

  it('renders empty state when there are 0 leads', () => {
    const emptySummary = { ...mockSummary, total_leads: 0, leads_by_status: {} };
    render(<LeadStatusChart summary={emptySummary} isLoading={false} />);

    expect(screen.getByText('No lead data to display')).toBeDefined();
  });
});
