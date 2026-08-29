import React, { Suspense } from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Loader2 } from 'lucide-react';
import { AuthLayout } from './layouts/AuthLayout';
import { AppLayout } from './layouts/AppLayout';
import { ProtectedRoute } from './components/ProtectedRoute';
import { Login } from './modules/auth/Login';
import { Register } from './modules/auth/Register';
import { LegalPage } from './pages/legal/LegalPage';
import { PricingPage } from './pages/PricingPage';
import { LandingPageView } from './pages/LandingPageView';
import { SubscriptionGateRoute } from './components/SubscriptionGateRoute';
import { MODULES_REGISTRY } from './routes/moduleRegistry';
import { ModuleGuardRoute } from './components/common/ModuleGuardRoute';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

export const App: React.FC = () => {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Suspense fallback={
          <div className="flex flex-col items-center justify-center min-h-screen bg-[var(--bg-app)] text-[var(--text-secondary)]">
            <Loader2 className="w-8 h-8 animate-spin text-cyan-400 mb-4" />
            <span className="text-sm font-medium tracking-wide">Loading workspace...</span>
          </div>
        }>
          <Routes>
            {/* Public Routes */}
            <Route element={<AuthLayout />}>
              <Route path="/login" element={<Login />} />
              <Route path="/register" element={<Register />} />
            </Route>

            {/* Public marketing / pricing storefront (no auth) */}
            <Route path="/pricing" element={<PricingPage />} />

            {/* Public landing pages (Website Engine, no auth) */}
            <Route path="/lp/:slug" element={<LandingPageView />} />

            {/* Public legal pages (no auth) */}
            <Route path="/legal/:doc" element={<LegalPage />} />
            <Route path="/legal" element={<LegalPage />} />

            {/* Protected Routes — single shared shell (AppLayout) for the whole app */}
            <Route element={<ProtectedRoute />}>
              <Route element={<AppLayout />}>

                {/* Operational workspace routes: blocked by SubscriptionGate once a
                    tenant's plan lapses */}
                <Route element={<SubscriptionGateRoute />}>
                  {MODULES_REGISTRY.filter(m => m.section === 'workspace').map((mod) => (
                    <Route key={mod.key} element={<ModuleGuardRoute moduleKey={mod.key} />}>
                      {mod.routes.map((r) => {
                        if (r.isNestedRouteContainer && r.nestedRoutes) {
                          return (
                            <Route key={r.path} path={r.path} element={<r.component />}>
                              {r.nestedRoutes.map((nr) => (
                                <Route key={nr.path} index={nr.index} path={nr.path} element={<nr.component />} />
                              ))}
                            </Route>
                          );
                        }
                        return <Route key={r.path} path={r.path} element={<r.component />} />;
                      })}
                    </Route>
                  ))}
                </Route>

                {/* Billing & Account routes (OrgAdmin only) — intentionally OUTSIDE
                    SubscriptionGateRoute so a lapsed tenant can still reactivate. */}
                {MODULES_REGISTRY.filter(m => m.section === 'billing').map((mod) => (
                  <Route key={mod.key} element={<ModuleGuardRoute moduleKey={mod.key} />}>
                    {mod.routes.map((r) => (
                      <Route key={r.path} path={r.path} element={<r.component />} />
                    ))}
                  </Route>
                ))}

              </Route>
            </Route>

            {/* Catch-all */}
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </Suspense>
      </BrowserRouter>
    </QueryClientProvider>
  );
};

export default App;
