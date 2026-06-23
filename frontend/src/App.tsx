import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthLayout } from './layouts/AuthLayout';
import { AppLayout } from './layouts/AppLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Login } from './modules/auth/Login';
import { Register } from './modules/auth/Register';
import { Home } from './modules/dashboard/Home';
import { Profile } from './modules/organization/Profile';
import { UsersPage } from './pages/UsersPage';
import { LeadsPage } from './pages/LeadsPage';
import { CompaniesPage } from './pages/CompaniesPage';
import { ContactsPage } from './pages/ContactsPage';
import { PipelineSettings } from './components/admin/PipelineSettings';
import { TenantsPage } from './pages/TenantsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

import { FeatureGuardRoute } from './components/common/FeatureGuardRoute';

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          {/* Public Routes */}
          <Route element={<AuthLayout />}>
            <Route path="/login" element={<Login />} />
            <Route path="/register" element={<Register />} />
          </Route>

          {/* Protected Routes */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>
              <Route path="/" element={<Home />} />
              
              {/* Lead Management Feature Guard */}
              <Route element={<FeatureGuardRoute featureCode="LEAD_MANAGEMENT" />}>
                <Route path="/leads" element={<LeadsPage />} />
                
                {/* OrgAdmin & Manager only */}
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin', 'Manager']} />}>
                  <Route path="/companies" element={<CompaniesPage />} />
                  <Route path="/contacts" element={<ContactsPage />} />
                </Route>
              </Route>
              
              {/* Sales Pipeline Feature Guard */}
              <Route element={<FeatureGuardRoute featureCode="SALES_PIPELINE" />}>
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
                  <Route path="/pipelines" element={<PipelineSettings />} />
                </Route>
              </Route>

              {/* Role-Based Access Feature Guard */}
              <Route element={<FeatureGuardRoute featureCode="ROLE_BASED_ACCESS" />}>
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin', 'Manager']} allowTeamLeader={true} />}>
                  <Route path="/users" element={<UsersPage />} />
                </Route>
              </Route>

              {/* OrgAdmin only (general profile always allowed) */}
              <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
                <Route path="/organization" element={<Profile />} />
              </Route>

              {/* SuperAdmin only */}
              <Route element={<ProtectedRoute allowedRoles={['SuperAdmin']} />}>
                <Route path="/tenants" element={<TenantsPage />} />
              </Route>
            </Route>
          </Route>

          {/* Catch-all */}
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
