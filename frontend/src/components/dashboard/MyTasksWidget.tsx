import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { taskApi, Task } from '../../services/taskApi';
import { ListChecks, CheckCircle2, Circle, Clock, Loader2 } from 'lucide-react';

const PRIORITY_DOT: Record<string, string> = {
  Urgent: 'bg-red-400', High: 'bg-amber-400', Medium: 'bg-slate-400', Low: 'bg-slate-600',
};

export const MyTasksWidget: React.FC = () => {
  const [tasks, setTasks] = useState<Task[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const navigate = useNavigate();

  const load = async () => {
    try {
      const open = await taskApi.list({ status: 'Todo', limit: 6 });
      const inprog = await taskApi.list({ status: 'InProgress', limit: 6 });
      setTasks([...inprog, ...open].slice(0, 6));
    } catch { /* silent */ } finally { setIsLoading(false); }
  };
  useEffect(() => { load(); }, []);

  const complete = async (e: React.MouseEvent, t: Task) => {
    e.stopPropagation();
    try { await taskApi.complete(t.id); load(); } catch (er: any) { alert(er.response?.data?.detail || 'Failed'); }
  };

  return (
    <div className="glass-panel border border-slate-800/85 rounded-2xl p-5">
      <div className="flex items-center justify-between mb-4">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2"><ListChecks className="w-4 h-4 text-brand-400" /> My Tasks</h3>
        <button onClick={() => navigate('/tasks')} className="text-xs text-brand-400 hover:text-brand-300 cursor-pointer">View all</button>
      </div>
      {isLoading ? (
        <div className="py-6 text-center text-slate-400"><Loader2 className="w-5 h-5 animate-spin inline" /></div>
      ) : tasks.length === 0 ? (
        <p className="text-xs text-slate-500">No open tasks. 🎉</p>
      ) : (
        <ul className="space-y-2">
          {tasks.map((t) => (
            <li key={t.id} onClick={() => navigate(`/tasks?taskId=${t.id}`)} className="flex items-center gap-2.5 p-2 bg-slate-950/40 border border-slate-800/60 rounded-lg cursor-pointer hover:border-slate-700">
              <button onClick={(e) => complete(e, t)} className="shrink-0 cursor-pointer">
                {t.status === 'Done' ? <CheckCircle2 className="w-4 h-4 text-emerald-400" /> : <Circle className="w-4 h-4 text-slate-600 hover:text-slate-400" />}
              </button>
              <span className={`w-1.5 h-1.5 rounded-full shrink-0 ${PRIORITY_DOT[t.priority] || PRIORITY_DOT.Medium}`}></span>
              <span className="text-xs text-slate-200 truncate flex-1">{t.title}</span>
              {t.due_date && <span className="text-[10px] text-slate-500 flex items-center gap-1 shrink-0"><Clock className="w-3 h-3" />{new Date(t.due_date).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}</span>}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
