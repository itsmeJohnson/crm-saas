import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { AuthLayout } from './layouts/AuthLayout';
import { AppLayout } from './layouts/AppLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Login } from './modules/auth/Login';
import { Register } from './modules/auth/Register';
import { LegalPage } from './pages/legal/LegalPage';
import { Home } from './modules/dashboard/Home';
import { Profile } from './modules/organization/Profile';
import { UsersPage } from './pages/UsersPage';
import { SettingsLayout, SettingsHome } from './pages/settings/SettingsLayout';
import { SettingsCallingPage } from './pages/settings/SettingsCallingPage';
import { IntegrationMarketplacePage } from './pages/settings/IntegrationMarketplacePage';
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
import { DepartmentsPage } from './pages/DepartmentsPage';
import { TeamsPage } from './pages/TeamsPage';
import { RolesPermissionsPage } from './pages/RolesPermissionsPage';
import { BranchTerritoryPage } from './pages/BranchTerritoryPage';
import { AttendancePage } from './pages/AttendancePage';
import { LeavePage } from './pages/LeavePage';
import { ShiftManagementPage } from './pages/ShiftManagementPage';
import { PerformancePage } from './pages/PerformancePage';
import { TargetsPage } from './pages/TargetsPage';
import { ApprovalsPage } from './pages/ApprovalsPage';
import { OrganizationAnalyticsPage } from './pages/OrganizationAnalyticsPage';
import { AutomationAnalyticsPage } from './pages/AutomationAnalyticsPage';
import { ExecutiveDashboardPage } from './pages/ExecutiveDashboardPage';
import { ReportBuilderPage } from './pages/ReportBuilderPage';
import { SalesAnalyticsPage } from './pages/SalesAnalyticsPage';
import { EmployeeAnalyticsPage } from './pages/EmployeeAnalyticsPage';
import { FinancialAnalyticsPage } from './pages/FinancialAnalyticsPage';
import { ForecastingPage } from './pages/ForecastingPage';
import { KpiPage } from './pages/KpiPage';
import { OkrPage } from './pages/OkrPage';
import { VisualizationPage } from './pages/VisualizationPage';
import { ScheduledReportsPage } from './pages/ScheduledReportsPage';
import { BiExportPage } from './pages/BiExportPage';
import { HistoricalAnalyticsPage } from './pages/HistoricalAnalyticsPage';
import { CompliancePage } from './pages/CompliancePage';
import { PredictivePage } from './pages/PredictivePage';
import { AiPlatformPage } from './pages/AiPlatformPage';
import { CopilotPage } from './pages/CopilotPage';
import { LeadIntelligencePage } from './pages/LeadIntelligencePage';
import { CommIntelligencePage } from './pages/CommIntelligencePage';
import { SalesIntelligencePage } from './pages/SalesIntelligencePage';
import { KnowledgeBasePage } from './pages/KnowledgeBasePage';
import { DocumentIntelligencePage } from './pages/DocumentIntelligencePage';
import { PredictionEnginePage } from './pages/PredictionEnginePage';
import { PromptStudioPage } from './pages/PromptStudioPage';
import { AiGovernancePage } from './pages/AiGovernancePage';
import { AiDeveloperPage } from './pages/AiDeveloperPage';
import { IntegrationsPage } from './pages/IntegrationsPage';
import { AiAnalyticsPage } from './pages/AiAnalyticsPage';
import { RecommendationsPage } from './pages/RecommendationsPage';
import { WorkflowAssistantPage } from './pages/WorkflowAssistantPage';
import { WorkflowsPage } from './pages/WorkflowsPage';
import { RulesPage } from './pages/RulesPage';
import { AutomationPage } from './pages/AutomationPage';
import { EventsPage } from './pages/EventsPage';
import { QueuePage } from './pages/QueuePage';
import { SchedulerPage } from './pages/SchedulerPage';
import { NotificationAutomationPage } from './pages/NotificationAutomationPage';
import { SLAPage } from './pages/SLAPage';
import { EscalationPage } from './pages/EscalationPage';
import { PipelineSettings } from './components/admin/PipelineSettings';
import { TenantsPage } from './pages/TenantsPage';
import { TrialRequestsPage } from './pages/TrialRequestsPage';
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

