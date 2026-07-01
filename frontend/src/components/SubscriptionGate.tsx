import React from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { AlertTriangle, CreditCard } from 'lucide-react';

/**
 * Blocks the operational CRM once a tenant's subscription/trial has lapsed.
 *
 * A lapse is detected either from the persisted status ("expired"/"suspended",
 * set by the subscription cron) or, to catch a trial/plan that runs out while
 * the user is still logged in, from a past `subscription_expires_at`. SuperAdmin
 * is never gated. The billing portal lives in a separate layout, so an OrgAdmin
 * can still reach /portal/plans to activate.
 */
export const SubscriptionGate: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { user, organization } = useAuthStore();
  const navigate = useNavigate();

  if (!user || user.role === 'SuperAdmin') {
    return <>{children}</>;
  }

  const status = organization?.subscription_status;
  const expiresAt = organization?.subscription_expires_at;
  const isLapsed =
    status === 'expired' ||
    status === 'suspended' ||
    (!!expiresAt && new Date(expiresAt).getTime() < Date.now());

  if (!isLapsed) {
    return <>{children}</>;
  }

  // Once the cron flips a lapsed trial to "expired" it's indistinguishable from
  // an expired paid plan, so trial-specific copy only shows for a mid-session lapse.
  const wasTrial = status === 'trial';
  const isOrgAdmin = user.role === 'OrgAdmin';

  return (
    <div className="min-h-full flex items-center justify-center p-6">
      <div className="max-w-md w-full glass-panel border border-slate-800 rounded-2xl p-8 text-center space-y-5">
        <div className="w-14 h-14 mx-auto rounded-2xl bg-amber-500/15 border border-amber-500/25 flex items-center justify-center">
          <AlertTriangle className="w-7 h-7 text-amber-400" />
        </div>
        <div className="space-y-2">
          <h2 className="text-xl font-bold text-slate-100">
            {status === 'suspended'
              ? 'Subscription Suspended'
              : wasTrial
                ? 'Trial Period Expired'
                : 'Subscription Expired'}
          </h2>
          <p className="text-sm text-slate-400">
            {status === 'suspended'
              ? 'Your organization’s subscription has been suspended. Please clear any pending dues and activate your plan to continue using the CRM.'
              : 'Your access to the CRM has ended. Kindly activate a subscription plan to continue using the platform.'}
          </p>
        </div>

        {isOrgAdmin ? (
          <button
            onClick={() => navigate('/portal/plans')}
            className="w-full py-3 px-4 bg-brand-500 hover:bg-brand-600 active:bg-brand-700 text-white font-semibold rounded-xl transition-all flex items-center justify-center gap-2 shadow-lg shadow-brand-500/20 cursor-pointer"
          >
            <CreditCard className="w-4 h-4" />
            Activate Subscription
          </button>
        ) : (
          <p className="text-xs text-slate-500 bg-slate-900/60 border border-slate-800 rounded-xl p-3">
            Please contact your organization administrator to renew the subscription.
          </p>
        )}
      </div>
    </div>
  );
};
