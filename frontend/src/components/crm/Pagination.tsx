import React from 'react';
import { ChevronLeft, ChevronRight, ChevronsLeft, ChevronsRight } from 'lucide-react';

interface PaginationProps {
  skip: number;
  limit: number;
  itemsCount: number;
  totalCount?: number;
  onPageChange: (newSkip: number) => void;
  onLimitChange?: (newLimit: number) => void;
}

export const Pagination: React.FC<PaginationProps> = ({
  skip,
  limit,
  itemsCount,
  totalCount,
  onPageChange,
  onLimitChange,
}) => {
  const currentPage = Math.floor(skip / limit) + 1;
  const total = totalCount !== undefined ? totalCount : (itemsCount < limit ? skip + itemsCount : skip + itemsCount + 1);
  const totalPages = totalCount !== undefined ? Math.max(1, Math.ceil(totalCount / limit)) : (itemsCount < limit ? currentPage : currentPage + 1);
  const startItem = totalCount === 0 ? 0 : skip + 1;
  const endItem = Math.min(skip + itemsCount, totalCount !== undefined ? totalCount : skip + itemsCount);
  const hasPrev = skip > 0;
  const hasNext = totalCount !== undefined ? (skip + limit) < totalCount : itemsCount === limit;

  const handlePrev = () => {
    if (hasPrev) {
      onPageChange(Math.max(0, skip - limit));
    }
  };

  const handleNext = () => {
    if (hasNext) {
      onPageChange(skip + limit);
    }
  };

  const handleFirst = () => {
    if (hasPrev) {
      onPageChange(0);
    }
  };

  const handleLast = () => {
    if (totalCount !== undefined && hasNext) {
      const lastSkip = Math.max(0, (totalPages - 1) * limit);
      onPageChange(lastSkip);
    }
  };

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 mt-6 px-2">
      {/* Page size selector and item counts */}
      <div className="flex items-center gap-4 text-xs text-slate-400">
        <div className="flex items-center gap-2">
          <span>Rows per page:</span>
          <select
            value={limit}
            onChange={(e) => onLimitChange?.(Number(e.target.value))}
            className="bg-slate-900 border border-slate-800 text-slate-200 text-xs rounded-lg px-2.5 py-1.5 focus:outline-hidden focus:border-brand-500 cursor-pointer"
          >
            <option value={25}>25</option>
            <option value={50}>50</option>
            <option value={100}>100</option>
          </select>
        </div>

        <div>
          Showing{' '}
          <span className="font-semibold text-slate-200">
            {startItem.toLocaleString()} – {endItem.toLocaleString()}
          </span>{' '}
          of{' '}
          <span className="font-semibold text-slate-200">
            {(totalCount !== undefined ? totalCount : total).toLocaleString()}
          </span>{' '}
          leads
        </div>
      </div>

      {/* Page navigation controls */}
      <div className="flex items-center gap-1.5">
        <button
          onClick={handleFirst}
          disabled={!hasPrev}
          title="First page"
          className={`p-2 border rounded-xl text-xs font-medium transition-all ${
            !hasPrev
              ? 'border-slate-800 bg-slate-900/30 text-slate-600 cursor-not-allowed'
              : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 cursor-pointer'
          }`}
        >
          <ChevronsLeft className="w-4 h-4" />
        </button>

        <button
          onClick={handlePrev}
          disabled={!hasPrev}
          className={`flex items-center gap-1.5 px-3 py-2 border rounded-xl text-xs font-medium transition-all ${
            !hasPrev
              ? 'border-slate-800 bg-slate-900/30 text-slate-600 cursor-not-allowed'
              : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 cursor-pointer'
          }`}
        >
          <ChevronLeft className="w-4 h-4" />
          Previous
        </button>

        <div className="px-3 py-1.5 text-xs font-semibold text-slate-300 border border-slate-800 bg-slate-950/70 rounded-xl">
          Page {currentPage} of {totalPages}
        </div>

        <button
          onClick={handleNext}
          disabled={!hasNext}
          className={`flex items-center gap-1.5 px-3 py-2 border rounded-xl text-xs font-medium transition-all ${
            !hasNext
              ? 'border-slate-800 bg-slate-900/30 text-slate-600 cursor-not-allowed'
              : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 cursor-pointer'
          }`}
        >
          Next
          <ChevronRight className="w-4 h-4" />
        </button>

        {totalCount !== undefined && (
          <button
            onClick={handleLast}
            disabled={!hasNext}
            title="Last page"
            className={`p-2 border rounded-xl text-xs font-medium transition-all ${
              !hasNext
                ? 'border-slate-800 bg-slate-900/30 text-slate-600 cursor-not-allowed'
                : 'border-slate-800 bg-slate-900 text-slate-300 hover:border-slate-700 hover:bg-slate-900/80 cursor-pointer'
            }`}
          >
            <ChevronsRight className="w-4 h-4" />
          </button>
        )}
      </div>
    </div>
  );
};
