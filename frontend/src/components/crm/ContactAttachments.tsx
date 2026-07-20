import React, { useEffect, useRef, useState } from 'react';
import { contactApi, ContactAttachment } from '../../services/contactApi';
import { Paperclip, Upload, Trash2, Loader2, FileText } from 'lucide-react';

export const ContactAttachments: React.FC<{ contactId: string }> = ({ contactId }) => {
  const [attachments, setAttachments] = useState<ContactAttachment[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const load = async () => {
    try {
      setAttachments(await contactApi.listAttachments(contactId));
    } catch {
      /* silent */
    }
  };
  useEffect(() => { load(); }, [contactId]);

  const handleUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setIsUploading(true);
    setError(null);
    try {
      await contactApi.uploadAttachment(contactId, file);
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Upload failed');
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (filename: string) => {
    try {
      await contactApi.deleteAttachment(contactId, filename);
      await load();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'Delete failed');
    }
  };

  return (
    <div>
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold text-slate-200 flex items-center gap-2">
          <Paperclip className="w-4 h-4 text-brand-400" /> Attachments
        </h3>
        <button
          onClick={() => fileInputRef.current?.click()}
          disabled={isUploading}
          className="flex items-center gap-1.5 px-3 py-1.5 bg-slate-950 border border-slate-800 hover:border-slate-700 rounded-lg text-xs font-semibold text-slate-300 hover:text-slate-100 transition-all cursor-pointer disabled:opacity-50"
        >
          {isUploading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Upload className="w-3.5 h-3.5" />} Upload
        </button>
        <input ref={fileInputRef} type="file" className="hidden" accept=".pdf,.png,.jpg,.jpeg,.webp,.csv,.xlsx,.docx" onChange={handleUpload} />
      </div>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
      {attachments.length === 0 ? (
        <p className="text-xs text-slate-500">No attachments yet.</p>
      ) : (
        <ul className="space-y-2">
          {attachments.map((a) => (
            <li key={a.filename + (a.uploaded_at || '')} className="flex items-center justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">
              <a href={a.url} target="_blank" rel="noreferrer" className="flex items-center gap-2 text-xs text-brand-400 hover:text-brand-300 truncate">
                <FileText className="w-3.5 h-3.5 shrink-0" />
                <span className="truncate">{a.filename}</span>
              </a>
              <button onClick={() => handleDelete(a.filename)} className="p-1 text-slate-500 hover:text-red-400 transition-colors cursor-pointer shrink-0" title="Delete">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
