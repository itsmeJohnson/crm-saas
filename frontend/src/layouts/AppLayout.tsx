import React from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { LayoutDashboard, LogOut, Building, Users, FolderKanban, Briefcase, Contact } from 'lucide-react';

export const AppLayout: React.FC = () => {
  const { user, organization, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const navItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Leads', path: '/leads', icon: FolderKanban },
    { name: 'Companies', path: '/companies', icon: Briefcase },
    { name: 'Contacts', path: '/contacts', icon: Contact },
    { name: 'Users', path: '/users', icon: Users },
    { name: 'Organization', path: '/organization', icon: Building },
  ];

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 glass-panel border-r border-slate-800 flex flex-col justify-between z-20">
        <div>
          {/* Logo */}
          <div className="p-6 flex items-center gap-3 border-b border-slate-800/80">
            <div className="w-8 h-8 bg-gradient-to-tr from-brand-500 to-indigo-500 rounded-lg flex items-center justify-center font-bold text-white shadow">
              C
            </div>
            <span className="font-semibold text-lg tracking-tight">CRM Enterprise</span>
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

        {/* User Profile & Logout */}
        <div className="p-4 border-t border-slate-800/80">
          <div className="flex items-center justify-between mb-4 px-2">
            <div className="overflow-hidden">
              <p className="text-sm font-semibold text-slate-200 truncate">
                {user?.first_name} {user?.last_name}
              </p>
              <p className="text-xs text-slate-400 truncate">{user?.email}</p>
              <span className="inline-block mt-1 px-1.5 py-0.5 text-[10px] font-semibold bg-brand-500/20 text-brand-300 rounded border border-brand-500/30">
                {user?.role}
              </span>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm font-medium text-red-400 hover:bg-red-500/10 hover:border-red-500/20 transition-all"
          >
            <LogOut className="w-4 h-4" />
            Sign Out
          </button>
        </div>
      </aside>

      {/* Main Workspace */}
      <main className="flex-1 flex flex-col overflow-hidden relative">
        <div className="absolute top-0 right-0 w-[400px] h-[400px] bg-brand-500/5 rounded-full blur-[100px] pointer-events-none"></div>
        <div className="flex-1 overflow-y-auto p-8 relative z-10">
          <Outlet />
        </div>
      </main>
    </div>
  );
};
