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

describe('AppLayout Component - Strict RBAC Navigation Suite', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement) => {
    return render(<BrowserRouter>{ui}</BrowserRouter>);
  };

  const setupMetadataMock = (overrides?: any) => {
    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = {
        loaded: true,
        crmConfig: {
          industry: 'telecalling',
          template: 'telecalling',
          enabled_modules: [
            'dashboard', 'leads', 'patients', 'appointments', 'treatments',
            'treatment_plans', 'recall', 'dentists', 'clinical_reports',
            'billing', 'communications', 'reports', 'admin_core', 'pipelines',
            'tasks', 'analytics_suite', 'platform_core'
          ],
          ...overrides
        },
        fetchBootstrap: vi.fn(),
      };
      return selector ? selector(state) : state;
    });
  };

  const ALL_FEATURES = [
    'LEAD_MANAGEMENT', 'SALES_PIPELINE', 'ROLE_BASED_ACCESS',
    'CLICK_TO_CALL', 'WHATSAPP_MESSAGING', 'LEAD_CAPTURE',
    'MANAGER_DASHBOARD', 'KPI_DASHBOARD', 'CUSTOM_REPORTS',
    'ADVANCED_ANALYTICS', 'AI_CALL_SUMMARY'
  ];

  it('renders SuperAdmin control profile with platform roots and hides cold-calling clutter', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          first_name: 'Super',
          last_name: 'Admin',
          email: 'samarthasankalpa@gmail.com',
          role: 'SuperAdmin',
        },
        organization: { name: 'Root Infrastructure' },
        features: ALL_FEATURES,
        logout: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    setupMetadataMock();
    renderWithRouter(<AppLayout />);

    // Header Title
    expect(screen.getAllByText('CRM Enterprise · Secure Multi-Tenant Platform').length).toBeGreaterThanOrEqual(1);

    // EXPOSE / PIN to SuperAdmin Menu
    expect(screen.getByText('Platform Administration')).toBeDefined();
    expect(screen.getByText('Tenants Directory')).toBeDefined();
    expect(screen.getByText('Trial Requests')).toBeDefined();

    expect(screen.getAllByText('Global Settings').length).toBeGreaterThanOrEqual(1);

    // Campaign Analytics (root metrics)
    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Team Analytics')).toBeDefined();
    expect(screen.getByText('KPIs')).toBeDefined();
    expect(screen.getByText('Report Builder')).toBeDefined();
    expect(screen.getByText('AI Copilot')).toBeDefined();
    expect(screen.getByText('Call Summaries')).toBeDefined();

    // HIDE from SuperAdmin Workspace Sidebars (operational clutter)
    expect(screen.queryByText('Dialer Console')).toBeNull();
    expect(screen.queryByText('Phone Calling')).toBeNull();
    expect(screen.queryByText('WhatsApp Center')).toBeNull();
    expect(screen.queryByText('Voice Broadcast')).toBeNull();
    expect(screen.queryByText('Marketing ROI')).toBeNull();
    expect(screen.queryByText('Sales Analytics')).toBeNull();
  });

  it('renders full operational floor suite for Manager/TeamLeader and blocks billing & platform', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        user: {
          first_name: 'John',
          last_name: 'A',
          email: 'johnsondev02@gmail.com',
          role: 'TeamLeader',
          is_team_leader: true,
        },
        organization: { name: 'Samartha Sankalpa' },
        features: ALL_FEATURES,
        logout: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    setupMetadataMock();
    renderWithRouter(<AppLayout />);

    // 1. HIDE / LOCK from Manager Menu
    expect(screen.queryByText('Platform Administration')).toBeNull();
    expect(screen.queryByText('Tenants Directory')).toBeNull();
    expect(screen.queryByText('Trial Requests')).toBeNull();
    expect(screen.queryByText('Billing & Account')).toBeNull();
    expect(screen.queryByText('Subscription')).toBeNull();
    expect(screen.queryByText('Seat Licensing')).toBeNull();
    expect(screen.queryByText('Global Settings')).toBeNull();

    // 2. EXPOSE in Lead Management
    expect(screen.getByText('Lead Management')).toBeDefined();
    expect(screen.getByText('Leads & Enquiries')).toBeDefined();
    expect(screen.getByText('Lead Capture')).toBeDefined();
    expect(screen.getByText('Websites')).toBeDefined();
    expect(screen.getByText('Email Sequences')).toBeDefined();
    expect(screen.getByText('Booking Links')).toBeDefined();
    expect(screen.getByText('Pipelines')).toBeDefined();

    // 3. EXPOSE in Dialer Console
    expect(screen.getByText('Dialer Console')).toBeDefined();
    expect(screen.getByText('Phone Calling')).toBeDefined();
    expect(screen.getByText('WhatsApp Center')).toBeDefined();
    expect(screen.getByText('Communications')).toBeDefined();
    expect(screen.queryByText('Voice Broadcast')).toBeNull();

    // 4. EXPOSE in Campaign Analytics
    expect(screen.getByText('Campaign Analytics')).toBeDefined();
    expect(screen.getByText('Dashboard')).toBeDefined();
    expect(screen.getByText('Marketing ROI')).toBeDefined();
    expect(screen.getByText('Team Analytics')).toBeDefined();
    expect(screen.getByText('Sales Analytics')).toBeDefined();
    expect(screen.getByText('KPIs')).toBeDefined();
    expect(screen.getByText('Report Builder')).toBeDefined();
    expect(screen.getByText('AI Copilot')).toBeDefined();
    expect(screen.getByText('Call Summaries')).toBeDefined();

    // 5. EXPOSE in Administration
    expect(screen.getByText('Administration')).toBeDefined();
    expect(screen.getByText('Staff & Team')).toBeDefined();
    expect(screen.getByText('Custom Objects')).toBeDefined();
    expect(screen.getByText('Dynamic Forms')).toBeDefined();
    expect(screen.getByText('Attendance')).toBeDefined();
    expect(screen.getByText('Leaves')).toBeDefined();
    expect(screen.getByText('Shifts')).toBeDefined();
    expect(screen.getByText('Performance')).toBeDefined();
    expect(screen.getByText('Targets')).toBeDefined();
    expect(screen.getByText('Approvals')).toBeDefined();

    // 6. Follow-ups & Reminders
    expect(screen.getByText('Follow-ups & Reminders')).toBeDefined();
    expect(screen.getByText('Tasks & Reminders')).toBeDefined();
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
        features: ALL_FEATURES,
        logout: vi.fn(),
      };
      return selector ? selector(state) : state;
    });

    setupMetadataMock();
    renderWithRouter(<AppLayout />);

    // Navigation Groups visible for Telecaller
    expect(screen.getByText('Lead Management')).toBeDefined();
    expect(screen.getByText('Dialer Console')).toBeDefined();
    expect(screen.getByText('Follow-ups & Reminders')).toBeDefined();

    // EXPOSE / SHOW in Telecaller Menu
    expect(screen.getByText('Leads & Enquiries')).toBeDefined();
    expect(screen.getByText('Phone Calling')).toBeDefined();
    expect(screen.getByText('WhatsApp Center')).toBeDefined();
    expect(screen.getByText('Communications')).toBeDefined();
    expect(screen.getByText('Tasks & Reminders')).toBeDefined();

    // REMOVE / HIDE from Telecaller Menu
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
    expect(screen.queryByText('Platform Administration')).toBeNull();
  });
});
