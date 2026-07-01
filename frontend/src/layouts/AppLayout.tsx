import React, { useState } from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import {
  LayoutDashboard, LogOut, Building, Users, FolderKanban,
  Workflow, Sun, Moon, Menu, X, CreditCard, ChevronRight
} from 'lucide-react';
import { InboundCallPopup } from '../components/crm/InboundCallPopup';
import { SubscriptionGate } from '../components/SubscriptionGate';

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
    { name: 'Dashboard',         path: '/',                  icon: LayoutDashboard },
    { name: 'Tenants',           path: '/tenants',           icon: Building,         roles: ['SuperAdmin'] },
    { name: 'Leads',             path: '/leads',             icon: FolderKanban,     featureCode: 'LEAD_MANAGEMENT' },
    { name: 'Pipelines',         path: '/pipelines',         icon: Workflow,          roles: ['OrgAdmin'],  featureCode: 'SALES_PIPELINE' },
    { name: 'Users',             path: '/users',             icon: Users,             roles: ['OrgAdmin', 'Manager'], featureCode: 'ROLE_BASED_ACCESS' },
    { name: 'Organization',      path: '/organization',      icon: Building,          roles: ['OrgAdmin'] },
    { name: 'Subscription',      path: '/portal/dashboard',  icon: CreditCard,        roles: ['OrgAdmin'] },
  ];

  const features = useAuthStore((state) => state.features);

  const navItems = allNavItems.filter((item) => {
    if (!user) return false;

    if (item.roles) {
      const hasRole = item.roles.includes(user.role);
      const isTeamLeaderUsers = item.name === 'Users' && user.role === 'Employee' && user.is_team_leader;
      if (!hasRole && !isTeamLeaderUsers) return false;
    }

    if (item.featureCode && user.role !== 'SuperAdmin') {
      if (!features.includes(item.featureCode)) return false;
    }

    return true;
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
        {navItems.map((item) => {
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
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-2 rounded-lg text-slate-400 hover:text-slate-200 hover:bg-slate-800/60 transition-colors cursor-pointer"
          >
            <Menu className="w-5 h-5" />
          </button>
        </header>

        {/* Main Content */}
        <main className="flex-1 overflow-y-auto" style={{ backgroundColor: 'var(--bg-app)' }}>
          <div className="p-4 md:p-6 min-h-full">
            <SubscriptionGate>
              <Outlet />
            </SubscriptionGate>
          </div>
        </main>
      </div>
    </div>
  );
};
