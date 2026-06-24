// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { SummaryCards } from '../SummaryCards';
import { DashboardSummaryResponse } from '../../../services/dashboardApi';

describe('SummaryCards Component', () => {
  afterEach(() => {
    cleanup();
  });

  const mockSummary: DashboardSummaryResponse = {
    total_leads: 12,
    contacts_count: 34,
    companies_count: 56,
    activities_count: 78,
    user_count: 5,
    leads_by_status: {},
    assigned_leads_breakdown: []
  };

  it('renders summary counts correctly', () => {
    render(<SummaryCards summary={mockSummary} isLoading={false} />);

    expect(screen.getByText('Total Leads')).toBeDefined();
    expect(screen.getByText('12')).toBeDefined();

    expect(screen.getByText('Activities')).toBeDefined();
    expect(screen.getByText('78')).toBeDefined();

    expect(screen.getByText('Active Team')).toBeDefined();
    expect(screen.getByText('5')).toBeDefined();
  });

  it('renders skeletons when loading', () => {
    const { container } = render(<SummaryCards summary={null} isLoading={true} />);
    
    const pulses = container.getElementsByClassName('animate-pulse');
    expect(pulses.length).toBe(3);
  });
});
