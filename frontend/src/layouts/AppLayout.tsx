import React, { useState } from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import {
  LayoutDashboard, LogOut, Building, Users, FolderKanban,
  Sun, Moon, Menu, X, CreditCard, ChevronDown,
  Gauge, Sparkles, FileText, Receipt, BarChart3, HardDrive, PhoneCall,
  UserCog, Settings, Activity, ListChecks, CalendarDays, MessagesSquare,
  MessageCircle, Megaphone, UsersRound, Clock, Stethoscope
} from 'lucide-react';
import { InboundCallPopup } from '../components/crm/InboundCallPopup';
import { NotificationBell } from '../components/notifications/NotificationBell';
import { useBrowserNotifications } from '../hooks/useBrowserNotifications';

export const AppLayout: React.FC = () => {
  const { user, organization, logout } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const navigate = useNavigate();
  useBrowserNotifications(!!user);
  const location = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const TRIAL_MODE = true;

  const NAV_GROUPS = [
    'Clinical Operations', 'Patient Engagement', 'Clinic Management',
    'Growth & Analytics', 'Administration', 'Platform'
  ];

  const allNavItems = [
    // ── Clinical Operations ────────────────────────────────────────────────
    { name: 'Dashboard',          path: '/',                  icon: LayoutDashboard,  section: 'workspace', group: 'Clinical Operations', trial: true },
    { name: 'Leads & Enquiries',  path: '/leads',             icon: FolderKanban,     section: 'workspace', group: 'Clinical Operations', trial: true },
    { name: 'Patients Directory', path: '/patients',          icon: Users,            section: 'workspace', group: 'Clinical Operations', trial: true },
    { name: 'Appointments',       path: '/appointments',      icon: CalendarDays,     section: 'workspace', group: 'Clinical Operations', trial: true },
    { name: 'Treatment Plans',    path: '/treatments',        icon: Activity,         section: 'workspace', group: 'Clinical Operations', trial: true },
    { name: 'Billing & Invoices', path: '/billing',           icon: Receipt,          section: 'workspace', group: 'Clinical Operations', trial: true },

    // ── Patient Engagement ─────────────────────────────────────────────────
    { name: 'Follow-ups & Recalls', path: '/follow-ups',      icon: Clock,            section: 'workspace', group: 'Patient Engagement', trial: true },
    { name: 'Communications',     path: '/communications',    icon: MessagesSquare,   section: 'workspace', group: 'Patient Engagement', trial: true },
    { name: 'Tasks & Reminders',  path: '/tasks',             icon: ListChecks,       section: 'workspace', group: 'Patient Engagement', trial: true },
    { name: 'WhatsApp Center',    path: '/whatsapp',          icon: MessageCircle,    section: 'workspace', group: 'Patient Engagement', trial: true },
    { name: 'Phone Calling',      path: '/calling',           icon: PhoneCall,        section: 'workspace', group: 'Patient Engagement', trial: true },

    // ── Clinic Management ──────────────────────────────────────────────────
    { name: 'Dentists & Surgeons', path: '/doctors',          icon: Stethoscope,      section: 'workspace', group: 'Clinic Management', trial: true },
    { name: 'Staff & Team',       path: '/staff',             icon: UsersRound,       section: 'workspace', group: 'Clinic Management', trial: true },

    // ── Growth & Analytics ─────────────────────────────────────────────────
    { name: 'Clinical Reports',   path: '/reports',           icon: BarChart3,        section: 'workspace', group: 'Growth & Analytics', trial: true },
    { name: 'Marketing ROI',      path: '/marketing',         icon: Megaphone,        section: 'workspace', group: 'Growth & Analytics', trial: true },

    // ── Administration ─────────────────────────────────────────────────────
    { name: 'Clinic Settings',    path: '/settings',          icon: Settings,         roles: ['SuperAdmin', 'OrgAdmin'], section: 'workspace', group: 'Administration', trial: true },
    { name: 'Organization',       path: '/organization',      icon: Building,         roles: ['OrgAdmin'], section: 'workspace', group: 'Administration', trial: true },

    // ── Platform (SuperAdmin) ──────────────────────────────────────────────
    { name: 'Tenants',            path: '/tenants',           icon: Building,         roles: ['SuperAdmin'], section: 'workspace', group: 'Platform', trial: true },
    { name: 'Trial Requests',     path: '/trial-requests',    icon: Clock,            roles: ['SuperAdmin'], section: 'workspace', group: 'Platform', trial: true },

    // ── Billing & Account (OrgAdmin only) ─────────────────────────────────
    { name: 'Billing Overview',   path: '/portal/dashboard',  icon: Gauge,            roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Subscription',       path: '/portal/subscription', icon: CreditCard,     roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Plans',              path: '/portal/plans',      icon: Sparkles,         roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Invoices',           path: '/portal/invoices',   icon: FileText,         roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Payments',           path: '/portal/payments',   icon: Receipt,          roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Usage',              path: '/portal/usage',      icon: BarChart3,        roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Storage',            path: '/portal/storage',    icon: HardDrive,        roles: ['OrgAdmin'], section: 'billing' },
    { name: 'Seat Licensing',     path: '/portal/users',      icon: UserCog,          roles: ['OrgAdmin'], section: 'billing' },
  ];

  const features = useAuthStore((state) => state.features);

  const navItems = allNavItems.filter((item) => {
    if (!user) return false;
    if (item.roles) {
      const hasRole = item.roles.includes(user.role);
      const isTeamLeaderUsers = item.name === 'Team Members' && user.role === 'Employee' && user.is_team_leader;
      if (!hasRole && !isTeamLeaderUsers) return false;
    }
    if ((item as any).featureCode && user.role !== 'SuperAdmin') {
      if (!features.includes((item as any).featureCode)) return false;
    }
    if (TRIAL_MODE && user.role !== 'SuperAdmin' && item.section !== 'billing' && !(item as any).trial) {
      return false;
    }
    return true;
  });

  const billingItems = navItems.filter((item) => item.section === 'billing');

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

  const initials = [user?.first_name?.[0], user?.last_name?.[0]]
    .filter(Boolean)
    .join('')
    .toUpperCase() || 'D';

  const roleLabel: Record<string, string> = {
    SuperAdmin: 'Super Admin',
    OrgAdmin: 'Practice Admin',
    Manager: 'Clinic Manager',
    Employee: user?.is_team_leader ? 'Lead Dentist' : 'Attending Dentist',
  };
  const displayRole = roleLabel[user?.role ?? ''] ?? user?.role ?? 'Doctor';

  const sidebarContent = (
    <div className="flex flex-col h-full select-none">
      {/* ── Minimalist Brand Header ── */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--border-color)]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-cyan-500/10 border border-cyan-500/30 flex items-center justify-center text-cyan-400 font-bold flex-shrink-0">
            <Stethoscope className="w-4 h-4" />
          </div>
          <div className="min-w-0">
            <span className="font-bold text-sm tracking-tight text-slate-100 block truncate">
              {organization?.name || 'SmileCare Dental'}
            </span>
            <span className="text-[10px] text-slate-400 font-medium tracking-wide block">
              Dental Practice Suite
            </span>
          </div>
        </div>
        <button
          onClick={() => setIsMobileOpen(false)}
          className="md:hidden p-1 rounded-lg text-slate-400 hover:text-slate-200"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── Navigation Tree ── */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-3">
        {groupedWorkspace.map(({ group, items }) => {
          const isCollapsed = collapsedGroups.has(group);
          const groupActive = items.some((item) =>
            location.pathname === item.path ||
            (item.path !== '/' && location.pathname.startsWith(item.path)));
          return (
            <div key={group} className="space-y-0.5">
              <button
                onClick={() => toggleGroup(group)}
                className="w-full flex items-center justify-between px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-300 transition-colors"
              >
                <span className={groupActive ? 'text-cyan-400' : ''}>{group}</span>
                <ChevronDown className={`w-3 h-3 transition-transform duration-150 ${isCollapsed ? '-rotate-90' : ''}`} />
              </button>
              {!isCollapsed && (
                <div className="space-y-0.5">
                  {items.map((item) => {
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
                        <Icon className={`w-4 h-4 flex-shrink-0 transition-colors ${isActive ? 'text-cyan-400' : 'text-slate-400'}`} />
                        <span className="truncate">{item.name}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {billingItems.length > 0 && (
          <div className="space-y-0.5 pt-2 border-t border-[var(--border-color)]">
            <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
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
                  <span className="truncate">{item.name}</span>
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* ── User Footer Card ── */}
      <div className="p-3 border-t border-[var(--border-color)]">
        <div className="flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-color)]">
          <div className="w-8 h-8 rounded-md bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center text-xs font-bold flex-shrink-0">
            {initials}
          </div>
          <div className="overflow-hidden flex-1 min-w-0">
            <p className="text-xs font-semibold text-slate-100 truncate leading-tight">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-[10px] text-slate-400 truncate mt-0.5">
              {displayRole}
            </p>
          </div>
          <button
            onClick={handleLogout}
            title="Sign Out"
            className="p-1.5 rounded text-slate-400 hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );

  const PLATFORM_PREFIXES = ['/tenants'];
  const isPlatformConsole = PLATFORM_PREFIXES.some(
    (p) => location.pathname === p || location.pathname.startsWith(p + '/'),
  );

  if (isPlatformConsole) {
    return (
      <div className="flex flex-col h-screen overflow-hidden bg-[var(--bg-app)] text-[var(--text-primary)]">
        <InboundCallPopup />
        <header className="flex items-center gap-3 px-6 py-3 border-b border-[var(--border-color)] bg-[var(--bg-surface)]">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-7 h-7 bg-cyan-500 rounded flex items-center justify-center font-bold text-white text-xs flex-shrink-0">C</div>
            <span className="font-bold text-sm text-slate-100 truncate">CRM Enterprise</span>
            <span className="text-xs text-slate-400 truncate">• {organization?.name}</span>
          </div>
          <div className="ml-auto flex items-center gap-2">
            <button
              onClick={toggleTheme}
              className="p-1.5 rounded-lg border border-[var(--border-color)] hover:bg-[var(--bg-card-hover)] text-xs text-slate-300 transition"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />}
            </button>
            <NotificationBell />
            <button
              onClick={handleLogout}
              className="px-2.5 py-1 rounded-lg border border-[var(--border-color)] hover:border-rose-500/30 hover:bg-rose-500/10 text-xs text-rose-400 transition"
            >
              <LogOut className="w-3.5 h-3.5" /> Sign Out
            </button>
          </div>
        </header>
        <main className="flex-1 overflow-y-auto bg-[var(--bg-app)]">
          <div className="p-6 min-h-full">
            <Outlet />
          </div>
        </main>
      </div>
    );
  }

  return (
    <div className="flex h-screen overflow-hidden flex-col md:flex-row bg-[var(--bg-app)] text-[var(--text-primary)]">
      <InboundCallPopup />

      {/* ── Desktop Minimalist Sidebar ── */}
      <aside className="hidden md:flex md:w-56 crm-sidebar flex-col z-20 flex-shrink-0">
        {sidebarContent}
      </aside>

      {/* ── Mobile Drawer ── */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-30 md:hidden flex">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setIsMobileOpen(false)}
          />
          <aside className="relative w-60 crm-sidebar shadow-2xl flex flex-col h-full z-10">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* ── Main Viewport ── */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Top Minimalist Header */}
        <header className="flex items-center justify-between px-6 py-2.5 border-b border-[var(--border-color)] bg-[var(--bg-surface)] z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsMobileOpen(true)}
              className="md:hidden p-1.5 rounded-lg border border-[var(--border-color)] text-slate-400"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="hidden sm:flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                Live OPD
              </span>
              <span className="text-xs text-slate-400">
                Dr. Johnson Dev • Main Operatory
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              className="p-1.5 rounded-lg border border-[var(--border-color)] hover:bg-[var(--bg-card-hover)] text-slate-400 hover:text-slate-200 transition"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />}
            </button>
            <NotificationBell />
          </div>
        </header>

        {/* Minimalist Canvas */}
        <main className="flex-1 overflow-y-auto bg-[var(--bg-app)]">
          <div className="p-4 md:p-6 min-h-full max-w-[1600px] mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
