import React, { useEffect, useState } from 'react';
import { leadApi, SavedFilter } from '../../services/leadApi';
import { Bookmark, Plus, Trash2 } from 'lucide-react';

interface Props {
  currentFilters: Record<string, any>;
  onApply: (definition: Record<string, any>) => void;
}

export const SavedFilters: React.FC<Props> = ({ currentFilters, onApply }) => {
  const [filters, setFilters] = useState<SavedFilter[]>([]);
  const [selected, setSelected] = useState('');

  const load = async () => {
    try {
      setFilters(await leadApi.listSavedFilters('lead'));
    } catch {
      /* silent */
    }
  };

  useEffect(() => {
    load();
  }, []);

  const handleApply = (id: string) => {
    setSelected(id);
    const sf = filters.find((f) => f.id === id);
    if (sf) onApply(sf.definition);
  };

  const handleSave = async () => {
    const name = window.prompt('Name this filter:');
    if (!name) return;
    try {
      await leadApi.createSavedFilter({ name, entity_type: 'lead', definition: currentFilters });
      await load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to save filter');
    }
  };

  const handleDelete = async () => {
    if (!selected) return;
    try {
      await leadApi.deleteSavedFilter(selected);
      setSelected('');
      await load();
    } catch (e: any) {
      alert(e.response?.data?.detail || 'Failed to delete filter');
    }
  };

  return (
    <div className="flex items-center gap-2">
      <div className="relative flex items-center">
        <Bookmark className="w-3.5 h-3.5 text-slate-500 absolute left-3 pointer-events-none" />
        <select
          value={selected}
          onChange={(e) => handleApply(e.target.value)}
          className="pl-8 pr-3 py-2.5 bg-slate-900 border border-slate-800 rounded-xl text-sm text-slate-200 focus:outline-none focus:border-brand-500/50 transition-all cursor-pointer"
        >
          <option value="">Saved filters…</option>
          {filters.map((f) => (
            <option key={f.id} value={f.id}>
              {f.name}{f.is_shared ? ' (shared)' : ''}
            </option>
          ))}
        </select>
      </div>
      <button
        onClick={handleSave}
        title="Save current filters"
        className="p-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-slate-400 hover:text-slate-200 transition-all cursor-pointer"
      >
        <Plus className="w-4 h-4" />
      </button>
      {selected && (
        <button
          onClick={handleDelete}
          title="Delete selected filter"
          className="p-2.5 bg-slate-900 border border-slate-800 hover:border-slate-700 rounded-xl text-slate-400 hover:text-red-400 transition-all cursor-pointer"
        >
          <Trash2 className="w-4 h-4" />
        </button>
      )}
    </div>
  );
};
