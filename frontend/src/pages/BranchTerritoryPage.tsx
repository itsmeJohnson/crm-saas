import React, { useCallback, useEffect, useState } from 'react';
import {
  Building, MapPin, Map, Plus, Loader2, Search, X, Check, Trash2, Pencil, Download, Upload,
  Network, BarChart3, Crown, Star,
} from 'lucide-react';
import {
  branchApi, Branch, Territory, TerritoryTreeNode, Pincode, BranchDashboard,
  BranchAnalyticsRow, TerritoryAnalyticsRow,
} from '../services/branchApi';
import { userApi } from '../services/userApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const LEVELS = ['region', 'zone', 'city', 'area'];
const StatusChip: React.FC<{ status: string }> = ({ status }) => (
  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${status === 'active' ? 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20' : 'bg-slate-700/40 text-slate-400 border-slate-600/40'}`}>{status}</span>
);
const F = "w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm";

/* ── Branch modal ── */
const BranchModal: React.FC<{ initial?: Branch | null; territories: Territory[]; users: any[]; onClose: () => void; onSaved: () => void }> =
  ({ initial, territories, users, onClose, onSaved }) => {
    const [f, setF] = useState<any>(initial ? { ...initial } : {
      name: '', code: '', branch_manager_id: '', territory_id: '', address_line: '', city: '',
      state: '', country: '', pin_code: '', phone: '', email: '', is_head_office: false, status: 'active',
    });
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const save = async () => {
      if (!f.name?.trim()) { setError('Name is required'); return; }
      setBusy(true); setError(null);
      try {
        const payload = {
          name: f.name, code: f.code || undefined, branch_manager_id: f.branch_manager_id || null,
          territory_id: f.territory_id || null, address_line: f.address_line || undefined,
          city: f.city || undefined, state: f.state || undefined, country: f.country || undefined,
          pin_code: f.pin_code || undefined, phone: f.phone || undefined, email: f.email || undefined,
          is_head_office: !!f.is_head_office, status: f.status,
        };
        if (initial) await branchApi.updateBranch(initial.id, payload);
        else await branchApi.createBranch(payload);
        onSaved();
      } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
    };
    return (
      <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
        <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-lg bg-slate-900 max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Building className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} branch</h3>
            <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
          </div>
          <div className="p-4 space-y-3">
            {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
            <div className="grid grid-cols-2 gap-2">
              <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className={F} />
              <input value={f.code || ''} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="Code" className={F} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select value={f.branch_manager_id || ''} onChange={(e) => setF({ ...f, branch_manager_id: e.target.value })} className={F}>
                <option value="">No branch manager</option>
                {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
              </select>
              <select value={f.territory_id || ''} onChange={(e) => setF({ ...f, territory_id: e.target.value })} className={F}>
                <option value="">No territory</option>
                {territories.map((t) => <option key={t.id} value={t.id}>{t.name} ({t.level})</option>)}
              </select>
            </div>
            <input value={f.address_line || ''} onChange={(e) => setF({ ...f, address_line: e.target.value })} placeholder="Address" className={F} />
            <div className="grid grid-cols-3 gap-2">
              <input value={f.city || ''} onChange={(e) => setF({ ...f, city: e.target.value })} placeholder="City" className={F} />
              <input value={f.state || ''} onChange={(e) => setF({ ...f, state: e.target.value })} placeholder="State" className={F} />
              <input value={f.pin_code || ''} onChange={(e) => setF({ ...f, pin_code: e.target.value })} placeholder="PIN" className={F} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input value={f.phone || ''} onChange={(e) => setF({ ...f, phone: e.target.value })} placeholder="Phone" className={F} />
              <input value={f.email || ''} onChange={(e) => setF({ ...f, email: e.target.value })} placeholder="Email" className={F} />
            </div>
            <label className="flex items-center gap-2 text-xs text-slate-300 cursor-pointer">
              <input type="checkbox" checked={!!f.is_head_office} onChange={(e) => setF({ ...f, is_head_office: e.target.checked })} /> Head office
            </label>
            <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
            </button>
          </div>
        </div>
      </div>
    );
  };

/* ── Territory modal ── */
const TerritoryModal: React.FC<{ initial?: Territory | null; territories: Territory[]; users: any[]; onClose: () => void; onSaved: () => void }> =
  ({ initial, territories, users, onClose, onSaved }) => {
    const [f, setF] = useState<any>(initial ? { ...initial } : {
      name: '', code: '', level: 'region', parent_id: '', manager_user_id: '', description: '', status: 'active',
    });
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const save = async () => {
      if (!f.name?.trim()) { setError('Name is required'); return; }
      setBusy(true); setError(null);
      try {
        const payload = {
          name: f.name, code: f.code || undefined, level: f.level, parent_id: f.parent_id || null,
          manager_user_id: f.manager_user_id || null, description: f.description || undefined, status: f.status,
        };
        if (initial) await branchApi.updateTerritory(initial.id, payload);
        else await branchApi.createTerritory(payload);
        onSaved();
      } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save')); } finally { setBusy(false); }
    };
    return (
      <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
        <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-md bg-slate-900 max-h-[90vh] overflow-y-auto">
          <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
            <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Map className="w-4 h-4 text-brand-400" /> {initial ? 'Edit' : 'New'} territory</h3>
            <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
          </div>
          <div className="p-4 space-y-3">
            {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
            <div className="grid grid-cols-2 gap-2">
              <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Name" className={F} />
              <input value={f.code || ''} onChange={(e) => setF({ ...f, code: e.target.value })} placeholder="Code" className={F} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <select value={f.level} onChange={(e) => setF({ ...f, level: e.target.value })} className={F}>
                {LEVELS.map((l) => <option key={l} value={l}>{l}</option>)}
              </select>
              <select value={f.parent_id || ''} onChange={(e) => setF({ ...f, parent_id: e.target.value })} className={F}>
                <option value="">No parent</option>
                {territories.filter((t) => t.id !== initial?.id).map((t) => <option key={t.id} value={t.id}>{t.name} ({t.level})</option>)}
              </select>
            </div>
            <select value={f.manager_user_id || ''} onChange={(e) => setF({ ...f, manager_user_id: e.target.value })} className={F}>
              <option value="">No territory manager</option>
              {users.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
            </select>
            <textarea value={f.description || ''} onChange={(e) => setF({ ...f, description: e.target.value })} rows={2} placeholder="Description" className={F} />
            <button onClick={save} disabled={busy} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
              {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : <Check className="w-4 h-4" />} {initial ? 'Save' : 'Create'}
            </button>
          </div>
        </div>
      </div>
    );
  };

/* ── Territory tree node ── */
const TreeNode: React.FC<{ node: TerritoryTreeNode; depth: number }> = ({ node, depth }) => (
  <div>
    <div className="flex items-center gap-2 py-1.5" style={{ paddingLeft: `${depth * 16}px` }}>
      <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase">{node.level}</span>
      <span className="text-sm text-slate-200">{node.name}</span>
      {node.code && <span className="text-[10px] text-slate-600">{node.code}</span>}
      <StatusChip status={node.status} />
    </div>
    {node.children.map((c) => <TreeNode key={c.id} node={c} depth={depth + 1} />)}
  </div>
);

/* ── PIN mapping panel ── */
const PincodePanel: React.FC<{ territories: Territory[]; branches: Branch[]; canManage: boolean }> = ({ territories, branches, canManage }) => {
  const [rows, setRows] = useState<Pincode[]>([]);
  const [search, setSearch] = useState('');
  const [form, setForm] = useState({ pin_code: '', city: '', territory_id: '', branch_id: '' });
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(() => { branchApi.listPincodes({ search: search || undefined }).then((r) => setRows(r.items)).catch(() => {}); }, [search]);
  useEffect(() => { load(); }, [load]);

  const add = async () => {
    if (!form.pin_code.trim() || !form.territory_id) { setError('PIN and territory are required'); return; }
    setError(null);
    try {
      await branchApi.upsertPincode({
        pin_code: form.pin_code, city: form.city || undefined, territory_id: form.territory_id,
        branch_id: form.branch_id || undefined,
      });
      setForm({ pin_code: '', city: '', territory_id: '', branch_id: '' }); load();
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to save mapping')); }
  };
  const doImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0]; if (!file) return;
    try { const r = await branchApi.importPincodes(file); window.alert(`Import: ${r.created} created, ${r.updated} updated, ${r.skipped} skipped, ${r.errors.length} error(s).`); load(); }
    catch (err: any) { setError(extractErrorMessage(err, 'Import failed')); }
    e.target.value = '';
  };

  return (
    <div className="space-y-3">
      {error && <div className="p-2.5 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      <div className="flex items-center gap-2">
        <div className="relative flex-1">
          <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
          <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search PIN / city…" className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 pl-8 pr-3 rounded-lg text-xs w-full" />
        </div>
        {canManage && (
          <label className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 cursor-pointer px-2.5 py-1.5 border border-slate-800 rounded-lg">
            <Upload className="w-3.5 h-3.5" /> Import CSV
            <input type="file" accept=".csv" onChange={doImport} className="hidden" />
          </label>
        )}
      </div>
      {canManage && (
        <div className="p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg grid grid-cols-5 gap-2">
          <input value={form.pin_code} onChange={(e) => setForm({ ...form, pin_code: e.target.value })} placeholder="PIN" className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs" />
          <input value={form.city} onChange={(e) => setForm({ ...form, city: e.target.value })} placeholder="City" className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs" />
          <select value={form.territory_id} onChange={(e) => setForm({ ...form, territory_id: e.target.value })} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
            <option value="">Territory…</option>
            {territories.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
          </select>
          <select value={form.branch_id} onChange={(e) => setForm({ ...form, branch_id: e.target.value })} className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs">
            <option value="">Branch (optional)</option>
            {branches.map((b) => <option key={b.id} value={b.id}>{b.name}</option>)}
          </select>
          <button onClick={add} className="text-xs text-emerald-400 cursor-pointer inline-flex items-center justify-center gap-1"><Plus className="w-3.5 h-3.5" /> Map</button>
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
            <th className="py-1.5 pr-2">PIN</th><th className="py-1.5 pr-2">City</th><th className="py-1.5 pr-2">Territory</th><th className="py-1.5 pr-2">Branch</th><th></th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.id} className="border-t border-slate-800/50 text-slate-300">
                <td className="py-1.5 pr-2 font-medium">{r.pin_code}</td>
                <td className="py-1.5 pr-2">{r.city || '—'}</td>
                <td className="py-1.5 pr-2">{r.territory_name || '—'}</td>
                <td className="py-1.5 pr-2">{r.branch_name || '—'}</td>
                <td className="py-1.5 text-right">{canManage && <button onClick={async () => { await branchApi.deletePincode(r.id); load(); }} className="text-slate-600 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="text-xs text-slate-500 py-4 text-center">No PIN mappings yet.</p>}
      </div>
    </div>
  );
};

/* ── Reports panel ── */
const ReportsPanel: React.FC = () => {
  const [branches, setBranches] = useState<BranchAnalyticsRow[]>([]);
  const [terrs, setTerrs] = useState<TerritoryAnalyticsRow[]>([]);
  useEffect(() => {
    branchApi.branchAnalytics().then(setBranches).catch(() => {});
    branchApi.territoryAnalytics().then(setTerrs).catch(() => {});
  }, []);
  const Table: React.FC<{ title: string; rows: any[]; nameKey: string }> = ({ title, rows, nameKey }) => (
    <div>
      <h4 className="text-xs font-semibold text-slate-300 mb-1.5">{title}</h4>
      <div className="overflow-x-auto">
        <table className="w-full text-xs">
          <thead><tr className="text-left text-[10px] text-slate-500 uppercase">
            <th className="py-1 pr-2">Name</th><th className="py-1 pr-2">Leads</th><th className="py-1 pr-2">Conv.</th><th className="py-1 pr-2">Rate</th><th className="py-1">Revenue</th>
          </tr></thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r[nameKey]} className="border-t border-slate-800/50 text-slate-300">
                <td className="py-1.5 pr-2">{r.name}</td>
                <td className="py-1.5 pr-2">{r.leads}</td>
                <td className="py-1.5 pr-2">{r.converted}</td>
                <td className="py-1.5 pr-2">{r.conversion_rate}%</td>
                <td className="py-1.5">₹{Math.round(r.revenue).toLocaleString()}</td>
              </tr>
            ))}
          </tbody>
        </table>
        {!rows.length && <p className="text-xs text-slate-500 py-3">No data yet.</p>}
      </div>
    </div>
  );
  return (
    <div className="space-y-4">
      <Table title="Branch performance" rows={branches} nameKey="branch_id" />
      <Table title="Territory performance" rows={terrs} nameKey="territory_id" />
    </div>
  );
};

/* ── Page ── */
export const BranchTerritoryPage: React.FC = () => {
  const { user } = useAuthStore();
  const canManage = user?.role === 'OrgAdmin';

  const [tab, setTab] = useState<'branches' | 'territories' | 'pincodes' | 'reports'>('branches');
  const [branches, setBranches] = useState<Branch[]>([]);
  const [territories, setTerritories] = useState<Territory[]>([]);
  const [tree, setTree] = useState<TerritoryTreeNode[]>([]);
  const [dash, setDash] = useState<BranchDashboard | null>(null);
  const [users, setUsers] = useState<any[]>([]);
  const [search, setSearch] = useState('');
  const [branchModal, setBranchModal] = useState<Branch | null | 'new'>(null);
  const [terrModal, setTerrModal] = useState<Territory | null | 'new'>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [b, t, tr, d] = await Promise.all([
        branchApi.listBranches({ search: search || undefined }),
        branchApi.listTerritories({}),
        branchApi.territoryTree(),
        branchApi.dashboard(),
      ]);
      setBranches(b.items); setTerritories(t); setTree(tr); setDash(d);
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to load')); } finally { setLoading(false); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [search]);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (canManage) userApi.getUsers({ is_active: true, limit: 200 }).then(setUsers).catch(() => {}); }, [canManage]);

  const doExport = async () => {
    const blob = await branchApi.exportBranches();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a'); a.href = url; a.download = 'branches.csv'; a.click();
    URL.revokeObjectURL(url);
  };
  const removeBranch = async (b: Branch) => {
    if (!window.confirm(`Delete branch "${b.name}"?`)) return;
    try { await branchApi.removeBranch(b.id); load(); } catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };
  const removeTerritory = async (t: Territory) => {
    if (!window.confirm(`Delete territory "${t.name}"?`)) return;
    try { await branchApi.removeTerritory(t.id); load(); } catch (e: any) { setError(extractErrorMessage(e, 'Delete failed')); }
  };

  return (
    <div className="p-4 sm:p-6 space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h1 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Building className="w-5 h-5 text-brand-400" /> Branches & Territories</h1>
        <div className="flex items-center gap-2">
          {canManage && tab === 'branches' && (
            <>
              <button onClick={doExport} className="inline-flex items-center gap-1.5 text-xs text-slate-400 hover:text-slate-200 cursor-pointer px-2.5 py-1.5 border border-slate-800 rounded-lg"><Download className="w-3.5 h-3.5" /> Export</button>
              <button onClick={() => setBranchModal('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New branch</button>
            </>
          )}
          {canManage && tab === 'territories' && (
            <button onClick={() => setTerrModal('new')} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white text-xs font-medium py-1.5 px-3 rounded-lg cursor-pointer"><Plus className="w-3.5 h-3.5" /> New territory</button>
          )}
        </div>
      </div>

      {dash && (
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
          {[
            { label: 'Branches', value: `${dash.active_branches}/${dash.total_branches}` },
            { label: 'Territories', value: dash.total_territories },
            { label: 'Mapped PINs', value: dash.mapped_pincodes },
            { label: 'Unmapped leads', value: dash.unmapped_leads },
            { label: 'Archived', value: dash.archived_branches },
          ].map((s) => (
            <div key={s.label} className="glass-panel border border-slate-800/85 rounded-xl p-3">
              <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider">{s.label}</p>
              <p className="text-xl font-bold text-slate-100 mt-0.5">{s.value}</p>
            </div>
          ))}
        </div>
      )}

      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}

      <div className="flex gap-1 border-b border-slate-800/60">
        {([['branches', 'Branches', Building], ['territories', 'Territories', Network], ['pincodes', 'PIN Mapping', MapPin], ['reports', 'Reports', BarChart3]] as const).map(([key, label, Icon]) => (
          <button key={key} onClick={() => setTab(key)}
                  className={`px-3 py-1.5 text-xs font-medium inline-flex items-center gap-1.5 border-b-2 -mb-px cursor-pointer ${tab === key ? 'border-brand-500 text-brand-300' : 'border-transparent text-slate-500 hover:text-slate-300'}`}>
            <Icon className="w-3.5 h-3.5" /> {label}
          </button>
        ))}
      </div>

      {loading ? (
        <div className="py-8 text-center text-slate-500"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : tab === 'branches' ? (
        <div className="space-y-2">
          <div className="relative w-64">
            <Search className="w-3.5 h-3.5 text-slate-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
            <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search branches…" className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 pl-8 pr-3 rounded-lg text-xs w-full" />
          </div>
          {branches.map((b) => (
            <div key={b.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
              <div className="min-w-0">
                <div className="flex items-center gap-2">
                  {b.is_head_office && <Star className="w-3.5 h-3.5 text-amber-400 shrink-0" />}
                  <p className="text-sm text-slate-200 font-medium truncate">{b.name}</p>
                  {b.code && <span className="text-[10px] text-slate-600">{b.code}</span>}
                  <StatusChip status={b.status} />
                </div>
                <p className="text-[11px] text-slate-500 mt-0.5 flex items-center gap-2 flex-wrap">
                  {b.city && <span className="inline-flex items-center gap-1"><MapPin className="w-3 h-3" /> {b.city}{b.pin_code ? ` · ${b.pin_code}` : ''}</span>}
                  {b.territory_name && <span>· {b.territory_name}</span>}
                  {b.manager_name && <span className="inline-flex items-center gap-1"><Crown className="w-3 h-3 text-amber-400/70" /> {b.manager_name}</span>}
                  <span>· {b.lead_count} lead(s)</span>
                </p>
              </div>
              {canManage && (
                <div className="flex items-center gap-1 shrink-0">
                  <button onClick={() => setBranchModal(b)} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                  <button onClick={() => removeBranch(b)} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                </div>
              )}
            </div>
          ))}
          {!branches.length && <p className="text-xs text-slate-500 py-6 text-center">No branches yet.</p>}
        </div>
      ) : tab === 'territories' ? (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="glass-panel border border-slate-800/85 rounded-2xl p-4">
            <h4 className="text-xs font-semibold text-slate-300 mb-2 flex items-center gap-1.5"><Network className="w-3.5 h-3.5 text-brand-400" /> Hierarchy</h4>
            {tree.length ? tree.map((n) => <TreeNode key={n.id} node={n} depth={0} />) : <p className="text-xs text-slate-500">No territories yet.</p>}
          </div>
          <div className="space-y-2">
            {territories.map((t) => (
              <div key={t.id} className="p-3 rounded-xl border border-slate-800/85 bg-slate-950/30 flex items-center justify-between gap-2">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] px-1.5 py-0.5 rounded bg-slate-800 text-slate-400 uppercase">{t.level}</span>
                    <p className="text-sm text-slate-200 font-medium truncate">{t.name}</p>
                    <StatusChip status={t.status} />
                  </div>
                  <p className="text-[11px] text-slate-500 mt-0.5">{t.branch_count} branch(es) · {t.pincode_count} PIN(s){t.manager_name ? ` · ${t.manager_name}` : ''}</p>
                </div>
                {canManage && (
                  <div className="flex items-center gap-1 shrink-0">
                    <button onClick={() => setTerrModal(t)} className="p-1.5 text-slate-500 hover:text-slate-300 cursor-pointer"><Pencil className="w-4 h-4" /></button>
                    <button onClick={() => removeTerritory(t)} className="p-1.5 text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : tab === 'pincodes' ? (
        <PincodePanel territories={territories} branches={branches} canManage={canManage} />
      ) : (
        <ReportsPanel />
      )}

      {branchModal && <BranchModal initial={branchModal === 'new' ? null : branchModal} territories={territories} users={users}
                                   onClose={() => setBranchModal(null)} onSaved={() => { setBranchModal(null); load(); }} />}
      {terrModal && <TerritoryModal initial={terrModal === 'new' ? null : terrModal} territories={territories} users={users}
                                    onClose={() => setTerrModal(null)} onSaved={() => { setTerrModal(null); load(); }} />}
    </div>
  );
};
