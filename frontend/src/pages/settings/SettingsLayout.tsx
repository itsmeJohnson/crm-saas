import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { Settings as SettingsIcon, Phone } from 'lucide-react';

/** Enterprise Settings module. Only Communication → Calling → MyOperator is
 *  functional in this phase; the remaining nodes are placeholders that light up
 *  as those modules land. The whole module is route-gated to SuperAdmin/OrgAdmin. */
const SECTIONS: { title: string; items: { label: string; to?: string; soon?: boolean }[] }[] = [
  { title: 'Organization', items: [
    { label: 'Organization', soon: true }, { label: 'Users & Roles', soon: true },
    { label: 'Departments', to: '/departments' }, { label: 'Teams', to: '/teams' },
  ] },
  { title: 'Communication', items: [
    { label: 'SMS', to: '/sms' }, { label: 'WhatsApp', to: '/whatsapp/settings' },
    { label: 'Calling', to: '/settings/calling' }, { label: 'Email', to: '/email' },
  ] },
  { title: 'Integrations', items: [
    { label: 'Marketplace', to: '/settings/integrations' },
    { label: 'MyOperator', to: '/settings/calling' }, { label: 'Knowlarity', soon: true },
    { label: 'Exotel', soon: true }, { label: 'MSG91', soon: true },
    { label: 'Twilio', soon: true }, { label: 'Gupshup', soon: true },
  ] },
  { title: 'Advanced', items: [
    { label: 'Security', soon: true }, { label: 'API Keys', soon: true },
    { label: 'Subscription', to: '/subscription' }, { label: 'Billing', soon: true },
    { label: 'Audit Logs', soon: true }, { label: 'Branding', soon: true }, { label: 'AI Settings', soon: true },
  ] },
];

export const SettingsLayout: React.FC = () => {
  const [mobileSectionOpen, setMobileSectionOpen] = React.useState(false);

  return (
    <div className="flex flex-col md:flex-row min-h-full">
      {/* Mobile Settings Navigation Header */}
      <div className="md:hidden border-b border-[var(--border-color)] bg-[var(--bg-subtle)] p-3 space-y-2">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2 text-[var(--text-primary)] font-bold text-sm">
            <SettingsIcon className="w-4 h-4 text-indigo-400" /> Settings Menu
          </div>
          <button
            onClick={() => setMobileSectionOpen((prev) => !prev)}
            className="text-xs px-2.5 py-1 rounded-lg border border-[var(--border-color)] bg-[var(--bg-card)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]"
          >
            {mobileSectionOpen ? 'Close Menu' : 'Browse Settings ▾'}
          </button>
        </div>

        {/* Quick mobile horizontal tabs for primary categories */}
        <div className="flex items-center gap-1.5 overflow-x-auto py-1 scrollbar-none text-xs">
          <NavLink
            to="/settings/calling"
            className={({ isActive }) =>
              `shrink-0 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-300 font-semibold'
                  : 'bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`
            }
          >
            Calling / Telephony
          </NavLink>
          <NavLink
            to="/whatsapp/settings"
            className={({ isActive }) =>
              `shrink-0 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-300 font-semibold'
                  : 'bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`
            }
          >
            WhatsApp
          </NavLink>
          <NavLink
            to="/sms"
            className={({ isActive }) =>
              `shrink-0 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-300 font-semibold'
                  : 'bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`
            }
          >
            SMS
          </NavLink>
          <NavLink
            to="/settings/integrations"
            className={({ isActive }) =>
              `shrink-0 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-300 font-semibold'
                  : 'bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`
            }
          >
            Integrations
          </NavLink>
          <NavLink
            to="/subscription"
            className={({ isActive }) =>
              `shrink-0 px-3 py-1.5 rounded-lg border text-xs font-medium transition-colors ${
                isActive
                  ? 'bg-indigo-600/20 border-indigo-500/40 text-indigo-300 font-semibold'
                  : 'bg-[var(--bg-card)] border-[var(--border-color)] text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
              }`
            }
          >
            Subscription
          </NavLink>
        </div>

        {/* Collapsible full menu drawer on mobile */}
        {mobileSectionOpen && (
          <div className="pt-2 border-t border-[var(--border-color)] grid grid-cols-2 gap-3 text-xs">
            {SECTIONS.map((sec) => (
              <div key={sec.title} className="space-y-1">
                <p className="text-[10px] font-bold uppercase tracking-wider text-[var(--text-muted)]">{sec.title}</p>
                {sec.items.map((it) =>
                  it.soon || !it.to ? (
                    <div key={it.label} className="py-1 text-[11px] text-[var(--text-muted)] flex items-center justify-between">
                      <span className="truncate">{it.label}</span>
                      <span className="text-[8px] uppercase bg-slate-800/80 text-slate-500 rounded px-1">soon</span>
                    </div>
                  ) : (
                    <NavLink
                      key={it.label}
                      to={it.to}
                      onClick={() => setMobileSectionOpen(false)}
                      className={({ isActive }) =>
                        `block py-1 text-[11px] truncate transition-colors ${
                          isActive ? 'text-indigo-400 font-semibold' : 'text-[var(--text-secondary)] hover:text-[var(--text-primary)]'
                        }`
                      }
                    >
                      {it.label}
                    </NavLink>
                  )
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Desktop Sidebar */}
      <aside className="hidden md:block w-64 shrink-0 border-r border-[var(--border-color)] bg-[var(--bg-subtle)] p-4 space-y-5">
        <div className="flex items-center gap-2 text-[var(--text-primary)] font-bold px-2">
          <SettingsIcon className="w-5 h-5 text-indigo-400" /> Settings
        </div>
        {SECTIONS.map((sec) => (
          <div key={sec.title} className="space-y-1">
            <p className="text-[10px] font-bold uppercase tracking-widest text-[var(--text-muted)] px-2">{sec.title}</p>
            {sec.items.map((it) =>
              it.soon || !it.to ? (
                <div key={it.label} className="px-3 py-1.5 text-sm text-[var(--text-muted)] cursor-not-allowed flex items-center justify-between">
                  {it.label} <span className="text-[9px] uppercase bg-slate-800/80 text-slate-500 rounded px-1.5 py-0.5">soon</span>
                </div>
              ) : (
                <NavLink
                  key={it.label}
                  to={it.to}
                  className={({ isActive }) =>
                    `block px-3 py-1.5 rounded-lg text-sm transition-colors ${
                      isActive ? 'bg-indigo-600/20 text-indigo-300 font-semibold' : 'text-[var(--text-secondary)] hover:bg-[var(--bg-card-hover)]'
                    }`
                  }
                >
                  {it.label}
                </NavLink>
              )
            )}
          </div>
        ))}
      </aside>

      {/* Main Content Area */}
      <main className="flex-1 min-w-0">
        <Outlet />
      </main>
    </div>
  );
};

/** Landing card when hitting /settings with no sub-page selected. */
export const SettingsHome: React.FC = () => (
  <div className="max-w-2xl mx-auto p-10 text-center space-y-3">
    <div className="w-12 h-12 mx-auto rounded-xl bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400">
      <Phone className="w-6 h-6" />
    </div>
    <h1 className="text-xl font-bold text-slate-100">Organization Settings</h1>
    <p className="text-sm text-slate-400">Configure telephony under <span className="text-indigo-300">Communication → Calling</span>. Credentials are org-level, encrypted, and never exposed to employees.</p>
  </div>
);
