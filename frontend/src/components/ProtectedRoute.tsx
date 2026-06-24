import React from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';

interface ProtectedRouteProps {
  allowedRoles?: string[];
  allowTeamLeader?: boolean;
}

export const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ allowedRoles, allowTeamLeader }) => {
  const token = useAuthStore((state) => state.accessToken);
  const user = useAuthStore((state) => state.user);

  if (!token) {
    return <Navigate to="/login" replace />;
  }

  if (allowedRoles && user) {
    const hasRole = allowedRoles.includes(user.role);
    const hasTeamLeaderAccess = allowTeamLeader && user.role === 'Employee' && user.is_team_leader;
    if (!hasRole && !hasTeamLeaderAccess) {
      return <Navigate to="/" replace />;
    }
  }

  return <Outlet />;
};
