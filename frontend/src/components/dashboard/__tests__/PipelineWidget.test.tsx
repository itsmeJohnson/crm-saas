// @vitest-environment happy-dom
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { PipelineWidget } from '../PipelineWidget';
import { DashboardSummaryResponse } from '../../../services/dashboardApi';

describe('PipelineWidget Component', () => {
  afterEach(() => {
    cleanup();
  });

  const baseSummary: DashboardSummaryResponse = {
    total_leads: 10,
    contacts_count: 0,
    companies_count: 0,
    activities_count: 0,
    user_count: 0,
    leads_by_status: {},
    assigned_leads_breakdown: [],
    leads_by_source: {},
    leads_by_stage: [
      { stage_id: '1', stage_name: 'New Lead', count: 5 },
      { stage_id: '2', stage_name: 'Won', count: 3 },
    ],
    conversion_rate: null,
    today: { leads_created: 0, meetings_due: 0, tasks_due: 0, follow_ups_due: 0 },
  };

  it('shows "not configured" when the org has no stage literally named "Converted"', () => {
    render(<PipelineWidget summary={baseSummary} isLoading={false} />);
    expect(screen.getByText('Conversion rate not configured')).toBeDefined();
    expect(screen.getByText('New Lead')).toBeDefined();
    expect(screen.getByText('Won')).toBeDefined();
  });

  it('shows the real percentage when conversion_rate is a number (including 0)', () => {
    render(<PipelineWidget summary={{ ...baseSummary, conversion_rate: 0 }} isLoading={false} />);
    expect(screen.getByText('0% converted')).toBeDefined();
  });

  it('shows an empty state when there are no pipeline stages', () => {
    render(<PipelineWidget summary={{ ...baseSummary, leads_by_stage: [] }} isLoading={false} />);
    expect(screen.getByText('No pipeline stages configured yet.')).toBeDefined();
  });
});
