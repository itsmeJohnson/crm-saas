import React from 'react';
import { Link } from 'react-router-dom';
import { Zap, FolderKanban, Users, Building2, Contact } from 'lucide-react';
import { useAuthStore } from '../../store/authStore';

interface QuickAction {
  label: string;
  path: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
  featureCode?: string;
}

const ALL_ACTIONS: QuickAction[] = [
  { label: 'View Leads', path: '/leads', icon: FolderKanban, featureCode: 'LEAD_MANAGEMENT' },
  { label: 'View Contacts', path: '/contacts', icon: Contact, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT' },
  { label: 'View Companies', path: '/companies', icon: Building2, roles: ['OrgAdmin', 'Manager'], featureCode: 'LEAD_MANAGEMENT' },
  { label: 'Manage Team', path: '/users', icon: Users, roles: ['OrgAdmin', 'Manager'], featureCode: 'ROLE_BASED_ACCESS' },
];

export const QuickActionsWidget: React.FC = () => {
  const { user, features } = useAuthStore();
  if (!user) return null;

  const actions = ALL_ACTIONS.filter((action) => {
    if (action.roles && !action.roles.includes(user.role)) return false;
    if (action.featureCode && user.role !== 'SuperAdmin' && !features.includes(action.featureCode)) return false;
    return true;
  });

  if (actions.length === 0) return null;

  return (
    <div className="glass-panel p-6 rounded-2xl border border-slate-800/80">
      <h3 className="text-sm font-bold text-slate-100 mb-4 flex items-center gap-2">
        <Zap className="w-4 h-4 text-brand-400" />
        Quick Actions
      </h3>
      <div className="grid grid-cols-2 gap-2.5">
        {actions.map((action) => (
          <Link
            key={action.path}
            to={action.path}
            className="flex items-center gap-2 px-3 py-2.5 rounded-xl bg-slate-900/60 border border-slate-800 hover:border-brand-500/40 hover:bg-slate-900 text-xs font-semibold text-slate-300 hover:text-slate-100 transition-all"
          >
            <action.icon className="w-3.5 h-3.5 text-brand-400 shrink-0" />
            <span className="truncate">{action.label}</span>
          </Link>
        ))}
      </div>
    </div>
  );
};
