import React, { useEffect, useState } from 'react';
import { noteApi, NoteResponse } from '../../services/noteApi';
import { useUserStore as useUsersListStore } from '../../store/userStore';
import { Trash2, AlertCircle, Loader2, Send } from 'lucide-react';

interface NotesPanelProps {
  leadId?: string;
  contactId?: string;
  companyId?: string;
}

export const NotesPanel: React.FC<NotesPanelProps> = ({
  leadId,
  contactId,
  companyId
}) => {
  const [notes, setNotes] = useState<NoteResponse[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [content, setContent] = useState('');
  const [isSubmitting, setIsSubmitting] = useState(false);

  const { users, fetchUsers } = useUsersListStore();

  const fetchNotes = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const data = await noteApi.getNotes({
        lead_id: leadId,
        contact_id: contactId,
        company_id: companyId
      });
      const sorted = data.sort((a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime());
      setNotes(sorted);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Failed to load notes');
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchNotes();
    if (users.length === 0) {
      fetchUsers();
    }
  }, [leadId, contactId, companyId]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    setIsSubmitting(true);
    try {
      const payload = {
        content: content.trim(),
        lead_id: leadId || null,
        contact_id: contactId || null,
        company_id: companyId || null
      };

      await noteApi.createNote(payload);
      setContent('');
      await fetchNotes();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'Failed to add note');
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleDelete = async (noteId: string) => {
    if (window.confirm('Are you sure you want to delete this note?')) {
      try {
        await noteApi.deleteNote(noteId);
        await fetchNotes();
      } catch (err: any) {
        alert(err.response?.data?.detail || 'Failed to delete note');
      }
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-sm font-semibold text-slate-200 uppercase tracking-wider">Internal Notes</h3>

      {/* Add Note Input Box */}
      <form onSubmit={handleSubmit} className="flex gap-2">
        <input
          type="text"
          placeholder="Type a new note..."
          value={content}
          onChange={(e) => setContent(e.target.value)}
          className="flex-1 px-3 py-2 bg-slate-900 border border-slate-800 rounded-xl text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/50"
          required
        />
        <button
          type="submit"
          disabled={isSubmitting || !content.trim()}
          className="px-3.5 bg-brand-500 hover:bg-brand-600 disabled:opacity-50 text-white rounded-xl text-xs font-semibold shadow transition-all cursor-pointer flex items-center justify-center"
        >
          {isSubmitting ? (
            <Loader2 className="w-3.5 h-3.5 animate-spin" />
          ) : (
            <Send className="w-3.5 h-3.5" />
          )}
        </button>
      </form>

      {/* Notes list */}
      {isLoading ? (
        <div className="py-8 flex justify-center text-slate-500">
          <Loader2 className="w-5 h-5 animate-spin" />
        </div>
      ) : error ? (
        <div className="p-3 border border-red-500/20 bg-red-500/5 text-red-400 text-xs rounded-xl flex items-center gap-2">
          <AlertCircle className="w-4 h-4" />
          <p>{error}</p>
        </div>
      ) : notes.length === 0 ? (
        <div className="p-6 border border-dashed border-slate-800 rounded-xl text-center text-xs text-slate-500">
          No notes added.
        </div>
      ) : (
        <div className="space-y-3">
          {notes.map((note) => {
            const author = users.find(u => u.id === note.created_by);
            const authorName = author ? `${author.first_name || ''} ${author.last_name || ''}`.trim() : note.created_by;

            return (
              <div
                key={note.id}
                className="p-3 bg-slate-900/30 border border-slate-800/80 rounded-xl group space-y-1.5"
              >
                <div className="flex items-start justify-between gap-4">
                  <span className="text-[10px] font-bold text-brand-400">
                    {authorName}
                  </span>
                  <div className="flex items-center gap-2 shrink-0">
                    <span className="text-[9px] text-slate-500">
                      {new Date(note.created_at).toLocaleString()}
                    </span>
                    <button
                      onClick={() => handleDelete(note.id)}
                      className="opacity-0 group-hover:opacity-100 text-slate-600 hover:text-red-400 cursor-pointer transition-all"
                      title="Delete Note"
                    >
                      <Trash2 className="w-3.5 h-3.5" />
                    </button>
                  </div>
                </div>
                <p className="text-xs text-slate-300 leading-relaxed break-words whitespace-pre-wrap">
                  {note.content}
                </p>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
};
