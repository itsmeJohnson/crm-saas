// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import { MyLeadsWidget } from '../MyLeadsWidget';
import type { EmployeeSummary } from '../../../services/dashboardApi';

const SUMMARY: EmployeeSummary = {
  my_leads_total: 12, my_leads_converted: 9,
  my_leads_by_status: [{ status: 'New', count: 6 }, { status: 'Won', count: 4 }, { status: 'Contacted', count: 2 }],
  today_calls: 5, today_meetings_count: 2, today_meetings: [], open_tasks: 3, overdue_tasks: 1,
};

describe('MyLeadsWidget', () => {
  afterEach(cleanup);
  const renderWidget = (data: EmployeeSummary | null) => render(<BrowserRouter><MyLeadsWidget data={data} /></BrowserRouter>);

  it('renders assigned + converted counts and status breakdown', () => {
    renderWidget(SUMMARY);
    expect(screen.getByText('My Leads')).toBeDefined();
    expect(screen.getByText('12')).toBeDefined();  // assigned
    expect(screen.getByText('9')).toBeDefined();   // converted
    expect(screen.getByText('New')).toBeDefined();
  });

  it('shows empty state with no leads', () => {
    renderWidget({ ...SUMMARY, my_leads_total: 0, my_leads_by_status: [] });
    expect(screen.getByText('No leads assigned to you.')).toBeDefined();
  });
});
