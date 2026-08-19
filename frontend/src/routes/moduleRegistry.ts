import React, { lazy } from 'react';
import {
  LayoutDashboard, FolderKanban, Users, CalendarDays, Activity, Receipt, Clock,
  MessagesSquare, ListChecks, MessageCircle, PhoneCall, Stethoscope, UsersRound,
  GitBranch, BarChart3, Megaphone, Webhook, Settings, Building, Gauge
} from 'lucide-react';

// Lazy-loaded workspace components
const Home = lazy(() => import('../modules/dashboard/Home').then(m => ({ default: m.Home })));
const Profile = lazy(() => import('../modules/organization/Profile').then(m => ({ default: m.Profile })));
const UsersPage = lazy(() => import('../pages/UsersPage').then(m => ({ default: m.UsersPage })));
const SettingsLayout = lazy(() => import('../pages/settings/SettingsLayout').then(m => ({ default: m.SettingsLayout })));
const SettingsHome = lazy(() => import('../pages/settings/SettingsLayout').then(m => ({ default: m.SettingsHome })));
const SettingsCallingPage = lazy(() => import('../pages/settings/SettingsCallingPage').then(m => ({ default: m.SettingsCallingPage })));
const IntegrationMarketplacePage = lazy(() => import('../pages/settings/IntegrationMarketplacePage').then(m => ({ default: m.IntegrationMarketplacePage })));
const LeadsPage = lazy(() => import('../pages/LeadsPage').then(m => ({ default: m.LeadsPage })));
const LeadReportsPage = lazy(() => import('../pages/LeadReportsPage').then(m => ({ default: m.LeadReportsPage })));
const LeadAutomationPage = lazy(() => import('../pages/LeadAutomationPage').then(m => ({ default: m.LeadAutomationPage })));
const CompaniesPage = lazy(() => import('../pages/CompaniesPage').then(m => ({ default: m.CompaniesPage })));
const ContactsPage = lazy(() => import('../pages/ContactsPage').then(m => ({ default: m.ContactsPage })));
const ContactReportsPage = lazy(() => import('../pages/ContactReportsPage').then(m => ({ default: m.ContactReportsPage })));
const CompanyReportsPage = lazy(() => import('../pages/CompanyReportsPage').then(m => ({ default: m.CompanyReportsPage })));
const CustomersPage = lazy(() => import('../pages/CustomersPage').then(m => ({ default: m.CustomersPage })));
const CustomerReportsPage = lazy(() => import('../pages/CustomerReportsPage').then(m => ({ default: m.CustomerReportsPage })));
const TasksPage = lazy(() => import('../pages/TasksPage').then(m => ({ default: m.TasksPage })));
const TaskReportsPage = lazy(() => import('../pages/TaskReportsPage').then(m => ({ default: m.TaskReportsPage })));
const CalendarPage = lazy(() => import('../pages/CalendarPage').then(m => ({ default: m.CalendarPage })));
const CommunicationCenterPage = lazy(() => import('../pages/CommunicationCenterPage').then(m => ({ default: m.CommunicationCenterPage })));
const CallingPage = lazy(() => import('../pages/CallingPage').then(m => ({ default: m.CallingPage })));
const CallingReportsPage = lazy(() => import('../pages/CallingReportsPage').then(m => ({ default: m.CallingReportsPage })));
const SmsPage = lazy(() => import('../pages/SmsPage').then(m => ({ default: m.SmsPage })));
const SmsReportsPage = lazy(() => import('../pages/SmsReportsPage').then(m => ({ default: m.SmsReportsPage })));
const WhatsAppPage = lazy(() => import('../pages/WhatsAppPage').then(m => ({ default: m.WhatsAppPage })));
const WhatsAppSettingsPage = lazy(() => import('../pages/WhatsAppSettingsPage').then(m => ({ default: m.WhatsAppSettingsPage })));
const WhatsAppReportsPage = lazy(() => import('../pages/WhatsAppReportsPage').then(m => ({ default: m.WhatsAppReportsPage })));
const EmailPage = lazy(() => import('../pages/EmailPage').then(m => ({ default: m.EmailPage })));
const EmailSettingsPage = lazy(() => import('../pages/EmailSettingsPage').then(m => ({ default: m.EmailSettingsPage })));
const EmailReportsPage = lazy(() => import('../pages/EmailReportsPage').then(m => ({ default: m.EmailReportsPage })));
const TemplatesPage = lazy(() => import('../pages/TemplatesPage').then(m => ({ default: m.TemplatesPage })));
const CampaignsPage = lazy(() => import('../pages/CampaignsPage').then(m => ({ default: m.CampaignsPage })));
const NotificationCenterPage = lazy(() => import('../pages/NotificationCenterPage').then(m => ({ default: m.NotificationCenterPage })));
const CommunicationAnalyticsPage = lazy(() => import('../pages/CommunicationAnalyticsPage').then(m => ({ default: m.CommunicationAnalyticsPage })));
const DepartmentsPage = lazy(() => import('../pages/DepartmentsPage').then(m => ({ default: m.DepartmentsPage })));
const TeamsPage = lazy(() => import('../pages/TeamsPage').then(m => ({ default: m.TeamsPage })));
const RolesPermissionsPage = lazy(() => import('../pages/RolesPermissionsPage').then(m => ({ default: m.RolesPermissionsPage })));
const BranchTerritoryPage = lazy(() => import('../pages/BranchTerritoryPage').then(m => ({ default: m.BranchTerritoryPage })));
const AttendancePage = lazy(() => import('../pages/AttendancePage').then(m => ({ default: m.AttendancePage })));
const LeavePage = lazy(() => import('../pages/LeavePage').then(m => ({ default: m.LeavePage })));
const ShiftManagementPage = lazy(() => import('../pages/ShiftManagementPage').then(m => ({ default: m.ShiftManagementPage })));
const PerformancePage = lazy(() => import('../pages/PerformancePage').then(m => ({ default: m.PerformancePage })));
const TargetsPage = lazy(() => import('../pages/TargetsPage').then(m => ({ default: m.TargetsPage })));
const ApprovalsPage = lazy(() => import('../pages/ApprovalsPage').then(m => ({ default: m.ApprovalsPage })));
const OrganizationAnalyticsPage = lazy(() => import('../pages/OrganizationAnalyticsPage').then(m => ({ default: m.OrganizationAnalyticsPage })));
const AutomationAnalyticsPage = lazy(() => import('../pages/AutomationAnalyticsPage').then(m => ({ default: m.AutomationAnalyticsPage })));
const ExecutiveDashboardPage = lazy(() => import('../pages/ExecutiveDashboardPage').then(m => ({ default: m.ExecutiveDashboardPage })));
const ReportBuilderPage = lazy(() => import('../pages/ReportBuilderPage').then(m => ({ default: m.ReportBuilderPage })));
const SalesAnalyticsPage = lazy(() => import('../pages/SalesAnalyticsPage').then(m => ({ default: m.SalesAnalyticsPage })));
const EmployeeAnalyticsPage = lazy(() => import('../pages/EmployeeAnalyticsPage').then(m => ({ default: m.EmployeeAnalyticsPage })));
const FinancialAnalyticsPage = lazy(() => import('../pages/FinancialAnalyticsPage').then(m => ({ default: m.FinancialAnalyticsPage })));
const ForecastingPage = lazy(() => import('../pages/ForecastingPage').then(m => ({ default: m.ForecastingPage })));
const KpiPage = lazy(() => import('../pages/KpiPage').then(m => ({ default: m.KpiPage })));
const OkrPage = lazy(() => import('../pages/OkrPage').then(m => ({ default: m.OkrPage })));
const VisualizationPage = lazy(() => import('../pages/VisualizationPage').then(m => ({ default: m.VisualizationPage })));
const ScheduledReportsPage = lazy(() => import('../pages/ScheduledReportsPage').then(m => ({ default: m.ScheduledReportsPage })));
const BiExportPage = lazy(() => import('../pages/BiExportPage').then(m => ({ default: m.BiExportPage })));
const HistoricalAnalyticsPage = lazy(() => import('../pages/HistoricalAnalyticsPage').then(m => ({ default: m.HistoricalAnalyticsPage })));
const CompliancePage = lazy(() => import('../pages/CompliancePage').then(m => ({ default: m.CompliancePage })));
const PredictivePage = lazy(() => import('../pages/PredictivePage').then(m => ({ default: m.PredictivePage })));
const AiPlatformPage = lazy(() => import('../pages/AiPlatformPage').then(m => ({ default: m.AiPlatformPage })));
const CopilotPage = lazy(() => import('../pages/CopilotPage').then(m => ({ default: m.CopilotPage })));
const LeadIntelligencePage = lazy(() => import('../pages/LeadIntelligencePage').then(m => ({ default: m.LeadIntelligencePage })));
const CommIntelligencePage = lazy(() => import('../pages/CommIntelligencePage').then(m => ({ default: m.CommIntelligencePage })));
const SalesIntelligencePage = lazy(() => import('../pages/SalesIntelligencePage').then(m => ({ default: m.SalesIntelligencePage })));
const KnowledgeBasePage = lazy(() => import('../pages/KnowledgeBasePage').then(m => ({ default: m.KnowledgeBasePage })));
const DocumentIntelligencePage = lazy(() => import('../pages/DocumentIntelligencePage').then(m => ({ default: m.DocumentIntelligencePage })));
const PredictionEnginePage = lazy(() => import('../pages/PredictionEnginePage').then(m => ({ default: m.PredictionEnginePage })));
const PromptStudioPage = lazy(() => import('../pages/PromptStudioPage').then(m => ({ default: m.PromptStudioPage })));
const AiGovernancePage = lazy(() => import('../pages/AiGovernancePage').then(m => ({ default: m.AiGovernancePage })));
const AiAnalyticsPage = lazy(() => import('../pages/AiAnalyticsPage').then(m => ({ default: m.AiAnalyticsPage })));
const AiDeveloperPage = lazy(() => import('../pages/AiDeveloperPage').then(m => ({ default: m.AiDeveloperPage })));
const IntegrationsPage = lazy(() => import('../pages/IntegrationsPage').then(m => ({ default: m.IntegrationsPage })));
const RecommendationsPage = lazy(() => import('../pages/RecommendationsPage').then(m => ({ default: m.RecommendationsPage })));
const WorkflowAssistantPage = lazy(() => import('../pages/WorkflowAssistantPage').then(m => ({ default: m.WorkflowAssistantPage })));
const WorkflowsPage = lazy(() => import('../pages/WorkflowsPage').then(m => ({ default: m.WorkflowsPage })));
const RulesPage = lazy(() => import('../pages/RulesPage').then(m => ({ default: m.RulesPage })));
const AutomationPage = lazy(() => import('../pages/AutomationPage').then(m => ({ default: m.AutomationPage })));
const EventsPage = lazy(() => import('../pages/EventsPage').then(m => ({ default: m.EventsPage })));
const QueuePage = lazy(() => import('../pages/QueuePage').then(m => ({ default: m.QueuePage })));
const SchedulerPage = lazy(() => import('../pages/SchedulerPage').then(m => ({ default: m.SchedulerPage })));
const NotificationAutomationPage = lazy(() => import('../pages/NotificationAutomationPage').then(m => ({ default: m.NotificationAutomationPage })));
const SLAPage = lazy(() => import('../pages/SLAPage').then(m => ({ default: m.SLAPage })));
const EscalationPage = lazy(() => import('../pages/EscalationPage').then(m => ({ default: m.EscalationPage })));
const PipelineSettings = lazy(() => import('../components/admin/PipelineSettings').then(m => ({ default: m.PipelineSettings })));
const TenantsPage = lazy(() => import('../pages/TenantsPage').then(m => ({ default: m.TenantsPage })));
const TrialRequestsPage = lazy(() => import('../pages/TrialRequestsPage').then(m => ({ default: m.TrialRequestsPage })));

