import React, { useCallback, useEffect, useState } from 'react';
import {
  DatabaseZap, Loader2, Plus, X, Check, Trash2, Play, KeyRound, RotateCcw, Copy, Download,
  LayoutDashboard, Share2, RefreshCw, History as HistoryIcon, Cloud, Webhook, CheckCircle2, AlertTriangle,
} from 'lucide-react';
import { biApi as api, BiMeta, BiToken, BiSync, ExportJob, BiDashboard, BiSettings } from '../services/biApi';
import { reportBuilderApi } from '../services/reportBuilderApi';
import { extractErrorMessage } from '../utils/errors';

const F = 'w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-1.5 px-2 rounded-lg text-xs';
const card = 'glass-panel border border-slate-800/85 rounded-xl p-4';
const BTN = 'px-3 py-1.5 rounded-lg text-xs font-semibold bg-brand-500/20 text-brand-300 hover:bg-brand-500/30 cursor-pointer flex items-center gap-1.5';

const saveBlob = (blob: Blob, name: string) => {
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  URL.revokeObjectURL(a.href);
};

export const BiExportPage: React.FC = () => {
  const [tab, setTab] = useState<'dashboard' | 'export' | 'feeds' | 'syncs' | 'history'>('dashboard');
  const [meta, setMeta] = useState<BiMeta | null>(null);
  const [dash, setDash] = useState<BiDashboard | null>(null);
  const [tokens, setTokens] = useState<BiToken[]>([]);
  const [syncs, setSyncs] = useState<BiSync[]>([]);
  const [jobs, setJobs] = useState<ExportJob[]>([]);
  const [reports, setReports] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [err, setErr] = useState('');
  const [msg, setMsg] = useState('');
  const flash = (m: string) => { setMsg(m); setTimeout(() => setMsg(''), 3000); };

  useEffect(() => { reportBuilderApi.list({}).then(setReports).catch(() => {}); }, []);

  const load = useCallback(async () => {
    setLoading(true); setErr('');
    try {
      if (!meta) setMeta(await api.meta());
      if (tab === 'dashboard') setDash(await api.dashboard());
      else if (tab === 'feeds') setTokens(await api.tokens());
      else if (tab === 'syncs') setSyncs(await api.syncs());
      else if (tab === 'history') setJobs(await api.history({ limit: 100 }));
    } catch (e) { setErr(extractErrorMessage(e, 'Failed to load.')); } finally { setLoading(false); }
  }, [tab, meta]);
  useEffect(() => { load(); }, [load]);

  const act = async (fn: () => Promise<any>, ok: string) => { try { await fn(); flash(ok); await load(); } catch (e) { setErr(extractErrorMessage(e, 'Failed')); } };

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-extrabold text-slate-100 flex items-center gap-2"><DatabaseZap className="w-6 h-6 text-brand-400" /> Export & BI Integration</h1>
        <p className="text-sm text-slate-500 mt-1">Download CSV/Excel/PDF/JSON, feed Power BI · Tableau · Looker · Metabase, push to webhooks and cloud storage, and run recurring data syncs.</p>
      </div>

      {msg && <div className="text-xs text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 rounded-lg px-3 py-2">{msg}</div>}
      {err && <div className="text-xs text-red-400 bg-red-500/10 border border-red-500/20 rounded-lg px-3 py-2">{err}</div>}

      <div className="flex items-center gap-1 bg-slate-900/50 border border-slate-800/70 rounded-xl p-1 w-fit flex-wrap">
        {([['dashboard', 'Dashboard', LayoutDashboard], ['export', 'Export', Download], ['feeds', 'BI Feeds', Share2], ['syncs', 'Data Sync', RefreshCw], ['history', 'History', HistoryIcon]] as [any, string, any][]).map(([k, l, Icon]) => (
          <button key={k} onClick={() => setTab(k)} className={`px-3 py-1.5 rounded-lg text-xs font-semibold flex items-center gap-1.5 cursor-pointer ${tab === k ? 'bg-brand-500/20 text-brand-300' : 'text-slate-400 hover:text-slate-200'}`}><Icon className="w-3.5 h-3.5" /> {l}</button>
        ))}
      </div>

      {loading && tab !== 'export' ? (
        <div className="py-20 text-center text-slate-400"><Loader2 className="w-6 h-6 animate-spin inline" /></div>
      ) : tab === 'dashboard' && dash ? (
        <div className="space-y-4">
          <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Exports</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.exports}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Success rate</p><p className="text-xl font-bold text-emerald-400 mt-1">{dash.success_rate}%</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Failed</p><p className="text-xl font-bold text-red-400 mt-1">{dash.failed}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">BI tokens</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.active_tokens}</p></div>
            <div className={card}><p className="text-[10px] font-semibold text-slate-500 uppercase">Active syncs</p><p className="text-xl font-bold text-slate-100 mt-1">{dash.active_syncs}</p></div>
          </div>
          <div className={card}>
            <p className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-2">Recent exports</p>
            {dash.recent.length === 0 ? <p className="text-xs text-slate-500">No exports yet.</p> :
              dash.recent.map((j) => <JobRow key={j.id} j={j} />)}
          </div>
        </div>
      ) : tab === 'export' && meta ? (
        <ExportTab meta={meta} reports={reports} flash={flash} setErr={setErr} />
      ) : tab === 'feeds' && meta ? (
        <FeedsTab meta={meta} tokens={tokens} act={act} flash={flash} setErr={setErr} reload={load} />
      ) : tab === 'syncs' && meta ? (
        <SyncsTab meta={meta} syncs={syncs} reports={reports} act={act} setErr={setErr} reload={load} flash={flash} />
      ) : tab === 'history' ? (
        <div className="space-y-2">
          {jobs.length === 0 && <p className="text-sm text-slate-500">No export history yet.</p>}
          {jobs.map((j) => <JobRow key={j.id} j={j} bordered />)}
        </div>
      ) : null}
    </div>
  );
};

