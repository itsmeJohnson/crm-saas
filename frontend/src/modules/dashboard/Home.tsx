import React, { Suspense, lazy } from 'react';
import { useAuthStore } from '../../store/authStore';

const DentalDashboard = lazy(() => import('../../pages/dental/DentalDashboard').then(m => ({ default: m.DentalDashboard })));
const EmployeeDashboard = lazy(() => import('./EmployeeDashboard').then(m => ({ default: m.EmployeeDashboard })));
const SuperAdminTelemetryDashboard = lazy(() => import('./SuperAdminTelemetryDashboard').then(m => ({ default: m.SuperAdminTelemetryDashboard })));

export const Home: React.FC = () => {
  const { user } = useAuthStore();
  const role = user?.role;
  const isSamarthaTenantAdmin = user?.email === 'samarthasankalpa@gmail.com';

  return (
    <div className="space-y-6">
      <Suspense fallback={
        <div className="grid grid-cols-1 md:grid-cols-4 gap-6 animate-pulse">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="h-32 bg-slate-900/60 border border-slate-800 rounded-2xl p-6 space-y-4">
              <div className="h-4 bg-slate-800 rounded w-1/2"></div>
              <div className="h-8 bg-slate-800 rounded w-3/4"></div>
            </div>
          ))}
        </div>
      }>
        {role === 'Employee' || role === 'TeamLeader' ? (
          <EmployeeDashboard />
        ) : (role === 'SuperAdmin' && !isSamarthaTenantAdmin) ? (
          <SuperAdminTelemetryDashboard />
        ) : (
          <DentalDashboard />
        )}
      </Suspense>
    </div>
  );
};
