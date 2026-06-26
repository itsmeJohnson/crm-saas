import React, { useState } from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import {
  LayoutDashboard, CreditCard, Sparkles, FileText, Receipt,
  BarChart3, HardDrive, PhoneCall, Users, User, Building2,
  LifeBuoy, Activity, Settings, ArrowLeft, Sun, Moon, Menu, X
} from 'lucide-react';

export const OrgPortalLayout: React.FC = () => {
  const { user, organization, logout } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const navigate = useNavigate();
  const location = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const portalNavItems = [
    { name: 'Dashboard', path: '/portal/dashboard', icon: LayoutDashboard },
    { name: 'Subscription', path: '/portal/subscription', icon: CreditCard },
    { name: 'Plans', path: '/portal/plans', icon: Sparkles },
    { name: 'Invoices', path: '/portal/invoices', icon: FileText },
    { name: 'Payments', path: '/portal/payments', icon: Receipt },
    { name: 'Usage', path: '/portal/usage', icon: BarChart3 },
    { name: 'Storage', path: '/portal/storage', icon: HardDrive },
    { name: 'Call Recordings', path: '/portal/recordings', icon: PhoneCall },
    { name: 'Users', path: '/portal/users', icon: Users },
    { name: 'Profile', path: '/portal/profile', icon: User },
    { name: 'Billing', path: '/portal/billing', icon: Building2 },
    { name: 'Support', path: '/portal/support', icon: LifeBuoy },
    { name: 'Activity Logs', path: '/portal/activity', icon: Activity },
    { name: 'Settings', path: '/portal/settings', icon: Settings },
  ];

  const sidebarContent = (
    <div className="flex flex-col justify-between h-full bg-slate-950">
      <div className="overflow-y-auto flex-1 scrollbar-thin">
        {/* Logo and close button */}
        <div className="p-6 flex items-center justify-between border-b border-slate-900">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-tr from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white shadow">
              S
            </div>
            <div>
              <span className="font-bold text-sm tracking-tight text-slate-100 block">Self Service Portal</span>
              <span className="text-[10px] text-slate-500 tracking-widest font-semibold uppercase">Organization Admin</span>
            </div>
          </div>
          <button
            onClick={() => setIsMobileOpen(false)}
            className="md:hidden p-1.5 border border-slate-900 hover:border-slate-800 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Back to CRM */}
        <div className="px-4 pt-4">
          <Link
            to="/"
            className="w-full flex items-center gap-2.5 px-4 py-2.5 bg-slate-900/60 border border-slate-900 hover:border-slate-800 text-xs font-semibold text-brand-400 hover:text-brand-300 rounded-xl transition-all"
          >
            <ArrowLeft className="w-3.5 h-3.5" />
            Back to CRM Workspace
          </Link>
        </div>

        {/* Navigation Links */}
        <nav className="px-4 py-6 space-y-1">
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
                    : 'text-slate-400 hover:bg-slate-900/50 hover:text-slate-200'
                }`}
              >
                <Icon className="w-4.5 h-4.5" />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer Profile Details */}
      <div className="p-4 border-t border-slate-900 bg-slate-950/60 space-y-4">
        <div className="flex items-center justify-between px-2">
          <div className="overflow-hidden max-w-[150px]">
            <p className="text-xs font-bold text-slate-200 truncate">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-[10px] text-slate-500 truncate">{user?.email}</p>
            <span className="inline-block mt-1 px-1.5 py-0.5 text-[9px] font-bold bg-brand-500/10 text-brand-400 rounded border border-brand-500/20">
              {organization?.name}
            </span>
          </div>

          {/* Theme Switcher */}
          <button
            onClick={toggleTheme}
            className="p-2 border border-slate-900 hover:border-slate-800 hover:bg-slate-900 rounded-xl text-slate-400 hover:text-slate-200 transition-all cursor-pointer bg-slate-950"
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
          className="w-full flex items-center justify-center gap-2 px-4 py-2 bg-slate-900 border border-slate-900 rounded-xl text-xs font-bold text-red-400 hover:bg-red-500/10 hover:border-red-500/20 transition-all cursor-pointer"
        >
          Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-slate-950 text-slate-200 overflow-hidden flex-col md:flex-row font-sans">
      {/* Sidebar for Desktop */}
      <aside className="hidden md:flex md:w-60 border-r border-slate-900 flex-col justify-between z-25">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-30 md:hidden flex">
          <div
            className="absolute inset-0 bg-slate-950/60 backdrop-blur-xs transition-opacity duration-200"
            onClick={() => setIsMobileOpen(false)}
          ></div>
          <aside className="relative w-60 bg-slate-950 border-r border-slate-900 shadow-2xl flex flex-col justify-between h-full z-10 animate-slide-in">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile Top Bar Header */}
        <header className="md:hidden flex items-center justify-between px-6 py-4 bg-slate-950 border-b border-slate-900 z-20">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-tr from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white shadow">
              S
            </div>
            <span className="font-semibold text-sm tracking-tight text-slate-100">Self Service Portal</span>
          </div>
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-2 border border-slate-900 hover:border-slate-800 hover:bg-slate-900 rounded-xl text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
          >
            <Menu className="w-5 h-5" />
          </button>
        </header>

        {/* Content Outlet */}
        <main className="flex-1 flex flex-col overflow-hidden relative bg-slate-950/30">
          <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-brand-500/5 rounded-full blur-[120px] pointer-events-none"></div>
          <div className="flex-1 overflow-y-auto p-4 md:p-8 relative z-10">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
