import React, { useCallback, useEffect, useState } from 'react';
import {
  Shield, Plus, Loader2, X, Check, Trash2, Pencil, Users, History, SlidersHorizontal,
  ListChecks, Save,
} from 'lucide-react';
import { rolesApi, Role, RoleDetail, RoleCatalog, MatrixCell, RoleUser, PermissionAuditRow } from '../services/rolesApi';
import { userApi } from '../services/userApi';
import { extractErrorMessage } from '../utils/errors';

const SCOPE_LABEL: Record<string, string> = { own: 'Own records', team: 'Team', department: 'Department', all: 'Everything' };

/* ── Create modal ── */
const RoleModal: React.FC<{ catalog: RoleCatalog; onClose: () => void; onSaved: () => void }> = ({ catalog, onClose, onSaved }) => {
  const [form, setForm] = useState({ name: '', description: '', base_role: 'Employee' });
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (!form.name.trim()) { setError('Name is required'); return; }
    setBusy(true); setError(null);
    try { await rolesApi.create(form); onSaved(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to create role')); }
    finally { setBusy(false); }
  };

  const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Shield className="w-4 h-4 text-brand-400" /> New custom role</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Role name" className={F} />
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} placeholder="Description" className={F} />
          <div>
            <p className="text-[11px] text-slate-500 mb-1">Inherits defaults from base role:</p>
            <select value={form.base_role} onChange={(e) => setForm({ ...form, base_role: e.target.value })} className={F}>
              {catalog.base_roles.map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} Create
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Matrix editor ── */
const MatrixEditor: React.FC<{ detail: RoleDetail; catalog: RoleCatalog; onSaved: (d: RoleDetail) => void }> = ({ detail, catalog, onSaved }) => {
  const [matrix, setMatrix] = useState<Record<string, MatrixCell>>({});
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => { setMatrix(JSON.parse(JSON.stringify(detail.matrix || {}))); setDirty(false); }, [detail]);

  const toggle = (resource: string, action: string) => {
    setMatrix((m) => {
      const cell = m[resource] || { actions: {}, scope: 'own' };
      return { ...m, [resource]: { ...cell, actions: { ...cell.actions, [action]: !cell.actions[action] } } };
    });
    setDirty(true);
  };
  const setScope = (resource: string, scope: string) => {
    setMatrix((m) => ({ ...m, [resource]: { ...(m[resource] || { actions: {} }), scope } }));
    setDirty(true);
  };

  const save = async () => {
    setBusy(true); setError(null);
    try { const d = await rolesApi.setMatrix(detail.id, matrix); onSaved(d); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to save matrix')); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-3">
      {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead>
            <tr className="text-left text-[10px] text-slate-500 uppercase">
              <th className="py-2 pr-3">Resource</th>
              {catalog.actions.map((a) => <th key={a} className="py-2 px-1.5 text-center">{a}</th>)}
              <th className="py-2 pl-3">Data scope</th>
            </tr>
          </thead>
          <tbody>
            {catalog.resources.map((r) => {
              const cell = matrix[r] || { actions: {}, scope: 'own' };
              return (
                <tr key={r} className="border-t border-slate-800/50">
                  <td className="py-1.5 pr-3 text-slate-300 font-medium whitespace-nowrap">
                    {r}
                    {catalog.feature_gated[r] && <span className="ml-1 text-[9px] text-slate-600" title={`Requires plan feature ${catalog.feature_gated[r]}`}>◆</span>}
                  </td>
                  {catalog.actions.map((a) => (
                    <td key={a} className="py-1.5 px-1.5 text-center">
                      <input type="checkbox" checked={!!cell.actions[a]} onChange={() => toggle(r, a)} className="cursor-pointer accent-indigo-500" />
                    </td>
                  ))}
                  <td className="py-1.5 pl-3">
                    <select value={cell.scope || 'own'} onChange={(e) => setScope(r, e.target.value)}
                            className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-1 px-1.5 rounded-md text-[11px]">
                      {catalog.scopes.map((s) => <option key={s} value={s}>{SCOPE_LABEL[s] || s}</option>)}
                    </select>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      <button onClick={save} disabled={!dirty || busy} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg disabled:opacity-40 cursor-pointer">
        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Save matrix
      </button>
    </div>
  );
};

/* ── Field permissions editor ── */
const FieldEditor: React.FC<{ detail: RoleDetail; catalog: RoleCatalog; onSaved: (d: RoleDetail) => void }> = ({ detail, catalog, onSaved }) => {
  const resources = Object.keys(catalog.fields);
  const [resource, setResource] = useState(resources[0] || 'leads');
  const [access, setAccess] = useState<Record<string, string>>({});
  const [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const map: Record<string, string> = {};
    detail.field_permissions.filter((f) => f.resource === resource).forEach((f) => { map[f.field_name] = f.access; });
    setAccess(map); setDirty(false);
  }, [detail, resource]);

  const save = async () => {
    setBusy(true); setError(null);
    try {
      const items = Object.entries(access).map(([field_name, a]) => ({ resource, field_name, access: a }));
      const d = await rolesApi.setFieldPermissions(detail.id, items);
      onSaved(d);
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save field permissions')); }
    finally { setBusy(false); }
  };

  return (
    <div className="space-y-3">
      {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      <select value={resource} onChange={(e) => setResource(e.target.value)} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
        {resources.map((r) => <option key={r} value={r}>{r}</option>)}
      </select>
      <div className="space-y-1.5">
        {(catalog.fields[resource] || []).map((f) => (
          <div key={f} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <span className="text-xs text-slate-300">{f}</span>
            <div className="flex gap-1">
              {catalog.field_access.map((a) => (
                <button key={a} onClick={() => { setAccess({ ...access, [f]: a }); setDirty(true); }}
                        className={`px-2 py-0.5 text-[10px] rounded-md border cursor-pointer ${(access[f] || 'write') === a
                          ? a === 'write' ? 'bg-emerald-500/15 text-emerald-400 border-emerald-500/30'
                            : a === 'read' ? 'bg-amber-500/15 text-amber-400 border-amber-500/30'
                              : 'bg-red-500/15 text-red-400 border-red-500/30'
                          : 'bg-slate-800/40 text-slate-500 border-slate-700/40'}`}>
                  {a}
                </button>
              ))}
            </div>
          </div>
        ))}
      </div>
      <button onClick={save} disabled={!dirty || busy} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg disabled:opacity-40 cursor-pointer">
        {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />} Save fields
      </button>
    </div>
  );
};

/* ── Assigned users panel ── */
const UsersPanel: React.FC<{ role: Role; onChanged: () => void }> = ({ role, onChanged }) => {
  const [assigned, setAssigned] = useState<RoleUser[]>([]);
  const [all, setAll] = useState<any[]>([]);
  const [pick, setPick] = useState<Set<string>>(new Set());
  const [adding, setAdding] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => { rolesApi.users(role.id).then(setAssigned).catch(() => {}); }, [role.id]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { userApi.getUsers({ is_active: true, limit: 200 }).then(setAll).catch(() => {}); }, []);

  const assignedIds = new Set(assigned.map((u) => u.id));
  const assignable = all.filter((u) => !assignedIds.has(u.id) && u.role !== 'OrgAdmin' && u.role !== 'SuperAdmin');

  const assign = async () => {
    if (!pick.size) return;
    setError(null);
    try { await rolesApi.assign(role.id, [...pick]); setPick(new Set()); setAdding(false); load(); onChanged(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to assign')); }
  };

  return (
    <div className="space-y-3">
      {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      {adding ? (
        <div className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg space-y-2">
          <div className="max-h-40 overflow-y-auto space-y-1">
            {assignable.map((u) => (
              <label key={u.id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={pick.has(u.id)} onChange={(e) => {
                  const s = new Set(pick); e.target.checked ? s.add(u.id) : s.delete(u.id); setPick(s);
                }} />
                {`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email} <span className="text-slate-600">({u.role})</span>
              </label>
            ))}
            {!assignable.length && <p className="text-xs text-slate-500">No assignable users (OrgAdmins are excluded).</p>}
          </div>
          <div className="flex gap-2">
            <button onClick={assign} className="text-xs text-emerald-400 cursor-pointer">Assign {pick.size ? `(${pick.size})` : ''}</button>
            <button onClick={() => { setAdding(false); setPick(new Set()); }} className="text-xs text-slate-500 cursor-pointer">Cancel</button>
          </div>
        </div>
      ) : (
        <button onClick={() => setAdding(true)} className="inline-flex items-center gap-1.5 text-xs text-brand-400 hover:text-brand-300 cursor-pointer"><Plus className="w-3.5 h-3.5" /> Assign users</button>
      )}
      <ul className="space-y-1.5">
        {assigned.map((u) => (
          <li key={u.id} className="flex items-center justify-between p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
            <div>
              <p className="text-xs text-slate-200">{u.name}</p>
              <p className="text-[10px] text-slate-500">{u.email} · base {u.role}</p>
            </div>
            <button onClick={async () => { await rolesApi.unassign(role.id, [u.id]); load(); onChanged(); }}
                    className="p-1 text-slate-600 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>
          </li>
        ))}
        {!assigned.length && <p className="text-xs text-slate-500">No users hold this role yet.</p>}
      </ul>
    </div>
  );
};

/* ── Audit panel ── */
const AuditPanel: React.FC = () => {
  const [rows, setRows] = useState<PermissionAuditRow[] | null>(null);
  useEffect(() => { rolesApi.audit().then(setRows).catch(() => setRows([])); }, []);
  if (!rows) return <div className="py-4 text-center text-slate-500"><Loader2 className="w-4 h-4 animate-spin inline" /></div>;
  return (
    <ul className="space-y-1.5">
      {rows.map((r) => (
        <li key={r.id} className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
          <div className="flex items-center justify-between">
            <span className="text-slate-200 font-medium">{r.action.replace(/_/g, ' ')}</span>
            <span className="text-[10px] text-slate-500">{new Date(r.created_at).toLocaleString()}</span>
          </div>
          <p className="text-[11px] text-slate-500 mt-0.5">
            by {r.actor_name || 'system'}{r.metadata?.name ? ` · ${r.metadata.name}` : r.metadata?.role ? ` · ${r.metadata.role}` : ''}
            {r.metadata?.changes ? ` · ${Array.isArray(r.metadata.changes) ? r.metadata.changes.length : Object.keys(r.metadata.changes).length} change(s)` : ''}
          </p>
        </li>
      ))}
      {!rows.length && <p className="text-xs text-slate-500">No permission changes recorded yet.</p>}
    </ul>
  );
};

/* ── Page ── */
export const RolesPermissionsPage: React.FC = () => {
  const [catalog, setCatalog] = useState<RoleCatalog | null>(null);
  const [roles, setRoles] = useState<Role[]>([]);
  const [detail, setDetail] = useState<RoleDetail | null>(null);
  const [tab, setTab] = useState<'matrix' | 'fields' | 'users' | 'audit'>('matrix');
  const [creating, setCreating] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async () => {
    try {
      const [cat, list] = await Promise.all([rolesApi.catalog(), rolesApi.list()]);
      setCatalog(cat); setRoles(list);
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to load roles')); }
    finally { setLoading(false); }
  }, []);
  useEffect(() => { load(); }, [load]);

  const open = async (r: Role) => {
    try { setDetail(await rolesApi.get(r.id)); setTab('matrix'); }
    catch (e: any) { setError(extractErrorMessage(e, 'Failed to open role')); }
  };

  const removeRole = async (r: Role) => {
    if (!window.confirm(`Delete role "${r.name}"?`)) return;
    try { await rolesApi.remove(r.id); setDetail(null); load(); }
    catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };

  const rename = async (r: Role) => {
    const name = window.prompt('Role name', r.name);
    if (!name || name === r.name) return;
    try { await rolesApi.update(r.id, { name }); load(); if (detail?.id === r.id) open(r); }
    catch (e: any) { setError(extractErrorMessage(e, 'Rename failed')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex items-center justify-between">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Shield className="w-5 h-5 text-brand-400" /> Roles & Permissions</h1>
        <button onClick={() => setCreating(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New role</button>
      </div>
      <p className="text-xs text-slate-500 max-w-3xl">
        Custom roles overlay the built-in roles (OrgAdmin / Manager / Employee stay authoritative for users without one).
        A new role inherits its base role's defaults; edit the matrix to restrict or extend it. Resources marked ◆ are
        gated by the plan — if the feature is missing, access is denied regardless of the matrix.
      </p>

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
        {/* Roles list */}
        <div className="space-y-2">
          {loading ? (
            <div className="py-8 text-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
          ) : roles.length === 0 ? (
            <p className="text-xs text-slate-500 py-4">No custom roles yet.</p>
          ) : roles.map((r) => (
            <div key={r.id} onClick={() => open(r)}
                 className={`p-3 rounded-xl border cursor-pointer transition ${detail?.id === r.id ? 'border-brand-500/50 bg-brand-500/5' : 'border-slate-800/85 bg-slate-950/30 hover:border-slate-700'}`}>
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm text-slate-200 font-medium truncate">{r.name}</p>
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={(e) => { e.stopPropagation(); rename(r); }} className="p-1 text-slate-600 hover:text-slate-300 cursor-pointer"><Pencil className="w-3 h-3" /></button>
                  <button onClick={(e) => { e.stopPropagation(); removeRole(r); }} className="p-1 text-slate-600 hover:text-red-400 cursor-pointer"><Trash2 className="w-3 h-3" /></button>
                </div>
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5">base {r.base_role} · {r.user_count} user(s) · {r.status}</p>
            </div>
          ))}
        </div>

        {/* Editor */}
        <div className="lg:col-span-3">
          {!detail || !catalog ? (
            <div className="glass-panel border border-slate-800/85 rounded-2xl p-8 text-center text-slate-500 text-sm">Select a role to edit its permission matrix.</div>
          ) : (
            <div className="glass-panel border border-slate-800/85 rounded-2xl p-4 space-y-3">
              <div>
                <h2 className="text-base font-semibold text-slate-100">{detail.name}</h2>
                {detail.description && <p className="text-xs text-slate-500 mt-0.5">{detail.description}</p>}
              </div>
              <div className="flex gap-1 border-b border-slate-800/60">
                {([['matrix', 'Matrix', SlidersHorizontal], ['fields', 'Fields', ListChecks], ['users', 'Users', Users], ['audit', 'Audit', History]] as const).map(([key, label, Icon]) => (
                  <button key={key} onClick={() => setTab(key)}
                          className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
                    <Icon className="w-3.5 h-3.5" /> {label}
                  </button>
                ))}
              </div>
              {tab === 'matrix' && <MatrixEditor detail={detail} catalog={catalog} onSaved={(d) => { setDetail(d); load(); }} />}
              {tab === 'fields' && <FieldEditor detail={detail} catalog={catalog} onSaved={(d) => setDetail(d)} />}
              {tab === 'users' && <UsersPanel role={detail} onChanged={() => { load(); open(detail); }} />}
              {tab === 'audit' && <AuditPanel />}
            </div>
          )}
        </div>
      </div>

      {creating && catalog && <RoleModal catalog={catalog} onClose={() => setCreating(false)} onSaved={() => { setCreating(false); load(); }} />}
    </div>
  );
};
