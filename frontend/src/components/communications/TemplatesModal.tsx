import React, { useEffect, useState } from 'react';
import { communicationApi, CommTemplate } from '../../services/communicationApi';
import { X, Plus, Trash2 } from 'lucide-react';

const inputCls = 'w-full px-3 py-2 bg-slate-900 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50';

export const TemplatesModal: React.FC<{ onClose: () => void }> = ({ onClose }) => {
  const [templates, setTemplates] = useState<CommTemplate[]>([]);
  const [name, setName] = useState('');
  const [channel, setChannel] = useState('Email');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = async () => { try { setTemplates(await communicationApi.listTemplates()); } catch { /* */ } };
  useEffect(() => { load(); }, []);

  const create = async () => {
    if (!name.trim() || !body.trim()) return;
    setError(null);
    try {
      await communicationApi.createTemplate({ name: name.trim(), channel, subject: subject || undefined, body });
      setName(''); setSubject(''); setBody(''); load();
    } catch (e: any) { setError(e.response?.data?.detail || 'Failed'); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-lg font-bold text-slate-100">Message Templates</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
        </div>

        <div className="space-y-2 p-3 bg-slate-950/40 border border-slate-800/70 rounded-xl">
          <div className="grid grid-cols-2 gap-2">
            <input value={name} onChange={(e) => setName(e.target.value)} placeholder="Template name" className={inputCls} />
            <select value={channel} onChange={(e) => setChannel(e.target.value)} className={inputCls}>
              {['Email', 'SMS', 'WhatsApp'].map((c) => <option key={c} value={c}>{c}</option>)}
            </select>
          </div>
          <input value={subject} onChange={(e) => setSubject(e.target.value)} placeholder="Subject (email)" className={inputCls} />
          <textarea value={body} onChange={(e) => setBody(e.target.value)} placeholder="Body — use {{first_name}}, {{full_name}}, {{company}}, {{owner}}" rows={3} className={inputCls} />
          <button onClick={create} className="w-full flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold cursor-pointer"><Plus className="w-3.5 h-3.5" /> Add Template</button>
          {error && <p className="text-xs text-red-400">{error}</p>}
        </div>

        {templates.length === 0 ? <p className="text-xs text-slate-500">No templates.</p> : (
          <ul className="space-y-2">
            {templates.map((t) => (
              <li key={t.id} className="flex items-start justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">
                <div className="min-w-0">
                  <p className="text-xs font-medium text-slate-200">{t.name} <span className="text-slate-500">· {t.channel}</span></p>
                  <p className="text-[11px] text-slate-500 truncate">{t.subject || t.body}</p>
                </div>
                <button onClick={async () => { await communicationApi.deleteTemplate(t.id); load(); }} className="p-1 text-slate-500 hover:text-red-400 cursor-pointer shrink-0"><Trash2 className="w-3.5 h-3.5" /></button>
              </li>
            ))}
          </ul>
        )}
      </div>
    </div>
  );
};
