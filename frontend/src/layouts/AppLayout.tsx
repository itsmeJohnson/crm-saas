import React, { useState, useEffect } from 'react';
import { Outlet, useNavigate, Link, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/authStore';
import { useThemeStore } from '../store/themeStore';
import { useMetadataStore } from '../store/metadataStore';
import { MODULES_REGISTRY } from '../routes/moduleRegistry';
import {
  LogOut, Sun, Moon, Menu, X, ChevronDown,
  Stethoscope, Building, FolderKanban, Receipt, LayoutDashboard, PhoneCall
} from 'lucide-react';
import { InboundCallPopup } from '../components/crm/InboundCallPopup';
import { WhatsAppLiveNotifier } from '../components/communications/WhatsAppLiveNotifier';
import { ReadOnlyBanner } from '../components/common/ReadOnlyBanner';
import { NotificationBell } from '../components/notifications/NotificationBell';
import { ActiveCallDisposition } from '../components/crm/ActiveCallDisposition';
import { CallbackTakeoverModal } from '../components/crm/CallbackTakeoverModal';
import { useBrowserNotifications } from '../hooks/useBrowserNotifications';
import { TELECALLING_NAV_GROUPS, TELECALLING_ITEM_GROUP_MAP, isTelecallingMode } from '../config/navigation';
import { api } from '../services/api';
import { useDialerStore } from '../store/dialerStore';
import { whatsappRealtime } from '../services/whatsappRealtime';

export const AppLayout: React.FC = () => {
  const { user, organization, logout } = useAuthStore();
  const { theme, toggleTheme } = useThemeStore();
  const navigate = useNavigate();
  useBrowserNotifications(!!user);
  const location = useLocation();
  const [isMobileOpen, setIsMobileOpen] = useState(false);

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  const { loaded: metadataLoaded, fetchBootstrap, crmConfig } = useMetadataStore();

  useEffect(() => {
    if (user && !metadataLoaded) {
      fetchBootstrap().catch(() => {});
    }
  }, [user, metadataLoaded, fetchBootstrap]);

  // Sync latest user role & profile from database reactively
  useEffect(() => {
    if (user) {
      api.get('/auth/me').then((res) => {
        const freshUser = res.data?.user || (res.data?.role ? res.data : null);
        if (freshUser && freshUser.role) {
          const targetRole = (freshUser.email === 'samarthasankalpa@gmail.com' && freshUser.role === 'SuperAdmin')
            ? 'OrgAdmin'
            : freshUser.role;
          const merged = { ...user, ...freshUser, role: targetRole };
          if (merged.role !== user.role || merged.email !== user.email) {
            useAuthStore.setState({ user: merged });
            try {
              localStorage.setItem('user', JSON.stringify(merged));
            } catch {}
          }
        }
      }).catch(() => {});
    }
  }, [user]);

  // Strategy A (Web Persistence): Accidental Refresh / Navigation Guard
  useEffect(() => {
    const handleBeforeUnload = (e: BeforeUnloadEvent) => {
      const activeLifecycle = useDialerStore.getState().callLifecycle;
      if (
        activeLifecycle === 'initiating' ||
        activeLifecycle === 'ringing' ||
        activeLifecycle === 'connected' ||
        activeLifecycle === 'disposition'
      ) {
        e.preventDefault();
        e.returnValue = 'A call is currently in progress or wrap-up disposition notes are pending. Refreshing or leaving will disconnect your session.';
        return e.returnValue;
      }
    };

    window.addEventListener('beforeunload', handleBeforeUnload);
    return () => {
      window.removeEventListener('beforeunload', handleBeforeUnload);
    };
  }, []);

  // Strategy A (Web Persistence): Recover dialer active call state & initialize WebRTC/WS on app load
  useEffect(() => {
    if (user?.id) {
      whatsappRealtime.connect(user.id);
      useDialerStore.getState().fetchCurrentState().catch(() => {});
      useDialerStore.getState().initWebRTC().catch(() => {});
    }
  }, [user?.id]);

  const TRIAL_MODE = true;
  const inTelecalling = isTelecallingMode();
  const effectiveRole = (user?.email === 'samarthasankalpa@gmail.com' && user?.role === 'SuperAdmin')
    ? 'OrgAdmin'
    : (user?.role ?? 'Staff');
  const isBaselineTelecaller = effectiveRole === 'Employee' && !user?.is_team_leader;
  const isSuperAdmin = effectiveRole === 'SuperAdmin' && user?.email !== 'samarthasankalpa@gmail.com';
  const isManagerOrTL = effectiveRole === 'Manager' || effectiveRole === 'TeamLeader' || (effectiveRole === 'Employee' && user?.is_team_leader);

  const TELECALLER_ALLOWED_ITEMS = new Set([
    'Leads & Enquiries',
    'Phone Calling',
    'WhatsApp Center',
    'Communications',
    'Tasks & Reminders',
  ]);

  const SUPERADMIN_HIDDEN_ITEMS = new Set([
    // Dialer Console items: SuperAdmins do not dial leads or text customers
    'Phone Calling',
    'WhatsApp Center',
    'Communications',
    'Voice Broadcast',
    // Local agency layout tabs under Campaign Analytics
    'Marketing ROI',
    'Sales Analytics',
    // Local operations clutter
    'Leads & Enquiries',
    'Contacts Directory',
    'Lead Capture',
    'Websites',
    'Email Sequences',
    'Booking Links',
    'Pipelines',
    'Tasks & Reminders',
    'Staff & Team',
    'Custom Objects',
    'Dynamic Forms',
    'Attendance',
    'Leaves',
    'Shifts',
    'Performance',
    'Targets',
    'Approvals',
    'Billing & Invoices',
  ]);

  const NAV_GROUPS = (inTelecalling || isBaselineTelecaller || isSuperAdmin || isManagerOrTL)
    ? TELECALLING_NAV_GROUPS
    : [
        'Clinical Operations', 'Patient Engagement', 'Clinic Management',
        'Growth & Analytics', 'Administration'
      ];

  const allNavItems = MODULES_REGISTRY.flatMap((mod) =>
    mod.routes
      .filter((r) => r.sidebar)
      .map((r) => {
        const rawItemName = r.sidebar!.name;
        const itemName = (rawItemName === 'Global Settings' && !isSuperAdmin)
          ? 'Settings'
          : rawItemName;
        const resolvedGroup = (inTelecalling || isBaselineTelecaller || isSuperAdmin || isManagerOrTL)
          ? (TELECALLING_ITEM_GROUP_MAP[itemName] || r.sidebar!.group || mod.group)
          : (r.sidebar!.group || mod.group);
        return {
          name: itemName,
          path: r.path,
          icon: r.sidebar!.icon || mod.icon,
          section: mod.section,
          group: resolvedGroup,
          trial: mod.trial,
          module: mod.key,
          roles: r.roles,
          featureCode: r.featureCode,
        };
      })
  );

  const features = useAuthStore((state) => state.features);

  const navItems = allNavItems.filter((item) => {
    if (!user) return false;

    // Platform administration section is reserved for SuperAdmin only
    if (
      (item.group === 'Platform' || item.group === 'Platform Administration' || item.module === 'platform_core') &&
      !isSuperAdmin
    ) {
      return false;
    }

    // SuperAdmin filtering: hide cold calling and operational clutter
    if (isSuperAdmin) {
      if (SUPERADMIN_HIDDEN_ITEMS.has(item.name)) return false;
    }

    // Baseline Telecaller restriction (Telecaller Employee role)
    if (isBaselineTelecaller) {
      if (!TELECALLER_ALLOWED_ITEMS.has(item.name)) return false;
    }

    // Manager / TeamLeader restriction: hide Global Settings (Settings layout is for SuperAdmin / OrgAdmin)
    if (isManagerOrTL && item.name === 'Global Settings') {
      return false;
    }

    if (item.roles) {
      const hasRole = isSuperAdmin || item.roles.includes(effectiveRole);
      const isTeamLeaderUsers = item.name === 'Staff & Team' && effectiveRole === 'Employee' && user.is_team_leader;
      if (!hasRole && !isTeamLeaderUsers) return false;
    }
    if (item.featureCode && !isSuperAdmin) {
      if (!features.includes(item.featureCode)) return false;
    }
    if (TRIAL_MODE && !isSuperAdmin && item.section !== 'billing' && !item.trial) {
      return false;
    }
    // Hide dental/clinical-only modules when the workspace is not that industry —
    // applies to everyone INCLUDING SuperAdmin (whose module gating is otherwise
    // bypassed below), so the owner's generic CRM has no medical leftovers.
    const DENTAL_ONLY = ['patients', 'appointments', 'treatments', 'treatment_plans', 'recall', 'dentists', 'clinical_reports'];
    if (item.module && (crmConfig?.industry || 'telecalling') !== 'healthcare_dental' && DENTAL_ONLY.includes(item.module)) {
      return false;
    }
    // Gating by resolved modules config
    if (crmConfig && item.module && !isSuperAdmin) {
      const alwaysEnabled = item.module === 'admin_core' || item.module === 'platform_core' || item.module === 'billing';
      if (!alwaysEnabled && !crmConfig.enabled_modules.includes(item.module)) return false;
    }
    return true;
  });

  const billingItems = navItems.filter((item) => item.section === 'billing');

  const groupedWorkspace = NAV_GROUPS
    .map((group) => ({
      group,
      items: navItems.filter((item) => item.section === 'workspace' && (item as any).group === group),
    }))
    .filter((g) => g.items.length > 0);

  const [collapsedGroups, setCollapsedGroups] = useState<Set<string>>(new Set());
  const toggleGroup = (group: string) =>
    setCollapsedGroups((prev) => {
      const next = new Set(prev);
      next.has(group) ? next.delete(group) : next.add(group);
      return next;
    });

  const initials = [user?.first_name?.[0], user?.last_name?.[0]]
    .filter(Boolean)
    .join('')
    .toUpperCase() || 'D';

  // Dynamic Configuration Mapping based on template industry
  const industry = crmConfig?.industry || 'telecalling';

  const groupTranslations: Record<string, Record<string, string>> = {
    healthcare_dental: {
      'Clinical Operations': 'Clinical Operations',
      'Patient Engagement': 'Patient Engagement',
      'Clinic Management': 'Clinic Management',
    },
    real_estate: {
      'Clinical Operations': 'Property Operations',
      'Patient Engagement': 'Client Engagement',
      'Clinic Management': 'Agency Management',
    },
    insurance: {
      'Clinical Operations': 'Policy Operations',
      'Patient Engagement': 'Client Engagement',
      'Clinic Management': 'Agency Management',
    },
    loan_recovery: {
      'Clinical Operations': 'Portfolio Operations',
      'Patient Engagement': 'Debtor Engagement',
      'Clinic Management': 'Collections Management',
    },
    telecalling: {
      'Clinical Operations': 'Call Center Operations',
      'Patient Engagement': 'Campaigns & Outreach',
      'Clinic Management': 'Call Center Management',
    },
    generic: {
      'Clinical Operations': 'Sales Operations',
      'Patient Engagement': 'Client Engagement',
      'Clinic Management': 'Workspace Management',
    }
  };

  const itemTranslations: Record<string, Record<string, string>> = {
    healthcare_dental: {
      'Patients Directory': 'Patients Directory',
      'Dentists & Surgeons': 'Dentists & Surgeons',
      'Treatment Plans': 'Treatment Plans',
      'Treatment Master': 'Treatment Master',
      'Clinical Reports': 'Clinical Reports',
      'Clinic Settings': 'Clinic Settings',
    },
    real_estate: {
      'Patients Directory': 'Contacts Directory',
      'Dentists & Surgeons': 'Agents & Brokers',
      'Treatment Plans': 'Property Deals',
      'Treatment Master': 'Services Master',
      'Clinical Reports': 'Performance Reports',
      'Clinic Settings': 'Agency Settings',
    },
    insurance: {
      'Patients Directory': 'Policyholders Directory',
      'Dentists & Surgeons': 'Agents & Underwriters',
      'Treatment Plans': 'Insurance Policies',
      'Treatment Master': 'Coverage Master',
      'Clinical Reports': 'Loss Reports',
      'Clinic Settings': 'Agency Settings',
    },
    loan_recovery: {
      'Patients Directory': 'Debtors Directory',
      'Dentists & Surgeons': 'Recovery Officers',
      'Treatment Plans': 'Payment Agreements',
      'Treatment Master': 'Recovery Catalogs',
      'Clinical Reports': 'Collections Reports',
      'Clinic Settings': 'Portfolio Settings',
    },
    telecalling: {
      'Patients Directory': 'Contacts Directory',
      'Dentists & Surgeons': 'Telecallers',
      'Treatment Plans': 'Deals',
      'Treatment Master': 'Product Catalog',
      'Clinical Reports': 'Call Reports',
      'Clinic Settings': 'Call Center Settings',
      'Follow-ups & Recalls': 'Follow-ups',
      'Appointments': 'Meetings',
    },
    generic: {
      'Patients Directory': 'Contacts Directory',
      'Dentists & Surgeons': 'Staff Directory',
      'Treatment Plans': 'Sales Deals',
      'Treatment Master': 'Product Catalog',
      'Clinical Reports': 'Sales Reports',
      'Clinic Settings': 'Workspace Settings',
      'Follow-ups & Recalls': 'Follow-ups',
      'Appointments': 'Meetings',
    }
  };

  const roleLabel: Record<string, Record<string, string>> = {
    healthcare_dental: {
      SuperAdmin: 'Super Admin',
      OrgAdmin: 'Practice Admin',
      Manager: 'Clinic Manager',
      Employee: user?.is_team_leader ? 'Lead Dentist' : 'Attending Dentist',
    },
    real_estate: {
      SuperAdmin: 'Super Admin',
      OrgAdmin: 'Agency Owner',
      Manager: 'Agency Manager',
      Employee: user?.is_team_leader ? 'Lead Agent' : 'Sales Agent',
    },
    insurance: {
      SuperAdmin: 'Super Admin',
      OrgAdmin: 'Agency Owner',
      Manager: 'Agency Manager',
      Employee: user?.is_team_leader ? 'Lead Underwriter' : 'Insurance Agent',
    },
    telecalling: {
      SuperAdmin: 'Super Admin',
      OrgAdmin: 'Org Admin',
      Manager: 'Floor Manager',
      Employee: user?.is_team_leader ? 'Team Lead' : 'Telecaller',
    },
    generic: {
      SuperAdmin: 'Super Admin',
      OrgAdmin: 'Org Admin',
      Manager: 'Manager',
      Employee: user?.is_team_leader ? 'Lead Employee' : 'Staff Member',
    }
  };

  const getGroupName = (g: string) => (inTelecalling || isBaselineTelecaller || isSuperAdmin || isManagerOrTL) ? g : ((groupTranslations[industry] ?? groupTranslations['generic'])[g] ?? g);
  const getItemName = (n: string) => (itemTranslations[industry] ?? itemTranslations['generic'])[n] ?? n;
  const getSubSuiteLabel = () => {
    switch (industry) {
      case 'healthcare_dental': return 'Dental Practice Suite';
      case 'real_estate': return 'Real Estate Brokerage';
      case 'insurance': return 'Insurance Agency Suite';
      case 'loan_recovery': return 'Debt Collection Suite';
      case 'telecalling': return 'Telecalling Suite';
      default: return 'Business Workspace';
    }
  };

  const BrandIcon = () => {
    switch (industry) {
      case 'healthcare_dental': return <Stethoscope className="w-4 h-4" />;
      case 'real_estate': return <Building className="w-4 h-4" />;
      case 'insurance': return <FolderKanban className="w-4 h-4" />;
      case 'loan_recovery': return <Receipt className="w-4 h-4" />;
      case 'telecalling': return <PhoneCall className="w-4 h-4" />;
      default: return <LayoutDashboard className="w-4 h-4" />;
    }
  };

  const displayRole = (roleLabel[industry] ?? roleLabel['generic'])[effectiveRole] ?? effectiveRole;

  const sidebarContent = (
    <div className="flex flex-col h-full select-none">
      {/* ── Minimalist Brand Header ── */}
      <div className="flex items-center justify-between px-4 py-4 border-b border-[var(--border-color)]">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-indigo-500/15 border border-indigo-500/30 flex items-center justify-center text-indigo-400 font-bold flex-shrink-0">
            {BrandIcon()}
          </div>
          <div className="min-w-0">
            <span className="font-bold text-sm tracking-tight text-[var(--text-primary)] block truncate">
              {isSuperAdmin
                ? 'CRM Enterprise · Secure Multi-Tenant Platform'
                : (organization?.name || 'Samartha Sankalpa Solutions')}
            </span>
            <span className="text-[10px] text-[var(--text-muted)] font-medium tracking-wide block">
              {isSuperAdmin
                ? 'System Infrastructure & Multi-Tenant Control'
                : 'Telecalling Suite'}
            </span>
          </div>
        </div>
        <button
          onClick={() => setIsMobileOpen(false)}
          className="md:hidden p-1 rounded-lg text-[var(--text-muted)] hover:text-[var(--text-primary)]"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* ── Navigation Tree ── */}
      <nav className="flex-1 overflow-y-auto px-2.5 py-3 space-y-3">
        {groupedWorkspace.map(({ group, items }) => {
          const isCollapsed = collapsedGroups.has(group);
          const groupActive = items.some((item) =>
            location.pathname === item.path ||
            (item.path !== '/' && location.pathname.startsWith(item.path)));
          return (
            <div key={group} className="space-y-0.5">
              <button
                onClick={() => toggleGroup(group)}
                className="w-full flex items-center justify-between px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500 hover:text-slate-300 transition-colors"
              >
                <span className={groupActive ? 'text-indigo-400 font-bold' : ''}>{getGroupName(group)}</span>
                <ChevronDown className={`w-3 h-3 transition-transform duration-150 ${isCollapsed ? '-rotate-90' : ''}`} />
              </button>
              {!isCollapsed && (
                <div className="space-y-0.5">
                  {items.map((item) => {
                    const Icon = item.icon;
                    const isActive = location.pathname === item.path ||
                      (item.path !== '/' && location.pathname.startsWith(item.path));
                    return (
                      <Link
                        key={item.name}
                        to={item.path}
                        onClick={() => setIsMobileOpen(false)}
                        className={`crm-nav-item ${isActive ? 'crm-nav-item--active' : ''}`}
                      >
                        <Icon className={`w-4 h-4 flex-shrink-0 transition-colors ${isActive ? 'text-indigo-400' : 'text-slate-400'}`} />
                        <span className="truncate">{getItemName(item.name)}</span>
                      </Link>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}

        {billingItems.length > 0 && (
          <div className="space-y-0.5 pt-2 border-t border-[var(--border-color)]">
            <p className="px-2 py-1 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
              Billing &amp; Account
            </p>
            {billingItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path ||
                (item.path !== '/' && location.pathname.startsWith(item.path));
              return (
                <Link
                  key={item.name}
                  to={item.path}
                  onClick={() => setIsMobileOpen(false)}
                  className={`crm-nav-item ${isActive ? 'crm-nav-item--active' : ''}`}
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  <span className="truncate">{item.name}</span>
                </Link>
              );
            })}
          </div>
        )}
      </nav>

      {/* ── User Footer Card ── */}
      <div className="p-3 border-t border-[var(--border-color)]">
        <div className="flex items-center gap-2.5 p-2 rounded-lg bg-[var(--bg-subtle)] border border-[var(--border-color)]">
          <div className="w-8 h-8 rounded-md bg-cyan-500/20 text-cyan-400 border border-cyan-500/30 flex items-center justify-center text-xs font-bold flex-shrink-0">
            {initials}
          </div>
          <div className="overflow-hidden flex-1 min-w-0">
            <p className="text-xs font-semibold text-[var(--text-primary)] truncate leading-tight">
              {user?.first_name} {user?.last_name}
            </p>
            <p className="text-[10px] text-[var(--text-muted)] truncate mt-0.5">
              {displayRole}
            </p>
          </div>
          <button
            onClick={handleLogout}
            title="Sign Out"
            className="p-1.5 rounded text-[var(--text-muted)] hover:text-rose-400 hover:bg-rose-500/10 transition-colors"
          >
            <LogOut className="w-3.5 h-3.5" />
          </button>
        </div>
      </div>
    </div>
  );

  return (
    <div className="flex h-screen overflow-hidden flex-col md:flex-row bg-[var(--bg-app)] text-[var(--text-primary)]">
      <ReadOnlyBanner />
      <InboundCallPopup />
      <WhatsAppLiveNotifier />
      <ActiveCallDisposition />
      <CallbackTakeoverModal />

      {/* ── Desktop Minimalist Sidebar ── */}
      <aside className="hidden md:flex md:w-56 crm-sidebar flex-col z-20 flex-shrink-0">
        {sidebarContent}
      </aside>

      {/* ── Mobile Drawer ── */}
      {isMobileOpen && (
        <div className="fixed inset-0 z-30 md:hidden flex">
          <div
            className="absolute inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setIsMobileOpen(false)}
          />
          <aside className="relative w-60 crm-sidebar shadow-2xl flex flex-col h-full z-10">
            {sidebarContent}
          </aside>
        </div>
      )}

      {/* ── Main Viewport ── */}
      <div className="flex-1 flex flex-col overflow-hidden min-w-0">
        {/* Top Minimalist Header */}
        <header className="flex items-center justify-between px-6 py-2.5 border-b border-[var(--border-color)] bg-[var(--bg-surface)] z-10">
          <div className="flex items-center gap-3">
            <button
              onClick={() => setIsMobileOpen(true)}
              className="md:hidden p-1.5 rounded-lg border border-[var(--border-color)] text-[var(--text-muted)]"
            >
              <Menu className="w-4 h-4" />
            </button>
            <div className="hidden sm:flex items-center gap-2">
              <span className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-[11px] font-medium bg-emerald-500/10 text-emerald-400 border border-emerald-500/20">
                <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
                {industry === 'healthcare_dental' ? 'Live OPD' : 'Live'}
              </span>
              <span className="text-xs text-[var(--text-secondary)]">
                {industry === 'healthcare_dental' ? 'Dr. Johnson Dev • Main Operatory' : `${displayRole} • ${getSubSuiteLabel()}`}
              </span>
            </div>
          </div>

          <div className="flex items-center gap-2">
            <button
              onClick={toggleTheme}
              title={`Switch to ${theme === 'dark' ? 'light' : 'dark'} theme`}
              className="p-1.5 rounded-lg border border-[var(--border-color)] hover:bg-[var(--bg-card-hover)] text-[var(--text-secondary)] hover:text-[var(--text-primary)] transition"
            >
              {theme === 'dark' ? <Sun className="w-4 h-4 text-amber-400" /> : <Moon className="w-4 h-4 text-indigo-400" />}
            </button>
            <NotificationBell />
          </div>
        </header>

        {/* Minimalist Canvas */}
        <main className="flex-1 overflow-y-auto bg-[var(--bg-app)]">
          <div className="p-4 md:p-6 min-h-full max-w-[1600px] mx-auto">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  );
};

export default AppLayout;
