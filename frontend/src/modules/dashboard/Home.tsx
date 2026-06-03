import React from 'react';
import { useAuthStore } from '../../store/authStore';
import { Shield, Sparkles, Building, Lock } from 'lucide-react';

export const Home: React.FC = () => {
  const { user, organization } = useAuthStore();

  const futureModules = [
    { name: 'Lead Management', desc: 'Capture, status pipelines, assignments', status: 'Module 4' },
    { name: 'Customer Contacts', desc: 'Contact details, communication logs', status: 'Module 5' },
    { name: 'Deal Opportunities', desc: 'Kanban boards, revenue forecasts', status: 'Module 6' },
  ];

  return (
    <div className="space-y-8">
      {/* Welcome Banner */}
      <div className="glass-panel p-8 rounded-2xl relative overflow-hidden flex flex-col md:flex-row items-start md:items-center justify-between gap-6">
        <div className="absolute top-0 right-0 w-[300px] h-[300px] bg-indigo-500/10 rounded-full blur-[80px] pointer-events-none"></div>
        
        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 px-3 py-1 bg-brand-500/10 text-brand-300 text-xs font-semibold rounded-full border border-brand-500/20">
            <Sparkles className="w-3.5 h-3.5" />
            Module 1 Live
          </div>
          <h1 className="text-4xl font-extrabold text-white tracking-tight">
            Welcome back, <span className="gradient-text">{user?.first_name || 'Admin'}</span>
          </h1>
          <p className="text-slate-400 text-sm md:text-base max-w-xl">
            You are authenticated into your tenant workspace. Module 1 handles secure session storage, token rotation, and multi-tenant scoping.
          </p>
        </div>

        <div className="flex items-center gap-3 px-5 py-4 bg-slate-900/60 border border-slate-800 rounded-xl">
          <Building className="w-10 h-10 text-brand-400" />
          <div>
            <p className="text-xs text-slate-500 uppercase tracking-wider font-semibold">Active Tenant</p>
            <p className="text-md font-bold text-white">{organization?.name}</p>
            <p className="text-xs text-slate-400">/{organization?.slug}</p>
          </div>
        </div>
      </div>

      {/* Grid details */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
        <div className="glass-panel p-6 rounded-2xl space-y-3">
          <div className="w-10 h-10 bg-brand-500/15 rounded-xl flex items-center justify-center">
            <Shield className="w-5 h-5 text-brand-400" />
          </div>
          <h3 className="font-bold text-lg text-white">RBAC Protected</h3>
          <p className="text-slate-400 text-sm">
            Your role is assigned as <span className="text-brand-300 font-medium">{user?.role}</span>. Organization settings are restricted to admins.
          </p>
        </div>

        <div className="glass-panel p-6 rounded-2xl space-y-3">
          <div className="w-10 h-10 bg-indigo-500/15 rounded-xl flex items-center justify-center">
            <Building className="w-5 h-5 text-indigo-400" />
          </div>
          <h3 className="font-bold text-lg text-white">Multi-Tenant Scoped</h3>
          <p className="text-slate-400 text-sm">
            All API queries are automatically bound to the header payload checking database identifiers dynamically.
          </p>
        </div>

        <div className="glass-panel p-6 rounded-2xl space-y-3">
          <div className="w-10 h-10 bg-purple-500/15 rounded-xl flex items-center justify-center">
            <Sparkles className="w-5 h-5 text-purple-400" />
          </div>
          <h3 className="font-bold text-lg text-white">Token Rotation</h3>
          <p className="text-slate-400 text-sm">
            Refresh tokens rotate on every API request expiration, securing active sessions without user logout disruption.
          </p>
        </div>
      </div>

      {/* Unlocked roadmap / future modules */}
      <div className="space-y-4">
        <h2 className="text-xl font-bold text-white tracking-tight">System Modules</h2>
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
          {futureModules.map((mod) => (
            <div key={mod.name} className="bg-slate-950 border border-slate-900 p-6 rounded-2xl flex flex-col justify-between opacity-60 relative overflow-hidden group">
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-slate-500 uppercase">{mod.status}</span>
                  <Lock className="w-3.5 h-3.5 text-slate-600" />
                </div>
                <h4 className="font-bold text-slate-300">{mod.name}</h4>
                <p className="text-slate-500 text-xs">{mod.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