// Lazy-loaded self-service portal components
const PortalDashboard = lazy(() => import('../pages/portal/PortalDashboard').then(m => ({ default: m.PortalDashboard })));
const PortalSubscription = lazy(() => import('../pages/portal/PortalSubscription').then(m => ({ default: m.PortalSubscription })));
const PortalPlans = lazy(() => import('../pages/portal/PortalPlans').then(m => ({ default: m.PortalPlans })));
const PortalInvoices = lazy(() => import('../pages/portal/PortalInvoices').then(m => ({ default: m.PortalInvoices })));
const PortalPayments = lazy(() => import('../pages/portal/PortalPayments').then(m => ({ default: m.PortalPayments })));
const PortalUsage = lazy(() => import('../pages/portal/PortalUsage').then(m => ({ default: m.PortalUsage })));
const PortalStorage = lazy(() => import('../pages/portal/PortalStorage').then(m => ({ default: m.PortalStorage })));
const PortalRecordings = lazy(() => import('../pages/portal/PortalRecordings').then(m => ({ default: m.PortalRecordings })));
const PortalUsers = lazy(() => import('../pages/portal/PortalUsers').then(m => ({ default: m.PortalUsers })));
const PortalProfile = lazy(() => import('../pages/portal/PortalProfile').then(m => ({ default: m.PortalProfile })));
const PortalBilling = lazy(() => import('../pages/portal/PortalBilling').then(m => ({ default: m.PortalBilling })));
const PortalSupport = lazy(() => import('../pages/portal/PortalSupport').then(m => ({ default: m.PortalSupport })));
const PortalActivityLogs = lazy(() => import('../pages/portal/PortalActivityLogs').then(m => ({ default: m.PortalActivityLogs })));
const PortalSettings = lazy(() => import('../pages/portal/PortalSettings').then(m => ({ default: m.PortalSettings })));

