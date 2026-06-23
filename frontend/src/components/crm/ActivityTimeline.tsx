import React, { useEffect, useState } from 'react';
import { activityApi, ActivityResponse } from '../../services/activityApi';
// Let's import useUserStore from '../../store/userStore'
import { useUserStore as useUsersListStore } from '../../store/userStore';
import { Phone, Calendar, Mail, CheckSquare, Plus, Trash2, CheckCircle2, Circle, Loader2, AlertCircle } from 'lucide-react';

interface ActivityTimelineProps {
  leadId?: string;
  contactId?: string;
  companyId?: string;
}

export const ActivityTimeline: React.FC<ActivityTimelineProps> = ({
  leadId,
  contactId,
  companyId
}) => {
  const [activities, setActivities] = useState<ActivityResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isAdding, setIsAdding] = useState(false);

  // Form states
  const [activityType, setActivityType] = useState('Call');
  const [subject, setSubject] = useState('');
  const [description, setDescription] = useState('');
  const [dueDate, setDueDate] = useState('');
  const [status, setStatus] = useState('Planned');
  const [assignedUserId, setAssignedUserId] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Load active users from userStore for assignee selection
  const { users, fetchUsers } = useUsersListStore();
  const activeUsers = users.filter(u => u.is_active);

  const fetchActivities = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await activityApi.getActivities({
        lead_id: leadId,
        contact_id: contactId,
        company_id: companyId
      });
      // Sort by due_date or created_at desc
      const sorted = data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setActivities(sorted);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load activities');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchActivities();
    if (users.length === 0) {
      fetchUsers();
    }
  }, [leadId, contactId, companyId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!subject.trim()) return;

    setIsSubmitting(true);
    try {
      const payload = {
        activity_type: activityType,
        subject,
        description: description.trim() || null,
        due_date: dueDate ? new Date(dueDate).toISOString() : null,
        status,
        assigned_user_id: assignedUserId || null,
        lead_id: leadId || null,
        contact_id: contactId || null,
        company_id: companyId || null
      };

      await activityApi.createActivity(payload);
      setSubject('');
      setDescription('');
      setDueDate('');
      setAssignedUserId('');
      setStatus('Planned');
      setIsAdding(false);
      await fetchActivities();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to log activity');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleToggleStatus = async (activity: ActivityResponse) => {
    const nextStatus = activity.status === 'Completed' ? 'Planned' : 'Completed';
    try {
      await activityApi.updateActivity(activity.id, { status: nextStatus });
      await fetchActivities();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to update status');
    }
  };

  const handleDelete = async (activityId: string) => {
    if (window.confirm('Are you sure you want to delete this activity?')) {
      try {
        await activityApi.deleteActivity(activityId);
        await fetchActivities();
      } catch (err: any) {
        alert(err.response?.data?.detail || 'Failed to delete activity');
      }
    }
  };

  const getActivityIcon = (type: string) => {
    switch (type) {
      case 'Call':
        return <Phone className="w-4 h-4 text-emerald-400" />;
      case 'Meeting':
        return <Calendar className="w-4 h-4 text-blue-400" />;
      case 'Email':
        return <Mail className="w-4 h-4 text-amber-400" />;
      case 'Task':
      default:
        return <CheckSquare className="w-4 h-4 text-purple-400" />;
    }
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Activity History</h3>
        <button
          onClick={() => setIsAdding(!isAdding)}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-900 border border-slate-800 hover:border-slate-700 active:bg-slate-950 rounded-xl text-xs font-semibold text-brand-400 transition-all cursor-pointer"
        >
          <Plus className="w-3.5 h-3.5" />
          Log Activity
        </button>
      </div>

      {/* Add Activity Form */}
      {isAdding && (
        <form onSubmit={handleSubmit} className="p-4 bg-slate-900/60 border border-slate-800/80 rounded-xl space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Type</label>
              <select
                value={activityType}
                onChange={(e) => setActivityType(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
              >
                <option value="Call">Call</option>
                <option value="Meeting">Meeting</option>
                <option value="Email">Email</option>
                <option value="Task">Task</option>
              </select>
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Status</label>
              <select
                value={status}
                onChange={(e) => setStatus(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
              >
                <option value="Planned">Planned</option>
                <option value="Completed">Completed</option>
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Subject</label>
            <input
              type="text"
              placeholder="e.g. Follow-up call, Initial intro"
              value={subject}
              onChange={(e) => setSubject(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
              required
            />
          </div>

          <div>
            <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Description</label>
            <textarea
              placeholder="Summary notes about the task or activity..."
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              className="w-full px-3 py-2 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50 h-16 resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Due Date</label>
              <input
                type="datetime-local"
                value={dueDate}
                onChange={(e) => setDueDate(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
              />
            </div>
            <div>
              <label className="block text-[10px] font-semibold text-slate-400 uppercase tracking-wider mb-1">Assignee</label>
              <select
                value={assignedUserId}
                onChange={(e) => setAssignedUserId(e.target.value)}
                className="w-full px-2.5 py-1.5 bg-slate-950 border border-slate-800 rounded-lg text-xs text-slate-200 focus:outline-none focus:border-brand-500/50"
              >
                <option value="">Unassigned</option>
                {activeUsers.map(u => (
                  <option key={u.id} value={u.id}>{`${u.first_name || ''} ${u.last_name || ''}`.trim() || u.email}</option>
                ))}
              </select>
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-1.5">
            <button
              type="button"
              onClick={() => setIsAdding(false)}
              className="px-3 py-1.5 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-400 transition-all cursor-pointer"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="px-3.5 py-1.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-lg text-xs font-semibold shadow transition-all cursor-pointer"
            >
              {isSubmitting ? 'Logging...' : 'Save Activity'}
            </button>
          </div>
        </form>
      )}

      {/* Timeline List */}
      {isLoading ? (
        <div className="py-12 flex justify-center text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : error ? (
        <div className="p-4 border border-red-500/20 bg-red-500/5 text-red-400 text-xs rounded-xl flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          <p>{error}</p>
        </div>
      ) : activities.length === 0 ? (
        <div className="p-8 border border-dashed border-slate-800 rounded-xl text-center text-xs text-slate-500">
          No activities logged yet.
        </div>
      ) : (
        <div className="relative border-l border-slate-800 pl-4.5 space-y-5 py-2">
          {activities.map((activity) => {
            const isCompleted = activity.status === 'Completed';
            const assigneeUser = users.find(u => u.id === activity.assigned_user_id);
            const assigneeName = assigneeUser ? `${assigneeUser.first_name || ''} ${assigneeUser.last_name || ''}`.trim() : null;

            const formatDuration = (seconds?: number | null) => {
              if (seconds === undefined || seconds === null) return null;
              const m = Math.floor(seconds / 60);
              const s = seconds % 60;
              return m > 0 ? `${m}m ${s}s` : `${s}s`;
            };

            return (
              <div key={activity.id} className="relative group">
                {/* Timeline Dot */}
                <div className="absolute -left-[27px] top-0.5 bg-slate-950 p-1 border border-slate-800 rounded-full flex items-center justify-center">
                  {getActivityIcon(activity.activity_type)}
                </div>

                <div className="space-y-1">
                  <div className="flex items-start justify-between gap-4">
                    <div className="flex items-center gap-2">
                      {/* Checkbox status toggle */}
                      <button
                        onClick={() => handleToggleStatus(activity)}
                        title={isCompleted ? 'Mark as Planned' : 'Mark as Completed'}
                        className="text-slate-500 hover:text-brand-400 cursor-pointer shrink-0 transition-colors"
                      >
                        {isCompleted ? (
                          <CheckCircle2 className="w-4 h-4 text-brand-500" />
                        ) : (
                          <Circle className="w-4 h-4" />
                        )}
                      </button>
                      <h4 className={`text-sm font-semibold ${isCompleted ? 'line-through text-slate-500' : 'text-slate-200'}`}>
                        {activity.subject}
                      </h4>
                    </div>

                    <button
                      onClick={() => handleDelete(activity.id)}
                      className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 cursor-pointer transition-all p-1"
                      title="Delete Activity"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>

                  {activity.description && (
                    <p className="text-xs text-slate-400 pl-6 leading-relaxed whitespace-pre-line">
                      {activity.description}
                    </p>
                  )}

                  {activity.activity_type === 'Call' && activity.recording_url && (
                    <div className="pl-6 pt-1">
                      <audio src={activity.recording_url} controls className="h-8 max-w-full rounded bg-slate-900 border border-slate-800" />
                    </div>
                  )}

                  <div className="flex flex-wrap items-center gap-x-3 gap-y-1 text-[10px] text-slate-500 pl-6 pt-1">
                    <span>
                      {new Date(activity.created_at).toLocaleString()}
                    </span>
                    {activity.due_date && (
                      <span className="flex items-center gap-1 text-slate-400">
                        <Calendar className="w-3 h-3" />
                        Due: {new Date(activity.due_date).toLocaleDateString()}
                      </span>
                    )}
                    {assigneeName && (
                      <span className="px-1.5 py-0.5 bg-slate-900 border border-slate-800 text-slate-400 rounded">
                        {assigneeName}
                      </span>
                    )}
                    {activity.activity_type === 'Call' && activity.call_direction && (
                      <span className={`px-1.5 py-0.5 rounded font-medium border ${
                        activity.call_direction === 'INBOUND' 
                          ? 'bg-blue-500/10 border-blue-500/20 text-blue-400' 
                          : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'
                      }`}>
                        {activity.call_direction}
                      </span>
                    )}
                    {activity.activity_type === 'Call' && activity.call_duration !== undefined && activity.call_duration !== null && (
                      <span className="px-1.5 py-0.5 bg-slate-900 border border-slate-800 text-slate-400 rounded">
                        {formatDuration(activity.call_duration)}
                      </span>
                    )}
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