const JobRow: React.FC<{ j: ExportJob; bordered?: boolean }> = ({ j, bordered }) => (
  <div className={`flex items-center gap-3 py-1.5 ${bordered ? `glass-panel border ${j.status === 'failed' ? 'border-red-500/30' : 'border-slate-800/85'} rounded-xl p-3` : 'border-b border-slate-800/50 last:border-0'}`}>
    {j.status === 'success' ? <CheckCircle2 className="w-4 h-4 text-emerald-400 shrink-0" /> : <AlertTriangle className="w-4 h-4 text-red-400 shrink-0" />}
    <div className="flex-1 min-w-0">
      <p className="text-sm text-slate-200 truncate">
        <span className="capitalize">{j.kind}</span> · {j.source_type}:{j.source_key} · <span className="uppercase">{j.format}</span>
        <span className="text-[10px] text-slate-500"> · {j.rows} rows{j.size_bytes ? ` · ${(j.size_bytes / 1024).toFixed(1)} KB` : ''}</span>
      </p>
      <p className="text-[11px] text-slate-500 truncate">{j.error || j.target || '—'}{j.created_at ? ` · ${new Date(j.created_at).toLocaleString()}` : ''}</p>
    </div>
  </div>
);

const ExportTab: React.FC<{ meta: BiMeta; reports: any[]; flash: (s: string) => void; setErr: (s: string) => void }> = ({ meta, reports, flash, setErr }) => {
  const [f, setF] = useState<any>({ source_type: 'dataset', source_key: 'leads', format: 'csv', url: '', path_prefix: '' });
  const [busy, setBusy] = useState('');
  const [settings, setSettings] = useState<BiSettings | null>(null);
  const set = (patch: any) => setF({ ...f, ...patch });
  useEffect(() => { api.settings().then(setSettings).catch(() => {}); }, []);

  const run = async (kind: 'download' | 'webhook' | 'cloud') => {
    setBusy(kind); setErr('');
    try {
      if (kind === 'download') {
        const blob = await api.download(f.source_type, f.source_key, f.format);
        saveBlob(blob, `${f.source_key}.${f.format}`);
        flash('Downloaded.');
      } else if (kind === 'webhook') {
        if (!f.url) { setErr('Webhook URL is required'); return; }
        const r = await api.webhookExport({ source_type: f.source_type, source_key: f.source_key, url: f.url, format: f.format === 'csv' ? 'csv' : 'json' });
        r.status === 'success' ? flash(`Pushed ${r.rows} rows to webhook.`) : setErr(r.error || 'Webhook push failed');
      } else {
        const r = await api.cloudExport({ source_type: f.source_type, source_key: f.source_key, format: f.format, path_prefix: f.path_prefix || undefined });
        r.status === 'success' ? flash(`Stored at ${r.target}`) : setErr(r.error || 'Cloud export failed');
      }
    } catch (e) { setErr(extractErrorMessage(e, 'Export failed')); } finally { setBusy(''); }
  };

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
      <div className={`${card} space-y-2`}>
        <p className="text-xs font-semibold text-slate-400 uppercase">One-off export</p>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-[11px] text-slate-400">Source
            <select value={f.source_type === 'dataset' ? `dataset:${f.source_key}` : `report:${f.source_key}`}
                    onChange={(e) => { const [t, ...k] = e.target.value.split(':'); set({ source_type: t, source_key: k.join(':') }); }} className={F}>
              <optgroup label="Datasets">{meta.datasets.map((d) => <option key={d.key} value={`dataset:${d.key}`}>{d.label}</option>)}</optgroup>
              <optgroup label="Saved reports">{reports.map((r) => <option key={r.id} value={`report:${r.id}`}>{r.name}</option>)}</optgroup>
            </select>
          </label>
          <label className="text-[11px] text-slate-400">Format
            <select value={f.format} onChange={(e) => set({ format: e.target.value })} className={F}>
              {meta.formats.map((x) => <option key={x} value={x}>{x.toUpperCase()}</option>)}
            </select>
          </label>
        </div>
        <button onClick={() => run('download')} disabled={busy !== ''} className={`${BTN} w-full justify-center`}>{busy === 'download' ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Download className="w-3.5 h-3.5" />} Download</button>
        <div className="pt-2 border-t border-slate-800/60 space-y-2">
          <p className="text-[11px] text-slate-400 flex items-center gap-1"><Webhook className="w-3 h-3" /> Push to webhook (JSON/CSV)</p>
          <div className="flex items-center gap-2">
            <input value={f.url} onChange={(e) => set({ url: e.target.value })} placeholder="https://warehouse.example.com/ingest" className={F} />
            <button onClick={() => run('webhook')} disabled={busy !== ''} className={`${BTN} shrink-0`}>{busy === 'webhook' ? '…' : 'Push'}</button>
          </div>
        </div>
        <div className="pt-2 border-t border-slate-800/60 space-y-2">
          <p className="text-[11px] text-slate-400 flex items-center gap-1"><Cloud className="w-3 h-3" /> Push to cloud storage ({settings?.storage_provider || 'local'})</p>
          <div className="flex items-center gap-2">
            <input value={f.path_prefix} onChange={(e) => set({ path_prefix: e.target.value })} placeholder="folder/prefix (optional)" className={F} />
            <button onClick={() => run('cloud')} disabled={busy !== ''} className={`${BTN} shrink-0`}>{busy === 'cloud' ? '…' : 'Store'}</button>
          </div>
        </div>
      </div>
      <StorageSettings settings={settings} setSettings={setSettings} providers={meta.storage_providers} setErr={setErr} flash={flash} />
    </div>
  );
};