// Dental Practice Modules
import { PatientsPage } from './pages/dental/PatientsPage';
import { AppointmentsPage } from './pages/dental/AppointmentsPage';
import { TreatmentsPage } from './pages/dental/TreatmentsPage';
import { BillingPage } from './pages/dental/BillingPage';
import { FollowupsPage } from './pages/dental/FollowupsPage';
import { DoctorsPage } from './pages/dental/DoctorsPage';
import { StaffPage } from './pages/dental/StaffPage';
import { DentalReportsPage } from './pages/dental/DentalReportsPage';
import { MarketingPage } from './pages/dental/MarketingPage';
import { LeadCapturePage } from './pages/dental/LeadCapturePage';
import { InvoiceSettingsPage } from './pages/dental/InvoiceSettingsPage';
import { TreatmentCatalogPage } from './pages/dental/TreatmentCatalogPage';
import { DentalSettingsPage } from './pages/dental/DentalSettingsPage';

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

          {/* Public legal pages (no auth) */}
          <Route path="/legal/:doc" element={<LegalPage />} />
          <Route path="/legal" element={<LegalPage />} />

          {/* Protected Routes — single shared shell (AppLayout) for the whole app */}
          <Route element={<ProtectedRoute />}>
            <Route element={<AppLayout />}>

              {/* Operational workspace routes: blocked by SubscriptionGate once a
                  tenant's plan lapses (the billing routes below stay reachable so
                  an OrgAdmin can reactivate). */}
              <Route element={<SubscriptionGateRoute />}>
                <Route path="/" element={<Home />} />

                {/* Dental Clinical Practice Routes */}
                <Route path="/patients" element={<PatientsPage />} />
                <Route path="/appointments" element={<AppointmentsPage />} />
                <Route path="/treatments" element={<TreatmentsPage />} />
                <Route path="/treatments/master" element={<TreatmentCatalogPage />} />
                <Route path="/billing" element={<BillingPage />} />
                <Route path="/billing/settings" element={<InvoiceSettingsPage />} />
                <Route path="/follow-ups" element={<FollowupsPage />} />
                <Route path="/doctors" element={<DoctorsPage />} />
                <Route path="/staff" element={<StaffPage />} />
                <Route path="/reports" element={<DentalReportsPage />} />
                <Route path="/marketing" element={<MarketingPage />} />
                <Route element={<FeatureGuardRoute featureCode="LEAD_CAPTURE" />}>
                  <Route path="/lead-capture" element={<LeadCapturePage />} />
                </Route>

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
                {/* Settings module — SuperAdmin / OrgAdmin only (backend also enforces). */}
                <Route element={<ProtectedRoute allowedRoles={['SuperAdmin', 'OrgAdmin']} />}>
                  <Route path="/settings" element={<SettingsLayout />}>
                    <Route index element={<SettingsHome />} />
                    <Route path="integrations" element={<IntegrationMarketplacePage />} />
                    <Route path="calling" element={<SettingsCallingPage />} />
                  </Route>
                </Route>
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin', 'Manager']} />}>
                  <Route path="/departments" element={<DepartmentsPage />} />
                </Route>
                {/* Teams: all authenticated roles (visibility is scoped server-side) */}
                <Route path="/teams" element={<TeamsPage />} />
                {/* Attendance: all authenticated roles (self clock; managers see their team) */}
                <Route path="/attendance" element={<AttendancePage />} />
                {/* Leave: all authenticated roles (self apply; managers approve) */}
                <Route path="/leaves" element={<LeavePage />} />
                {/* Shifts: all authenticated roles (view own schedule; admin manages) */}
                <Route path="/shifts" element={<ShiftManagementPage />} />
                {/* Performance: all authenticated roles (own scorecard; managers set goals) */}
                <Route path="/performance" element={<PerformancePage />} />
                {/* Targets: unified cross-scope view (all roles; managers create) */}
                <Route path="/targets" element={<TargetsPage />} />
                {/* Approvals: generic multi-level approval workflow (all roles) */}
                <Route path="/approvals" element={<ApprovalsPage />} />
                {/* Organization Analytics: management-level (OrgAdmin/Manager) */}
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin', 'Manager']} />}>
                  <Route path="/org-analytics" element={<OrganizationAnalyticsPage />} />
                  <Route path="/executive-dashboard" element={<ExecutiveDashboardPage />} />
                  <Route path="/report-builder" element={<ReportBuilderPage />} />
                  <Route path="/sales-analytics" element={<SalesAnalyticsPage />} />
                  <Route path="/employee-analytics" element={<EmployeeAnalyticsPage />} />
                  <Route path="/financial-analytics" element={<FinancialAnalyticsPage />} />
                  <Route path="/forecasting" element={<ForecastingPage />} />
                  <Route path="/kpi" element={<KpiPage />} />
                  <Route path="/okr" element={<OkrPage />} />
                  <Route path="/visualizations" element={<VisualizationPage />} />
                  <Route path="/scheduled-reports" element={<ScheduledReportsPage />} />
                  <Route path="/bi" element={<BiExportPage />} />
                  <Route path="/historical-analytics" element={<HistoricalAnalyticsPage />} />
                  <Route path="/compliance" element={<CompliancePage />} />
                  <Route path="/predictive" element={<PredictivePage />} />
                  <Route path="/ai" element={<AiPlatformPage />} />
                  <Route path="/copilot" element={<CopilotPage />} />
                  <Route path="/lead-intelligence" element={<LeadIntelligencePage />} />
                  <Route path="/comm-intelligence" element={<CommIntelligencePage />} />
                  <Route path="/sales-intelligence" element={<SalesIntelligencePage />} />
                  <Route path="/knowledge" element={<KnowledgeBasePage />} />
                  <Route path="/document-intelligence" element={<DocumentIntelligencePage />} />
                  <Route path="/prediction-engine" element={<PredictionEnginePage />} />
                  <Route path="/prompt-studio" element={<PromptStudioPage />} />
                  <Route path="/ai-governance" element={<AiGovernancePage />} />
                  <Route path="/ai-analytics" element={<AiAnalyticsPage />} />
                  <Route path="/ai-developer" element={<AiDeveloperPage />} />
                  <Route path="/integrations" element={<IntegrationsPage />} />
                  <Route path="/recommendations" element={<RecommendationsPage />} />
                  <Route path="/workflow-assistant" element={<WorkflowAssistantPage />} />
                  <Route path="/automation-analytics" element={<AutomationAnalyticsPage />} />
                  <Route path="/workflows" element={<WorkflowsPage />} />
                  <Route path="/rules" element={<RulesPage />} />
                  <Route path="/automation" element={<AutomationPage />} />
                  <Route path="/events" element={<EventsPage />} />
                  <Route path="/queue" element={<QueuePage />} />
                  <Route path="/scheduler" element={<SchedulerPage />} />
                  <Route path="/notification-automation" element={<NotificationAutomationPage />} />
                  <Route path="/sla" element={<SLAPage />} />
                  <Route path="/escalation" element={<EscalationPage />} />
                </Route>
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin']} />}>
                  <Route path="/roles" element={<RolesPermissionsPage />} />
                </Route>
                {/* Branches & Territories: OrgAdmin/Manager (managers view, admins manage) */}
                <Route element={<ProtectedRoute allowedRoles={['OrgAdmin', 'Manager']} />}>
                  <Route path="/branches" element={<BranchTerritoryPage />} />
                </Route>
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
                  <Route path="/trial-requests" element={<TrialRequestsPage />} />
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
