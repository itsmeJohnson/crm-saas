import React, { useEffect, useState } from 'react';
import { taskApi, Task, ChecklistItem } from '../../services/taskApi';
import { useUserStore } from '../../store/userStore';
import { X, Plus, Trash2, Loader2 } from 'lucide-react';

const inputCls = 'w-full px-3.5 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50';

export const TaskModal: React.FC<{ task?: Task | null; onClose: () => void; onSaved: () => void }> = ({ task, onClose, onSaved }) => {
  const { users, fetchUsers } = useUserStore();
  const activeUsers = users.filter((u) => u.is_active);

  const [title, setTitle] = useState(task?.title || '');
  const [description, setDescription] = useState(task?.description || '');
  const [priority, setPriority] = useState(task?.priority || 'Medium');
  const [statusV, setStatusV] = useState(task?.status || 'Todo');
  const [dueDate, setDueDate] = useState(task?.due_date ? task.due_date.slice(0, 16) : '');
  const [remindAt, setRemindAt] = useState(task?.remind_at ? task.remind_at.slice(0, 16) : '');
  const [assignee, setAssignee] = useState(task?.assigned_user_id || '');
  const [recurrence, setRecurrence] = useState(task?.recurrence || 'none');
  const [checklist, setChecklist] = useState<ChecklistItem[]>(task?.checklist || []);
  const [newItem, setNewItem] = useState('');
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => { if (users.length === 0) fetchUsers(); }, []);

  const submit = async () => {
    if (!title.trim()) return;
    setSubmitting(true);
    try {
      const payload = {
        title, description: description || null, priority, status: statusV,
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
        remind_at: remindAt ? new Date(remindAt).toISOString() : null,
        assigned_user_id: assignee || null, recurrence, checklist,
      };
      if (task) await taskApi.update(task.id, payload);
      else await taskApi.create({ ...payload, title });
      onSaved(); onClose();
    } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } finally { setSubmitting(false); }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-sm" onClick={onClose}></div>
      <div className="relative w-full max-w-lg bg-slate-900 border border-slate-800 rounded-2xl shadow-2xl p-6 z-10 space-y-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between border-b border-slate-800 pb-4">
          <h2 className="text-lg font-bold text-slate-100">{task ? 'Edit Task' : 'New Task'}</h2>
          <button onClick={onClose} className="p-1 text-slate-400 hover:text-slate-200"><X className="w-5 h-5" /></button>
        </div>

        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Task title" className={inputCls} />
        <textarea value={description} onChange={(e) => setDescription(e.target.value)} placeholder="Description" rows={2} className={inputCls} />

        <div className="grid grid-cols-2 gap-3">
          <div>
            <label className="text-xs text-slate-400">Priority</label>
            <select value={priority} onChange={(e) => setPriority(e.target.value)} className={inputCls}>
              {['Low', 'Medium', 'High', 'Urgent'].map((p) => <option key={p} value={p}>{p}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400">Status</label>
            <select value={statusV} onChange={(e) => setStatusV(e.target.value)} className={inputCls}>
              {['Todo', 'InProgress', 'Done', 'Cancelled'].map((s) => <option key={s} value={s}>{s}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400">Due</label>
            <input type="datetime-local" value={dueDate} onChange={(e) => setDueDate(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-400">Remind at</label>
            <input type="datetime-local" value={remindAt} onChange={(e) => setRemindAt(e.target.value)} className={inputCls} />
          </div>
          <div>
            <label className="text-xs text-slate-400">Assignee</label>
            <select value={assignee} onChange={(e) => setAssignee(e.target.value)} className={inputCls}>
              <option value="">Unassigned</option>
              {activeUsers.map((u) => <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>)}
            </select>
          </div>
          <div>
            <label className="text-xs text-slate-400">Recurrence</label>
            <select value={recurrence} onChange={(e) => setRecurrence(e.target.value)} className={inputCls}>
              {['none', 'daily', 'weekly', 'monthly'].map((r) => <option key={r} value={r}>{r}</option>)}
            </select>
          </div>
        </div>

        <div>
          <label className="text-xs text-slate-400">Checklist</label>
          <div className="space-y-1.5 mt-1">
            {checklist.map((it, idx) => (
              <div key={it.id || idx} className="flex items-center gap-2">
                <input type="checkbox" checked={it.done} onChange={(e) => setChecklist(checklist.map((c, i) => i === idx ? { ...c, done: e.target.checked } : c))} className="accent-brand-500" />
                <input value={it.text} onChange={(e) => setChecklist(checklist.map((c, i) => i === idx ? { ...c, text: e.target.value } : c))} className={inputCls + ' flex-1 py-1.5'} />
                <button onClick={() => setChecklist(checklist.filter((_, i) => i !== idx))} className="p-1 text-slate-500 hover:text-red-400"><Trash2 className="w-3.5 h-3.5" /></button>
              </div>
            ))}
            <div className="flex gap-2">
              <input value={newItem} onChange={(e) => setNewItem(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter' && newItem.trim()) { setChecklist([...checklist, { text: newItem.trim(), done: false }]); setNewItem(''); } }} placeholder="Add checklist item…" className={inputCls + ' flex-1 py-1.5'} />
              <button onClick={() => { if (newItem.trim()) { setChecklist([...checklist, { text: newItem.trim(), done: false }]); setNewItem(''); } }} className="p-2 bg-slate-950 border border-slate-800 rounded-lg text-slate-300"><Plus className="w-4 h-4" /></button>
            </div>
          </div>
        </div>

        <div className="flex justify-end gap-3 pt-3 border-t border-slate-800">
          <button onClick={onClose} className="px-4 py-2 border border-slate-800 hover:border-slate-700 rounded-xl text-sm font-semibold text-slate-300 cursor-pointer">Cancel</button>
          <button onClick={submit} disabled={submitting} className="flex items-center gap-2 px-5 py-2 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-xl text-sm font-semibold cursor-pointer">
            {submitting && <Loader2 className="w-4 h-4 animate-spin" />} Save
          </button>
        </div>
      </div>
    </div>
  );
};