// Lazy-loaded dental components
const PatientsPage = lazy(() => import('../pages/dental/PatientsPage').then(m => ({ default: m.PatientsPage })));
const AppointmentsPage = lazy(() => import('../pages/dental/AppointmentsPage').then(m => ({ default: m.AppointmentsPage })));
const TreatmentsPage = lazy(() => import('../pages/dental/TreatmentsPage').then(m => ({ default: m.TreatmentsPage })));
const BillingPage = lazy(() => import('../pages/dental/BillingPage').then(m => ({ default: m.BillingPage })));
const FollowupsPage = lazy(() => import('../pages/dental/FollowupsPage').then(m => ({ default: m.FollowupsPage })));
const DoctorsPage = lazy(() => import('../pages/dental/DoctorsPage').then(m => ({ default: m.DoctorsPage })));
const StaffPage = lazy(() => import('../pages/dental/StaffPage').then(m => ({ default: m.StaffPage })));
const DentalReportsPage = lazy(() => import('../pages/dental/DentalReportsPage').then(m => ({ default: m.DentalReportsPage })));
const MarketingPage = lazy(() => import('../pages/dental/MarketingPage').then(m => ({ default: m.MarketingPage })));
const LeadCapturePage = lazy(() => import('../pages/dental/LeadCapturePage').then(m => ({ default: m.LeadCapturePage })));
const InvoiceSettingsPage = lazy(() => import('../pages/dental/InvoiceSettingsPage').then(m => ({ default: m.InvoiceSettingsPage })));
const TreatmentCatalogPage = lazy(() => import('../pages/dental/TreatmentCatalogPage').then(m => ({ default: m.TreatmentCatalogPage })));

