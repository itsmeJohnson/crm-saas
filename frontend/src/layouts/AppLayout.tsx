import React, { useState } from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { LayoutDashboard, LogOut, Building, Users, FolderKanban, Workflow, Sun, Moon, Menu, X } from 'lucide-react';
import { InboundCallPopup } from '../components/crm/InboundCallPopup';

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
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Tenants', path: '/tenants', icon: Building, roles: ['SuperAdmin'] },
    { name: 'Leads', path: '/leads', icon: FolderKanban },
    { name: 'Pipelines', path: '/pipelines', icon: Workflow, roles: ['OrgAdmin'] },
    { name: 'Users', path: '/users', icon: Users, roles: ['OrgAdmin', 'Manager'] },
    { name: 'Organization', path: '/organization', icon: Building, roles: ['OrgAdmin'] },
  ];

  const navItems = allNavItems.filter((item) => {
    if (!item.roles) return true;
    if (!user) return false;
    if (item.name === 'Users' && user.role === 'Employee' && user.is_team_leader) {
      return true; // Allow Team Leaders to access the Users link
    }
    return item.roles.includes(user.role);
  });

  const sidebarContent = (
    <div className="flex flex-col justify-between h-full">
      <div>
        {/* Logo and close button */}
        <div className="p-6 flex items-center justify-between border-b border-slate-800/80">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-tr from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white shadow">
              C
            </div>
            <span className="font-semibold text-lg tracking-tight text-slate-100">CRM Enterprise</span>
          </div>
          <button
            onClick={() => setIsMobileOpen(false)}
            className="md:hidden p-1.5 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-lg text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Org Display */}
        <div className="mx-4 my-4 p-3 bg-slate-900/50 border border-slate-800 rounded-xl flex items-center gap-2">
          <Building className="w-4 h-4 text-brand-400" />
          <div className="overflow-hidden">
            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Tenant</p>
            <p className="text-sm font-medium text-slate-200 truncate">{organization?.name}</p>
          </div>
        </div>

        {/* Navigation Links */}
        <nav className="px-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = location.pathname === item.path;
            return (
              <Link
                key={item.name}
                to={item.path}
                onClick={() => setIsMobileOpen(false)}
                className={`flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium transition-all duration-150 ${
                  isActive
                    ? 'bg-brand-500 text-white shadow-lg shadow-brand-500/20'
                    : 'text-slate-400 hover:bg-slate-900/80 hover:text-slate-100'
                }`}
              >
                <Icon className="w-5 h-5" />
                {item.name}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* User Profile, Theme Switcher & Logout */}
      <div className="p-4 border-t border-slate-800/80 space-y-4">
        <div className="flex items-center justify-between px-2">
          <div className="overflow-hidden max-w-[150px]">
            <p className="text-sm font-semibold text-slate-200 truncate">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-xs text-slate-400 truncate">{user?.email}</p>
            <span className="inline-block mt-1 px-1.5 py-0.5 text-[10px] font-semibold bg-brand-500/20 text-brand-300 rounded border border-brand-500/30">
              {user?.role}
            </span>
          </div>

          {/* Theme switcher */}
          <button
            onClick={toggleTheme}
            title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
            className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-xl text-slate-400 hover:text-slate-200 transition-all cursor-pointer bg-slate-950/20"
          >
            {theme === 'dark' ? (
              <Sun className="w-4.5 h-4.5 text-amber-400" />
            ) : (
              <Moon className="w-4.5 h-4.5 text-indigo-400" />
            )}
          </button>
        </div>
        <button
          onClick={handleLogout}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 hover:border-red-500/20 transition-all cursor-pointer"
        >
          <LogOut className="w-4 h-4" />
          Sign Out
        </button>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden flex-col md:flex-row">
      <InboundCallPopup />
      {/* Sidebar for Desktop */}
      <aside className="hidden md:flex md:w-64 glass-panel border-r border-slate-800 flex-col justify-between z-25">
        {sidebarContent}
      </aside>

      {/* Mobile Drawer Navigation */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-30 md:hidden flex">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-slate-950/60 backdrop-blur-xs transition-opacity duration-200"
            onClick={() => setIsMobileOpen(false)}
          ></div>

          {/* Slide Drawer */}
          <aside className="relative w-64 max-w-xs bg-slate-950 border-r border-slate-800/80 shadow-2xl flex flex-col justify-between h-full z-10 animate-slide-in">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* Main Workspace Wrapper */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Mobile Top Bar Header */}
        <header className="md:hidden flex items-center justify-between px-6 py-4 bg-slate-900/60 border-b border-slate-800/80 z-20">
          <div className="flex items-center gap-3">
            <div className="w-8 h-8 bg-gradient-to-tr from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white shadow">
              C
            </div>
            <span className="font-semibold text-base tracking-tight text-slate-100">CRM Enterprise</span>
          </div>
          <button
            onClick={() => setIsMobileOpen(true)}
            className="p-2 border border-slate-800 hover:border-slate-700 hover:bg-slate-900 rounded-xl text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
          >
            <Menu className="w-5 h-5" />
          </button>
        </header>

        {/* Main Content Area */}
        <main className="flex-1 flex flex-col overflow-hidden relative">
          <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-brand-500/5 rounded-full blur-[100px] pointer-events-none"></div>
          <div className="flex-1 overflow-y-auto p-4 md:p-8 relative z-10">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};