const StorageSettings: React.FC<{ settings: BiSettings | null; setSettings: (s: BiSettings) => void; providers: string[]; setErr: (s: string) => void; flash: (s: string) => void }> =
  ({ settings, setSettings, providers, setErr, flash }) => {
    const [f, setF] = useState<any>({});
    const [busy, setBusy] = useState(false);
    useEffect(() => { if (settings) setF({ storage_provider: settings.storage_provider, s3_bucket: settings.s3_bucket || '', s3_region: settings.s3_region || '', s3_prefix: settings.s3_prefix || '' }); }, [settings]);
    const save = async () => {
      setBusy(true);
      try {
        const payload: any = { ...f };
        if (!payload.s3_access_key) delete payload.s3_access_key;
        if (!payload.s3_secret_key) delete payload.s3_secret_key;
        setSettings(await api.updateSettings(payload));
        flash('Storage settings saved.');
      } catch (e) { setErr(extractErrorMessage(e, 'Save failed')); } finally { setBusy(false); }
    };
    return (
      <div className={`${card} space-y-2 h-fit`}>
        <p className="text-xs font-semibold text-slate-400 uppercase flex items-center gap-1.5"><Cloud className="w-3.5 h-3.5" /> Cloud storage settings</p>
        <label className="text-[11px] text-slate-400 block">Provider
          <select value={f.storage_provider || 'local'} onChange={(e) => setF({ ...f, storage_provider: e.target.value })} className={F}>
            {providers.map((p) => <option key={p} value={p}>{p === 'local' ? 'Local directory (default)' : 'S3-compatible'}</option>)}
          </select>
        </label>
        {f.storage_provider === 's3' && (
          <>
            <div className="grid grid-cols-2 gap-2">
              <input value={f.s3_bucket || ''} onChange={(e) => setF({ ...f, s3_bucket: e.target.value })} placeholder="Bucket" className={F} />
              <input value={f.s3_region || ''} onChange={(e) => setF({ ...f, s3_region: e.target.value })} placeholder="Region" className={F} />
            </div>
            <div className="grid grid-cols-2 gap-2">
              <input value={f.s3_access_key || ''} onChange={(e) => setF({ ...f, s3_access_key: e.target.value })} placeholder={settings?.s3_access_key ? `Access key (${settings.s3_access_key})` : 'Access key'} className={F} />
              <input type="password" value={f.s3_secret_key || ''} onChange={(e) => setF({ ...f, s3_secret_key: e.target.value })} placeholder={settings?.s3_secret_key ? 'Secret key (set)' : 'Secret key'} className={F} />
            </div>
            <input value={f.s3_prefix || ''} onChange={(e) => setF({ ...f, s3_prefix: e.target.value })} placeholder="Key prefix (optional)" className={F} />
          </>
        )}
        <button onClick={save} disabled={busy} className={`${BTN} w-full justify-center`}>{busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Check className="w-3.5 h-3.5" />} Save settings</button>
      </div>
    );
  };

