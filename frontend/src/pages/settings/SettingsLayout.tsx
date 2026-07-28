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
    { label: 'SMS', to: '/sms' }, { label: 'WhatsApp', to: '/whatsapp' },
    { label: 'Calling', to: '/settings/calling' }, { label: 'Email', to: '/email' },
  ] },
  { title: 'Integrations', items: [
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

export const SettingsLayout: React.FC = () => (
  <div className="flex min-h-full">
    <aside className="w-64 shrink-0 border-r border-slate-800 bg-slate-950/40 p-4 space-y-5">
      <div className="flex items-center gap-2 text-slate-100 font-bold px-2">
        <SettingsIcon className="w-5 h-5 text-indigo-400" /> Settings
      </div>
      {SECTIONS.map((sec) => (
        <div key={sec.title} className="space-y-1">
          <p className="text-[10px] font-bold uppercase tracking-widest text-slate-500 px-2">{sec.title}</p>
          {sec.items.map((it) => it.soon || !it.to ? (
            <div key={it.label} className="px-3 py-1.5 text-sm text-slate-600 cursor-not-allowed flex items-center justify-between">
              {it.label} <span className="text-[9px] uppercase bg-slate-800 text-slate-500 rounded px-1.5 py-0.5">soon</span>
            </div>
          ) : (
            <NavLink key={it.label} to={it.to}
              className={({ isActive }) => `block px-3 py-1.5 rounded-lg text-sm transition-colors ${isActive ? 'bg-indigo-600/20 text-indigo-300 font-semibold' : 'text-slate-300 hover:bg-slate-800/60'}`}>
              {it.label}
            </NavLink>
          ))}
        </div>
      ))}
    </aside>
    <main className="flex-1 min-w-0"><Outlet /></main>
  </div>
);

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
