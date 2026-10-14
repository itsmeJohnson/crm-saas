import React, { useEffect, useState } from 'react';
import { Mails, Plus, Loader2, Trash2, X, ChevronDown, ChevronUp, Clock } from 'lucide-react';
import { emailSequenceApi, EmailSequence, SequenceInput } from '../services/emailSequenceApi';
import { extractErrorMessage } from '../utils/errors';

type StepDraft = { subject: string; body: string; delay_hours: number };

const blankStep = (): StepDraft => ({ subject: '', body: '', delay_hours: 24 });
const blankDraft = (): SequenceInput => ({
  name: '', description: '', trigger: 'manual', is_active: true,
  steps: [{ subject: 'Thanks for reaching out, {{first_name}}', body: 'Hi {{first_name}},\n\nThanks for your interest. How can we help?', delay_hours: 0 }],
});

function delayLabel(h: number): string {
  if (h === 0) return 'immediately';
  if (h % 24 === 0) return `after ${h / 24} day${h / 24 > 1 ? 's' : ''}`;
  return `after ${h} hour${h > 1 ? 's' : ''}`;
}

export const EmailSequencesPage: React.FC = () => {
  const [items, setItems] = useState<EmailSequence[]>([]);
  const [loading, setLoading] = useState(true);
  const [msg, setMsg] = useState<string | null>(null);
  const [editing, setEditing] = useState<EmailSequence | 'new' | null>(null);
  const [draft, setDraft] = useState<SequenceInput>(blankDraft());
  const [saving, setSaving] = useState(false);
  const [expanded, setExpanded] = useState<string | null>(null);

  const load = async () => {
    setLoading(true);
    try { setItems(await emailSequenceApi.list()); }
    catch (err: any) { setMsg(extractErrorMessage(err, 'Failed to load sequences')); }
    finally { setLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const openNew = () => { setDraft(blankDraft()); setEditing('new'); };
  const openEdit = (s: EmailSequence) => {
    setDraft({
      name: s.name, description: s.description || '', trigger: s.trigger, is_active: s.is_active,
      steps: s.steps.map((st) => ({ subject: st.subject, body: st.body, delay_hours: st.delay_hours })),
    });
    setEditing(s);
  };

  const setStep = (i: number, patch: Partial<StepDraft>) =>
    setDraft((d) => ({ ...d, steps: d.steps.map((s, idx) => (idx === i ? { ...s, ...patch } : s)) }));
  const addStep = () => setDraft((d) => ({ ...d, steps: [...d.steps, blankStep()] }));
  const removeStep = (i: number) => setDraft((d) => ({ ...d, steps: d.steps.filter((_, idx) => idx !== i) }));

  const save = async () => {
    if (!draft.name.trim()) { setMsg('Give the sequence a name'); return; }
    if (draft.steps.length === 0) { setMsg('Add at least one step'); return; }
    for (const [i, s] of draft.steps.entries()) {
      if (!s.subject.trim() || !s.body.trim()) { setMsg(`Step ${i + 1} needs a subject and body`); return; }
    }
    setSaving(true); setMsg(null);
    try {
      if (editing === 'new') await emailSequenceApi.create(draft);
      else if (editing) await emailSequenceApi.update(editing.id, draft);
      setEditing(null); load();
    } catch (err: any) { setMsg(extractErrorMessage(err, 'Failed to save')); }
    finally { setSaving(false); }
  };

  const remove = async (s: EmailSequence) => {
    if (!confirm(`Delete "${s.name}"? Active enrollments will stop.`)) return;
    try { await emailSequenceApi.remove(s.id); load(); } catch (err: any) { setMsg(extractErrorMessage(err, 'Failed')); }
  };
  const toggle = async (s: EmailSequence) => {
    try { await emailSequenceApi.update(s.id, { is_active: !s.is_active } as any); load(); }
    catch (err: any) { setMsg(extractErrorMessage(err, 'Failed')); }
  };

  return (
    <div className="space-y-6">
      <div className="border-b border-slate-800/60 pb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight bg-gradient-to-r from-slate-100 to-slate-400 bg-clip-text text-transparent flex items-center gap-3">
            <Mails className="w-7 h-7 text-brand-400" /> Email Sequences
          </h1>
          <p className="text-sm text-slate-400 mt-1">Automated multi-step follow-up emails. Enroll leads manually or auto-enroll every new lead.</p>
        </div>
        <button onClick={openNew} className="inline-flex items-center gap-2 bg-gradient-to-r from-brand-500 to-indigo-500 text-white font-medium py-2 px-4 rounded-lg text-sm cursor-pointer">
          <Plus className="w-4 h-4" /> New Sequence
        </button>
      </div>

      {msg && <div className="p-3 bg-slate-800/60 border border-slate-700/60 text-slate-300 rounded-lg text-xs">{msg}</div>}

      {editing && (
        <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 space-y-4">
          <div className="flex items-center justify-between">
            <h2 className="text-sm font-semibold text-slate-200">{editing === 'new' ? 'New sequence' : 'Edit sequence'}</h2>
            <button onClick={() => setEditing(null)} className="text-slate-400 hover:text-slate-200"><X className="w-4 h-4" /></button>
          </div>
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <label className="block">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Name</span>
              <input value={draft.name} onChange={(e) => setDraft({ ...draft, name: e.target.value })}
                className="mt-1 w-full px-3 py-2 rounded-lg glass-input" placeholder="New lead nurture" />
            </label>
            <label className="block">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Trigger</span>
              <select value={draft.trigger} onChange={(e) => setDraft({ ...draft, trigger: e.target.value as any })}
                className="mt-1 w-full px-3 py-2 rounded-lg glass-input">
                <option value="manual">Manual — enroll leads yourself</option>
                <option value="lead_created">Automatic — every new lead</option>
              </select>
            </label>
          </div>

          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold text-slate-400 uppercase tracking-wider">Steps</span>
              <span className="text-[11px] text-slate-500">Use {'{{first_name}}'}, {'{{company}}'}, {'{{title}}'} as placeholders</span>
            </div>
            {draft.steps.map((s, i) => (
              <div key={i} className="border border-slate-800 rounded-lg p-4 space-y-3 bg-slate-950/40">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-brand-300">Step {i + 1}</span>
                  {draft.steps.length > 1 && (
                    <button onClick={() => removeStep(i)} className="text-red-400 hover:text-red-300"><Trash2 className="w-3.5 h-3.5" /></button>
                  )}
                </div>
                <div className="flex items-center gap-2">
                  <Clock className="w-3.5 h-3.5 text-slate-500" />
                  <span className="text-xs text-slate-400">Send</span>
                  <input type="number" min={0} value={s.delay_hours} onChange={(e) => setStep(i, { delay_hours: Number(e.target.value) })}
                    className="w-20 px-2 py-1 rounded glass-input text-sm" />
                  <span className="text-xs text-slate-400">hours after {i === 0 ? 'enrollment' : 'previous step'}</span>
                </div>
                <input value={s.subject} onChange={(e) => setStep(i, { subject: e.target.value })}
                  className="w-full px-3 py-2 rounded-lg glass-input text-sm" placeholder="Subject line" />
                <textarea value={s.body} onChange={(e) => setStep(i, { body: e.target.value })} rows={4}
                  className="w-full px-3 py-2 rounded-lg glass-input text-sm" placeholder="Email body" />
              </div>
            ))}
            <button onClick={addStep} className="inline-flex items-center gap-1.5 text-xs text-brand-300 hover:text-brand-200">
              <Plus className="w-3.5 h-3.5" /> Add step
            </button>
          </div>

          <div className="flex justify-end gap-2">
            <button onClick={() => setEditing(null)} className="px-4 py-2 rounded-lg text-sm text-slate-300 border border-slate-700 hover:bg-slate-800">Cancel</button>
            <button onClick={save} disabled={saving} className="inline-flex items-center gap-2 px-4 py-2 rounded-lg text-sm bg-brand-500 text-white disabled:opacity-50">
              {saving && <Loader2 className="w-4 h-4 animate-spin" />} Save
            </button>
          </div>
        </div>
      )}

      {loading ? (
        <div className="py-12 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : items.length === 0 ? (
        <div className="py-12 text-center text-slate-500 text-sm">No sequences yet. Create your first follow-up drip.</div>
      ) : (
        <div className="space-y-3">
          {items.map((s) => (
            <div key={s.id} className="bg-slate-900/50 border border-slate-800 rounded-xl p-5">
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="flex items-center gap-2">
                    <h3 className="font-semibold text-slate-100 truncate">{s.name}</h3>
                    <span className={`text-[10px] px-2 py-0.5 rounded-full border ${s.is_active ? 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' : 'text-slate-400 border-slate-700 bg-slate-800/60'}`}>
                      {s.is_active ? 'Active' : 'Paused'}
                    </span>
                    <span className="text-[10px] px-2 py-0.5 rounded-full border text-indigo-300 border-indigo-500/30 bg-indigo-500/10">
                      {s.trigger === 'lead_created' ? 'Auto: new leads' : 'Manual'}
                    </span>
                  </div>
                  <p className="text-xs text-slate-500 mt-1">{s.steps.length} step{s.steps.length !== 1 ? 's' : ''}</p>
                </div>
                <div className="flex items-center gap-2 shrink-0">
                  <button onClick={() => setExpanded(expanded === s.id ? null : s.id)} className="p-1.5 rounded border border-slate-700 text-slate-300 hover:bg-slate-800">
                    {expanded === s.id ? <ChevronUp className="w-3.5 h-3.5" /> : <ChevronDown className="w-3.5 h-3.5" />}
                  </button>
                  <button onClick={() => toggle(s)} className="text-xs px-3 py-1.5 rounded border border-slate-700 text-slate-300 hover:bg-slate-800">{s.is_active ? 'Pause' : 'Activate'}</button>
                  <button onClick={() => openEdit(s)} className="text-xs px-3 py-1.5 rounded border border-slate-700 text-slate-300 hover:bg-slate-800">Edit</button>
                  <button onClick={() => remove(s)} className="text-xs px-3 py-1.5 rounded border border-slate-800 text-red-400 hover:bg-red-500/10 hover:border-red-500/30"><Trash2 className="w-3.5 h-3.5" /></button>
                </div>
              </div>
              {expanded === s.id && (
                <ol className="mt-4 space-y-2 border-t border-slate-800 pt-4">
                  {s.steps.map((st, i) => (
                    <li key={st.id || i} className="flex gap-3 text-sm">
                      <span className="text-brand-300 font-semibold shrink-0">{i + 1}.</span>
                      <div>
                        <p className="text-slate-200">{st.subject}</p>
                        <p className="text-xs text-slate-500">Sent {delayLabel(st.delay_hours)}{i > 0 ? ' after the previous step' : ''}</p>
                      </div>
                    </li>
                  ))}
                </ol>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

export default EmailSequencesPage;