const FeedsTab: React.FC<{ meta: BiMeta; tokens: BiToken[]; act: any; flash: (s: string) => void; setErr: (s: string) => void; reload: () => Promise<void> }> =
  ({ meta, tokens, act, flash, setErr, reload }) => {
    const [name, setName] = useState('');
    const [revealed, setRevealed] = useState<Record<string, string>>({});
    const base = window.location.origin;
    const copy = (text: string) => { navigator.clipboard?.writeText(text).then(() => flash('Copied.')).catch(() => setErr('Copy failed')); };
    const create = async () => {
      if (!name.trim()) { setErr('Token name is required'); return; }
      try {
        const t = await api.createToken({ name });
        setRevealed((r) => ({ ...r, [t.id]: t.token }));
        setName('');
        flash('Token created — copy it now, it is shown once.');
        await reload();
      } catch (e) { setErr(extractErrorMessage(e, 'Failed')); }
    };
    const rotate = async (id: string) => {
      try {
        const t = await api.rotateToken(id);
        setRevealed((r) => ({ ...r, [t.id]: t.token }));
        flash('Token rotated — update your BI tools.');
        await reload();
      } catch (e) { setErr(extractErrorMessage(e, 'Failed')); }
    };
    return (
      <div className="space-y-4">
        <div className={`${card} flex items-center gap-2`}>
          <KeyRound className="w-4 h-4 text-brand-400 shrink-0" />
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="New BI token name (e.g. Power BI production)" className={F} />
          <button onClick={create} className={`${BTN} shrink-0`}><Plus className="w-3.5 h-3.5" /> Create</button>
        </div>
        {tokens.map((t) => {
          const tok = revealed[t.id];
          return (
            <div key={t.id} className={card}>
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-100">{t.name}</span>
                <code className="text-[11px] text-brand-300 bg-slate-950/50 px-1.5 py-0.5 rounded">{tok || t.token}</code>
                {tok && <button onClick={() => copy(tok)} className="text-slate-400 hover:text-brand-300 cursor-pointer"><Copy className="w-3.5 h-3.5" /></button>}
                {!t.is_active && <span className="text-[10px] text-slate-500">disabled</span>}
                <span className="text-[10px] text-slate-500">used {t.use_count}×{t.last_used_at ? ` · last ${new Date(t.last_used_at).toLocaleString()}` : ''}</span>
                <span className="flex-1" />
                <button title="Rotate" onClick={() => rotate(t.id)} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-300 cursor-pointer"><RotateCcw className="w-4 h-4" /></button>
                <button title={t.is_active ? 'Disable' : 'Enable'} onClick={() => act(() => api.updateToken(t.id, { is_active: !t.is_active }), t.is_active ? 'Disabled.' : 'Enabled.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-brand-300 cursor-pointer">{t.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}</button>
                <button title="Delete" onClick={() => window.confirm(`Delete token "${t.name}"?`) && act(() => api.removeToken(t.id), 'Deleted.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
              </div>
              {tok && (
                <div className="mt-3 grid grid-cols-1 md:grid-cols-2 gap-2">
                  {meta.connectors.map((c) => {
                    const url = c.url_template.replace('{base}', base).replace('{token}', tok).replace('{dataset}', 'leads');
                    return (
                      <div key={c.tool} className="bg-slate-950/40 border border-slate-800/60 rounded-lg p-2.5">
                        <p className="text-xs font-semibold text-slate-200 mb-1">{c.label}</p>
                        <ol className="text-[11px] text-slate-500 list-decimal ml-4 space-y-0.5">{c.steps.map((s, i) => <li key={i}>{s}</li>)}</ol>
                        <button onClick={() => copy(url)} className="mt-1.5 text-[11px] text-brand-400 hover:text-brand-300 cursor-pointer flex items-center gap-1"><Copy className="w-3 h-3" /> Copy feed URL</button>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })}
        {tokens.length === 0 && <p className="text-sm text-slate-500">Create a token to connect Power BI, Tableau, Looker or Metabase.</p>}
      </div>
    );
  };

const SyncsTab: React.FC<{ meta: BiMeta; syncs: BiSync[]; reports: any[]; act: any; setErr: (s: string) => void; reload: () => Promise<void>; flash: (s: string) => void }> =
  ({ meta, syncs, reports, act, setErr, reload, flash }) => {
    const [f, setF] = useState<any>({ name: '', source_type: 'dataset', source_key: 'leads', format: 'json', destination: 'webhook', mode: 'full', frequency: 'daily', target_url: '', path_prefix: '' });
    const set = (patch: any) => setF({ ...f, ...patch });
    const create = async () => {
      if (!f.name.trim()) { setErr('Sync name is required'); return; }
      try {
        await api.createSync({ ...f, target_url: f.target_url || undefined, path_prefix: f.path_prefix || undefined });
        flash('Sync created.');
        set({ name: '' });
        await reload();
      } catch (e) { setErr(extractErrorMessage(e, 'Failed')); }
    };
    return (
      <div className="space-y-4">
        <div className={`${card} space-y-2`}>
          <p className="text-xs font-semibold text-slate-400 uppercase">New data sync</p>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <input value={f.name} onChange={(e) => set({ name: e.target.value })} placeholder="Sync name" className={F} />
            <select value={f.source_type === 'dataset' ? `dataset:${f.source_key}` : `report:${f.source_key}`}
                    onChange={(e) => { const [t, ...k] = e.target.value.split(':'); set({ source_type: t, source_key: k.join(':') }); }} className={F}>
              <optgroup label="Datasets">{meta.datasets.map((d) => <option key={d.key} value={`dataset:${d.key}`}>{d.label}</option>)}</optgroup>
              <optgroup label="Saved reports">{reports.map((r) => <option key={r.id} value={`report:${r.id}`}>{r.name}</option>)}</optgroup>
            </select>
            <select value={f.format} onChange={(e) => set({ format: e.target.value })} className={F}>{meta.sync_formats.map((x) => <option key={x} value={x}>{x.toUpperCase()}</option>)}</select>
            <select value={f.destination} onChange={(e) => set({ destination: e.target.value })} className={F}>{meta.destinations.map((x) => <option key={x} value={x}>{x}</option>)}</select>
            <select value={f.mode} onChange={(e) => set({ mode: e.target.value })} className={F}>{meta.modes.map((x) => <option key={x} value={x}>{x}</option>)}</select>
            <select value={f.frequency} onChange={(e) => set({ frequency: e.target.value })} className={F}>{meta.frequencies.map((x) => <option key={x} value={x}>{x}</option>)}</select>
            {f.destination === 'webhook'
              ? <input value={f.target_url} onChange={(e) => set({ target_url: e.target.value })} placeholder="Webhook URL" className={`${F} col-span-2`} />
              : <input value={f.path_prefix} onChange={(e) => set({ path_prefix: e.target.value })} placeholder="Storage folder (optional)" className={`${F} col-span-2`} />}
          </div>
          <button onClick={create} className={BTN}><Plus className="w-3.5 h-3.5" /> Create sync</button>
        </div>
        {syncs.map((s) => (
          <div key={s.id} className="glass-panel border border-slate-800/85 rounded-xl p-4 flex items-center gap-3">
            <div className="flex-1 min-w-0">
              <div className="flex items-center gap-2 flex-wrap">
                <span className="text-sm font-semibold text-slate-100 truncate">{s.name}</span>
                <span className="px-1.5 py-0.5 text-[10px] rounded bg-slate-700/40 text-slate-400 border border-slate-600/40">{s.source_type}:{s.source_key}</span>
                <span className="px-1.5 py-0.5 text-[10px] rounded bg-brand-500/10 text-brand-300 uppercase">{s.format}</span>
                <span className="text-[10px] text-slate-400 capitalize">{s.destination} · {s.mode} · {s.frequency}</span>
                {!s.is_active && <span className="text-[10px] text-slate-500">paused</span>}
                {s.last_status && <span className={`text-[10px] font-semibold ${s.last_status === 'success' ? 'text-emerald-400' : 'text-red-400'}`}>{s.last_status}</span>}
              </div>
              <p className="text-[11px] text-slate-500 mt-0.5 truncate">{s.target_url || s.path_prefix || 'default storage'} · ran {s.run_count}×{s.last_cursor ? ` · cursor ${s.last_cursor}` : ''}{s.next_run_at ? ` · next ${new Date(s.next_run_at).toLocaleString()}` : ''}</p>
            </div>
            <div className="flex items-center gap-1.5 shrink-0">
              <button title="Run now" onClick={() => act(() => api.runSync(s.id), 'Sync ran.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-emerald-400 cursor-pointer"><Play className="w-4 h-4" /></button>
              <button title={s.is_active ? 'Pause' : 'Resume'} onClick={() => act(() => api.updateSync(s.id, { is_active: !s.is_active }), s.is_active ? 'Paused.' : 'Resumed.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-amber-300 cursor-pointer">{s.is_active ? <X className="w-4 h-4" /> : <Check className="w-4 h-4" />}</button>
              <button title="Delete" onClick={() => window.confirm(`Delete "${s.name}"?`) && act(() => api.removeSync(s.id), 'Deleted.')} className="p-1.5 rounded hover:bg-slate-800 text-slate-400 hover:text-red-400 cursor-pointer"><Trash2 className="w-4 h-4" /></button>
            </div>
          </div>
        ))}
        {syncs.length === 0 && <p className="text-sm text-slate-500">No syncs — schedule a recurring push to your warehouse or storage.</p>}
      </div>
    );
  };
