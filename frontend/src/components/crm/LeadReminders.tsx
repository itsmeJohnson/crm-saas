import React, { useEffect, useState } from 'react';
import { leadApi, LeadReminder } from '../../services/leadApi';
import { Bell, Plus, Trash2, Check } from 'lucide-react';

interface Props {
  leadId: string;
}

export const LeadReminders: React.FC<Props> = ({ leadId }) => {
  const [reminders, setReminders] = useState<LeadReminder[]>([]);
  const [remindAt, setRemindAt] = useState('');
  const [note, setNote] = useState('');
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setReminders(await leadApi.listReminders(leadId));
    } catch {
      /* silent */
    }
  };

  useEffect(() => {
    load();
  }, [leadId]);

  const handleCreate = async () => {
    if (!remindAt) return;
    setError(null);
    try {
      await leadApi.createReminder(leadId, { remind_at: new Date(remindAt).toISOString(), note: note || undefined });
      setRemindAt('');
      setNote('');
      await load();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to add reminder');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await leadApi.deleteReminder(leadId, id);
      await load();
    } catch {
      /* silent */
    }
  };

  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
        <Bell className="w-4 h-4 text-amber-400" />
        Reminders
      </h3>

      <div className="flex flex-col sm:flex-row gap-2 mb-3">
        <input
          type="datetime-local"
          value={remindAt}
          onChange={(e) => setRemindAt(e.target.value)}
          className="flex-1 px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
        />
        <input
          type="text"
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (optional)"
          className="flex-1 px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200 placeholder:text-slate-500 focus:outline-none focus:border-brand-500/50"
        />
        <button
          onClick={handleCreate}
          className="flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold transition-all cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          Add
        </button>
      </div>

      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}

      {reminders.length === 0 ? (
        <p className="text-xs text-slate-500">No reminders set.</p>
      ) : (
        <ul className="space-y-2">
          {reminders.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">
              <div className="min-w-0">
                <p className="text-xs text-slate-200 truncate">
                  {new Date(r.remind_at).toLocaleString()}
                  {r.is_sent && (
                    <span className="ml-2 inline-flex items-center gap-1 text-[10px] text-emerald-400">
                      <Check className="w-3 h-3" /> sent
                    </span>
                  )}
                </p>
                {r.note && <p className="text-[11px] text-slate-400 truncate">{r.note}</p>}
              </div>
              <button
                onClick={() => handleDelete(r.id)}
                className="p-1 text-slate-500 hover:text-red-400 transition-colors cursor-pointer shrink-0"
                title="Delete reminder"
              >
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
