// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { BrowserRouter } from 'react-router-dom';
import React from 'react';
import { AppLayout } from '../AppLayout';
import { useAuthStore } from '../../store/authStore';
import { useMetadataStore } from '../../store/metadataStore';

// Mock Zustand Stores
vi.mock('../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../../store/metadataStore', () => ({
  useMetadataStore: vi.fn(),
}));

describe('AppLayout Component - Sidebar Role Visibility', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement) => {
    return render(<BrowserRouter>{ui}</BrowserRouter>);
  };

  const setupMetadataMock = () => {
    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = {
        loaded: true,
        crmConfig: {
          industry: 'healthcare_dental',
          template: 'healthcare_dental',
          enabled_modules: [
            'dashboard', 'leads', 'patients', 'appointments', 'treatments',
            'treatment_plans', 'recall', 'dentists', 'clinical_reports',
            'billing', 'communications', 'reports', 'admin_core', 'pipelines',
            'tasks'
          ]
        },
        fetchBootstrap: vi.fn(),
      };
      return selector ? selector(state) : state;
    });
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

    setupMetadataMock();
    renderWithRouter(<AppLayout />);

    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Leads & Enquiries')).toBeDefined();
    expect(screen.getByText('Pipelines')).toBeDefined();
    expect(screen.getByText('Staff & Team')).toBeDefined();
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

    setupMetadataMock();
    renderWithRouter(<AppLayout />);

    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Leads & Enquiries')).toBeDefined();
    expect(screen.getByText('Staff & Team')).toBeDefined();
    expect(screen.queryByText('Pipelines')).toBeNull();
    expect(screen.queryByText('Organization')).toBeNull();

    // Billing & Account is OrgAdmin-only — a Manager sees none of it.
    expect(screen.queryByText('Billing & Account')).toBeNull();
    expect(screen.queryByText('Subscription')).toBeNull();
  });

  it('enforces strict RBAC navigation groups for baseline Telecaller Employee role', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          first_name: 'Charlie',
          last_name: 'Telecaller',
          email: 'contact@johnsonsoftwares.com',
          role: 'Employee',
          is_team_leader: false,
        },
        organization: { name: 'Demo Corp' },
        features: ['LEAD_MANAGEMENT', 'CLICK_TO_CALL', 'WHATSAPP_MESSAGING', 'ROLE_BASED_ACCESS'],
        logout: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    setupMetadataMock();
    renderWithRouter(<AppLayout />);

    // 1. Navigation Groups visible for Telecaller
    expect(screen.getByText('Lead Management')).toBeDefined();
    expect(screen.getByText('Dialer Console')).toBeDefined();
    expect(screen.getByText('Follow-ups & Reminders')).toBeDefined();

    // 2. EXPOSE / SHOW in Telecaller Menu
    expect(screen.getByText('Leads & Enquiries')).toBeDefined();
    expect(screen.getByText('Phone Calling')).toBeDefined();
    expect(screen.getByText('WhatsApp Center')).toBeDefined();
    expect(screen.getByText('Communications')).toBeDefined();
    expect(screen.getByText('Tasks & Reminders')).toBeDefined();

    // 3. REMOVE / HIDE from Telecaller Menu
    expect(screen.queryByText('Billing & Invoices')).toBeNull();
    expect(screen.queryByText('Marketing ROI')).toBeNull();
    expect(screen.queryByText('Voice Broadcast')).toBeNull();
    expect(screen.queryByText('Staff & Team')).toBeNull();
    expect(screen.queryByText('Dashboard')).toBeNull();
    expect(screen.queryByText('Pipelines')).toBeNull();
    expect(screen.queryByText('Organization')).toBeNull();
    expect(screen.queryByText('Billing & Account')).toBeNull();
    expect(screen.queryByText('Campaign Analytics')).toBeNull();
    expect(screen.queryByText('Administration')).toBeNull();
  });

  it('allows TeamLeader employee to view Staff & Team', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          first_name: 'David',
          last_name: 'Lead',
          email: 'lead@johnsonsoftwares.com',
          role: 'Employee',
          is_team_leader: true,
        },
        organization: { name: 'Demo Corp' },
        features: ['LEAD_MANAGEMENT', 'CLICK_TO_CALL', 'WHATSAPP_MESSAGING', 'ROLE_BASED_ACCESS'],
        logout: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    setupMetadataMock();
    renderWithRouter(<AppLayout />);

    expect(screen.getByText('Staff & Team')).toBeDefined();
  });
});
