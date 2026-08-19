import React, { Suspense, lazy } from 'react';
import { useMetadataStore } from '../../store/metadataStore';
import { useAuthStore } from '../../store/authStore';

const DentalDashboard = lazy(() => import('../../pages/dental/DentalDashboard').then(m => ({ default: m.DentalDashboard })));
const EmployeeDashboard = lazy(() => import('./EmployeeDashboard').then(m => ({ default: m.EmployeeDashboard })));
const AnalyticsDashboard = lazy(() => import('../../components/dashboard/AnalyticsDashboard').then(m => ({ default: m.AnalyticsDashboard })));

export const Home: React.FC = () => {
  const { crmConfig } = useMetadataStore();
  const { user } = useAuthStore();

  const template = crmConfig?.template || 'healthcare_dental';
  const role = user?.role;

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
        {template === 'healthcare_dental' ? (
          <DentalDashboard />
        ) : role === 'Employee' ? (
          <EmployeeDashboard />
        ) : (
          <AnalyticsDashboard />
        )}
      </Suspense>
    </div>
  );
};
