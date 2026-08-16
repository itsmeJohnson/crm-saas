// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { EmployeeHeroCard } from '../EmployeeHeroCard';

const SUMMARY = {
  my_leads_total: 12, my_leads_converted: 3, my_leads_by_status: [],
  today_calls: 7, today_meetings_count: 2, today_meetings: [], open_tasks: 5, overdue_tasks: 1,
  employee_name: 'Amit Kumar', is_online: true, check_in_at: '2026-07-24T09:15:00Z',
  working_minutes: 135, calls_made_today: 7, todays_follow_ups: 4, overdue_follow_ups: 2,
  new_leads: 6, interested_leads: 3, meetings_today: 2, tasks_pending: 5,
};

describe('EmployeeHeroCard', () => {
  afterEach(() => cleanup());

  it('shows the employee name, online status and all day stats', () => {
    render(<EmployeeHeroCard summary={SUMMARY as any} name="Amit" />);
    expect(screen.getByText('Amit Kumar')).toBeDefined();
    expect(screen.getByText('Online')).toBeDefined();
    expect(screen.getByText('2h 15m')).toBeDefined();      // working duration
    expect(screen.getByText("Today's Follow-ups")).toBeDefined();
    expect(screen.getByText('Overdue Follow-ups')).toBeDefined();
    expect(screen.getByText('Interested Leads')).toBeDefined();
    expect(screen.getByText('4')).toBeDefined();            // todays_follow_ups value
  });

  it('renders Offline and dashes when the employee has not checked in', () => {
    render(<EmployeeHeroCard summary={{ ...SUMMARY, is_online: false, check_in_at: null, working_minutes: 0 } as any} name="Amit" />);
    expect(screen.getByText('Offline')).toBeDefined();
  });
});
