import React, { useMemo, useState, useEffect } from 'react';
import { X, Mail, ArrowRight, Loader2, Send } from 'lucide-react';
import { LeadResponse } from '../../services/leadApi';
import {
  configForStage, fillTemplate, humanize, buildEmailHtml, AGENCY, StageField,
} from '../../utils/stageAutomation';

interface Props {
  lead: LeadResponse;
  toStageName: string;
  fromStageName?: string;
  onCancel: () => void;
  onConfirm: (opts: { withEmail: boolean; to?: string; subject?: string; body?: string }) => Promise<void>;
}

const TEST_FALLBACK = 'johnsondev02@gmail.com';
const INPUT = 'w-full px-3 py-2 rounded-lg text-sm bg-slate-950/60 border border-slate-700 text-slate-100 focus:outline-none focus:border-brand-500';

export const StageEmailDialog: React.FC<Props> = ({ lead, toStageName, fromStageName, onCancel, onConfirm }) => {
  const cfg = useMemo(() => configForStage(toStageName), [toStageName]);
  const leadName = `${lead.first_name || ''} ${lead.last_name || ''}`.trim() || 'there';

  const [fields, setFields] = useState<Record<string, string>>({});
  const [to, setTo] = useState(lead.email || TEST_FALLBACK);
  const [subject, setSubject] = useState('');
  const [intro, setIntro] = useState('');
  const [introDirty, setIntroDirty] = useState(false);
  const [subjectDirty, setSubjectDirty] = useState(false);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showHtml, setShowHtml] = useState(false);

  const ctx = useMemo<Record<string, any>>(() => ({
    name: leadName,
    first_name: lead.first_name || leadName,
    property: lead.title || 'your property',
    agency: AGENCY,
    value: lead.value ?? '',
    email: lead.email || '',
    phone: lead.phone || '',
    ...fields,
  }), [leadName, lead, fields]);

  useEffect(() => {
    if (!cfg?.sendsEmail) return;
    if (!subjectDirty) setSubject(fillTemplate(cfg.subject || '', ctx));
    if (!introDirty) setIntro(fillTemplate(cfg.intro || '', ctx));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ctx, cfg]);

  // Build the details rows (humanized) from the stage's detailRows spec.
  const rows = useMemo(() =>
    (cfg?.detailRows || []).map((r) => ({ label: r.label, value: humanize(ctx[r.key]) })),
    [cfg, ctx]);

  const html = useMemo(() =>
    cfg?.sendsEmail ? buildEmailHtml({ name: leadName, intro, detailsTitle: cfg.detailsTitle, rows, signatureName: cfg.signatureName }) : '',
    [cfg, leadName, intro, rows]);

  const missing = (cfg?.fields || []).filter((f) => f.required && !fields[f.key]?.trim());

  const send = async () => {
    if (missing.length) { setError(`Please fill: ${missing.map((m) => m.label).join(', ')}`); return; }
    if (!to.trim()) { setError('A recipient email is required.'); return; }
    setSending(true); setError(null);
    try {
      await onConfirm({ withEmail: true, to: to.trim(), subject, body: html });
    } catch (e: any) {
      setError(e?.message || 'Could not send. The move was not applied.');
      setSending(false);
    }
  };

  const justMove = async () => {
    setSending(true); setError(null);
    try { await onConfirm({ withEmail: false }); }
    catch (e: any) { setError(e?.message || 'Could not move the lead.'); setSending(false); }
  };

  const field = (f: StageField) => {
    if (f.type === 'select') {
      return (
        <select className={INPUT} value={fields[f.key] || ''} onChange={(e) => setFields({ ...fields, [f.key]: e.target.value })}>
          <option value="">Select…</option>
          {(f.options || []).map((o) => <option key={o} value={o}>{o}</option>)}
        </select>
      );
    }
    if (f.type === 'textarea') {
      return <textarea rows={2} className={INPUT} placeholder={f.placeholder} value={fields[f.key] || ''} onChange={(e) => setFields({ ...fields, [f.key]: e.target.value })} />;
    }
    return <input type={f.type} className={INPUT} placeholder={f.placeholder} value={fields[f.key] || ''} onChange={(e) => setFields({ ...fields, [f.key]: e.target.value })} />;
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/60 backdrop-blur-sm" onClick={onCancel}>
      <div className="w-full max-w-2xl max-h-[92vh] overflow-y-auto rounded-2xl border border-slate-800 shadow-2xl bg-slate-900" onClick={(e) => e.stopPropagation()}>
        <div className="p-5 border-b border-slate-800">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="flex items-center gap-2 text-xs font-medium text-slate-400">
                <span className="truncate">{fromStageName || 'Current'}</span>
                <ArrowRight className="w-3.5 h-3.5 text-brand-400 shrink-0" />
                <span className="font-semibold text-brand-400 truncate">{toStageName}</span>
              </div>
              <h2 className="mt-1 text-lg font-bold text-slate-100">{cfg?.label || 'Move lead'}</h2>
              <p className="text-sm text-slate-400 truncate">{leadName} · {lead.title}</p>
            </div>
            <button onClick={onCancel} className="text-slate-400 hover:text-slate-200 shrink-0"><X className="w-5 h-5" /></button>
          </div>
        </div>

        {!cfg?.sendsEmail ? (
          <div className="p-5 space-y-4">
            <p className="text-sm text-slate-300">Move this lead to <b className="text-slate-100">{toStageName}</b>? No client email is sent for this stage.</p>
            <div className="flex justify-end gap-2">
              <button onClick={onCancel} className="px-4 py-2 rounded-lg text-sm border border-slate-700 text-slate-300 hover:bg-slate-800">Cancel</button>
              <button onClick={justMove} disabled={sending} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-brand-500 hover:bg-brand-600 text-white disabled:opacity-50">
                {sending && <Loader2 className="w-4 h-4 animate-spin" />} Move lead
              </button>
            </div>
          </div>
        ) : (
          <div className="p-5 space-y-4">
            {(cfg.fields && cfg.fields.length > 0) && (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                {cfg.fields.map((f) => (
                  <label key={f.key} className={f.type === 'textarea' ? 'sm:col-span-2 block' : 'block'}>
                    <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">{f.label}{f.required && ' *'}</span>
                    <div className="mt-1">{field(f)}</div>
                  </label>
                ))}
              </div>
            )}

            <div className="flex items-center gap-2 text-sm">
              <span className="text-xs font-semibold text-slate-400 w-14 shrink-0">To</span>
              <input value={to} onChange={(e) => setTo(e.target.value)} className={INPUT} />
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Subject</span>
              <input value={subject} onChange={(e) => { setSubject(e.target.value); setSubjectDirty(true); }} className={`${INPUT} mt-1 font-medium`} />
            </div>
            <div>
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wide">Message to client</span>
              <textarea value={intro} onChange={(e) => { setIntro(e.target.value); setIntroDirty(true); }} rows={4} className={`${INPUT} mt-1 leading-relaxed`} />
              <p className="text-[11px] text-slate-500 mt-1">This becomes the intro; the branded header, details card, and signature are added automatically.</p>
            </div>

            {/* Live branded preview */}
            <div className="rounded-xl border border-slate-800 overflow-hidden">
              <button type="button" onClick={() => setShowHtml((v) => !v)}
                className="w-full flex items-center gap-2 px-3 py-2 bg-slate-950/50 border-b border-slate-800 text-left">
                <Mail className="w-4 h-4 text-brand-400" />
                <span className="text-xs font-semibold text-slate-400">Email preview — {AGENCY}</span>
                <span className="ml-auto text-[11px] text-slate-500">{showHtml ? 'hide' : 'show'}</span>
              </button>
              {showHtml && (
                <div className="max-h-72 overflow-y-auto bg-slate-200">
                  <div dangerouslySetInnerHTML={{ __html: html }} />
                </div>
              )}
            </div>

            {error && <p className="text-sm text-red-400">{error}</p>}

            <div className="flex flex-wrap justify-end gap-2">
              <button onClick={onCancel} className="px-4 py-2 rounded-lg text-sm border border-slate-700 text-slate-300 hover:bg-slate-800">Cancel</button>
              <button onClick={justMove} disabled={sending} className="px-4 py-2 rounded-lg text-sm border border-slate-700 text-slate-300 hover:bg-slate-800 disabled:opacity-50">Move without email</button>
              <button onClick={send} disabled={sending} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm font-medium bg-brand-500 hover:bg-brand-600 text-white disabled:opacity-50">
                {sending ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />} Send &amp; move
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
};
