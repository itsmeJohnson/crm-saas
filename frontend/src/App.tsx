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

// Self Service Portal imports
import { OrgPortalLayout } from './layouts/OrgPortalLayout';
import { PortalDashboard } from './pages/portal/PortalDashboard';
import { PortalSubscription } from './pages/portal/PortalSubscription';
import { PortalPlans } from './pages/portal/PortalPlans';
import { PortalInvoices } from './pages/portal/PortalInvoices';
import { PortalPayments } from './pages/portal/PortalPayments';
import { PortalUsage } from './pages/portal/PortalUsage';
import { PortalStorage } from './pages/portal/PortalStorage';
import { PortalRecordings } from './pages/portal/PortalRecordings';
import { PortalUsers } from './pages/portal/PortalUsers';
import { PortalProfile } from './pages/portal/PortalProfile';
import { PortalBilling } from './pages/portal/PortalBilling';
import { PortalSupport } from './pages/portal/PortalSupport';
import { PortalActivityLogs } from './pages/portal/PortalActivityLogs';
import { PortalSettings } from './pages/portal/PortalSettings';


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

            {/* Organization Self-Service Portal Layout (restricted to OrgAdmin) */}
            <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
              <Route element={<OrgPortalLayout />}>
                <Route path="/portal/dashboard" element={<PortalDashboard />} />
                <Route path="/portal/subscription" element={<PortalSubscription />} />
                <Route path="/portal/plans" element={<PortalPlans />} />
                <Route path="/portal/invoices" element={<PortalInvoices />} />
                <Route path="/portal/payments" element={<PortalPayments />} />
                <Route path="/portal/usage" element={<PortalUsage />} />
                <Route path="/portal/storage" element={<PortalStorage />} />
                <Route path="/portal/recordings" element={<PortalRecordings />} />
                <Route path="/portal/users" element={<PortalUsers />} />
                <Route path="/portal/profile" element={<PortalProfile />} />
                <Route path="/portal/billing" element={<PortalBilling />} />
                <Route path="/portal/support" element={<PortalSupport />} />
                <Route path="/portal/activity" element={<PortalActivityLogs />} />
                <Route path="/portal/settings" element={<PortalSettings />} />
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
