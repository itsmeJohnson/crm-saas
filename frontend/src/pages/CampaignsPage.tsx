import React, { useCallback, useEffect, useState } from 'react';
import {
  Megaphone, Plus, Loader2, Search, Play, Pause, X, RefreshCw, Rocket, Ban,
  Mail, MessageSquare, MessageCircle, Phone, Users, TrendingUp, Eye, MousePointerClick, Trophy,
} from 'lucide-react';
import { campaignApi, Campaign, CampaignReport } from '../services/campaignApi';
import { templateApi, Template } from '../services/templateApi';
import { useAuthStore } from '../store/authStore';
import { extractErrorMessage } from '../utils/errors';

const CHANNELS = ['SMS', 'Email', 'WhatsApp', 'Call'];
const CHANNEL_ICON: Record<string, any> = { SMS: MessageSquare, Email: Mail, WhatsApp: MessageCircle, Call: Phone };
const STATUS_STYLE: Record<string, string> = {
  draft: 'bg-slate-700/40 text-slate-300 border-slate-600/40',
  scheduled: 'bg-sky-500/10 text-sky-400 border-sky-500/20',
  running: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
  paused: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  completed: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
  cancelled: 'bg-red-500/10 text-red-400 border-red-500/20',
};

const Chip: React.FC<{ status: string }> = ({ status }) => (
  <span className={`px-2 py-0.5 text-[10px] font-semibold rounded-md border ${STATUS_STYLE[status] || STATUS_STYLE.draft}`}>{status}</span>
);

/* ── Create wizard ── */
const CreateModal: React.FC<{ onClose: () => void; onCreated: (c: Campaign) => void }> = ({ onClose, onCreated }) => {
  const [name, setName] = useState('');
  const [channel, setChannel] = useState('SMS');
  const [templateId, setTemplateId] = useState('');
  const [body, setBody] = useState('');
  const [subject, setSubject] = useState('');
  const [statusFilter, setStatusFilter] = useState('New');
  const [source, setSource] = useState('');
  const [cost, setCost] = useState('0');
  const [templates, setTemplates] = useState<Template[]>([]);
  const [preview, setPreview] = useState<number | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    templateApi.list({ status: 'approved', channel }).then(setTemplates).catch(() => setTemplates([]));
  }, [channel]);

  const audienceDef = () => {
    const d: Record<string, any> = {};
    if (statusFilter) d.status = statusFilter;
    if (source) d.source = source;
    return d;
  };

  const doPreview = async () => {
    try {
      const r = await campaignApi.previewAudience({ channel, entity_type: 'lead', audience_type: 'filter', audience_definition: audienceDef() });
      setPreview(r.count);
    } catch (e: any) { setError(extractErrorMessage(e, 'Preview failed')); }
  };

  const submit = async () => {
    setError(null);
    if (!name.trim()) { setError('Name is required'); return; }
    if (channel !== 'Call' && !templateId && !body.trim()) { setError('Pick a template or enter a message'); return; }
    setSaving(true);
    try {
      const c = await campaignApi.create({
        name, channel, template_id: templateId || undefined, body: body || undefined, subject: subject || undefined,
        audience_type: 'filter', entity_type: 'lead', audience_definition: audienceDef(),
        cost_per_message: parseFloat(cost) || 0,
      });
      onCreated(c);
    } catch (e: any) { setError(extractErrorMessage(e, 'Failed to create campaign')); } finally { setSaving(false); }
  };

  return (
    <div className="fixed inset-0 z-40 flex items-center justify-center bg-black/50 backdrop-blur-sm p-4">
      <div className="glass-panel border border-slate-800/85 rounded-2xl w-full max-w-xl bg-slate-900 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-4 border-b border-slate-800/60">
          <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><Megaphone className="w-4 h-4 text-brand-400" /> New campaign</h3>
          <button onClick={onClose} className="p-1 text-slate-500 hover:text-slate-300 cursor-pointer"><X className="w-4 h-4" /></button>
        </div>
        <div className="p-4 space-y-3">
          {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
          <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Campaign name"
                 className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          <div className="grid grid-cols-2 gap-2">
            <select value={channel} onChange={(e) => { setChannel(e.target.value); setTemplateId(''); }} className="bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
              {CHANNELS.map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
            <input type="number" step="0.01" value={cost} onChange={(e) => setCost(e.target.value)} placeholder="Cost / message"
                   className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
          </div>
          {channel !== 'Call' && (
            <>
              <select value={templateId} onChange={(e) => setTemplateId(e.target.value)} className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-300 py-2 px-3 rounded-lg text-sm">
                <option value="">— No template (inline message) —</option>
                {templates.map((t) => <option key={t.id} value={t.id}>{t.name}</option>)}
              </select>
              {!templateId && channel === 'Email' && (
                <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject"
                       className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
              )}
              {!templateId && (
                <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} placeholder="Message body — supports {{first_name}} etc."
                          className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-sm" />
              )}
            </>
          )}
          <div className="p-3 bg-slate-950/50 border border-slate-800/70 rounded-lg space-y-2">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1"><Users className="w-3.5 h-3.5" /> Audience (leads)</p>
            <div className="grid grid-cols-2 gap-2">
              <input value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)} placeholder="Status (e.g. New)"
                     className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-xs" />
              <input value={source} onChange={(e) => setSource(e.target.value)} placeholder="Source (optional)"
                     className="bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 px-3 rounded-lg text-xs" />
            </div>
            <div className="flex items-center gap-2">
              <button onClick={doPreview} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><Users className="w-3.5 h-3.5" /> Preview audience</button>
              {preview !== null && <span className="text-xs text-slate-300"><b className="text-brand-400">{preview}</b> reachable recipients</span>}
            </div>
          </div>
          <button onClick={submit} disabled={saving} className="w-full inline-flex items-center justify-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm disabled:opacity-40 cursor-pointer">
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <Plus className="w-4 h-4" />} Create draft
          </button>
        </div>
      </div>
    </div>
  );
};

