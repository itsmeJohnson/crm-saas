// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { QuickActionsWidget } from '../QuickActionsWidget';
import { useAuthStore } from '../../../store/authStore';

vi.mock('../../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('QuickActionsWidget Component', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement) => render(<BrowserRouter>{ui}</BrowserRouter>);

  it('shows Manage Team for OrgAdmin with ROLE_BASED_ACCESS enabled', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: { role: 'OrgAdmin' },
      features: ['LEAD_MANAGEMENT', 'ROLE_BASED_ACCESS'],
    } as any);
    renderWithRouter(<QuickActionsWidget />);
    expect(screen.getByText('Manage Team')).toBeDefined();
    expect(screen.getByText('View Contacts')).toBeDefined();
  });

  it('hides admin-only actions for a Telecaller (plain Employee)', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: { role: 'Employee' },
      features: ['LEAD_MANAGEMENT'],
    } as any);
    renderWithRouter(<QuickActionsWidget />);
    expect(screen.getByText('View Leads')).toBeDefined();
    expect(screen.queryByText('Manage Team')).toBeNull();
    expect(screen.queryByText('View Contacts')).toBeNull();
  });

  it('hides feature-gated actions when the plan does not include them', () => {
    vi.mocked(useAuthStore).mockReturnValue({
      user: { role: 'OrgAdmin' },
      features: [],
    } as any);
    renderWithRouter(<QuickActionsWidget />);
    expect(screen.queryByText('View Leads')).toBeNull();
  });
});
