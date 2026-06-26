import React, { useState } from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import {
  LayoutDashboard, CreditCard, Sparkles, FileText, Receipt,
  BarChart3, HardDrive, PhoneCall, Users, User, Building2,
  LifeBuoy, Activity, Settings, ArrowLeft, Sun, Moon, Menu, X,
} from 'lucide-react';

// Portal nav items mapped to feature codes (null = always visible)
// underDev = true means the page shows "Under Development" UI
const ALL_PORTAL_NAV = [
  { name: 'Dashboard',      path: '/portal/dashboard',    icon: LayoutDashboard, featureCode: null,          underDev: false },
  { name: 'Subscription',   path: '/portal/subscription', icon: CreditCard,      featureCode: null,          underDev: false },
  { name: 'Plans',          path: '/portal/plans',        icon: Sparkles,        featureCode: null,          underDev: false },
  { name: 'Invoices',       path: '/portal/invoices',     icon: FileText,        featureCode: null,          underDev: false },
  { name: 'Payments',       path: '/portal/payments',     icon: Receipt,         featureCode: null,          underDev: false },
  { name: 'Users',          path: '/portal/users',        icon: Users,           featureCode: 'ROLE_BASED_ACCESS', underDev: false },
  { name: 'Usage',          path: '/portal/usage',        icon: BarChart3,       featureCode: null,          underDev: false },
  { name: 'Call Recordings',path: '/portal/recordings',   icon: PhoneCall,       featureCode: 'CALL_RECORDING',    underDev: false },
  { name: 'Storage',        path: '/portal/storage',      icon: HardDrive,       featureCode: null,          underDev: true  },
  { name: 'Activity Logs',  path: '/portal/activity',     icon: Activity,        featureCode: 'ADVANCED_ANALYTICS', underDev: true },
  { name: 'Profile',        path: '/portal/profile',      icon: User,            featureCode: null,          underDev: false },
  { name: 'Billing',        path: '/portal/billing',      icon: Building2,       featureCode: null,          underDev: false },
  { name: 'Support',        path: '/portal/support',      icon: LifeBuoy,        featureCode: null,          underDev: false },
  { name: 'Settings',       path: '/portal/settings',     icon: Settings,        featureCode: null,          underDev: false },
];