export interface RouteDefinition {
  path: string;
  component: React.ComponentType<any>;
  roles?: string[];
  featureCode?: string;
  isNestedRouteContainer?: boolean;
  nestedRoutes?: { path: string; component: React.ComponentType<any>; index?: boolean }[];
  sidebar?: {
    name: string;
    icon?: any;
    group?: string;
  };
}

export interface ModuleDefinition {
  key: string;
  label: string;
  icon: any;
  group: string;
  section: 'workspace' | 'billing';
  trial?: boolean;
  routes: RouteDefinition[];
}

export const MODULES_REGISTRY: ModuleDefinition[] = [
  // ── CRM Core / Generic Modules ──
  {
    key: 'dashboard',
    label: 'Dashboard',
    icon: LayoutDashboard,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/', component: Home, sidebar: { name: 'Dashboard' } }]
  },
  {
    key: 'leads',
    label: 'Leads & Enquiries',
    icon: FolderKanban,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/leads', component: LeadsPage, featureCode: 'LEAD_MANAGEMENT', sidebar: { name: 'Leads & Enquiries' } },
      { path: '/leads/reports', component: LeadReportsPage, featureCode: 'LEAD_MANAGEMENT' },
      { path: '/leads/automation', component: LeadAutomationPage, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT' },
      { path: '/lead-capture', component: LeadCapturePage, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_CAPTURE', sidebar: { name: 'Lead Capture', icon: Webhook, group: 'Growth & Analytics' } }
    ]
  },
  {
    key: 'contacts',
    label: 'Contacts',
    icon: Users,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/contacts', component: ContactsPage, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', sidebar: { name: 'Patients Directory' } },
      { path: '/contacts/reports', component: ContactReportsPage, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT' }
    ]
  },
  {
    key: 'companies',
    label: 'Companies',
    icon: Building,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/companies', component: CompaniesPage, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT' },
      { path: '/companies/reports', component: CompanyReportsPage, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT' }
    ]
  },
  {
    key: 'customers',
    label: 'Customers',
    icon: Users,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/customers', component: CustomersPage, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT' },
      { path: '/customers/reports', component: CustomerReportsPage, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT' }
    ]
  },
  {
    key: 'opportunities',
    label: 'Opportunities & Pipelines',
    icon: GitBranch,
    group: 'Clinic Management',
    section: 'workspace',
    trial: true,
    routes: []
  },
  {
    key: 'pipelines',
    label: 'Pipelines',
    icon: GitBranch,
    group: 'Clinic Management',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/pipelines', component: PipelineSettings, roles: ['OrgAdmin'], featureCode: 'SALES_PIPELINE', sidebar: { name: 'Pipelines' } }]
  },
  {
    key: 'activities',
    label: 'Activities',
    icon: Clock,
    group: 'Patient Engagement',
    section: 'workspace',
    trial: true,
    routes: []
  },
  {
    key: 'tasks',
    label: 'Tasks & Reminders',
    icon: ListChecks,
    group: 'Patient Engagement',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/tasks', component: TasksPage, sidebar: { name: 'Tasks & Reminders' } },
      { path: '/tasks/reports', component: TaskReportsPage }
    ]
  },
  {
    key: 'follow_ups',
    label: 'Follow-ups & Recalls',
    icon: Clock,
    group: 'Patient Engagement',
    section: 'workspace',
    trial: true,
    routes: []
  },
  {
    key: 'communications',
    label: 'Communications',
    icon: MessagesSquare,
    group: 'Patient Engagement',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/communications', component: CommunicationCenterPage, sidebar: { name: 'Communications' } },
      { path: '/calling', component: CallingPage, sidebar: { name: 'Phone Calling', icon: PhoneCall } },
      { path: '/calling/reports', component: CallingReportsPage },
      { path: '/sms', component: SmsPage },
      { path: '/sms/reports', component: SmsReportsPage },
      { path: '/whatsapp', component: WhatsAppPage, sidebar: { name: 'WhatsApp Center', icon: MessageCircle } },
      { path: '/whatsapp/reports', component: WhatsAppReportsPage },
      { path: '/whatsapp/settings', component: WhatsAppSettingsPage, roles: ['OrgAdmin'] },
      { path: '/email', component: EmailPage },
      { path: '/email/reports', component: EmailReportsPage },
      { path: '/email/settings', component: EmailSettingsPage, roles: ['OrgAdmin'] },
      { path: '/templates', component: TemplatesPage },
      { path: '/campaigns', component: CampaignsPage },
      { path: '/notifications', component: NotificationCenterPage },
      { path: '/communication-analytics', component: CommunicationAnalyticsPage }
    ]
  },
  {
    key: 'billing',
    label: 'Billing & Invoices',
    icon: Receipt,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: []
  },
  {
    key: 'reports',
    label: 'Marketing ROI',
    icon: Megaphone,
    group: 'Growth & Analytics',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/marketing', component: MarketingPage, sidebar: { name: 'Marketing ROI' } }]
  },

  // ── Dental-Specific Industry Modules ──
  {
    key: 'patients',
    label: 'Patients Directory',
    icon: Users,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/patients', component: PatientsPage, sidebar: { name: 'Patients Directory' } }]
  },
  {
    key: 'appointments',
    label: 'Appointments',
    icon: CalendarDays,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/appointments', component: AppointmentsPage, sidebar: { name: 'Appointments' } },
      { path: '/calendar', component: CalendarPage }
    ]
  },
  {
    key: 'treatments',
    label: 'Treatment Master',
    icon: Stethoscope,
    group: 'Clinic Management',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/treatments/master', component: TreatmentCatalogPage, roles: ['OrgAdmin', 'Manager'], sidebar: { name: 'Treatment Master' } }]
  },
  {
    key: 'treatment_plans',
    label: 'Treatment Plans',
    icon: Activity,
    group: 'Clinical Operations',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/treatments', component: TreatmentsPage, sidebar: { name: 'Treatment Plans' } }]
  },
  {
    key: 'recall',
    label: 'Follow-ups & Recalls',
    icon: Clock,
    group: 'Patient Engagement',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/follow-ups', component: FollowupsPage, sidebar: { name: 'Follow-ups & Recalls' } }]
  },
  {
    key: 'dentists',
    label: 'Dentists & Surgeons',
    icon: Stethoscope,
    group: 'Clinic Management',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/doctors', component: DoctorsPage, sidebar: { name: 'Dentists & Surgeons' } }]
  },
  {
    key: 'clinical_reports',
    label: 'Clinical Reports',
    icon: BarChart3,
    group: 'Growth & Analytics',
    section: 'workspace',
    trial: true,
    routes: [{ path: '/reports', component: DentalReportsPage, sidebar: { name: 'Clinical Reports' } }]
  },

  // ── General Administrative / Core Workspace Features (Always Active / under dashboard module) ──
  {
    key: 'admin_core',
    label: 'Workspace Management',
    icon: Settings,
    group: 'Administration',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/staff', component: StaffPage, sidebar: { name: 'Staff & Team', group: 'Clinic Management', icon: UsersRound } },
      { path: '/settings', component: SettingsLayout, roles: ['SuperAdmin', 'OrgAdmin'], isNestedRouteContainer: true, sidebar: { name: 'Clinic Settings', group: 'Administration', icon: Settings }, nestedRoutes: [
        { path: '', component: SettingsHome, index: true },
        { path: 'integrations', component: IntegrationMarketplacePage },
        { path: 'calling', component: SettingsCallingPage }
      ]},
      { path: '/departments', component: DepartmentsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/teams', component: TeamsPage },
      { path: '/users', component: UsersPage, roles: ['OrgAdmin', 'Manager'], featureCode: 'ROLE_BASED_ACCESS' },
      { path: '/attendance', component: AttendancePage },
      { path: '/leaves', component: LeavePage },
      { path: '/shifts', component: ShiftManagementPage },
      { path: '/performance', component: PerformancePage },
      { path: '/targets', component: TargetsPage },
      { path: '/approvals', component: ApprovalsPage },
      { path: '/roles', component: RolesPermissionsPage, roles: ['OrgAdmin'] },
      { path: '/organization', component: Profile, roles: ['OrgAdmin'], sidebar: { name: 'Organization', icon: Building, group: 'Administration' } },
      { path: '/branches', component: BranchTerritoryPage, roles: ['OrgAdmin', 'Manager'] },
      // Billing Operations
      { path: '/billing', component: BillingPage, sidebar: { name: 'Billing & Invoices', group: 'Clinical Operations', icon: Receipt } },
      { path: '/billing/settings', component: InvoiceSettingsPage, roles: ['OrgAdmin', 'Manager'] }
    ]
  },
  {
    key: 'analytics_suite',
    label: 'Analytics Suite',
    icon: BarChart3,
    group: 'Growth & Analytics',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/org-analytics', component: OrganizationAnalyticsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/executive-dashboard', component: ExecutiveDashboardPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/report-builder', component: ReportBuilderPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/sales-analytics', component: SalesAnalyticsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/employee-analytics', component: EmployeeAnalyticsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/financial-analytics', component: FinancialAnalyticsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/forecasting', component: ForecastingPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/kpi', component: KpiPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/okr', component: OkrPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/visualizations', component: VisualizationPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/scheduled-reports', component: ScheduledReportsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/bi', component: BiExportPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/historical-analytics', component: HistoricalAnalyticsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/compliance', component: CompliancePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/predictive', component: PredictivePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/ai', component: AiPlatformPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/copilot', component: CopilotPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/lead-intelligence', component: LeadIntelligencePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/comm-intelligence', component: CommIntelligencePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/sales-intelligence', component: SalesIntelligencePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/knowledge', component: KnowledgeBasePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/document-intelligence', component: DocumentIntelligencePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/prediction-engine', component: PredictionEnginePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/prompt-studio', component: PromptStudioPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/ai-governance', component: AiGovernancePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/ai-analytics', component: AiAnalyticsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/ai-developer', component: AiDeveloperPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/integrations', component: IntegrationsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/recommendations', component: RecommendationsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/workflow-assistant', component: WorkflowAssistantPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/automation-analytics', component: AutomationAnalyticsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/workflows', component: WorkflowsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/rules', component: RulesPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/automation', component: AutomationPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/events', component: EventsPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/queue', component: QueuePage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/scheduler', component: SchedulerPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/notification-automation', component: NotificationAutomationPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/sla', component: SLAPage, roles: ['OrgAdmin', 'Manager'] },
      { path: '/escalation', component: EscalationPage, roles: ['OrgAdmin', 'Manager'] }
    ]
  },
  {
    key: 'platform_core',
    label: 'Platform Administration',
    icon: Building,
    group: 'Platform',
    section: 'workspace',
    trial: true,
    routes: [
      { path: '/tenants', component: TenantsPage, roles: ['SuperAdmin'], sidebar: { name: 'Tenants' } },
      { path: '/trial-requests', component: TrialRequestsPage, roles: ['SuperAdmin'], sidebar: { name: 'Trial Requests' } }
    ]
  },

  // ── Unified Self Service Portal Modules (Billing & Account Section) ──
  {
    key: 'billing',
    label: 'Billing Overview',
    icon: Gauge,
    group: 'Billing & Account',
    section: 'billing',
    routes: [
      { path: '/portal/dashboard', component: PortalDashboard, roles: ['OrgAdmin'], sidebar: { name: 'Billing Overview' } },
      { path: '/portal/subscription', component: PortalSubscription, roles: ['OrgAdmin'], sidebar: { name: 'Subscription' } },
      { path: '/portal/plans', component: PortalPlans, roles: ['OrgAdmin'], sidebar: { name: 'Plans' } },
      { path: '/portal/invoices', component: PortalInvoices, roles: ['OrgAdmin'], sidebar: { name: 'Invoices' } },
      { path: '/portal/payments', component: PortalPayments, roles: ['OrgAdmin'], sidebar: { name: 'Payments' } },
      { path: '/portal/usage', component: PortalUsage, roles: ['OrgAdmin'], sidebar: { name: 'Usage' } },
      { path: '/portal/storage', component: PortalStorage, roles: ['OrgAdmin'], sidebar: { name: 'Storage' } },
      { path: '/portal/recordings', component: PortalRecordings, roles: ['OrgAdmin'] },
      { path: '/portal/users', component: PortalUsers, roles: ['OrgAdmin'], sidebar: { name: 'Seat Licensing' } },
      { path: '/portal/profile', component: PortalProfile, roles: ['OrgAdmin'] },
      { path: '/portal/billing', component: PortalBilling, roles: ['OrgAdmin'] },
      { path: '/portal/support', component: PortalSupport, roles: ['OrgAdmin'] },
      { path: '/portal/activity', component: PortalActivityLogs, roles: ['OrgAdmin'] },
      { path: '/portal/settings', component: PortalSettings, roles: ['OrgAdmin'] }
    ]
  }
];
