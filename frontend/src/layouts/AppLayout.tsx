import React, { useState } from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import {
  LayoutDashboard, LogOut, Building, Building2, Contact, Users, FolderKanban,
  Workflow, Sun, Moon, Menu, X, CreditCard, ChevronRight,
  Gauge, Sparkles, FileText, Receipt, BarChart3, HardDrive, PhoneCall,
  UserCog, User, Landmark, Settings, LifeBuoy, Activity, Zap, HeartHandshake, ListChecks, CalendarDays, MessagesSquare, MessageSquare, MessageCircle, Mail, LayoutTemplate, Megaphone, Bell, Shield, UsersRound, MapPin, Clock, Plane
} from 'lucide-react';
import { InboundCallPopup } from '../components/crm/InboundCallPopup';
import { NotificationBell } from '../components/notifications/NotificationBell';

export const AppLayout: React.FC = () => {
  const { user, organization, logout } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const allNavItems = [
    // ── Workspace ──────────────────────────────────────────────────────────
    { name: 'Dashboard',         path: '/',                  icon: LayoutDashboard,  section: 'workspace' },
    { name: 'Tenants',           path: '/tenants',           icon: Building,         roles: ['SuperAdmin'], section: 'workspace' },
    { name: 'Tasks',             path: '/tasks',             icon: ListChecks,        section: 'workspace' },
    { name: 'Calendar',          path: '/calendar',          icon: CalendarDays,      section: 'workspace' },
    { name: 'Communications',    path: '/communications',    icon: MessagesSquare,    section: 'workspace' },
    { name: 'Notifications',     path: '/notifications',     icon: Bell,              section: 'workspace' },
    { name: 'Templates',         path: '/templates',         icon: LayoutTemplate,    section: 'workspace' },
    { name: 'Campaigns',         path: '/campaigns',         icon: Megaphone,         featureCode: 'CAMPAIGN_MANAGEMENT', section: 'workspace' },
    { name: 'Comm Analytics',    path: '/communication-analytics', icon: BarChart3,   roles: ['OrgAdmin', 'Manager'], section: 'workspace' },
    { name: 'Calling',           path: '/calling',           icon: PhoneCall,         section: 'workspace' },
    { name: 'Call Reports',      path: '/calling/reports',   icon: BarChart3,         section: 'workspace' },
    { name: 'SMS',               path: '/sms',               icon: MessageSquare,     featureCode: 'SMS_MESSAGING', section: 'workspace' },
    { name: 'SMS Reports',       path: '/sms/reports',       icon: BarChart3,         featureCode: 'SMS_MESSAGING', section: 'workspace' },
    { name: 'WhatsApp',          path: '/whatsapp',          icon: MessageCircle,     featureCode: 'WHATSAPP_MESSAGING', section: 'workspace' },
    { name: 'WhatsApp Reports',  path: '/whatsapp/reports',  icon: BarChart3,         featureCode: 'WHATSAPP_MESSAGING', section: 'workspace' },
    { name: 'WhatsApp Settings', path: '/whatsapp/settings', icon: Settings,          roles: ['OrgAdmin'], featureCode: 'WHATSAPP_MESSAGING', section: 'workspace' },
    { name: 'Email',             path: '/email',             icon: Mail,              featureCode: 'EMAIL_MESSAGING', section: 'workspace' },
    { name: 'Email Reports',     path: '/email/reports',     icon: BarChart3,         featureCode: 'EMAIL_MESSAGING', section: 'workspace' },
    { name: 'Email Settings',    path: '/email/settings',    icon: Settings,          roles: ['OrgAdmin'], featureCode: 'EMAIL_MESSAGING', section: 'workspace' },
    { name: 'Leads',             path: '/leads',             icon: FolderKanban,     featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Lead Reports',      path: '/leads/reports',     icon: BarChart3,         featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Lead Automation',   path: '/leads/automation',  icon: Zap,               roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Companies',         path: '/companies',         icon: Building2,         roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Company Reports',   path: '/companies/reports', icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Contacts',          path: '/contacts',          icon: Contact,           roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Customers',         path: '/customers',         icon: HeartHandshake,    roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Customer Reports',  path: '/customers/reports', icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Contact Reports',   path: '/contacts/reports',  icon: BarChart3,         roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT', section: 'workspace' },
    { name: 'Pipelines',         path: '/pipelines',         icon: Workflow,          roles: ['OrgAdmin'],  featureCode: 'SALES_PIPELINE', section: 'workspace' },
    { name: 'Team Members',      path: '/users',             icon: Users,             roles: ['OrgAdmin', 'Manager'], featureCode: 'ROLE_BASED_ACCESS', section: 'workspace' },
    { name: 'Teams',             path: '/teams',             icon: UsersRound,        roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace' },
    { name: 'Attendance',        path: '/attendance',        icon: Clock,             roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace' },
    { name: 'Leave',             path: '/leaves',            icon: Plane,             roles: ['OrgAdmin', 'Manager', 'Employee'], section: 'workspace' },
    { name: 'Roles & Permissions', path: '/roles',           icon: Shield,            roles: ['OrgAdmin'], section: 'workspace' },
    { name: 'Branches',          path: '/branches',          icon: MapPin,            roles: ['OrgAdmin', 'Manager'], section: 'workspace' },
    { name: 'Departments',       path: '/departments',       icon: Building2,         roles: ['OrgAdmin', 'Manager'], section: 'workspace' },
    { name: 'Organization',      path: '/organization',      icon: Building,          roles: ['OrgAdmin'], section: 'workspace' },

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

    return true;
  });

  const workspaceItems = navItems.filter((item) => item.section === 'workspace');
  const billingItems = navItems.filter((item) => item.section === 'billing');

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
        {workspaceItems.map((item) => {
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
