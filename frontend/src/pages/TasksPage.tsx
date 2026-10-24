import React, { useEffect, useState, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { taskApi, Task, TaskComment, TaskDependency, TaskAttachment } from '../services/taskApi';
import { TaskModal } from '../components/tasks/TaskModal';
import { useUserStore } from '../store/userStore';
import {
  Plus, X, Search, Loader2, CheckCircle2, Circle, Calendar as CalIcon, List as ListIcon,
  Paperclip, Upload, Trash2, Link2, MessageSquare, ChevronLeft, ChevronRight, Repeat, Clock,
} from 'lucide-react';

const PRIORITY_COLOR: Record<string, string> = {
  Urgent: 'text-status-danger-fg bg-status-danger-bg border-status-danger-fg/20',
  High: 'text-status-danger-fg bg-status-danger-bg border-status-danger-fg/20',
  Medium: 'text-status-warning-fg bg-status-warning-bg border-status-warning-fg/20',
  Low: 'text-muted bg-subtle border-default',
};

export const TasksPage: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [view, setView] = useState<'list' | 'calendar'>('list');
  const [isLoading, setIsLoading] = useState(true);
  const [statusF, setStatusF] = useState('All');
  const [priorityF, setPriorityF] = useState('All');
  const [overdue, setOverdue] = useState(false);
  const [search, setSearch] = useState('');
  const [modalTask, setModalTask] = useState<Task | null | undefined>(undefined); // undefined=closed
  const [detailId, setDetailId] = useState<string | null>(null);
  const [month, setMonth] = useState(() => { const d = new Date(); return new Date(d.getFullYear(), d.getMonth(), 1); });
  const [searchParams, setSearchParams] = useSearchParams();

  const load = useCallback(async () => {
    setIsLoading(true);
    try {
      if (view === 'calendar') {
        const from = new Date(month.getFullYear(), month.getMonth(), 1).toISOString();
        const to = new Date(month.getFullYear(), month.getMonth() + 1, 0, 23, 59).toISOString();
        setTasks(await taskApi.calendar(from, to));
      } else {
        setTasks(await taskApi.list({
          status: statusF === 'All' ? undefined : statusF,
          priority: priorityF === 'All' ? undefined : priorityF,
          overdue: overdue || undefined,
          search: search.trim() || undefined,
          limit: 200,
        }));
      }
    } catch { /* silent */ } finally { setIsLoading(false); }
  }, [view, statusF, priorityF, overdue, search, month]);

  useEffect(() => { load(); }, [load]);

  useEffect(() => {
    const tid = searchParams.get('taskId');
    if (tid) { setDetailId(tid); searchParams.delete('taskId'); setSearchParams(searchParams); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const toggleComplete = async (t: Task) => {
    try {
      if (t.status === 'Done') await taskApi.update(t.id, { status: 'Todo' });
      else await taskApi.complete(t.id);
      load();
    } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); }
  };

  return (
    <div className="space-y-6">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 border-b border-default pb-6">
        <div>
          <h1 className="text-3xl font-bold tracking-tight text-strong">Tasks</h1>
          <p className="text-sm text-muted mt-1">Plan, assign, and track work with checklists, dependencies &amp; reminders.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="flex items-center rounded-xl overflow-hidden border border-default bg-subtle p-0.5">
            <button onClick={() => setView('list')} className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg cursor-pointer transition ${view === 'list' ? 'bg-card text-indigo-600 dark:text-indigo-400 shadow-xs' : 'text-muted hover:text-strong'}`}><ListIcon className="w-3.5 h-3.5" /> List</button>
            <button onClick={() => setView('calendar')} className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold rounded-lg cursor-pointer transition ${view === 'calendar' ? 'bg-card text-indigo-600 dark:text-indigo-400 shadow-xs' : 'text-muted hover:text-strong'}`}><CalIcon className="w-3.5 h-3.5" /> Calendar</button>
          </div>
          <button onClick={() => setModalTask(null)} className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-700 active:bg-indigo-800 text-white rounded-xl text-xs font-semibold shadow-xs cursor-pointer transition">
            <Plus className="w-4 h-4" /> New Task
          </button>
        </div>
      </div>

      {view === 'list' ? (
        <>
          <div className="flex flex-wrap gap-3">
            <div className="relative flex-1 min-w-48">
              <Search className="w-4 h-4 text-muted absolute left-3 top-1/2 -translate-y-1/2 pointer-events-none" />
              <input value={search} onChange={(e) => setSearch(e.target.value)} placeholder="Search tasks…" className="w-full pl-9 pr-3 py-2 bg-card border border-default rounded-xl text-xs text-strong focus:outline-none focus:ring-2 focus:ring-indigo-500/20 placeholder:text-muted" />
            </div>
            <select value={statusF} onChange={(e) => setStatusF(e.target.value)} className="px-3 py-2 bg-card border border-default rounded-xl text-xs text-strong focus:outline-none focus:ring-2 focus:ring-indigo-500/20">
              {['All', 'Todo', 'InProgress', 'Done', 'Cancelled'].map((s) => <option key={s} value={s}>{s === 'All' ? 'All statuses' : s}</option>)}
            </select>
            <select value={priorityF} onChange={(e) => setPriorityF(e.target.value)} className="px-3 py-2 bg-card border border-default rounded-xl text-xs text-strong focus:outline-none focus:ring-2 focus:ring-indigo-500/20">
              {['All', 'Low', 'Medium', 'High', 'Urgent'].map((p) => <option key={p} value={p}>{p === 'All' ? 'All priorities' : p}</option>)}
            </select>
            <label className="flex items-center gap-2 px-3 py-2 bg-card border border-default rounded-xl text-xs text-body cursor-pointer select-none">
              <input type="checkbox" checked={overdue} onChange={(e) => setOverdue(e.target.checked)} className="accent-indigo-600 rounded" /> Overdue
            </label>
          </div>

          <div className="bg-card rounded-2xl border border-default divide-y divide-default shadow-xs overflow-hidden">
            {isLoading ? (
              <div className="py-16 text-center text-muted"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
            ) : tasks.length === 0 ? (
              <div className="py-16 text-center space-y-3">
                <CheckCircle2 className="w-10 h-10 text-muted mx-auto stroke-1" />
                <div>
                  <p className="text-sm font-semibold text-strong">No tasks found</p>
                  <p className="text-xs text-muted mt-1">Get organized by planning and assigning your team's next action items.</p>
                </div>
                <button onClick={() => setModalTask(null)} className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer transition">
                  <Plus className="w-3.5 h-3.5" /> Add your first task
                </button>
              </div>
            ) : tasks.map((t) => (
              <div key={t.id} className="flex items-center gap-3 px-5 py-3.5 bg-card hover:bg-hover cursor-pointer transition" onClick={() => setDetailId(t.id)}>
                <button onClick={(e) => { e.stopPropagation(); toggleComplete(t); }} className="shrink-0 cursor-pointer">
                  {t.status === 'Done' ? <CheckCircle2 className="w-5 h-5 text-emerald-500" /> : <Circle className="w-5 h-5 text-muted hover:text-strong" />}
                </button>
                <div className="min-w-0 flex-1">
                  <p className={`text-sm font-semibold ${t.status === 'Done' ? 'text-muted line-through' : 'text-strong'}`}>{t.title}</p>
                  <div className="flex items-center gap-2 text-[11px] text-muted mt-0.5">
                    {t.due_date && <span className="flex items-center gap-1"><Clock className="w-3 h-3" />{new Date(t.due_date).toLocaleDateString()}</span>}
                    {t.recurrence !== 'none' && <span className="flex items-center gap-1"><Repeat className="w-3 h-3" />{t.recurrence}</span>}
                    {t.checklist && t.checklist.length > 0 && <span>{t.checklist.filter((c) => c.done).length}/{t.checklist.length}</span>}
                  </div>
                </div>
                <span className={`shrink-0 px-2 py-0.5 rounded-lg text-[11px] font-semibold border ${PRIORITY_COLOR[t.priority] || PRIORITY_COLOR.Medium}`}>{t.priority}</span>
                <span className="shrink-0 text-[11px] text-muted w-20 text-right">{t.status}</span>
              </div>
            ))}
          </div>
        </>
      ) : (
        <CalendarView month={month} setMonth={setMonth} tasks={tasks} isLoading={isLoading} onOpen={setDetailId} />
      )}

      {modalTask !== undefined && <TaskModal task={modalTask} onClose={() => setModalTask(undefined)} onSaved={load} />}
      {detailId && <TaskDetail taskId={detailId} onClose={() => { setDetailId(null); load(); }} onEdit={(t) => setModalTask(t)} />}
    </div>
  );
};

