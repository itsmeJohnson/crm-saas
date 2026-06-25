import React from 'react';
import { Outlet } from 'react-router-dom';

export const AuthLayout: React.FC = () => {
  return (
    <div
      className="min-h-screen flex flex-col justify-center items-center relative overflow-hidden px-4"
      style={{ backgroundColor: 'var(--bg-app)' }}
    >
      {/* Subtle background accent — much more restrained than before */}
      <div className="absolute inset-0 overflow-hidden pointer-events-none">
        <div className="absolute top-[10%] right-[15%] w-[320px] h-[320px] bg-brand-500/6 rounded-full blur-[90px]" />
        <div className="absolute bottom-[10%] left-[10%] w-[280px] h-[280px] bg-indigo-500/5 rounded-full blur-[90px]" />
      </div>

      {/* Card */}
      <div
        className="w-full max-w-[420px] rounded-2xl relative z-10 shadow-lg"
        style={{
          backgroundColor: 'var(--bg-card)',
          border: '1px solid var(--border-color)',
          boxShadow: 'var(--shadow-lg)',
        }}
      >
        {/* Header */}
        <div className="px-8 pt-8 pb-6 border-b" style={{ borderColor: 'var(--border-color)' }}>
          <div className="flex items-center gap-3 mb-5">
            <div className="w-10 h-10 bg-gradient-to-br from-brand-500 to-indigo-500 rounded-xl flex items-center justify-center shadow-md shadow-brand-500/30 flex-shrink-0">
              <span className="font-bold text-base text-white">C</span>
            </div>
            <div>
              <h1 className="text-xl font-bold tracking-tight" style={{ color: 'var(--text-primary)' }}>
                CRM Enterprise
              </h1>
              <p className="text-xs" style={{ color: 'var(--text-muted)' }}>
                Sales & Customer Management
              </p>
            </div>
          </div>
        </div>

        {/* Auth form */}
        <div className="px-8 py-6">
          <Outlet />
        </div>
      </div>

      {/* Footer */}
      <p className="mt-6 text-xs relative z-10" style={{ color: 'var(--text-muted)' }}>
        © {new Date().getFullYear()} CRM Enterprise · Secure Multi-Tenant Platform
      </p>
    </div>
  );
};
