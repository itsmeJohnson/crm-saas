import React, { useState, useEffect } from 'react';
import {
  Clock, CheckCircle2, Phone, MessageSquare, Search, RefreshCw
} from 'lucide-react';
import { api } from '../../services/api';

export const FollowupsPage: React.FC = () => {
  const [tasks, setTasks] = useState<any[]>([]);
  const [activeTab, setActiveTab] = useState<'due_today' | 'overdue' | 'recall' | 'upcoming' | 'completed'>('due_today');
  const [search, setSearch] = useState('');
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    fetchFollowups();
  }, []);

  const fetchFollowups = async () => {
    setIsLoading(true);
    try {
      const res = await api.get('/tasks/?limit=100');
      const list = res.data?.items || res.data || [];
      setTasks(list);
    } catch (e) {
      console.error(e);
    } finally {
      setIsLoading(false);
    }
  };

  const handleMarkDone = async (taskId: string) => {
    try {
      await api.patch(`/tasks/${taskId}`, { status: 'Done' });
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: 'Done' } : t));
    } catch {
      setTasks(prev => prev.map(t => t.id === taskId ? { ...t, status: 'Done' } : t));
    }
  };

  const now = new Date();
  const todayStr = now.toISOString().split('T')[0];

  const filteredTasks = tasks.filter((t) => {
    const title = (t.title || '').toLowerCase();
    const desc = (t.description || '').toLowerCase();
    const matchesSearch = title.includes(search.toLowerCase()) || desc.includes(search.toLowerCase());

    const isDone = t.status === 'Done';
    const isRecall = title.includes('recall');
    const tDate = t.due_date ? new Date(t.due_date).toISOString().split('T')[0] : todayStr;
    const isPast = t.due_date && new Date(t.due_date) < now && tDate !== todayStr;
    const isToday = tDate === todayStr;

    let matchesTab = false;
    if (activeTab === 'completed') matchesTab = isDone;
    else if (!isDone) {
      if (activeTab === 'recall') matchesTab = isRecall;
      else if (activeTab === 'overdue') matchesTab = isPast && !isRecall;
      else if (activeTab === 'due_today') matchesTab = isToday;
      else if (activeTab === 'upcoming') matchesTab = !isPast && !isToday;
    }

    return matchesSearch && matchesTab;
  });

  const dueTodayCount = tasks.filter(t => t.status !== 'Done' && (t.due_date ? new Date(t.due_date).toISOString().split('T')[0] === todayStr : true)).length;
  const overdueCount = tasks.filter(t => t.status !== 'Done' && t.due_date && new Date(t.due_date) < now && new Date(t.due_date).toISOString().split('T')[0] !== todayStr).length;
  const recallCount = tasks.filter(t => t.status !== 'Done' && (t.title || '').toLowerCase().includes('recall')).length;

  return (
    <div className="space-y-6 select-none">
      {/* Header Bento */}
      <div className="bento-card p-6 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div className="flex items-center gap-3.5">
          <div className="w-12 h-12 rounded-2xl bg-gradient-to-br from-amber-400 to-orange-500 flex items-center justify-center text-white shadow-lg shadow-amber-500/25 flex-shrink-0">
            <Clock className="w-6 h-6" />
          </div>
          <div>
            <h1 className="text-xl font-black text-slate-100">
              Follow-up &amp; 6-Month Recall Center
            </h1>
            <p className="text-xs text-slate-400 mt-0.5">
              Post-op recovery calls, treatment inquiry follow-ups &amp; automated preventive recall schedules.
            </p>
          </div>
        </div>

        <button
          onClick={fetchFollowups}
          className="neo-btn px-4 py-2.5 text-xs text-slate-300 self-start sm:self-auto"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`} />
          Refresh Queues
        </button>
      </div>

      {/* Tab Selector Bento */}
      <div className="bento-card p-4 space-y-3">
        <div className="flex items-center gap-2 overflow-x-auto">
          {[
            { id: 'due_today', label: 'Due Today', count: dueTodayCount, color: 'text-amber-400' },
            { id: 'overdue', label: 'Overdue', count: overdueCount, color: 'text-rose-400' },
            { id: 'recall', label: '6M Recalls Due', count: recallCount, color: 'text-purple-400' },
            { id: 'upcoming', label: 'Upcoming', count: tasks.length - dueTodayCount - overdueCount },
            { id: 'completed', label: 'Completed' },
          ].map((tab) => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id as any)}
              className={`px-4 py-2 rounded-xl text-xs font-bold whitespace-nowrap transition cursor-pointer flex items-center gap-2 ${
                activeTab === tab.id
                  ? 'neo-btn-primary'
                  : 'neo-btn text-slate-400 hover:text-slate-200'
              }`}
            >
              <span>{tab.label}</span>
              {tab.count !== undefined && tab.count > 0 && (
                <span className="neo-pill text-[10px] py-0 px-1.5 font-bold">
                  {tab.count}
                </span>
              )}
            </button>
          ))}
        </div>

        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3.5 top-1/2 -translate-y-1/2" />
          <input
            type="text"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search patient name, procedure, or remarks..."
            className="neo-input w-full pl-10 pr-4 py-2 text-xs"
          />
        </div>
      </div>

      {/* Task Queue Cards Bento */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
        {isLoading ? (
          <div className="col-span-full neo-inset p-12 text-center text-slate-400">
            <RefreshCw className="w-5 h-5 animate-spin mx-auto text-cyan-400 mb-2" />
            Loading follow-up queues...
          </div>
        ) : filteredTasks.length === 0 ? (
          <div className="col-span-full neo-inset p-12 text-center text-slate-400 space-y-2">
            <CheckCircle2 className="w-8 h-8 mx-auto text-emerald-400" />
            <p className="text-xs font-bold text-slate-300">No tasks pending in this queue!</p>
            <p className="text-[11px] text-slate-500">All follow-ups and routine recalls are up to date.</p>
          </div>
        ) : (
          filteredTasks.map((task) => {
            const isDone = task.status === 'Done';
            const isRecall = (task.title || '').toLowerCase().includes('recall');

            return (
              <div
                key={task.id}
                className="bento-card p-5 space-y-3.5 hover:scale-[1.01] transition-transform duration-200"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className={`neo-pill text-[10px] font-bold ${
                    isRecall
                      ? 'text-purple-400 bg-purple-500/10 border-purple-500/20'
                      : 'text-amber-400 bg-amber-500/10 border-amber-500/20'
                  }`}>
                    {isRecall ? '6-Month Routine Recall' : 'Clinical Follow-up'}
                  </span>
                  <span className="text-[10px] text-slate-500 font-medium">
                    {task.due_date ? new Date(task.due_date).toLocaleDateString('en-IN') : 'Today'}
                  </span>
                </div>

                <div>
                  <h3 className="text-xs font-bold text-slate-100 line-clamp-1">
                    {task.title}
                  </h3>
                  <p className="text-[11px] text-slate-400 line-clamp-2 mt-1">
                    {task.description || 'Call patient for follow-up review.'}
                  </p>
                </div>

                <div className="pt-3 border-t border-slate-800/40 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => alert(`Initiating Call to patient for: ${task.title}`)}
                      className="neo-btn px-2.5 py-1 text-xs text-cyan-400 flex items-center gap-1 font-semibold"
                    >
                      <Phone className="w-3 h-3" /> Call
                    </button>
                    <button
                      onClick={() => alert(`Opening WhatsApp chat for: ${task.title}`)}
                      className="neo-btn px-2.5 py-1 text-xs text-emerald-400 flex items-center gap-1 font-semibold"
                    >
                      <MessageSquare className="w-3 h-3" /> WA
                    </button>
                  </div>

                  {!isDone && (
                    <button
                      onClick={() => handleMarkDone(task.id)}
                      className="neo-btn p-1.5 text-emerald-400 hover:text-emerald-300"
                      title="Mark Completed"
                    >
                      <CheckCircle2 className="w-4 h-4" />
                    </button>
                  )}
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};

export default FollowupsPage;
