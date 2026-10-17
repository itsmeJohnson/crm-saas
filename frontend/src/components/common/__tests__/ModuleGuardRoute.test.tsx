// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';
import { ModuleGuardRoute } from '../ModuleGuardRoute';
import { useAuthStore } from '../../../store/authStore';
import { useMetadataStore } from '../../../store/metadataStore';

// Mock stores
vi.mock('../../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

vi.mock('../../../store/metadataStore', () => ({
  useMetadataStore: vi.fn(),
}));

describe('ModuleGuardRoute Component', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  const renderWithRouter = (ui: React.ReactElement, initialEntries = ['/patients']) => {
    return render(
      <MemoryRouter initialEntries={initialEntries}>
        <Routes>
          <Route element={ui}>
            <Route path="/patients" element={<div>Patients Page Rendered</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );
  };

  it('renders loading indicator when bootstrap is not loaded', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = { user: { role: 'Employee' }, features: [] };
      return selector ? selector(state) : state;
    });

    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = { loaded: false, crmConfig: null };
      return selector ? selector(state) : state;
    });

    renderWithRouter(<ModuleGuardRoute moduleKey="patients" />);
    expect(screen.getByText('Loading workspace configuration...')).toBeDefined();
  });

  it('blocks render and displays Module Disabled when module is not in enabled_modules', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = { user: { role: 'Employee' }, features: [] };
      return selector ? selector(state) : state;
    });

    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = {
        loaded: true,
        crmConfig: {
          industry: 'real_estate',
          template: 'real_estate',
          enabled_modules: ['dashboard', 'leads'],
        },
      };
      return selector ? selector(state) : state;
    });

    renderWithRouter(<ModuleGuardRoute moduleKey="patients" />);
    expect(screen.getByText('Module Disabled')).toBeDefined();
    expect(screen.queryByText('Patients Page Rendered')).toBeNull();
  });

  it('allows access and renders children when module is enabled', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = { user: { role: 'Employee' }, features: [] };
      return selector ? selector(state) : state;
    });

    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = {
        loaded: true,
        crmConfig: {
          industry: 'healthcare_dental',
          template: 'healthcare_dental',
          enabled_modules: ['dashboard', 'patients'],
        },
      };
      return selector ? selector(state) : state;
    });

    renderWithRouter(<ModuleGuardRoute moduleKey="patients" />);
    expect(screen.getByText('Patients Page Rendered')).toBeDefined();
    expect(screen.queryByText('Module Disabled')).toBeNull();
  });

  it('blocks render and displays Access Denied when user role is unauthorized for the matched route', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = { user: { role: 'Employee' }, features: [] };
      return selector ? selector(state) : state;
    });

    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = {
        loaded: true,
        crmConfig: {
          industry: 'healthcare_dental',
          template: 'healthcare_dental',
          enabled_modules: ['dashboard', 'treatments'],
        },
      };
      return selector ? selector(state) : state;
    });

    // Match /treatments/master which requires OrgAdmin/Manager role
    render(
      <MemoryRouter initialEntries={['/treatments/master']}>
        <Routes>
          <Route element={<ModuleGuardRoute moduleKey="treatments" />}>
            <Route path="/treatments/master" element={<div>Treatment Master Rendered</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Access Denied')).toBeDefined();
    expect(screen.queryByText('Treatment Master Rendered')).toBeNull();
  });

  it('blocks direct URL access to /billing for Telecaller Employee role and displays Access Denied (403)', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = { user: { role: 'Employee', is_team_leader: false }, features: [] };
      return selector ? selector(state) : state;
    });

    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = {
        loaded: true,
        crmConfig: {
          industry: 'telecalling',
          template: 'telecalling',
          enabled_modules: ['admin_core', 'leads'],
        },
      };
      return selector ? selector(state) : state;
    });

    render(
      <MemoryRouter initialEntries={['/billing']}>
        <Routes>
          <Route element={<ModuleGuardRoute moduleKey="admin_core" />}>
            <Route path="/billing" element={<div>Billing Invoicing Rendered</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Access Denied')).toBeDefined();
    expect(screen.getByText('You do not have the required role to view this page.')).toBeDefined();
    expect(screen.queryByText('Billing Invoicing Rendered')).toBeNull();
  });

  it('allows direct URL access to /billing for OrgAdmin role', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = { user: { role: 'OrgAdmin' }, features: [] };
      return selector ? selector(state) : state;
    });

    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = {
        loaded: true,
        crmConfig: {
          industry: 'telecalling',
          template: 'telecalling',
          enabled_modules: ['admin_core', 'leads'],
        },
      };
      return selector ? selector(state) : state;
    });

    render(
      <MemoryRouter initialEntries={['/billing']}>
        <Routes>
          <Route element={<ModuleGuardRoute moduleKey="admin_core" />}>
            <Route path="/billing" element={<div>Billing Invoicing Rendered</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Billing Invoicing Rendered')).toBeDefined();
    expect(screen.queryByText('Access Denied')).toBeNull();
  });

  it('blocks direct URL access to /marketing for Telecaller Employee role', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = { user: { role: 'Employee', is_team_leader: false }, features: [] };
      return selector ? selector(state) : state;
    });

    vi.mocked(useMetadataStore).mockImplementation((selector: any) => {
      const state = {
        loaded: true,
        crmConfig: {
          industry: 'telecalling',
          template: 'telecalling',
          enabled_modules: ['reports'],
        },
      };
      return selector ? selector(state) : state;
    });

    render(
      <MemoryRouter initialEntries={['/marketing']}>
        <Routes>
          <Route element={<ModuleGuardRoute moduleKey="reports" />}>
            <Route path="/marketing" element={<div>Marketing Page Rendered</div>} />
          </Route>
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Access Denied')).toBeDefined();
    expect(screen.queryByText('Marketing Page Rendered')).toBeNull();
  });
});
