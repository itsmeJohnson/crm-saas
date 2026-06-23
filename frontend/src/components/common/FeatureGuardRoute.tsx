import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../../store/authStore';

interface FeatureGuardRouteProps {
  featureCode: string;
}

export const FeatureGuardRoute: React.FC<FeatureGuardRouteProps> = ({ featureCode }) => {
  const user = useAuthStore((state) => state.user);
  const features = useAuthStore((state) => state.features);

  if (!user) {
    return <Navigate to="/login" replace />;
  }

  // SuperAdmin bypasses feature constraints
  if (user.role === 'SuperAdmin') {
    return <Outlet />;
  }

  const isEnabled = features.includes(featureCode);

  if (!isEnabled) {
    return <Navigate to="/" replace />;
  }

  return <Outlet />;
};
