import React, { useCallback, useEffect, useRef, useState } from 'react';
import {
  Building2, Plus, Loader2, Search, X, Users, Target, Archive, ArchiveRestore, Trash2,
  Pencil, Download, Upload, ChevronRight, Wallet, UserPlus, Check,
} from 'lucide-react';
import { departmentApi, Department, TreeNode, Member, Performance } from '../services/departmentApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const METRICS = ['leads_converted', 'calls_made', 'tasks_completed', 'revenue', 'activities', 'custom'];
const emptyForm = { name: '', code: '', description: '', parent_department_id: '', head_user_id: '', budget: '', budget_period: 'monthly', cost_center: '', color: '', status: 'active' };

const StatusChip: React.FC<{ status: string }> = ({ status }) => (
  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-slate-700/40 text-slate-400 border-slate-600/40'}`}>{status}</span>
);

/* ── Create / edit modal ── */
const DeptModal: React.FC<{ initial?: Department | null; depts: Department[]; users: any[]; onClose: () => void; onSaved: () => void }> = ({ initial, depts, users, onClose, onSaved }) => {
  const [form, setForm] = useState<any>(initial ? {
    name: initial.name, code: initial.code || '', description: initial.description || '',
    parent_department_id: initial.parent_department_id || '', head_user_id: initial.head_user_id || '',
    budget: initial.budget ?? '', budget_period: initial.budget_period || 'monthly',
    cost_center: initial.cost_center || '', color: initial.color || '', status: initial.status,
  } : emptyForm);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const save = async () => {
    if (!form.name.trim()) { setError('Name is required'); return; }
    setBusy(true); setError(null);
    try {
      const payload = {
        name: form.name, code: form.code || undefined, description: form.description || undefined,
        parent_department_id: form.parent_department_id || null, head_user_id: form.head_user_id || null,
        budget: form.budget === '' ? null : parseFloat(form.budget), budget_period: form.budget_period || undefined,
        cost_center: form.cost_center || undefined, color: form.color || undefined, status: form.status,
      };
      if (initial) await departmentApi.update(initial.id, payload);
      else await departmentApi.create(payload);
      onSaved();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
  };

  const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";
  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-lg bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Building2 className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} department</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <div className="grid grid-cols-2 gap-2">
            <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Name" className={F} />
            <input value={form.code} onChange={(e) => setForm({ ...form, code: e.target.value })} placeholder="Code (unique)" className={F} />
          </div>
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} rows={2} placeholder="Description" className={F} />
          <div className="grid grid-cols-2 gap-2">
            <select value={form.parent_department_id} onChange={(e) => setForm({ ...form, parent_department_id: e.target.value })} className={F}>
              <option value="">No parent</option>
              {depts.filter((d) => d.id !== initial?.id).map((d) => <option key={d.id} value={d.id}>{d.name}</option>)}
            </select>
            <select value={form.head_user_id} onChange={(e) => setForm({ ...form, head_user_id: e.target.value })} className={F}>
              <option value="">No head</option>
              {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
            </select>
          </div>
          <div className="grid grid-cols-3 gap-2">
            <input type="number" value={form.budget} onChange={(e) => setForm({ ...form, budget: e.target.value })} placeholder="Budget" className={F} />
            <select value={form.budget_period} onChange={(e) => setForm({ ...form, budget_period: e.target.value })} className={F}>
              {['monthly', 'quarterly', 'yearly'].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
            <input value={form.cost_center} onChange={(e) => setForm({ ...form, cost_center: e.target.value })} placeholder="Cost center" className={F} />
          </div>
          <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Members panel ── */
const MembersPanel: React.FC<{ deptId: string; canManage: boolean; users: any[]; onChanged: () => void }> = ({ deptId, canManage, users, onChanged }) => {
  const [members, setMembers] = useState<Member[]>([]);
  const [adding, setAdding] = useState(false);
  const [pick, setPick] = useState<Set<string>>(new Set());

  const load = useCallback(() => { departmentApi.members(deptId).then(setMembers).catch(() => {}); }, [deptId]);
  useEffect(() => { load(); }, [load]);

  const memberIds = new Set(members.map((m) => m.id));
  const assignable = users.filter((u) => !memberIds.has(u.id));

  const add = async () => {
    if (pick.size) { await departmentApi.assignMembers(deptId, [...pick]); setPick(new Set()); setAdding(false); load(); onChanged(); }
  };
  const remove = async (uid: string) => { await departmentApi.removeMembers(deptId, [uid]); load(); onChanged(); };

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-4">
      <div className="flex items-center justify-between mb-3">
        <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Users className="w-4 h-4 text-brand-400" /> Members ({members.length})</h4>
        {canManage && <button onClick={() => setAdding((a) => !a)} className="inline-flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 cursor-pointer"><UserPlus className="w-3.5 h-3.5" /> Add</button>}
      </div>
      {adding && (
        <div className="mb-3 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
          <div className="max-h-40 overflow-y-auto space-y-1">
            {assignable.length === 0 ? <p className="text-xs text-slate-500 py-2">All users already assigned.</p> : assignable.map((u) => (
              <label key={u.id} className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
                <input type="checkbox" checked={pick.has(u.id)} onChange={() => setPick((s) => { const n = new Set(s); n.has(u.id) ? n.delete(u.id) : n.add(u.id); return n; })} className="w-3.5 h-3.5 rounded" />
                {`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email} <span className="text-slate-600">· {u.role}</span>
              </label>
            ))}
          </div>
          <button onClick={add} disabled={pick.size === 0} className="mt-2 w-full bg-brand-500 text-white text-xs py-1.5 rounded-lg disabled:opacity-40 cursor-pointer">Assign {pick.size || ''}</button>
        </div>
      )}
      {members.length === 0 ? <p className="text-xs text-slate-500">No members.</p> : (
        <ul className="space-y-1">
          {members.map((m) => (
            <li key={m.id} className="flex items-center gap-2 p-1.5 bg-slate-950/40 border border-slate-800/60 rounded-lg text-xs">
              <span className="text-slate-200 flex-1 truncate">{m.name} <span className="text-slate-600">· {m.role}</span></span>
              {canManage && <button onClick={() => remove(m.id)} className="p-0.5 text-slate-500 hover:text-red-400 cursor-pointer"><X className="w-3.5 h-3.5" /></button>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

/* ── Targets + KPIs ── */
const TargetsPanel: React.FC<{ deptId: string; canManage: boolean; refreshKey: number }> = ({ deptId, canManage, refreshKey }) => {
  const [perf, setPerf] = useState<Performance | null>(null);
  const [adding, setAdding] = useState(false);
  const [form, setForm] = useState({ name: '', metric: 'leads_converted', target_value: '', period: 'monthly' });

  const load = useCallback(() => { departmentApi.performance(deptId).then(setPerf).catch(() => {}); }, [deptId]);
  useEffect(() => { load(); }, [load, refreshKey]);

  const add = async () => {
    if (!form.name.trim() || !form.target_value) return;
    await departmentApi.createTarget(deptId, { ...form, target_value: parseFloat(form.target_value) });
    setForm({ name: '', metric: 'leads_converted', target_value: '', period: 'monthly' }); setAdding(false); load();
  };
  const del = async (tid: string) => { await departmentApi.deleteTarget(deptId, tid); load(); };

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-4 space-y-3">
      <div className="flex items-center justify-between">
        <h4 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Target className="w-4 h-4 text-brand-400" /> Targets &amp; KPIs</h4>
        {canManage && <button onClick={() => setAdding((a) => !a)} className="inline-flex items-center gap-1 text-xs text-brand-400 hover:text-brand-300 cursor-pointer"><Plus className="w-3.5 h-3.5" /> Target</button>}
      </div>
      {perf && (
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-2">
          {Object.entries(perf.metrics).map(([k, v]) => (
            <div key={k} className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <p className="text-[9px] text-slate-500 uppercase tracking-wider">{k.replace('_', ' ')}</p>
              <p className="text-base font-bold text-slate-100">{k === 'revenue' ? `₹${v}` : v}</p>
            </div>
          ))}
        </div>
      )}
      {adding && (
        <div className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg grid grid-cols-2 gap-2">
          <input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="Target name" className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded text-xs" />
          <select value={form.metric} onChange={(e) => setForm({ ...form, metric: e.target.value })} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-1.5 px-2 rounded text-xs">
            {METRICS.map((m) => <option key={m} value={m}>{m}</option>)}
          </select>
          <input type="number" value={form.target_value} onChange={(e) => setForm({ ...form, target_value: e.target.value })} placeholder="Target value" className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded text-xs" />
          <button onClick={add} className="bg-brand-500 text-white text-xs rounded cursor-pointer">Add</button>
        </div>
      )}
      {perf && perf.kpis.length > 0 && (
        <ul className="space-y-2">
          {perf.kpis.map((k) => (
            <li key={k.target_id} className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg">
              <div className="flex items-center justify-between text-xs mb-1">
                <span className="text-slate-200">{k.name} <span className="text-slate-500">({k.metric})</span></span>
                <div className="flex items-center gap-2"><span className="text-slate-400">{k.actual} / {k.target_value}</span>{canManage && <button onClick={() => del(k.target_id)} className="text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-3 h-3" /></button>}</div>
              </div>
              <div className="h-1.5 bg-slate-800/60 rounded-full overflow-hidden"><div className={`h-full rounded-full ${k.attainment >= 100 ? 'bg-emerald-500' : 'bg-gradient-to-r from-brand-500 to-indigo-500'}`} style={{ width: `${Math.min(100, k.attainment)}%` }} /></div>
              <p className="text-[10px] text-slate-500 mt-0.5">{k.attainment}% attained</p>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};

const TreeItem: React.FC<{ node: TreeNode; depth: number; onSelect: (id: string) => void; activeId: string | null }> = ({ node, depth, onSelect, activeId }) => (
  <>
    <button onClick={() => onSelect(node.id)} style={{ paddingLeft: `${12 + depth * 16}px` }}
            className={`w-full text-left pr-3 py-2 border-b border-slate-800/40 hover:bg-slate-900/50 cursor-pointer ${activeId === node.id ? 'bg-slate-900/60' : ''}`}>
      <div className="flex items-center gap-1.5">
        {node.children.length > 0 && <ChevronRight className="w-3 h-3 text-slate-600" />}
        <Building2 className="w-3.5 h-3.5 text-slate-400 shrink-0" />
        <span className="text-sm font-medium text-slate-200 truncate flex-1">{node.name}</span>
        <span className="text-[10px] text-slate-500">{node.member_count}</span>
        <StatusChip status={node.status} />
      </div>
    </button>
    {node.children.map((c) => <TreeItem key={c.id} node={c} depth={depth + 1} onSelect={onSelect} activeId={activeId} />)}
  </>
);

export const DepartmentsPage: React.FC = () => {
  const { user } = useAuthStore();
  const canManage = !!user && ['SuperAdmin', 'OrgAdmin'].includes(user.role);

  const [tree, setTree] = useState<TreeNode[]>([]);
  const [flat, setFlat] = useState<Department[]>([]);
  const [users, setUsers] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusF, setStatusF] = useState('');
  const [activeId, setActiveId] = useState<string | null>(null);
  const [detail, setDetail] = useState<Department | null>(null);
  const [showCreate, setShowCreate] = useState(false);
  const [editing, setEditing] = useState<Department | null>(null);
  const [refreshKey, setRefreshKey] = useState(0);
  const fileRef = useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [t, l] = await Promise.all([
        departmentApi.tree(),
        departmentApi.list({ search: search || undefined, status: statusF || undefined }),
      ]);
      setTree(t); setFlat(l.items);
    } finally { setLoading(false); }
  }, [search, statusF]);

  useEffect(() => { const t = setTimeout(load, search ? 300 : 0); return () => clearTimeout(t); }, [load, search]);
  useEffect(() => { if (canManage) userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {}); }, [canManage]);
  useEffect(() => { if (activeId) departmentApi.get(activeId).then(setDetail).catch(() => setDetail(null)); else setDetail(null); }, [activeId, refreshKey]);

  const refresh = () => { setRefreshKey((k) => k + 1); load(); };

  const toggleStatus = async () => { if (detail) { await departmentApi.setStatus(detail.id, detail.status === 'active' ? 'archived' : 'active'); refresh(); } };
  const del = async () => {
    if (!detail || !confirm(`Delete "${detail.name}"?`)) return;
    try { await departmentApi.remove(detail.id); setActiveId(null); load(); }
    catch (e: any) { alert(extractErrorMessage(e, 'Delete failed')); }
  };
  const doExport = async () => {
    const blob = await departmentApi.exportCsv();
    const url = URL.createObjectURL(blob); const a = document.createElement('a');
    a.href = url; a.download = 'departments.csv'; a.click(); URL.revokeObjectURL(url);
  };
  const onImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    try { const r = await departmentApi.importCsv(file); alert(`Imported: ${r.created} created, ${r.updated} updated`); load(); }
    catch (err: any) { alert(extractErrorMessage(err, 'Import failed')); }
    finally { if (fileRef.current) fileRef.current.value = ''; }
  };

  return (
    <div className="space-y-4">
      <div className="border-b border-slate-800/60 pb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <Building2 className="w-7 h-7 text-brand-400" /> Departments
          </h1>
          <p className="text-sm text-slate-400 mt-1">Org units, hierarchy, heads, members, budgets &amp; KPIs.</p>
        </div>
        {canManage && (
          <div className="flex items-center gap-2">
            <input type="file" ref={fileRef} accept=".csv" onChange={onImport} className="hidden" />
            <button onClick={() => fileRef.current?.click()} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-2 px-3 rounded-lg text-sm cursor-pointer"><Upload className="w-4 h-4" /> Import</button>
            <button onClick={doExport} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-2 px-3 rounded-lg text-sm cursor-pointer"><Download className="w-4 h-4" /> Export</button>
            <button onClick={() => setShowCreate(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm cursor-pointer"><Plus className="w-4 h-4" /> New</button>
          </div>
        )}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-210px)] min-h-[520px]">
        {/* Tree */}
        <div className="glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          <div className="p-3 border-b border-slate-800/60 space-y-2">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search…" className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 pl-9 pr-3 rounded-lg text-sm" />
            </div>
            <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-300 py-1.5 px-2 rounded-lg text-xs">
              <option value="">All statuses</option><option value="active">Active</option><option value="archived">Archived</option>
            </select>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
              : (search || statusF) ? (
                flat.length === 0 ? <p className="py-10 text-center text-xs text-slate-500">No departments.</p>
                  : flat.map((d) => (
                    <button key={d.id} onClick={() => setActiveId(d.id)} className={`w-full text-left px-3 py-2 border-b border-slate-800/40 hover:bg-slate-900/50 cursor-pointer ${activeId === d.id ? 'bg-slate-900/60' : ''}`}>
                      <div className="flex items-center gap-2"><Building2 className="w-3.5 h-3.5 text-slate-400" /><span className="text-sm font-medium text-slate-200 truncate flex-1">{d.name}</span><span className="text-[10px] text-slate-500">{d.member_count}</span><StatusChip status={d.status} /></div>
                    </button>
                  ))
              ) : tree.length === 0 ? <p className="py-10 text-center text-xs text-slate-500">No departments yet.</p>
                : tree.map((n) => <TreeItem key={n.id} node={n} depth={0} onSelect={setActiveId} activeId={activeId} />)}
          </div>
        </div>

        {/* Detail */}
        <div className="lg:col-span-2 overflow-y-auto space-y-4 pr-1">
          {!detail ? (
            <div className="glass-panel border border-slate-800/85 rounded-2xl h-full flex items-center justify-center text-slate-500 text-sm">
              <div className="text-center"><Building2 className="w-10 h-10 mx-auto mb-2 text-slate-600" />Select a department</div>
            </div>
          ) : (
            <>
              <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2">{detail.name} {detail.code && <span className="text-xs text-slate-500">· {detail.code}</span>}</h2>
                    <div className="flex items-center gap-2 mt-1"><StatusChip status={detail.status} /><span className="text-xs text-slate-500">{detail.member_count} members</span>{detail.head_name && <span className="text-xs text-slate-400">Head: {detail.head_name}</span>}</div>
                    {detail.description && <p className="text-xs text-slate-400 mt-2">{detail.description}</p>}
                  </div>
                  {canManage && (
                    <div className="flex items-center gap-1.5 shrink-0">
                      <button onClick={() => setEditing(detail)} title="Edit" className="p-2 rounded-lg text-slate-400 hover:text-brand-400 border border-slate-700/60 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                      <button onClick={toggleStatus} title={detail.status === 'active' ? 'Archive' : 'Activate'} className="p-2 rounded-lg text-slate-400 hover:text-amber-400 border border-slate-700/60 cursor-pointer">{detail.status === 'active' ? <Archive className="w-4 h-4" /> : <ArchiveRestore className="w-4 h-4" />}</button>
                      <button onClick={del} title="Delete" className="p-2 rounded-lg text-slate-400 hover:text-red-400 border border-slate-700/60 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                    </div>
                  )}
                </div>
                {detail.budget != null && (
                  <div className="flex items-center gap-2 mt-3 text-sm"><Wallet className="w-4 h-4 text-emerald-400" /><span className="text-slate-300">₹{detail.budget.toLocaleString()}</span><span className="text-[11px] text-slate-500">/ {detail.budget_period}</span>{detail.cost_center && <span className="text-[11px] text-slate-500">· {detail.cost_center}</span>}</div>
                )}
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <MembersPanel deptId={detail.id} canManage={canManage} users={users} onChanged={refresh} />
                <TargetsPanel deptId={detail.id} canManage={canManage} refreshKey={refreshKey} />
              </div>
            </>
          )}
        </div>
      </div>

      {showCreate && <DeptModal depts={flat} users={users} onClose={() => setShowCreate(false)} onSaved={() => { setShowCreate(false); refresh(); }} />}
      {editing && <DeptModal initial={editing} depts={flat} users={users} onClose={() => setEditing(null)} onSaved={() => { setEditing(null); refresh(); }} />}
    </div>
  );
};