export const OrgPortalLayout: React.FC = () => {
  const { user, organization, logout, features } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Filter nav: hide items whose feature is NOT in user's plan
  const portalNavItems = ALL_PORTAL_NAV.filter(item => {
    if (!item.featureCode) return true; // always-visible items
    return features.includes(item.featureCode);
  });

  const sidebarContent = (
    <div className="flex flex-col justify-between h-full bg-[var(--bg-surface)]">
      <div className="overflow-y-auto flex-1 scrollbar-thin">
        {/* Logo + close */}
        <div className="p-6 flex items-center justify-between border-b border-[var(--border-color)]">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-tr from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white shadow">
              S
            </div>
            <div>
              <span className="font-bold text-sm tracking-tight text-[var(--text-primary)] block">Self Service Portal</span>
              <span className="text-[10px] text-[var(--text-muted)] tracking-widest font-semibold uppercase">Organization Admin</span>
            </div>
          </div>
          <button
            onClick={() => setIsMobileOpen(false)}
            className="md:hidden p-1.5 border border-[var(--border-color)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-subtle)] rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Back to CRM */}
        <div className="px-4 pt-4">
          <Link
            to="/"
            className="w-full flex items-center gap-2.5 px-4 py-2.5 bg-[var(--bg-subtle)] border border-[var(--border-color)] hover:border-[var(--border-strong)] text-xs font-semibold text-brand-400 hover:text-brand-300 rounded-xl transition-all"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to CRM Workspace
          </Link>
        </div>

        {/* Plan badge */}
        {organization?.subscription_plan && (
          <div className="px-4 pt-3">
            <div className="flex items-center gap-2 px-3 py-2 bg-brand-500/10 border border-brand-500/20 rounded-xl">
              <Sparkles className="w-3.5 h-3.5 text-brand-400 shrink-0" />
              <div className="min-w-0">
                <p className="text-[10px] text-[var(--text-muted)] uppercase tracking-wider font-semibold">Active Plan</p>
                <p className="text-xs font-bold text-brand-400 capitalize">{organization.subscription_plan}</p>
              </div>
            </div>
          </div>
        )}

        {/* Navigation Links */}
        <nav className="px-4 py-4 space-y-0.5">
          {portalNavItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.name}
                to={item.path}
                onClick={() => setIsMobileOpen(false)}
                className={`flex items-center gap-3 px-4 py-2.5 rounded-xl text-xs font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/10'
                    : 'text-[var(--text-secondary)] hover:bg-[var(--bg-subtle)] hover:text-[var(--text-primary)]'
                }`}
              >
                <Icon className="w-4 h-4 shrink-0" />
                <span className="flex-1">{item.name}</span>
                {item.underDev && !isActive && (
                  <span className="text-[9px] font-bold px-1.5 py-0.5 rounded-full bg-amber-500/10 text-amber-400 border border-amber-500/20">
                    BETA
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer */}
      <div className="p-4 border-t border-[var(--border-color)] bg-[var(--bg-app)]/60 space-y-4">
        <div className="flex items-center justify-between px-2">
          <div className="overflow-hidden max-w-[150px]">
            <p className="text-xs font-bold text-[var(--text-primary)] truncate">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-[10px] text-[var(--text-muted)] truncate">{user?.email}</p>
            <span className="inline-block mt-1 px-1.5 py-0.5 text-[9px] font-bold bg-brand-500/10 text-brand-400 rounded border border-brand-500/20">
              {organization?.name}
            </span>
          </div>
          <button
            onClick={toggleTheme}
            className="p-2 border border-[var(--border-color)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-subtle)] rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all cursor-pointer"
          >
            {theme === 'dark' ? (
              <Sun className="w-3.5 h-3.5 text-amber-400" />
            ) : (
              <Moon className="w-3.5 h-3.5 text-indigo-400" />
            )}
          </button>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-[var(--bg-subtle)] border border-[var(--border-color)] rounded-xl text-xs font-bold text-red-400 hover:bg-red-500/10 hover:border-red-500/20 transition-all cursor-pointer"
        >
          Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-[var(--bg-app)] text-[var(--text-primary)] overflow-hidden flex-col md:flex-row font-sans">
      {/* Sidebar for Desktop */}
      <aside className="hidden md:flex md:w-60 border-r border-[var(--border-color)] flex-col justify-between z-25">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-30 md:hidden flex">
          <div
            className="absolute inset-0 bg-[var(--bg-app)]/60 backdrop-blur-xs transition-opacity duration-200"
            onClick={() => setIsMobileOpen(false)}
          ></div>
          <aside className="relative w-60 bg-[var(--bg-surface)] border-r border-[var(--border-color)] shadow-2xl flex flex-col justify-between h-full z-10 animate-slide-in">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile Top Bar */}
        <header className="md:hidden flex items-center justify-between px-6 py-4 bg-[var(--bg-surface)] border-b border-[var(--border-color)] z-20">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-tr from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white shadow">
              S
            </div>
            <span className="font-semibold text-sm tracking-tight text-[var(--text-primary)]">Self Service Portal</span>
          </div>
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-2 border border-[var(--border-color)] hover:border-[var(--border-strong)] hover:bg-[var(--bg-subtle)] rounded-xl text-[var(--text-muted)] hover:text-[var(--text-primary)] transition-all cursor-pointer"
          >
            <Menu className="w-5 h-5" />
          </button>
        </header>

        {/* Content Outlet */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-brand-500/5 rounded-full blur-[120px] pointer-events-none"></div>
          <div className="flex-1 overflow-y-auto p-4 md:p-8 relative z-10">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
