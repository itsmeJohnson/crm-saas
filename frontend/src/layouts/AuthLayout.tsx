import React from 'react';
import { Outlet } from 'react-router-dom';

export const AuthLayout: React.FC = () => {
  return (
    <div className="min-h-screen bg-slate-950 flex flex-col justify-center items-center relative overflow-hidden px-4">
      {/* Decorative Blur Orbs */}
      <div className="absolute top-[-10%] left-[-10%] w-[500px] h-[500px] bg-brand-500/10 rounded-full blur-[120px] pointer-events-none"></div>
      <div className="absolute bottom-[-10%] right-[-10%] w-[500px] h-[500px] bg-indigo-500/10 rounded-full blur-[120px] pointer-events-none"></div>

      <div className="w-full max-w-md glass-panel p-8 rounded-2xl shadow-2xl relative z-10">
        <div className="flex flex-col items-center mb-8">
          <div className="w-12 h-12 bg-gradient-to-tr from-brand-500 to-indigo-500 rounded-xl flex items-center justify-center shadow-lg mb-3">
            <span className="font-bold text-xl text-white">C</span>
          </div>
          <h1 className="text-3xl font-extrabold tracking-tight text-white mb-1">
            CRM <span className="gradient-text">Enterprise</span>
          </h1>
          <p className="text-slate-400 text-sm text-center">Multi-Tenant Sales & Customer Management</p>
        </div>
        
        <Outlet />
      </div>
    </div>
  );
};
