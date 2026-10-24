import React from 'react';
import { Search, RotateCcw, X, SlidersHorizontal } from 'lucide-react';

export interface FilterChip {
  id: string;
  label: string;
  value: string;
  onRemove: () => void;
}

interface FiltersProps {
  search: string;
  onSearchChange: (val: string) => void;
  placeholder?: string;
  onReset: () => void;
  children?: React.ReactNode;
  activeChips?: FilterChip[];
  extraFilters?: React.ReactNode;
  hasActiveFilters?: boolean;
}

export const Filters: React.FC<FiltersProps> = ({
  search,
  onSearchChange,
  placeholder = 'Search leads by name, company, email, phone, or title...',
  onReset,
  children,
  activeChips = [],
  extraFilters,
}) => {
  const [showAdvanced, setShowAdvanced] = React.useState(false);
  const [localSearch, setLocalSearch] = React.useState(search);

  // Sync external changes (reset or chip removal)
  React.useEffect(() => {
    setLocalSearch(search);
  }, [search]);

  // Debounce keystrokes by 300ms
  React.useEffect(() => {
    if (localSearch === search) return;
    const timer = setTimeout(() => {
      onSearchChange(localSearch);
    }, 300);
    return () => clearTimeout(timer);
  }, [localSearch, search, onSearchChange]);

  const handleClear = () => {
    setLocalSearch('');
    onSearchChange('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      onSearchChange(localSearch);
    }
  };

  return (
    <div className="space-y-2 mb-3">
      {/* Main Filter Bar */}
      <div className="bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 shadow-xs p-2.5 sm:p-3 rounded-xl flex flex-wrap items-center gap-2">
        {/* Search */}
        <div className="relative flex-1 min-w-[220px]">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-400" />
          <input
            type="text"
            placeholder={placeholder}
            value={localSearch}
            onChange={(e) => setLocalSearch(e.target.value)}
            onKeyDown={handleKeyDown}
            className="w-full pl-9 pr-8 py-2 bg-slate-50 dark:bg-slate-800/80 border border-slate-200 dark:border-slate-700 rounded-lg text-xs text-slate-900 dark:text-slate-100 placeholder-slate-400 focus:outline-hidden focus:bg-white dark:focus:bg-slate-800 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-500/20 shadow-xs transition-all"
          />
          {localSearch && (
            <button
              onClick={handleClear}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600 dark:hover:text-slate-200 p-0.5 cursor-pointer"
              title="Clear search"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>

        {/* Quick Select Filters (Status, Owner, Priority) */}
        {children}

        {/* Toggle Advanced Filters Button */}
        {extraFilters && (
          <button
            type="button"
            onClick={() => setShowAdvanced(!showAdvanced)}
            className={`flex items-center gap-1.5 px-3 py-2 border rounded-lg text-xs font-semibold transition-all cursor-pointer shadow-xs ${
              showAdvanced
                ? 'bg-indigo-50 dark:bg-indigo-950/40 border-indigo-200 dark:border-indigo-800 text-indigo-700 dark:text-indigo-300'
                : 'bg-white dark:bg-slate-800 border-slate-200 dark:border-slate-700 text-slate-700 dark:text-slate-300 hover:bg-slate-50 dark:hover:bg-slate-700'
            }`}
            title="Toggle advanced filters"
          >
            <SlidersHorizontal className="w-3.5 h-3.5" />
            <span className="hidden sm:inline">Advanced</span>
          </button>
        )}

        {/* Reset Button */}
        <button
          onClick={onReset}
          className="flex items-center justify-center gap-1.5 px-3 py-2 bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 hover:bg-slate-50 dark:hover:bg-slate-700 active:scale-[0.98] rounded-lg text-xs font-semibold text-slate-700 dark:text-slate-300 transition-all cursor-pointer shrink-0 shadow-xs"
          title="Reset all filters"
        >
          <RotateCcw className="w-3 h-3 text-slate-400" />
          <span>Reset</span>
        </button>
      </div>

      {/* Advanced Filters Drawer/Panel */}
      {showAdvanced && extraFilters && (
        <div className="p-3 bg-white dark:bg-slate-900 border border-slate-200 dark:border-slate-800 rounded-xl flex flex-wrap items-center gap-2.5 shadow-xs animate-in fade-in duration-150">
          {extraFilters}
        </div>
      )}

      {/* Active Filter Chips */}
      {activeChips.length > 0 && (
        <div className="flex items-center gap-2 flex-wrap pt-0.5 px-0.5">
          <span className="text-[11px] font-semibold text-slate-500 dark:text-slate-400">
            Active filters ({activeChips.length}):
          </span>
          {activeChips.map((chip) => (
            <span
              key={chip.id}
              className="inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md bg-white dark:bg-slate-800 border border-slate-200 dark:border-slate-700 text-[11px] text-slate-800 dark:text-slate-200 shadow-xs"
            >
              <span className="text-slate-500 dark:text-slate-400">{chip.label}:</span>
              <span className="font-semibold text-indigo-600 dark:text-indigo-400">{chip.value}</span>
              <button
                type="button"
                onClick={chip.onRemove}
                className="text-slate-400 hover:text-rose-600 transition-colors cursor-pointer ml-0.5"
                title={`Remove ${chip.label} filter`}
              >
                <X className="w-3 h-3" />
              </button>
            </span>
          ))}
          <button
            type="button"
            onClick={onReset}
            className="text-[11px] text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 hover:underline font-medium cursor-pointer ml-1"
          >
            Clear all
          </button>
        </div>
      )}
    </div>
  );
};
