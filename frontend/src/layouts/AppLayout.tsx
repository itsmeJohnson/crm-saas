import React, { useState } from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import {
  LayoutDashboard, LogOut, Building, Building2, Contact, Users, FolderKanban,
  Workflow, Sun, Moon, Menu, X, CreditCard, ChevronRight, ChevronDown,
  Gauge, Sparkles, FileText, Receipt, BarChart3, HardDrive, PhoneCall,
  UserCog, User, Landmark, Settings, LifeBuoy, Activity, Zap, HeartHandshake, ListChecks, CalendarDays, MessagesSquare, MessageSquare, MessageCircle, Mail, LayoutTemplate, Megaphone, Bell, Shield, UsersRound, MapPin, Clock, Plane, Trophy, Target, CheckCircle2, Filter, Cog, Radio, Layers, CalendarClock, BellRing, TrendingUp, Briefcase, BookOpen, ScanText, Wand2, Brain, ShieldCheck, Code2, Plug
} from 'lucide-react';
import { InboundCallPopup } from '../components/crm/InboundCallPopup';
import { NotificationBell } from '../components/notifications/NotificationBell';
import { useBrowserNotifications } from '../hooks/useBrowserNotifications';

export const AppLayout: React.FC = () => {
  const { user, organization, logout } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const navigate = useNavigate();
  // Pop reminders/follow-ups as desktop notifications while the app is open.
  useBrowserNotifications(!!user);
  const location = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // TRIAL_MODE hides non-essential features for trial tenants (Lean CRM set).
  // SuperAdmin (the platform owner) always sees the full product. Flip to false
  // to expose every feature to all roles.
  const TRIAL_MODE = true;

  // Order in which nav groups render.
  const NAV_GROUPS = [
    'Overview', 'Platform', 'CRM', 'Communications', 'Productivity',
    'Workforce', 'Analytics', 'Automation', 'AI Suite', 'Administration',
  ];

  const allNavItems = [
    // ── Overview ───────────────────────────────────────────────────────────
    { name: 'Dashboard',         path: '/',                  icon: LayoutDashboard,  section: 'workspace', group: 'Overview', trial: true },
    { name: 'Executive Dashboard', path: '/executive-dashboard', icon: Gauge,          roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Overview' },
    { name: 'Org Analytics',     path: '/org-analytics',     icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Overview' },

    // ── Platform (SuperAdmin) ──────────────────────────────────────────────
    { name: 'Tenants',           path: '/tenants',           icon: Building,         roles: ['SuperAdmin'], section: 'workspace', group: 'Platform', trial: true },
    { name: 'Trial Requests',    path: '/trial-requests',    icon: Clock,            roles: ['SuperAdmin'], section: 'workspace', group: 'Platform', trial: true },

    // ── CRM ────────────────────────────────────────────────────────────────
    { name: 'Leads',             path: '/leads',             icon: FolderKanban,     featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Lead Reports',      path: '/leads/reports',     icon: BarChart3,         featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Lead Automation',   path: '/leads/automation',  icon: Zap,               roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM' },
    { name: 'Companies',         path: '/companies',         icon: Building2,         roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Company Reports',   path: '/companies/reports', icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Contacts',          path: '/contacts',          icon: Contact,           roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Contact Reports',   path: '/contacts/reports',  icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Customers',         path: '/customers',         icon: HeartHandshake,    roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Customer Reports',  path: '/customers/reports', icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Pipelines',         path: '/pipelines',         icon: Workflow,          roles: ['OrgAdmin'],  featureCode: 'SALES_PIPELINE', section: 'workspace', group: 'CRM', trial: true },
    { name: 'Lead Intelligence', path: '/lead-intelligence', icon: Sparkles,          roles: ['OrgAdmin', 'Manager', 'Employee'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace', group: 'CRM' },

    // ── Communications ─────────────────────────────────────────────────────
    { name: 'Communications',    path: '/communications',    icon: MessagesSquare,    section: 'workspace', group: 'Communications', trial: true },
    { name: 'Calling',           path: '/calling',           icon: PhoneCall,         section: 'workspace', group: 'Communications', trial: true },
    { name: 'Call Reports',      path: '/calling/reports',   icon: BarChart3,         section: 'workspace', group: 'Communications', trial: true },
    { name: 'SMS',               path: '/sms',               icon: MessageSquare,     featureCode: 'SMS_MESSAGING', section: 'workspace', group: 'Communications', trial: true },
    { name: 'SMS Reports',       path: '/sms/reports',       icon: BarChart3,         featureCode: 'SMS_MESSAGING', section: 'workspace', group: 'Communications', trial: true },
    { name: 'WhatsApp',          path: '/whatsapp',          icon: MessageCircle,     featureCode: 'WHATSAPP_MESSAGING', section: 'workspace', group: 'Communications', trial: true },
    { name: 'WhatsApp Reports',  path: '/whatsapp/reports',  icon: BarChart3,         featureCode: 'WHATSAPP_MESSAGING', section: 'workspace', group: 'Communications', trial: true },
    { name: 'WhatsApp Settings', path: '/whatsapp/settings', icon: Settings,          roles: ['OrgAdmin'], featureCode: 'WHATSAPP_MESSAGING', section: 'workspace', group: 'Communications', trial: true },
    { name: 'Email',             path: '/email',             icon: Mail,              featureCode: 'EMAIL_MESSAGING', section: 'workspace', group: 'Communications', trial: true },
    { name: 'Email Reports',     path: '/email/reports',     icon: BarChart3,         featureCode: 'EMAIL_MESSAGING', section: 'workspace', group: 'Communications', trial: true },
    { name: 'Email Settings',    path: '/email/settings',    icon: Settings,          roles: ['OrgAdmin'], featureCode: 'EMAIL_MESSAGING', section: 'workspace', group: 'Communications', trial: true },
    { name: 'Templates',         path: '/templates',         icon: LayoutTemplate,    section: 'workspace', group: 'Communications', trial: true },
    { name: 'Campaigns',         path: '/campaigns',         icon: Megaphone,         featureCode: 'CAMPAIGN_MANAGEMENT', section: 'workspace', group: 'Communications', trial: true },
    { name: 'Comm Analytics',    path: '/communication-analytics', icon: BarChart3,   roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Communications' },
    { name: 'Comm Intelligence', path: '/comm-intelligence', icon: MessagesSquare,    roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Communications' },

    // ── Productivity ───────────────────────────────────────────────────────
    { name: 'Tasks',             path: '/tasks',             icon: ListChecks,        section: 'workspace', group: 'Productivity', trial: true },
    { name: 'Calendar',          path: '/calendar',          icon: CalendarDays,      section: 'workspace', group: 'Productivity', trial: true },
    { name: 'Notifications',     path: '/notifications',     icon: Bell,              section: 'workspace', group: 'Productivity', trial: true },

    // ── Workforce ──────────────────────────────────────────────────────────
    { name: 'Team Members',      path: '/users',             icon: Users,             roles: ['OrgAdmin', 'Manager'], featureCode: 'ROLE_BASED_ACCESS', section: 'workspace', group: 'Workforce', trial: true },
    { name: 'Teams',             path: '/teams',             icon: UsersRound,        roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Workforce', trial: true },
    { name: 'Attendance',        path: '/attendance',        icon: Clock,             roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Workforce', trial: true },
    { name: 'Leave',             path: '/leaves',            icon: Plane,             roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Workforce', trial: true },
    { name: 'Shifts',            path: '/shifts',            icon: Clock,             roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Workforce', trial: true },
    { name: 'Performance',       path: '/performance',       icon: Trophy,            roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Workforce' },
    { name: 'Targets',           path: '/targets',           icon: Target,            roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Workforce' },
    { name: 'Goals & OKRs',      path: '/okr',               icon: Target,            roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Workforce' },
    { name: 'Approvals',         path: '/approvals',         icon: CheckCircle2,      roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'Workforce' },

    // ── Analytics (advanced) ───────────────────────────────────────────────
    { name: 'Report Builder',    path: '/report-builder',    icon: FileText,          roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Sales Analytics',   path: '/sales-analytics',   icon: TrendingUp,        roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Employee Analytics', path: '/employee-analytics', icon: UserCog,          roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Financial Analytics', path: '/financial-analytics', icon: Landmark,        roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Forecasting',       path: '/forecasting',       icon: TrendingUp,        roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'KPI Engine',        path: '/kpi',               icon: Gauge,             roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Visualizations',    path: '/visualizations',    icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Scheduled Reports', path: '/scheduled-reports', icon: CalendarClock,     roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Export & BI',       path: '/bi',                icon: HardDrive,         roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Historical Analytics', path: '/historical-analytics', icon: Clock,       roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Predictive Analytics', path: '/predictive',      icon: Sparkles,          roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },
    { name: 'Sales Intelligence', path: '/sales-intelligence', icon: Briefcase,        roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Analytics' },

    // ── Automation ─────────────────────────────────────────────────────────
    { name: 'Workflows',         path: '/workflows',         icon: Workflow,          roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'Rule Engine',       path: '/rules',             icon: Filter,            roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'Automation',        path: '/automation',        icon: Cog,               roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'Automation Analytics', path: '/automation-analytics', icon: Activity,      roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'Event Bus',         path: '/events',            icon: Radio,             roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'Background Queue',  path: '/queue',             icon: Layers,            roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'Scheduler',         path: '/scheduler',         icon: CalendarClock,     roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'Notification Rules', path: '/notification-automation', icon: BellRing,     roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'SLA Management',     path: '/sla',               icon: Gauge,             roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },
    { name: 'Escalation',        path: '/escalation',        icon: TrendingUp,        roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Automation' },

    // ── AI Suite ───────────────────────────────────────────────────────────
    { name: 'AI Platform',       path: '/ai',                icon: Zap,               roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'AI Suite' },
    { name: 'CRM Copilot',       path: '/copilot',           icon: Sparkles,          roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'AI Suite' },
    { name: 'Knowledge Base',    path: '/knowledge',         icon: BookOpen,          roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'AI Suite' },
    { name: 'Document Intelligence', path: '/document-intelligence', icon: ScanText,  roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'AI Suite' },
    { name: 'Prediction Engine',  path: '/prediction-engine',   icon: Brain,             roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'AI Suite' },
    { name: 'Prompt Studio',      path: '/prompt-studio',       icon: Wand2,             roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'AI Suite' },
    { name: 'AI Governance',      path: '/ai-governance',       icon: ShieldCheck,       roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'AI Suite' },
    { name: 'AI Analytics',       path: '/ai-analytics',        icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'AI Suite' },
    { name: 'AI API & SDK',       path: '/ai-developer',        icon: Code2,             roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'AI Suite' },
    { name: 'Recommendations',   path: '/recommendations',    icon: Sparkles,          roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace', group: 'AI Suite' },
    { name: 'Workflow Assistant', path: '/workflow-assistant', icon: Wand2,           roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'AI Suite' },

    // ── Administration ─────────────────────────────────────────────────────
    { name: 'Settings',          path: '/settings',          icon: Settings,          roles: ['SuperAdmin', 'OrgAdmin'], section: 'workspace', group: 'Administration', trial: true },
    { name: 'Organization',      path: '/organization',      icon: Building,          roles: ['OrgAdmin'], section: 'workspace', group: 'Administration', trial: true },
    { name: 'Roles & Permissions', path: '/roles',           icon: Shield,            roles: ['OrgAdmin'], section: 'workspace', group: 'Administration' },
    { name: 'Branches',          path: '/branches',          icon: MapPin,            roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Administration' },
    { name: 'Departments',       path: '/departments',       icon: Building2,         roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Administration' },
    { name: 'Integration Hub',    path: '/integrations',        icon: Plug,              roles: ['OrgAdmin', 'Manager'], section: 'workspace', group: 'Administration' },
    { name: 'Audit & Compliance', path: '/compliance',        icon: Shield,            roles: ['OrgAdmin'], section: 'workspace', group: 'Administration' },

    // ── Billing & Account (OrgAdmin only) ─────────────────────────────────
    { name: 'Billing Overview',  path: '/portal/dashboard',  icon: Gauge,             roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Subscription',      path: '/portal/subscription', icon: CreditCard,      roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Plans',             path: '/portal/plans',      icon: Sparkles,          roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Invoices',          path: '/portal/invoices',   icon: FileText,          roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Payments',          path: '/portal/payments',   icon: Receipt,           roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Usage',             path: '/portal/usage',      icon: BarChart3,         roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Storage',           path: '/portal/storage',    icon: HardDrive,         roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Call Recordings',   path: '/portal/recordings', icon: PhoneCall,         roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Seat Licensing',    path: '/portal/users',      icon: UserCog,           roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Company Profile',   path: '/portal/profile',    icon: User,              roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Billing Details',   path: '/portal/billing',    icon: Landmark,          roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Preferences',       path: '/portal/settings',   icon: Settings,          roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Support',           path: '/portal/support',    icon: LifeBuoy,          roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Activity Logs',     path: '/portal/activity',   icon: Activity,          roles: ['OrgAdmin'], section: 'billing' },
  ];

  const features = useAuthStore((state) => state.features);

  const navItems = allNavItems.filter((item) => {
    if (!user) return false;

    if (item.roles) {
      const hasRole = item.roles.includes(user.role);
      const isTeamLeaderUsers = item.name === 'Team Members' && user.role === 'Employee' && user.is_team_leader;
      if (!hasRole && !isTeamLeaderUsers) return false;
    }

    if (item.featureCode && user.role !== 'SuperAdmin') {
      if (!features.includes(item.featureCode)) return false;
    }

    // Trial gating: hide non-essential features from tenant users. The platform
    // owner (SuperAdmin) always sees everything; billing is always available.
    if (TRIAL_MODE && user.role !== 'SuperAdmin' && item.section !== 'billing' && !(item as any).trial) {
      return false;
    }

    return true;
  });

  const billingItems = navItems.filter((item) => item.section === 'billing');

  // Group workspace items by their nav group, preserving NAV_GROUPS order.
  const groupedWorkspace = NAV_GROUPS
    .map((group) => ({
      group,
      items: navItems.filter((item) => item.section === 'workspace' && (item as any).group === group),
    }))
    .filter((g) => g.items.length > 0);

  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const toggleGroup = (group: string) =>
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      next.has(group) ? next.delete(group) : next.add(group);
      return next;
    });

  /* ── Avatar initials ── */
  const initials = [user?.first_name?.[0], user?.last_name?.[0]]
    .filter(Boolean)
    .join('')
    .toUpperCase() || '?';

  /* ── Role display label ── */
  const roleLabel: Record<string, string> = {
    SuperAdmin: 'Super Admin',
    OrgAdmin: 'Admin',
    Manager: 'Manager',
    Employee: user?.is_team_leader ? 'Team Leader' : 'Employee',
  };
  const displayRole = roleLabel[user?.role ?? ''] ?? user?.role ?? '';

  const sidebarContent = (
    <div className="flex flex-col h-full">

      {/* ── Logo ── */}
      <div className="flex items-center justify-between px-5 py-4 border-b border-slate-800/60">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white text-sm shadow-md shadow-brand-500/30 flex-shrink-0">
            C
          </div>
          <div>
            <span className="font-semibold text-sm tracking-tight text-slate-100 block leading-tight">
              CRM Enterprise
            </span>
            <span className="text-[10px] text-slate-500 font-medium tracking-wide">
              {organization?.name ?? 'Workspace'}
            </span>
          </div>
        </div>
        <button
          onClick={() => setIsMobileOpen(false)}
          className="md:hidden p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors cursor-pointer"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── Navigation ── */}
      <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-0.5">
        {groupedWorkspace.map(({ group, items }) => {
          const isCollapsed = collapsedGroups.has(group);
          const groupActive = items.some((item) =>
            location.pathname === item.path ||
            (item.path !== '/' && location.pathname.startsWith(item.path)));
          return (
            <div key={group} className="mb-0.5">
              <button
                onClick={() => toggleGroup(group)}
                className="w-full flex items-center justify-between px-3 pt-3 pb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500 hover:text-slate-300 transition-colors cursor-pointer"
              >
                <span className={groupActive ? 'text-brand-400' : ''}>{group}</span>
                <ChevronDown className={`w-3 h-3 transition-transform ${isCollapsed ? '-rotate-90' : ''}`} />
              </button>
              {!isCollapsed && items.map((item) => {
                const Icon = item.icon;
                const isActive = location.pathname === item.path ||
                  (item.path !== '/' && location.pathname.startsWith(item.path));
                return (
                  <Link
                    key={item.name}
                    to={item.path}
                    onClick={() => setIsMobileOpen(false)}
                    className={`crm-nav-item ${isActive ? 'crm-nav-item--active' : ''}`}
                  >
                    <Icon className="w-4 h-4 flex-shrink-0" />
                    <span>{item.name}</span>
                    {isActive && (
                      <ChevronRight className="w-3 h-3 ml-auto opacity-50" />
                    )}
                  </Link>
                );
              })}
            </div>
          );
        })}

        {billingItems.length > 0 && (
          <>
            <p className="px-3 pt-4 pb-1.5 text-[10px] font-bold uppercase tracking-wider text-slate-500">
              Billing &amp; Account
            </p>
            {billingItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path ||
                (item.path !== '/' && location.pathname.startsWith(item.path));
              return (
                <Link
                  key={item.name}
                  to={item.path}
                  onClick={() => setIsMobileOpen(false)}
                  className={`crm-nav-item ${isActive ? 'crm-nav-item--active' : ''}`}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span>{item.name}</span>
                  {isActive && (
                    <ChevronRight className="w-3 h-3 ml-auto opacity-50" />
                  )}
                </Link>
              );
            })}
          </>
        )}
      </nav>

      {/* ── User Profile & Footer ── */}
      <div className="px-3 py-4 border-t border-slate-800/60 space-y-2">
        {/* Theme toggle row */}
        <div className="flex items-center justify-between px-1 mb-3">
          <span className="text-xs text-slate-500">Appearance</span>
          <button
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-lg text-xs font-medium text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors cursor-pointer border border-slate-800/60"
          >
            {theme === 'dark' ? (
              <><Sun className="w-3.5 h-3.5 text-amber-400" /><span>Light</span></>
            ) : (
              <><Moon className="w-3.5 h-3.5 text-indigo-400" /><span>Dark</span></>
            )}
          </button>
        </div>

        {/* User card */}
        <div className="flex items-center gap-3 px-2 py-2.5 rounded-xl bg-slate-900/50 border border-slate-800/60">
          {/* Avatar */}
          <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500/80 to-indigo-500/80 flex items-center justify-center text-white text-xs font-bold flex-shrink-0">
            {initials}
          </div>
          <div className="overflow-hidden flex-1 min-w-0">
            <p className="text-sm font-semibold text-slate-200 truncate leading-tight">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-[11px] text-slate-500 truncate leading-tight mt-0.5">
              {user?.email}
            </p>
          </div>
          <span className="flex-shrink-0 inline-flex items-center px-1.5 py-0.5 text-[9px] font-bold uppercase tracking-wider rounded-md bg-brand-500/15 text-brand-400 border border-brand-500/25">
            {displayRole}
          </span>
        </div>

        {/* Sign out */}
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-3 py-2.5 rounded-xl text-xs font-semibold text-slate-500 hover:text-red-400 hover:bg-red-500/8 transition-all cursor-pointer border border-transparent hover:border-red-500/15"
        >
          <LogOut className="w-3.5 h-3.5" />
          Sign Out
        </button>
      </div>
    </div>
  );

  // The Tenants console renders its OWN "Control Center" sidebar, so it gets a
  // single-column fullscreen shell (no global CRM sidebar) to avoid stacking
  // two sidebars. Other platform pages (e.g. Trial Requests) have no sidebar of
  // their own, so they keep the normal AppLayout shell and its navigation.
  const PLATFORM_PREFIXES = ['/tenants'];
  const isPlatformConsole = PLATFORM_PREFIXES.some(
    (p) => location.pathname === p || location.pathname.startsWith(p + '/'),
  );

  if (isPlatformConsole) {
    return (
      <div className="flex flex-col h-screen overflow-hidden" style={{ backgroundColor: 'var(--bg-app)', color: 'var(--text-primary)' }}>
        <InboundCallPopup />
        <header className="flex items-center gap-3 px-4 py-2.5 border-b border-slate-800/60 z-20" style={{ backgroundColor: 'var(--bg-surface)' }}>
          <div className="flex items-center gap-2.5 min-w-0">
            <div className="w-8 h-8 bg-gradient-to-br from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white text-sm flex-shrink-0">C</div>
            <span className="font-semibold text-sm text-slate-100 truncate">CRM Enterprise</span>
            <span className="hidden sm:inline text-[10px] text-slate-500 truncate">{organization?.name}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={toggleTheme}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              className="p-1.5 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 border border-slate-800/60 transition-colors cursor-pointer"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />}
            </button>
            <NotificationBell />
            <button
              onClick={handleLogout}
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs font-semibold text-slate-500 hover:text-red-400 hover:bg-red-500/8 border border-transparent hover:border-red-500/15 transition-all cursor-pointer"
            >
              <LogOut className="w-3.5 h-3.5" /> <span className="hidden sm:inline">Sign Out</span>
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto" style={{ backgroundColor: 'var(--bg-app)' }}>
          <div className="p-4 md:p-6 min-h-full">
            <Outlet />
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden flex-col md:flex-row" style={{ backgroundColor: 'var(--bg-app)', color: 'var(--text-primary)' }}>
      <InboundCallPopup />

      {/* ── Desktop Sidebar ── */}
      <aside className="hidden md:flex md:w-56 crm-sidebar flex-col z-20 flex-shrink-0">
        {sidebarContent}
      </aside>

      {/* ── Mobile Drawer ── */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-30 md:hidden flex">
          <div
            className="absolute inset-0 bg-black/50 backdrop-blur-sm"
            onClick={() => setIsMobileOpen(false)}
          />
          <aside className="relative w-56 max-w-xs crm-sidebar shadow-2xl flex flex-col h-full z-10">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* ── Main Workspace ── */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Mobile Top Bar */}
        <header className="md:hidden flex items-center justify-between px-5 py-3.5 border-b border-slate-800/60 z-20" style={{ backgroundColor: 'var(--bg-surface)' }}>
          <div className="flex items-center gap-2.5">
            <div className="w-7 h-7 bg-gradient-to-br from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white text-xs shadow">
              C
            </div>
            <span className="font-semibold text-sm text-slate-100">CRM Enterprise</span>
          </div>
          <div className="flex items-center gap-1">
            <NotificationBell />
            <button
              onClick={() => setIsMobileOpen(true)}
              className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors cursor-pointer"
            >
              <Menu className="w-5 h-5" />
            </button>
          </div>
        </header>

        {/* Persistent Top Bar (desktop only — mobile gets the bell in its own top bar above) */}
        <header className="hidden md:flex items-center justify-end px-6 py-2.5 border-b border-slate-800/60 z-20" style={{ backgroundColor: 'var(--bg-surface)' }}>
          <NotificationBell />
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto" style={{ backgroundColor: 'var(--bg-app)' }}>
          <div className="p-4 md:p-6 min-h-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
