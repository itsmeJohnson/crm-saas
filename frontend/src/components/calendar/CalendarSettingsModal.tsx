import React, { useEffect, useState } from 'react';
import { calendarApi, Holiday, WorkingHours } from '../../services/calendarApi';
import { X, Plus, Trash2, Copy, Check } from 'lucide-react';

const DAYS = [['mon', 'Mon'], ['tue', 'Tue'], ['wed', 'Wed'], ['thu', 'Thu'], ['fri', 'Fri'], ['sat', 'Sat'], ['sun', 'Sun']];

export const CalendarSettingsModal: React.FC<{ canManage: boolean; onClose: () => void }> = ({ canManage, onClose }) => {
  const [wh, setWh] = useState<WorkingHours | null>(null);
  const [holidays, setHolidays] = useState<Holiday[]>([]);
  const [feedUrl, setFeedUrl] = useState('');
  const [copied, setCopied] = useState(false);
  const [hName, setHName] = useState('');
  const [hDate, setHDate] = useState('');
  const [hAnnual, setHAnnual] = useState(false);

  const load = async () => {
    const [w, h, f] = await Promise.all([calendarApi.getWorkingHours(), calendarApi.listHolidays(), calendarApi.feedUrl()]);
    setWh(w); setHolidays(h); setFeedUrl(f.url);
  };
  useEffect(() => { load(); }, []);

  const setDay = async (key: string, patch: Partial<{ enabled: boolean; start: string; end: string }>) => {
    if (!wh) return;
    const days = { ...wh.days, [key]: { ...wh.days[key], ...patch } };
    setWh({ ...wh, days });
    await calendarApi.updateWorkingHours({ days });
  };

  const addHoliday = async () => {
    if (!hName.trim() || !hDate) return;
    await calendarApi.createHoliday({ name: hName.trim(), holiday_date: hDate, recurring_annual: hAnnual });
    setHName(''); setHDate(''); setHAnnual(false); load();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-5 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-lg font-bold text-slate-100">Calendar Settings</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
        </div>

        {/* Subscribe URL */}
        <div>
          <h3 className="text-sm font-semibold text-slate-200 mb-2">Subscribe (Google / Outlook / Apple)</h3>
          <p className="text-xs text-slate-500 mb-2">Add this read-only URL as a subscribed calendar in your calendar app.</p>
          <div className="flex gap-2">
            <input readOnly value={feedUrl} className="flex-1 px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-300" />
            <button onClick={() => { navigator.clipboard.writeText(feedUrl); setCopied(true); setTimeout(() => setCopied(false), 1500); }} className="px-3 py-2 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 cursor-pointer flex items-center gap-1.5">
              {copied ? <Check className="w-3.5 h-3.5 text-emerald-400" /> : <Copy className="w-3.5 h-3.5" />} {copied ? 'Copied' : 'Copy'}
            </button>
          </div>
        </div>

        {/* Working hours */}
        <div>
          <h3 className="text-sm font-semibold text-slate-200 mb-2">Working Hours {!canManage && <span className="text-xs text-slate-500">(admin only)</span>}</h3>
          {wh && (
            <div className="space-y-1.5">
              {DAYS.map(([key, label]) => {
                const d = wh.days[key] || { enabled: false, start: '09:00', end: '17:00' };
                return (
                  <div key={key} className="flex items-center gap-2 text-xs">
                    <label className="flex items-center gap-1.5 w-16"><input type="checkbox" disabled={!canManage} checked={d.enabled} onChange={(e) => setDay(key, { enabled: e.target.checked })} className="accent-brand-500" /> {label}</label>
                    <input type="time" disabled={!canManage || !d.enabled} value={d.start} onChange={(e) => setDay(key, { start: e.target.value })} className="px-2 py-1 bg-slate-950/50 border border-slate-800 rounded text-slate-200 disabled:opacity-40" />
                    <span className="text-slate-600">–</span>
                    <input type="time" disabled={!canManage || !d.enabled} value={d.end} onChange={(e) => setDay(key, { end: e.target.value })} className="px-2 py-1 bg-slate-950/50 border border-slate-800 rounded text-slate-200 disabled:opacity-40" />
                  </div>
                );
              })}
            </div>
          )}
        </div>

        {/* Holidays */}
        <div>
          <h3 className="text-sm font-semibold text-slate-200 mb-2">Holidays</h3>
          {canManage && (
            <div className="flex flex-wrap gap-2 mb-2">
              <input value={hName} onChange={(e) => setHName(e.target.value)} placeholder="Name" className="flex-1 min-w-24 px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200" />
              <input type="date" value={hDate} onChange={(e) => setHDate(e.target.value)} className="px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200" />
              <label className="flex items-center gap-1 text-xs text-slate-400"><input type="checkbox" checked={hAnnual} onChange={(e) => setHAnnual(e.target.checked)} className="accent-brand-500" /> Yearly</label>
              <button onClick={addHoliday} className="px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold cursor-pointer"><Plus className="w-3.5 h-3.5" /></button>
            </div>
          )}
          {holidays.length === 0 ? <p className="text-xs text-slate-500">No holidays.</p> : (
            <ul className="space-y-1">
              {holidays.map((h) => (
                <li key={h.id} className="flex items-center justify-between gap-2 text-xs p-1.5 bg-slate-950/40 border border-slate-800/60 rounded">
                  <span className="text-slate-300">{h.name} <span className="text-slate-500">· {h.holiday_date}{h.recurring_annual ? ' (yearly)' : ''}</span></span>
                  {canManage && <button onClick={async () => { await calendarApi.deleteHoliday(h.id); load(); }} className="text-slate-500 hover:text-red-400 cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>}
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
