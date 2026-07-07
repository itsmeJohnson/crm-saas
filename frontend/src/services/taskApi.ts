import { api } from './api';

export interface ChecklistItem { id?: string; text: string; done: boolean }

export interface TaskAttachment { filename: string; url: string; size?: number; uploaded_by?: string; uploaded_at?: string }

export interface Task {
  id: string;
  organization_id: string;
  title: string;
  description: string | null;
  priority: string;
  status: string;
  due_date: string | null;
  remind_at: string | null;
  completed_at: string | null;
  assigned_user_id: string | null;
  created_by: string;
  lead_id: string | null;
  contact_id: string | null;
  company_id: string | null;
  recurrence: string;
  recurrence_parent_id: string | null;
  checklist: ChecklistItem[] | null;
  attachments: TaskAttachment[] | null;
  created_at: string;
  updated_at: string;
}

export interface TaskComment { id: string; task_id: string; body: string; created_by: string; created_at: string }
export interface TaskDependency { id: string; task_id: string; depends_on_task_id: string; depends_on_title: string | null; depends_on_status: string | null }

export interface TaskListFilters {
  status?: string; priority?: string; assigned_user_id?: string;
  lead_id?: string; contact_id?: string; company_id?: string;
  overdue?: boolean; due_from?: string; due_to?: string; search?: string; skip?: number; limit?: number;
}

export interface TaskReport {
  total: number; open: number; completed: number; overdue: number; due_today: number; completion_rate: number;
  by_status: { label: string; count: number }[];
  by_priority: { label: string; count: number }[];
  by_assignee: { label: string; count: number }[];
}

type TaskWrite = Partial<{
  title: string; description: string | null; priority: string; status: string;
  due_date: string | null; remind_at: string | null; assigned_user_id: string | null;
  lead_id: string | null; contact_id: string | null; company_id: string | null;
  recurrence: string; checklist: ChecklistItem[] | null;
}>;

export const taskApi = {
  list: async (params: TaskListFilters) => {
    const response = await api.get<Task[]>('/tasks/', { params });
    return response.data;
  },
  get: async (id: string) => (await api.get<Task>(`/tasks/${id}`)).data,
  create: async (payload: TaskWrite & { title: string }) => (await api.post<Task>('/tasks/', payload)).data,
  update: async (id: string, payload: TaskWrite) => (await api.patch<Task>(`/tasks/${id}`, payload)).data,
  remove: async (id: string) => { await api.delete(`/tasks/${id}`); },
  complete: async (id: string) => (await api.post<Task>(`/tasks/${id}/complete`)).data,
  toggleChecklist: async (id: string, itemId: string, done: boolean) =>
    (await api.patch<Task>(`/tasks/${id}/checklist`, { item_id: itemId, done })).data,

  listComments: async (id: string) => (await api.get<TaskComment[]>(`/tasks/${id}/comments`)).data,
  addComment: async (id: string, body: string) => (await api.post<TaskComment>(`/tasks/${id}/comments`, { body })).data,
  deleteComment: async (id: string, commentId: string) => { await api.delete(`/tasks/${id}/comments/${commentId}`); },

  listAttachments: async (id: string) => (await api.get<TaskAttachment[]>(`/tasks/${id}/attachments`)).data,
  uploadAttachment: async (id: string, file: File) => {
    const form = new FormData(); form.append('file', file);
    return (await api.post<TaskAttachment>(`/tasks/${id}/attachments`, form, { headers: { 'Content-Type': 'multipart/form-data' } })).data;
  },
  deleteAttachment: async (id: string, filename: string) => { await api.delete(`/tasks/${id}/attachments/${encodeURIComponent(filename)}`); },

  listDependencies: async (id: string) => (await api.get<TaskDependency[]>(`/tasks/${id}/dependencies`)).data,
  addDependency: async (id: string, dependsOn: string) => (await api.post<TaskDependency>(`/tasks/${id}/dependencies`, { depends_on_task_id: dependsOn })).data,
  deleteDependency: async (id: string, depId: string) => { await api.delete(`/tasks/${id}/dependencies/${depId}`); },

  bulkUpdate: async (taskIds: string[], fields: { status?: string; priority?: string; assigned_user_id?: string }) =>
    (await api.post<{ affected_count: number; task_ids: string[] }>('/tasks/bulk-update', { task_ids: taskIds, fields })).data,
  bulkDelete: async (taskIds: string[]) =>
    (await api.post<{ affected_count: number; task_ids: string[] }>('/tasks/bulk-delete', { task_ids: taskIds })).data,

  calendar: async (from: string, to: string) => (await api.get<Task[]>('/tasks/calendar', { params: { date_from: from, date_to: to } })).data,
  report: async () => (await api.get<TaskReport>('/tasks/reports')).data,
};