const CalendarView: React.FC<{ month: Date; setMonth: (d: Date) => void; tasks: Task[]; isLoading: boolean; onOpen: (id: string) => void }> = ({ month, setMonth, tasks, isLoading, onOpen }) => {
  const first = new Date(month.getFullYear(), month.getMonth(), 1);
  const startDay = first.getDay();
  const daysInMonth = new Date(month.getFullYear(), month.getMonth() + 1, 0).getDate();
  const byDay: Record<number, Task[]> = {};
  for (const t of tasks) {
    if (!t.due_date) continue;
    const d = new Date(t.due_date);
    if (d.getMonth() === month.getMonth() && d.getFullYear() === month.getFullYear()) (byDay[d.getDate()] ||= []).push(t);
  }
  const cells: (number | null)[] = [...Array(startDay).fill(null), ...Array.from({ length: daysInMonth }, (_, i) => i + 1)];

  return (
    <div className="bg-card rounded-2xl border border-default p-5 shadow-xs">
      <div className="flex items-center justify-between mb-4">
        <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() - 1, 1))} className="p-1.5 text-muted hover:text-strong cursor-pointer"><ChevronLeft className="w-5 h-5" /></button>
        <h3 className="text-sm font-semibold text-strong">{month.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })}</h3>
        <button onClick={() => setMonth(new Date(month.getFullYear(), month.getMonth() + 1, 1))} className="p-1.5 text-muted hover:text-strong cursor-pointer"><ChevronRight className="w-5 h-5" /></button>
      </div>
      {isLoading ? <div className="py-16 text-center text-muted"><Loader2 className="w-5 h-5 animate-spin inline" /></div> : (
        <div className="grid grid-cols-7 gap-1">
          {['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'].map((d) => <div key={d} className="text-[10px] font-semibold text-muted uppercase text-center py-1">{d}</div>)}
          {cells.map((day, idx) => (
            <div key={idx} className={`min-h-[76px] rounded-lg p-1 ${day ? 'bg-subtle border border-default' : ''}`}>
              {day && <p className="text-[11px] text-muted mb-1">{day}</p>}
              <div className="space-y-0.5">
                {(byDay[day || -1] || []).slice(0, 3).map((t) => (
                  <button key={t.id} onClick={() => onOpen(t.id)} className={`w-full text-left truncate px-1 py-0.5 rounded text-[10px] font-medium border cursor-pointer ${PRIORITY_COLOR[t.priority] || PRIORITY_COLOR.Medium} ${t.status === 'Done' ? 'opacity-50 line-through' : ''}`}>{t.title}</button>
                ))}
                {(byDay[day || -1] || []).length > 3 && <p className="text-[9px] text-muted px-1">+{(byDay[day || -1] || []).length - 3} more</p>}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
};

const TaskDetail: React.FC<{ taskId: string; onClose: () => void; onEdit: (t: Task) => void }> = ({ taskId, onClose, onEdit }) => {
  const { users } = useUserStore();
  const [task, setTask] = useState<Task | null>(null);
  const [comments, setComments] = useState<TaskComment[]>([]);
  const [deps, setDeps] = useState<TaskDependency[]>([]);
  const [attachments, setAttachments] = useState<TaskAttachment[]>([]);
  const [allTasks, setAllTasks] = useState<Task[]>([]);
  const [newComment, setNewComment] = useState('');
  const [depTarget, setDepTarget] = useState('');
  const fileRef = React.useRef<HTMLInputElement>(null);

  const load = useCallback(async () => {
    const [t, c, d, a] = await Promise.all([
      taskApi.get(taskId), taskApi.listComments(taskId), taskApi.listDependencies(taskId), taskApi.listAttachments(taskId),
    ]);
    setTask(t); setComments(c); setDeps(d); setAttachments(a);
  }, [taskId]);

  useEffect(() => { load(); taskApi.list({ limit: 200 }).then(setAllTasks).catch(() => {}); }, [load]);

  if (!task) return null;
  const owner = users.find((u) => u.id === task.assigned_user_id);

  const toggleItem = async (itemId: string, done: boolean) => { await taskApi.toggleChecklist(task.id, itemId, done); load(); };
  const addComment = async () => { if (!newComment.trim()) return; await taskApi.addComment(task.id, newComment.trim()); setNewComment(''); load(); };
  const addDep = async () => { if (!depTarget) return; try { await taskApi.addDependency(task.id, depTarget); setDepTarget(''); load(); } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } };
  const upload = async (e: React.ChangeEvent<HTMLInputElement>) => { const f = e.target.files?.[0]; if (!f) return; try { await taskApi.uploadAttachment(task.id, f); load(); } catch (er: any) { alert(er.response?.data?.detail || 'Failed'); } finally { if (fileRef.current) fileRef.current.value = ''; } };
  const complete = async () => { try { await taskApi.complete(task.id); load(); } catch (e: any) { alert(e.response?.data?.detail || 'Failed'); } };

  return (
    <div className="fixed inset-0 z-40 overflow-hidden flex justify-end">
      <div className="absolute inset-0 bg-slate-950/60 backdrop-blur-xs" onClick={onClose}></div>
      <div className="relative w-full max-w-2xl bg-card border-l border-default shadow-2xl flex flex-col h-full z-10 animate-slide-in">
        <div className="p-6 border-b border-default flex items-start justify-between gap-3">
          <div className="min-w-0">
            <span className={`inline-block px-2 py-0.5 rounded-lg text-[11px] font-semibold border mb-2 ${PRIORITY_COLOR[task.priority] || PRIORITY_COLOR.Medium}`}>{task.priority} · {task.status}</span>
            <h2 className="text-xl font-bold text-strong">{task.title}</h2>
            <p className="text-xs text-muted mt-1">
              {task.due_date && <>Due {new Date(task.due_date).toLocaleString()} · </>}
              {owner ? `${owner.first_name || ''} ${owner.last_name || ''}`.trim() : 'Unassigned'}
              {task.recurrence !== 'none' && ` · repeats ${task.recurrence}`}
            </p>
          </div>
          <div className="flex items-center gap-2 shrink-0">
            <button onClick={() => onEdit(task)} className="px-3 py-1.5 border border-default hover:bg-hover rounded-xl text-xs font-semibold text-body cursor-pointer">Edit</button>
            {task.status !== 'Done' && <button onClick={complete} className="px-3 py-1.5 bg-status-success-bg border border-status-success-fg/30 hover:opacity-90 rounded-xl text-xs font-semibold text-status-success-fg cursor-pointer">Complete</button>}
            <button onClick={onClose} className="p-1.5 border border-default hover:bg-hover rounded-xl text-muted hover:text-strong cursor-pointer"><X className="w-5 h-5" /></button>
          </div>
        </div>

        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {task.description && <p className="text-sm text-body whitespace-pre-wrap">{task.description}</p>}

          {task.checklist && task.checklist.length > 0 && (
            <div className="bg-card border border-default p-4 rounded-2xl shadow-xs">
              <h3 className="text-sm font-semibold text-strong mb-3">Checklist ({task.checklist.filter((c) => c.done).length}/{task.checklist.length})</h3>
              <ul className="space-y-1.5">
                {task.checklist.map((it) => (
                  <li key={it.id} className="flex items-center gap-2">
                    <input type="checkbox" checked={it.done} onChange={(e) => toggleItem(it.id!, e.target.checked)} className="accent-indigo-600" />
                    <span className={`text-sm ${it.done ? 'text-muted line-through' : 'text-body'}`}>{it.text}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          {/* Dependencies */}
          <div className="bg-card border border-default p-4 rounded-2xl shadow-xs">
            <h3 className="text-sm font-semibold text-strong mb-3 flex items-center gap-2"><Link2 className="w-4 h-4 text-indigo-500" /> Blocked by</h3>
            <div className="flex gap-2 mb-2">
              <select value={depTarget} onChange={(e) => setDepTarget(e.target.value)} className="flex-1 px-3 py-2 bg-subtle border border-default rounded-lg text-xs text-strong">
                <option value="">Select a task…</option>
                {allTasks.filter((t) => t.id !== task.id).map((t) => <option key={t.id} value={t.id}>{t.title}</option>)}
              </select>
              <button onClick={addDep} className="px-3 py-2 bg-subtle border border-default hover:bg-hover rounded-lg text-xs font-semibold text-body cursor-pointer">Add</button>
            </div>
            {deps.length === 0 ? <p className="text-xs text-muted">No blockers.</p> : (
              <ul className="space-y-1.5">
                {deps.map((d) => (
                  <li key={d.id} className="flex items-center justify-between gap-2 text-xs">
                    <span className="text-body truncate">{d.depends_on_title} <span className={d.depends_on_status === 'Done' ? 'text-status-success-fg' : 'text-status-warning-fg'}>· {d.depends_on_status}</span></span>
                    <button onClick={async () => { await taskApi.deleteDependency(task.id, d.id); load(); }} className="text-muted hover:text-status-danger-fg cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Attachments */}
          <div className="bg-card border border-default p-4 rounded-2xl shadow-xs">
            <div className="flex items-center justify-between mb-3">
              <h3 className="text-sm font-semibold text-strong flex items-center gap-2"><Paperclip className="w-4 h-4 text-indigo-500" /> Attachments</h3>
              <button onClick={() => fileRef.current?.click()} className="flex items-center gap-1.5 px-3 py-1.5 bg-subtle border border-default hover:bg-hover rounded-lg text-xs font-semibold text-body cursor-pointer"><Upload className="w-3.5 h-3.5" /> Upload</button>
              <input ref={fileRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.webp,.csv,.xlsx,.docx" onChange={upload} />
            </div>
            {attachments.length === 0 ? <p className="text-xs text-muted">No attachments.</p> : (
              <ul className="space-y-1.5">
                {attachments.map((a) => (
                  <li key={a.filename} className="flex items-center justify-between gap-2 text-xs">
                    <a href={a.url} target="_blank" rel="noreferrer" className="text-indigo-600 dark:text-indigo-400 hover:underline truncate">{a.filename}</a>
                    <button onClick={async () => { await taskApi.deleteAttachment(task.id, a.filename); load(); }} className="text-muted hover:text-status-danger-fg cursor-pointer"><Trash2 className="w-3.5 h-3.5" /></button>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* Comments */}
          <div className="bg-card border border-default p-4 rounded-2xl shadow-xs">
            <h3 className="text-sm font-semibold text-strong mb-3 flex items-center gap-2"><MessageSquare className="w-4 h-4 text-muted" /> Comments</h3>
            <div className="flex gap-2 mb-3">
              <input value={newComment} onChange={(e) => setNewComment(e.target.value)} onKeyDown={(e) => { if (e.key === 'Enter') addComment(); }} placeholder="Add a comment…" className="flex-1 px-3 py-2 bg-subtle border border-default rounded-lg text-xs text-strong placeholder:text-muted focus:outline-none focus:ring-1 focus:ring-indigo-500" />
              <button onClick={addComment} className="px-3 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-lg text-xs font-semibold cursor-pointer">Post</button>
            </div>
            {comments.length === 0 ? <p className="text-xs text-muted">No comments.</p> : (
              <ul className="space-y-2">
                {comments.map((c) => {
                  const u = users.find((x) => x.id === c.created_by);
                  return (
                    <li key={c.id} className="text-xs">
                      <span className="text-body">{c.body}</span>
                      <span className="text-muted"> — {u ? `${u.first_name || ''} ${u.last_name || ''}`.trim() : 'User'}, {new Date(c.created_at).toLocaleString()}</span>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
