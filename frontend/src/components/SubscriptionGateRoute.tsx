import React from 'react';
import { Outlet } from 'react-router-dom';
import { SubscriptionGate } from './SubscriptionGate';

/**
 * Route-level wrapper applying SubscriptionGate to a group of nested routes.
 * Deliberately NOT applied to /portal/* routes, since an OrgAdmin must still be
 * able to reach billing/plans to reactivate a lapsed subscription.
 */
export const SubscriptionGateRoute: React.FC = () => (
  <SubscriptionGate>
    <Outlet />
  </SubscriptionGate>
);