/* ── Detail with reports + lifecycle ── */
const Detail: React.FC<{ campaign: Campaign; canManage: boolean; onChanged: (c: Campaign) => void }> = ({ campaign, canManage, onChanged }) => {
  const [report, setReport] = useState<CampaignReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadReport = useCallback(() => {
    campaignApi.reports(campaign.id).then(setReport).catch(() => {});
  }, [campaign.id]);

  useEffect(() => { loadReport(); }, [loadReport]);

  const doAction = async (fn: () => Promise<Campaign>) => {
    setBusy(true); setError(null);
    try { const c = await fn(); onChanged(c); loadReport(); } catch (e: any) { setError(extractErrorMessage(e, 'Action failed')); } finally { setBusy(false); }
  };

  const Icon = CHANNEL_ICON[campaign.channel] || Megaphone;
  const s = campaign.status;

  return (
    <div className="flex-1 overflow-y-auto p-5 space-y-4">
      {error && <div className="p-3 bg-red-500/10 border border-red-500/20 text-red-400 rounded-lg text-xs">{error}</div>}
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-slate-100 flex items-center gap-2"><Icon className="w-5 h-5 text-brand-400" /> {campaign.name}</h2>
          <div className="flex items-center gap-2 mt-1"><Chip status={s} /><span className="text-xs text-slate-500">{campaign.channel} · {campaign.total_recipients} recipients</span></div>
        </div>
      </div>

      {/* Lifecycle actions */}
      {canManage && (
        <div className="flex flex-wrap gap-2">
          {(s === 'draft' || s === 'scheduled') && <button disabled={busy} onClick={() => doAction(() => campaignApi.build(campaign.id))} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><Users className="w-3.5 h-3.5" /> Build audience</button>}
          {(s === 'draft' || s === 'scheduled' || s === 'paused') && <button disabled={busy} onClick={() => doAction(() => campaignApi.launch(campaign.id))} className="inline-flex items-center gap-1.5 bg-emerald-500/15 text-emerald-400 border border-emerald-500/25 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><Rocket className="w-3.5 h-3.5" /> Launch</button>}
          {s === 'running' && <button disabled={busy} onClick={() => doAction(() => campaignApi.pause(campaign.id))} className="inline-flex items-center gap-1.5 bg-orange-500/15 text-orange-400 border border-orange-500/25 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><Pause className="w-3.5 h-3.5" /> Pause</button>}
          {s === 'paused' && <button disabled={busy} onClick={() => doAction(() => campaignApi.resume(campaign.id))} className="inline-flex items-center gap-1.5 bg-amber-500/15 text-amber-400 border border-amber-500/25 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><Play className="w-3.5 h-3.5" /> Resume</button>}
          {campaign.failed_count > 0 && s !== 'cancelled' && <button disabled={busy} onClick={() => doAction(() => campaignApi.retry(campaign.id))} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><RefreshCw className="w-3.5 h-3.5" /> Retry failed</button>}
          {s !== 'completed' && s !== 'cancelled' && <button disabled={busy} onClick={() => doAction(() => campaignApi.cancel(campaign.id))} className="inline-flex items-center gap-1.5 bg-red-500/15 text-red-400 border border-red-500/25 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><Ban className="w-3.5 h-3.5" /> Cancel</button>}
          <button disabled={busy} onClick={loadReport} className="inline-flex items-center gap-1.5 bg-slate-800 text-slate-300 border border-slate-700/60 py-1.5 px-3 rounded-lg text-xs cursor-pointer"><RefreshCw className="w-3.5 h-3.5" /> Refresh</button>
        </div>
      )}

      {/* Reports */}
      {report && (
        <>
          <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
            {[
              { label: 'Sent', value: report.sent, icon: Rocket, color: 'text-brand-400', sub: `of ${report.total_recipients}` },
              { label: 'Delivered', value: `${report.delivery_rate}%`, icon: MessageSquare, color: 'text-sky-400', sub: `${report.delivered}` },
              { label: 'Failed', value: report.failed, icon: Ban, color: 'text-red-400', sub: '' },
              { label: 'Opened', value: `${report.open_rate}%`, icon: Eye, color: 'text-emerald-400', sub: `${report.opened}` },
              { label: 'Clicked', value: `${report.click_rate}%`, icon: MousePointerClick, color: 'text-indigo-400', sub: `${report.clicked}` },
              { label: 'Converted', value: `${report.conversion_rate}%`, icon: Trophy, color: 'text-amber-400', sub: `${report.converted}` },
            ].map((k) => (
              <div key={k.label} className="p-3 bg-slate-950/40 border border-slate-800/60 rounded-lg">
                <p className="text-[10px] font-semibold text-slate-500 uppercase tracking-wider flex items-center gap-1"><k.icon className={`w-3 h-3 ${k.color}`} /> {k.label}</p>
                <p className="text-lg font-bold text-slate-100 mt-0.5">{k.value} <span className="text-[11px] text-slate-500 font-normal">{k.sub}</span></p>
              </div>
            ))}
          </div>
          {/* ROI */}
          <div className="p-4 bg-gradient-to-r from-slate-950/60 to-slate-900/40 border border-slate-800/70 rounded-xl">
            <p className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider flex items-center gap-1 mb-2"><TrendingUp className="w-3.5 h-3.5" /> ROI</p>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div><p className="text-[10px] text-slate-500 uppercase">Cost</p><p className="text-base font-bold text-slate-200">₹{report.cost.toFixed(2)}</p></div>
              <div><p className="text-[10px] text-slate-500 uppercase">Revenue</p><p className="text-base font-bold text-emerald-400">₹{report.revenue.toFixed(2)}</p></div>
              <div><p className="text-[10px] text-slate-500 uppercase">Net ROI</p><p className={`text-base font-bold ${report.roi >= 0 ? 'text-emerald-400' : 'text-red-400'}`}>₹{report.roi.toFixed(2)} <span className="text-[11px]">({report.roi_pct}%)</span></p></div>
            </div>
          </div>
        </>
      )}
    </div>
  );
};

export const CampaignsPage: React.FC = () => {
  const { user } = useAuthStore();
  const canManage = !!user && ['SuperAdmin', 'OrgAdmin', 'Manager'].includes(user.role);

  const [list, setList] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [search, setSearch] = useState('');
  const [statusF, setStatusF] = useState('');
  const [selected, setSelected] = useState<Campaign | null>(null);
  const [showCreate, setShowCreate] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try { setList(await campaignApi.list({ search: search || undefined, status: statusF || undefined })); }
    finally { setLoading(false); }
  }, [search, statusF]);

  useEffect(() => { const t = setTimeout(load, search ? 300 : 0); return () => clearTimeout(t); }, [load, search]);

  const onChanged = (c: Campaign) => { setSelected(c); setList((prev) => prev.map((x) => (x.id === c.id ? c : x))); };

  return (
    <div className="space-y-4">
      <div className="border-b border-slate-800/60 pb-4 flex items-center justify-between gap-3">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <Megaphone className="w-7 h-7 text-brand-400" /> Campaigns
          </h1>
          <p className="text-sm text-slate-400 mt-1">Bulk SMS, Email, WhatsApp &amp; Call outreach with delivery, engagement &amp; ROI.</p>
        </div>
        {canManage && <button onClick={() => setShowCreate(true)} className="inline-flex items-center gap-1.5 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm cursor-pointer"><Plus className="w-4 h-4" /> New</button>}
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 h-[calc(100vh-210px)] min-h-[520px]">
        {/* List */}
        <div className="glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          <div className="p-3 border-b border-slate-800/60 space-y-2">
            <div className="relative">
              <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search…"
                     className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-200 py-2 pl-9 pr-3 rounded-lg text-sm" />
            </div>
            <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className="w-full bg-slate-800/70 border border-slate-700/70 text-slate-300 py-1.5 px-2 rounded-lg text-xs">
              <option value="">All statuses</option>{['draft', 'scheduled', 'running', 'paused', 'completed', 'cancelled'].map((x) => <option key={x} value={x}>{x}</option>)}
            </select>
          </div>
          <div className="flex-1 overflow-y-auto">
            {loading ? <div className="py-10 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
              : list.length === 0 ? <p className="py-10 text-center text-xs text-slate-500">No campaigns.</p>
              : list.map((c) => {
                const Icon = CHANNEL_ICON[c.channel] || Megaphone;
                return (
                  <button key={c.id} onClick={() => setSelected(c)} className={`w-full text-left px-3 py-2.5 border-b border-slate-800/40 hover:bg-slate-900/50 cursor-pointer ${selected?.id === c.id ? 'bg-slate-900/60' : ''}`}>
                    <div className="flex items-center gap-2">
                      <Icon className="w-3.5 h-3.5 text-slate-400 shrink-0" />
                      <span className="text-sm font-semibold text-slate-200 truncate flex-1">{c.name}</span>
                      <Chip status={c.status} />
                    </div>
                    <div className="text-[11px] text-slate-500 mt-0.5">{c.sent_count}/{c.total_recipients} sent · {c.converted_count} converted</div>
                  </button>
                );
              })}
          </div>
        </div>

        {/* Detail */}
        <div className="lg:col-span-2 glass-panel border border-slate-800/85 rounded-2xl flex flex-col overflow-hidden">
          {!selected ? (
            <div className="flex-1 flex items-center justify-center text-slate-500 text-sm">
              <div className="text-center"><Megaphone className="w-10 h-10 mx-auto mb-2 text-slate-600" />Select a campaign</div>
            </div>
          ) : (
            <Detail campaign={selected} canManage={canManage} onChanged={onChanged} />
          )}
        </div>
      </div>

      {showCreate && <CreateModal onClose={() => setShowCreate(false)} onCreated={(c) => { setShowCreate(false); setSelected(c); load(); }} />}
    </div>
  );
};
