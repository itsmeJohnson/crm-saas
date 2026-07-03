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
import { LeadReportsPage } from './pages/LeadReportsPage';
import { LeadAutomationPage } from './pages/LeadAutomationPage';
import { CompaniesPage } from './pages/CompaniesPage';
import { ContactsPage } from './pages/ContactsPage';
import { ContactReportsPage } from './pages/ContactReportsPage';
import { CompanyReportsPage } from './pages/CompanyReportsPage';
import { CustomersPage } from './pages/CustomersPage';
import { CustomerReportsPage } from './pages/CustomerReportsPage';
import { TasksPage } from './pages/TasksPage';
import { TaskReportsPage } from './pages/TaskReportsPage';
import { CalendarPage } from './pages/CalendarPage';
import { CommunicationCenterPage } from './pages/CommunicationCenterPage';
import { CallingPage } from './pages/CallingPage';
import { CallingReportsPage } from './pages/CallingReportsPage';
import { SmsPage } from './pages/SmsPage';
import { SmsReportsPage } from './pages/SmsReportsPage';
import { WhatsAppPage } from './pages/WhatsAppPage';
import { WhatsAppSettingsPage } from './pages/WhatsAppSettingsPage';
import { WhatsAppReportsPage } from './pages/WhatsAppReportsPage';
import { EmailPage } from './pages/EmailPage';
import { EmailSettingsPage } from './pages/EmailSettingsPage';
import { EmailReportsPage } from './pages/EmailReportsPage';
import { TemplatesPage } from './pages/TemplatesPage';
import { CampaignsPage } from './pages/CampaignsPage';
import { NotificationCenterPage } from './pages/NotificationCenterPage';
import { CommunicationAnalyticsPage } from './pages/CommunicationAnalyticsPage';
import { PipelineSettings } from './components/admin/PipelineSettings';
import { TenantsPage } from './pages/TenantsPage';
import { SubscriptionGateRoute } from './components/SubscriptionGateRoute';

// Self Service Portal imports
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

          {/* Protected Routes — single shared shell (AppLayout) for the whole app */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>

              {/* Operational workspace routes: blocked by SubscriptionGate once a
                  tenant's plan lapses (the billing routes below stay reachable so
                  an OrgAdmin can reactivate). */}
              <Route element={<SubscriptionGateRoute />}>
                <Route path="/" element={<Home />} />

                {/* Tasks & Calendar — available to all active users */}
                <Route path="/tasks" element={<TasksPage />} />
                <Route path="/tasks/reports" element={<TaskReportsPage />} />
                <Route path="/calendar" element={<CalendarPage />} />
                <Route path="/communications" element={<CommunicationCenterPage />} />
                <Route path="/calling" element={<CallingPage />} />
                <Route path="/calling/reports" element={<CallingReportsPage />} />
                <Route path="/sms" element={<SmsPage />} />
                <Route path="/sms/reports" element={<SmsReportsPage />} />
                <Route path="/whatsapp" element={<WhatsAppPage />} />
                <Route path="/whatsapp/reports" element={<WhatsAppReportsPage />} />
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
                  <Route path="/whatsapp/settings" element={<WhatsAppSettingsPage />} />
                </Route>
                <Route path="/email" element={<EmailPage />} />
                <Route path="/email/reports" element={<EmailReportsPage />} />
                <Route path="/templates" element={<TemplatesPage />} />
                <Route path="/campaigns" element={<CampaignsPage />} />
                <Route path="/notifications" element={<NotificationCenterPage />} />
                <Route path="/communication-analytics" element={<CommunicationAnalyticsPage />} />
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
                  <Route path="/email/settings" element={<EmailSettingsPage />} />
                </Route>

                {/* Lead Management Feature Guard */}
                <Route element={<FeatureGuardRoute featureCode="LEAD_MANAGEMENT" />}>
                  <Route path="/leads" element={<LeadsPage />} />
                  <Route path="/leads/reports" element={<LeadReportsPage />} />

                  {/* OrgAdmin & Manager only */}
                  <Route element={<ProtectedRoute allowedRoles={['OrgAdmin', 'Manager']} />}>
                    <Route path="/leads/automation" element={<LeadAutomationPage />} />
                    <Route path="/companies" element={<CompaniesPage />} />
                    <Route path="/companies/reports" element={<CompanyReportsPage />} />
                    <Route path="/contacts" element={<ContactsPage />} />
                    <Route path="/contacts/reports" element={<ContactReportsPage />} />
                    <Route path="/customers" element={<CustomersPage />} />
                    <Route path="/customers/reports" element={<CustomerReportsPage />} />
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

              {/* Billing & Account routes (OrgAdmin only) — intentionally OUTSIDE
                  SubscriptionGateRoute so a lapsed tenant can still reactivate. */}
              <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
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
