import React, { useEffect, useState } from 'react';
import { contactApi, ContactRelationship, ContactResponse } from '../../services/contactApi';
import { Users, Plus, Trash2 } from 'lucide-react';

const REL_TYPES = ['reports_to', 'manager_of', 'colleague', 'assistant', 'other'];

export const ContactRelationships: React.FC<{ contactId: string }> = ({ contactId }) => {
  const [rels, setRels] = useState<ContactRelationship[]>([]);
  const [options, setOptions] = useState<ContactResponse[]>([]);
  const [relatedId, setRelatedId] = useState('');
  const [relType, setRelType] = useState('colleague');
  const [error, setError] = useState<string | null>(null);

  const load = async () => {
    try {
      setRels(await contactApi.listRelationships(contactId));
    } catch {
      /* silent */
    }
  };

  useEffect(() => {
    load();
    contactApi.getContacts({ limit: 100 }).then((c) => setOptions(c.filter((x) => x.id !== contactId))).catch(() => {});
  }, [contactId]);

  const handleAdd = async () => {
    if (!relatedId) return;
    setError(null);
    try {
      await contactApi.addRelationship(contactId, { related_contact_id: relatedId, relationship_type: relType });
      setRelatedId('');
      await load();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Failed to add relationship');
    }
  };

  const handleDelete = async (id: string) => {
    try {
      await contactApi.deleteRelationship(contactId, id);
      await load();
    } catch {
      /* silent */
    }
  };

  return (
    <div>
      <h3 className="text-sm font-semibold text-slate-200 mb-3 flex items-center gap-2">
        <Users className="w-4 h-4 text-indigo-400" /> Relationships
      </h3>
      <div className="flex flex-col sm:flex-row gap-2 mb-3">
        <select value={relType} onChange={(e) => setRelType(e.target.value)} className="px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200">
          {REL_TYPES.map((t) => <option key={t} value={t}>{t.replace('_', ' ')}</option>)}
        </select>
        <select value={relatedId} onChange={(e) => setRelatedId(e.target.value)} className="flex-1 px-3 py-2 bg-slate-950/50 border border-slate-800 rounded-lg text-xs text-slate-200">
          <option value="">Select contact…</option>
          {options.map((o) => <option key={o.id} value={o.id}>{o.first_name} {o.last_name}</option>)}
        </select>
        <button onClick={handleAdd} className="flex items-center justify-center gap-1.5 px-3 py-2 bg-brand-500 hover:bg-brand-600 text-white rounded-lg text-xs font-semibold cursor-pointer">
          <Plus className="w-3.5 h-3.5" /> Link
        </button>
      </div>
      {error && <p className="text-xs text-red-400 mb-2">{error}</p>}
      {rels.length === 0 ? (
        <p className="text-xs text-slate-500">No linked contacts.</p>
      ) : (
        <ul className="space-y-2">
          {rels.map((r) => (
            <li key={r.id} className="flex items-center justify-between gap-2 p-2 bg-slate-950/40 border border-slate-800/70 rounded-lg">
              <span className="text-xs text-slate-200 truncate">
                <span className="text-slate-500">{r.relationship_type.replace('_', ' ')}:</span> {r.related_contact_name || r.related_contact_id}
              </span>
              <button onClick={() => handleDelete(r.id)} className="p-1 text-slate-500 hover:text-red-400 transition-colors cursor-pointer shrink-0" title="Remove">
                <Trash2 className="w-3.5 h-3.5" />
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
};
