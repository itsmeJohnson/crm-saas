import React from 'react';
import { Navigate, useLocation, matchPath, Outlet } from 'react-router-dom';
import { Loader2, ShieldAlert, Ban, HelpCircle } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';
import { useMetadataStore } from '../../store/metadataStore';
import { MODULES_REGISTRY } from '../../routes/moduleRegistry';

interface ModuleGuardRouteProps {
  moduleKey: string;
}

export const ModuleGuardRoute: React.FC<ModuleGuardRouteProps> = ({ moduleKey }) => {
  const location = useLocation();
  const user = useAuthStore((state) => state.user);
  const features = useAuthStore((state) => state.features);
  
  const { loaded: metadataLoaded, crmConfig } = useMetadataStore();

  // 1. Authenticate user
  if (!user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  // 2. Wait for tenant bootstrap configurations to load
  if (!metadataLoaded) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] text-[var(--text-secondary)]">
        <Loader2 className="w-8 h-8 animate-spin text-cyan-400 mb-4" />
        <span className="text-sm font-medium tracking-wide">Loading workspace configuration...</span>
      </div>
    );
  }

  // 3. Confirm crmConfig is resolved
  if (!crmConfig) {
    return <AccessDeniedView title="Configuration Error" subtitle="The workspace configuration could not be resolved. Please try refreshing or contacting support." icon={HelpCircle} />;
  }

  // 4. Verify module existence in the registry
  const modDef = MODULES_REGISTRY.find((m) => m.key === moduleKey);
  if (!modDef) {
    return <AccessDeniedView title="Module Not Found" subtitle={`The requested module "${moduleKey}" is not registered in the system registry.`} icon={Ban} />;
  }

  // 5. Verify module enabled status for this tenant
  const isEnabled =
    moduleKey === 'admin_core' ||
    moduleKey === 'platform_core' ||
    moduleKey === 'billing' ||
    (crmConfig.enabled_modules && crmConfig.enabled_modules.includes(moduleKey));

  if (!isEnabled) {
    return (
      <AccessDeniedView 
        title="Module Disabled" 
        subtitle={`The "${modDef.label}" module is disabled for your organization. Please ask your administrator to enable it.`} 
        icon={Ban} 
      />
    );
  }

  // 6. Check specific route authorization rules inside the module
  const matchingRoute = modDef.routes.find((r) =>
    matchPath({ path: r.path, end: !r.isNestedRouteContainer }, location.pathname)
  );

  if (matchingRoute && user.role !== 'SuperAdmin') {
    if (matchingRoute.roles && !matchingRoute.roles.includes(user.role)) {
      return <AccessDeniedView title="Access Denied" subtitle="You do not have the required role to view this page." icon={ShieldAlert} />;
    }
    if (matchingRoute.featureCode && !features.includes(matchingRoute.featureCode)) {
      return <AccessDeniedView title="Feature Restricted" subtitle="This feature is not enabled on your current subscription plan." icon={ShieldAlert} />;
    }
  }

  // 7. Success - render the nested route component
  return <Outlet />;
};

interface AccessDeniedViewProps {
  title: string;
  subtitle: string;
  icon: React.ComponentType<any>;
}

const AccessDeniedView: React.FC<AccessDeniedViewProps> = ({ title, subtitle, icon: Icon }) => {
  return (
    <div className="flex items-center justify-center min-h-[70vh] px-4 select-none animate-fade-in">
      <div className="w-full max-w-md p-8 rounded-2xl bg-slate-900/60 border border-slate-800/80 shadow-2xl backdrop-blur-md text-center">
        <div className="w-14 h-14 mx-auto rounded-xl bg-cyan-950/40 border border-cyan-500/20 flex items-center justify-center text-cyan-400 mb-5">
          <Icon className="w-6 h-6" />
        </div>
        <h2 className="text-xl font-bold text-slate-100 tracking-tight mb-2">
          {title}
        </h2>
        <p className="text-sm text-slate-400 leading-relaxed max-w-sm mx-auto mb-6">
          {subtitle}
        </p>
        <button
          onClick={() => window.location.href = '/'}
          className="px-5 py-2.5 rounded-lg bg-cyan-600 hover:bg-cyan-500 text-white font-medium text-xs tracking-wide shadow-lg shadow-cyan-950/50 transition-all duration-150 cursor-pointer"
        >
          Back to Dashboard
        </button>
      </div>
    </div>
  );
};
