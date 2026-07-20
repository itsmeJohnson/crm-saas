// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { AppLayout } from '../AppLayout';
import { useAuthStore } from '../../store/authStore';

// Mock Zustand Stores
vi.mock('../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('AppLayout Component - Sidebar Role Visibility', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement) => {
    return render(<BrowserRouter>{ui}</BrowserRouter>);
  };

  it('renders all links for OrgAdmin role', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          first_name: 'Alice',
          last_name: 'Admin',
          email: 'admin@democorp.com',
          role: 'OrgAdmin',
        },
        organization: { name: 'Demo Corp' },
        features: ['LEAD_MANAGEMENT', 'SALES_PIPELINE', 'ROLE_BASED_ACCESS'],
        logout: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    renderWithRouter(<AppLayout />);

    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Leads')).toBeDefined();
    expect(screen.getByText('Pipelines')).toBeDefined();
    expect(screen.getByText('Team Members')).toBeDefined();
    expect(screen.getByText('Organization')).toBeDefined();

    // Billing & Account section is unified into the same sidebar for OrgAdmin.
    expect(screen.getByText('Billing & Account')).toBeDefined();
    expect(screen.getByText('Subscription')).toBeDefined();
    expect(screen.getByText('Seat Licensing')).toBeDefined();
  });

  it('renders standard links and Users, but hides Organization setting for Manager role', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          first_name: 'Bob',
          last_name: 'Manager',
          email: 'mgr@democorp.com',
          role: 'Manager',
        },
        organization: { name: 'Demo Corp' },
        features: ['LEAD_MANAGEMENT', 'SALES_PIPELINE', 'ROLE_BASED_ACCESS'],
        logout: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    renderWithRouter(<AppLayout />);

    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Leads')).toBeDefined();
    expect(screen.getByText('Team Members')).toBeDefined();
    expect(screen.queryByText('Pipelines')).toBeNull();
    expect(screen.queryByText('Organization')).toBeNull();

    // Billing & Account is OrgAdmin-only — a Manager sees none of it.
    expect(screen.queryByText('Billing & Account')).toBeNull();
    expect(screen.queryByText('Subscription')).toBeNull();
  });

  it('renders only standard links, hiding both Users and Organization settings for Employee role', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          first_name: 'Charlie',
          last_name: 'Employee',
          email: 'emp@democorp.com',
          role: 'Employee',
        },
        organization: { name: 'Demo Corp' },
        features: ['LEAD_MANAGEMENT', 'SALES_PIPELINE', 'ROLE_BASED_ACCESS'],
        logout: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    renderWithRouter(<AppLayout />);

    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Leads')).toBeDefined();
    expect(screen.queryByText('Pipelines')).toBeNull();
    expect(screen.queryByText('Team Members')).toBeNull();
    expect(screen.queryByText('Organization')).toBeNull();
    expect(screen.queryByText('Billing & Account')).toBeNull();
  });
});
