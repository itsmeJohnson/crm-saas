// @vitest-environment happy-dom
import { describe, it, expect, vi, afterEach } from 'vitest';
import { render, screen, cleanup } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import React from 'react';
import { ProtectedRoute } from '../ProtectedRoute';
import { useAuthStore } from '../../store/authStore';

// Mock Zustand Stores
vi.mock('../../store/authStore', () => ({
  useAuthStore: vi.fn(),
}));

describe('ProtectedRoute Component', () => {
  afterEach(() => {
    cleanup();
    vi.clearAllMocks();
  });

  it('redirects to /login if no access token is present', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        accessToken: null,
        user: null,
      };
      return selector ? selector(state) : state;
    });

    render(
      <MemoryRouter initialEntries={['/protected']}>
        <Routes>
          <Route element={<ProtectedRoute />}>
            <Route path="/protected" element={<div>Protected Content</div>} />
          </Route>
          <Route path="/login" element={<div>Login Page</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Login Page')).toBeDefined();
    expect(screen.queryByText('Protected Content')).toBeNull();
  });

  it('redirects to / if user role is not allowed', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        accessToken: 'valid-token',
        user: { role: 'Employee' },
      };
      return selector ? selector(state) : state;
    });

    render(
      <MemoryRouter initialEntries={['/admin-only']}>
        <Routes>
          <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
            <Route path="/admin-only" element={<div>Admin Content</div>} />
          </Route>
          <Route path="/" element={<div>Dashboard Root</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Dashboard Root')).toBeDefined();
    expect(screen.queryByText('Admin Content')).toBeNull();
  });

  it('allows access to protected route if user role is in allowedRoles', () => {
    vi.mocked(useAuthStore).mockImplementation((selector: any) => {
      const state = {
        accessToken: 'valid-token',
        user: { role: 'OrgAdmin' },
      };
      return selector ? selector(state) : state;
    });

    render(
      <MemoryRouter initialEntries={['/admin-only']}>
        <Routes>
          <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
            <Route path="/admin-only" element={<div>Admin Content</div>} />
          </Route>
          <Route path="/" element={<div>Dashboard Root</div>} />
        </Routes>
      </MemoryRouter>
    );

    expect(screen.getByText('Admin Content')).toBeDefined();
    expect(screen.queryByText('Dashboard Root')).toBeNull();
  });
});
